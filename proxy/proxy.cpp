/**
 * Modified by Zitian Liu 
 * liu238@illinois.edu
 * Spring 2013
 */ 
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <assert.h>
#include <time.h>
#include <libgen.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <pthread.h>
#include <fstream>
#include <iostream>
#include <map>
#include <vector>

#include "ClientInfo.h"

#define MAX_HOSTNAME_LEN 150
#define BUF_SIZE         1024
#define PROXY_PORT       8962

#define LOCK_MUTEX(lock)    if(pthread_mutex_lock(lock)){exit(10);}
#define UNLOCK_MUTEX(lock)  if(pthread_mutex_unlock(lock)){exit(11);}

using namespace std;

/**********
 * NOTE:
 * Expected input file containing list of DNS servers
 * Each line in the file should contain only one an IP address
 * Lines starting with `#' are ignored (comments)
 **********/

//socket to liste to DNS servers for replies
static int socketToDNSServers;

//socket to listen from client
static int proxySocket;

static char *hostName = NULL;

//
// When the proxy is active, a lock file with this file name will be created;
// it contains server start time and level of replication (see details in main).
// This lock file will be created under the same directory of the proxy
// executable.
static char LOCK_FILE_NAME[] = "proxy_active";

/**
 * Prints out usage info
 */
void usage(char *execName){
    cerr<<"Usage:\n\t"<<execName<<" -f <DNS file>"<<endl;
}

/**
 * stores all given DNS servers
 * struct sockaddr_in    - the socket struct corresponding to that DNS server
 */
static vector<struct sockaddr_in> dnsServers;

/**
 * uint16_t    - all pending queries' transaction ID
 * ClientInfo    - the corresponding ClientInfo object pointer
 */
static map<uint16_t, ClientInfo*> pendingQueries;
static pthread_mutex_t mapLock;

/**
 * Ckecks if a given trsaction ID conflicts with any pending queries
 */
static inline bool conflictId(uint16_t id)
{
    bool rv = false;

    LOCK_MUTEX(&mapLock);
    map<uint16_t, ClientInfo*>::iterator i = pendingQueries.find(id);
    if(i != pendingQueries.end())
    {
        rv = true;
    }
    UNLOCK_MUTEX(&mapLock);

    return rv;
}

/**
 * If a trsaction ID conflicts, this function will return a new, non-conflicting one
 */
static uint16_t getNewId()
{
    LOCK_MUTEX(&mapLock);
    while(1)
    {
        uint16_t newId = rand() % (65535u);
        map<uint16_t, ClientInfo*>::iterator i = pendingQueries.find(newId);
        if(i == pendingQueries.end())
        {
            UNLOCK_MUTEX(&mapLock);
            return newId;
        }
    }
}

/**
 * Given a raw DNS query, return the domain name to be queried
 * Empty string is returned if any exception occurs
 */
static string rebuildQueryName(const char* q)
{
    const char *name = q + 12;
    char fieldLen = (char)*name;
    string ret;
    for(; fieldLen != 0; name+=fieldLen, fieldLen = (char)*name)
    {
        char tmp[fieldLen+1];
        memcpy(tmp, ++name, fieldLen);
        tmp[(uint8_t)fieldLen] = '\0';
        string currentField(tmp);
        ret += currentField;
        ret += '.';
    }

    try
    {
        ret.erase(ret.length()-1, 1);
    }
    catch(...)
    {
        cerr << "EXCEPTION CAUGHT!" << endl;
        return string("");
    }
    return ret;
}

/**
 * Client listener thread
 */
void *listenToClients(void *junk)
{
    //used to hold details of the other host
    char buf[BUF_SIZE];
    struct sockaddr_in otherHostAddr;
    socklen_t slen=sizeof(otherHostAddr);
    int i;
    int pktSize;

    //receive packets from the clients
    while(1)
    {
        memset((void *)&buf, 0x00, BUF_SIZE);
        bzero((char *) &otherHostAddr, sizeof(otherHostAddr)); 

        if(-1 == (pktSize = recvfrom(proxySocket,
                                     buf,
                                     BUF_SIZE,
                                     0,
                                     (struct sockaddr*)&otherHostAddr,
                                     &slen)))
        {
            perror("recvfrom");
            exit(EXIT_FAILURE);
        }
        if(0 == pktSize)
        {
            pthread_exit(NULL);
        }

        int clientPort = ntohs(otherHostAddr.sin_port);
        string clientIp(inet_ntoa(otherHostAddr.sin_addr));
        //cerr<<"Client's IP is "<<clientIp<<endl;
        string question = rebuildQueryName(buf);
        ClientInfo *newClient = new ClientInfo(clientIp,
                                               question,
                                               clientPort,
                                               *(uint16_t*)buf);
        if(conflictId(*(uint16_t*)buf))
        {
            cerr<<"Transaction ID conflict resolved"<<endl;
            *(uint16_t*)buf = getNewId();
            newClient->reassignId(*(uint16_t*)buf);
        }

        LOCK_MUTEX(&mapLock);
        pendingQueries[*(uint16_t*)buf] = newClient;
        UNLOCK_MUTEX(&mapLock);

        //relay query
        newClient->setTimeOfQuery();
        for(i=0; (unsigned)i<dnsServers.size(); i++)
        {
            int ret, bytesSent = 0;
            while(bytesSent < pktSize)
            {
                if((ret = sendto(socketToDNSServers,
                                 buf+(ptrdiff_t)bytesSent,
                                 pktSize-bytesSent,
                                 0,
                                 (struct sockaddr*)&(dnsServers[i]),
                                 slen)) == -1)
                {
                    perror("Error sendto() to DNS");
                    exit(EXIT_FAILURE);
                }
                bytesSent += ret;
            }
        }
    }
}

/**
 * Server listener thread
 */
void *listenToDnsServers(void *junk){
    int pktSize;

    //used to hold details of the other host
    struct sockaddr_in otherHostAddr;
    socklen_t slen=sizeof(otherHostAddr);

    //map from client ip to server ip
    //map<string, string> receivedResponse;

    while(1)
    {
        char responseBuf[BUF_SIZE];
        memset(responseBuf, 0x00, BUF_SIZE);
        if(-1 == (pktSize = recvfrom(socketToDNSServers,
                               responseBuf,
                               BUF_SIZE,
                               0,
                               (struct sockaddr*)&otherHostAddr,
                               &slen)))
        {
            perror("recvfrom");
            exit(EXIT_FAILURE);
        }
        if(0 == pktSize)
        {
            pthread_exit(NULL);
        }
        string serverIP(inet_ntoa(otherHostAddr.sin_addr));
        uint16_t responseTransacId = *(uint16_t*)responseBuf;
        //cerr<<"Got response from "<<serverIP<<"!"<<endl;

        LOCK_MUTEX(&mapLock);
        map<uint16_t, ClientInfo*>::iterator res =
            pendingQueries.find(responseTransacId);
        if(res == pendingQueries.end())
        {
            // if not found, this query must have benn answered already,
            // slinently continue.
            UNLOCK_MUTEX(&mapLock);
            continue;
        }
        ClientInfo *target = res->second;
        pendingQueries.erase(res);
        UNLOCK_MUTEX(&mapLock);
        target->setTimeOfReply();

        // restore the transaction ID
        *(uint16_t*)responseBuf = target->originalId;

        struct sockaddr_in client_addr;
        bzero(&client_addr, sizeof(client_addr));

        client_addr.sin_family = AF_INET;
        client_addr.sin_port = htons(target->port);

        socklen_t slen_t= sizeof(client_addr);
        //cout<<target->question<<"\t"<<serverIP;
        if (inet_aton((target->ip).c_str(), &client_addr.sin_addr)==0){
            perror("inet_aton");
            exit(EXIT_FAILURE);
        }
        //cout<<"Sending pkt to client "<<client_addr.sin_addr.s_addr<<" on port "<<client_addr.sin_port <<endl;
        int bytesSent = 0, ret;
        while(bytesSent < pktSize)
        {
            if((ret = sendto(proxySocket,
                             responseBuf+(ptrdiff_t)bytesSent,
                             pktSize-bytesSent,
                             0,
                             (struct sockaddr*)&client_addr,
                             slen_t)) == -1)
            {
                perror("Erro sendto() to client");
                exit(EXIT_FAILURE);
            }
            bytesSent += ret;
        }
        printf("%-30s%-20s%lu\n",
               target->question.c_str(),
               serverIP.c_str(),
               (unsigned long)target->getQueryDuration());
        delete target;
    }
}

/**
 * Sets up the 'inward' socket, ie the one interacts with clients
 */
static void setupClientListenerSocket(void)
{
    struct sockaddr_in proxyAddr;
    //set data to 0
    memset((void *)&proxyAddr, 0, sizeof(proxyAddr));
    bzero((char *) &proxyAddr, sizeof(proxyAddr)); 
    proxyAddr.sin_family = AF_INET;
    proxyAddr.sin_port = htons(DNS_PORT);
    proxyAddr.sin_addr.s_addr = htonl(INADDR_ANY);

    if( (proxySocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)) == -1){
        perror("socket");
        exit(EXIT_FAILURE);
    }
    //bind the socket to the port
    if( bind(proxySocket, (struct sockaddr* )&proxyAddr, sizeof(proxyAddr))  == -1){
        perror("proxyAddr bind");
        exit(EXIT_FAILURE);
    }
}

/**
 * Sets up the 'outward' socket, ie the one interacts with remote DNS servers
 */
static void setupDnsSenderSocket(void)
{
    struct sockaddr_in proxySenderAddr;
    bzero((char *) &proxySenderAddr, sizeof(proxySenderAddr));
    proxySenderAddr.sin_family = AF_INET;
    proxySenderAddr.sin_port = htons(PROXY_PORT);
    proxySenderAddr.sin_addr.s_addr = htonl(INADDR_ANY);

    if ((socketToDNSServers = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP))==-1){
        perror("socket");
        exit(EXIT_FAILURE);
    }

    //bind the socket to the port
    if( bind(socketToDNSServers,
             (struct sockaddr* )&proxySenderAddr,
             sizeof(proxySenderAddr)) == -1){
        perror("proxySender bind");
        exit(EXIT_FAILURE);
    }
}

/**
 * SIGQUIT signal handler
 */
static void sigq_handler(int sig)
{
    shutdown(socketToDNSServers, SHUT_RDWR);
    shutdown(proxySocket, SHUT_RDWR);
}

/**
 * Entry point
 */
int main(int argc, char **argv){
    char c;
    char *dnsFile = NULL;
    char *print_str = NULL;
    char *abs_lock_path = NULL;
    char *abs_lock_dir = NULL;
    char *temp;
    FILE *init_file_lock = NULL;
    struct timeval curr_time;
    long time_usec = -1;
    int rv;

    // parse input param
    while((c = getopt(argc, argv, "f:")) != -1)
    {
        switch(c)
        {
            case 'f':
                dnsFile = optarg;
                break;
            case '?':
            default:
                cerr<<"Unrecognized parameter"<<endl;
                usage(argv[0]);
                exit(EXIT_FAILURE);
        }
    }

    if(!dnsFile)
    {
        cerr<<"Missing DNS file"<<endl;
        usage(argv[0]);
        exit(EXIT_FAILURE);
    }

    if(optind < argc)
    {
        cerr<<"Too many argument(s)"<<endl;
        usage(argv[0]);
        exit(EXIT_FAILURE);
    }

    if(NULL == (abs_lock_path = (char*)malloc(256)))
    {
        perror("malloc");
        exit(EXIT_FAILURE);
    }

    // get the path to proxy executable
    if(-1 == (rv = readlink("/proc/self/exe",abs_lock_path,256)))
    {
        perror("readlink");
        exit(EXIT_FAILURE);
    }

    // null terminate the string
    abs_lock_path[rv] = '\0';

    // make a copy of the path for dirname()
    if(NULL == (temp = strdup(abs_lock_path)))
    {
        perror("strdup");
        exit(EXIT_FAILURE);
    }

    // get the directory path to the executable
    if(NULL == (abs_lock_dir = dirname(temp)))
    {
        perror("dirname");
        exit(EXIT_FAILURE);
    }

    //
    // construct the absolute path for lock file,
    // this guarantees the lock will always be under the same
    // directory as the proxy executable, regardless of the location
    // where the proxy is launched
    //
    if(0 > snprintf(abs_lock_path, 256, "%s/%s", abs_lock_dir, LOCK_FILE_NAME))
    {
        perror("snprintf");
        exit(EXIT_FAILURE);
    }

    // don't need this anymore
    free(temp);

    // open the dns file and read in each entry
    ifstream dnsServFile(dnsFile);
    if(!dnsServFile.is_open()){
        cout<<"Cannot open DNS Server file: "<<argv[1]<<endl;
        exit(EXIT_FAILURE);
    }

    //map from server ip address to the sock addr
    while(!dnsServFile.eof()){
        string ip;
        dnsServFile >> ip;
        if (ip.length() == 0) {
            continue;
        }

        struct sockaddr_in serv_addr;
        bzero(&serv_addr, sizeof(serv_addr));
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(DNS_PORT);
        if (inet_aton(ip.c_str(), &serv_addr.sin_addr)==0){
            fprintf(stderr, "inet_aton() failed errno is %d\n", errno);
            cout << ip << endl;
            exit(EXIT_FAILURE);
        }
        dnsServers.push_back(serv_addr);
    }

    if(!(hostName = (char*)malloc(sizeof(char) * MAX_HOSTNAME_LEN)))
    {
        cerr<<"Error mallocing memory for hostname"<<endl;
        exit(EXIT_FAILURE);
    }
    if(gethostname(hostName, MAX_HOSTNAME_LEN))
    {
        cerr<<"Error getting host name"<<endl;
        exit(EXIT_FAILURE);
    }

    setupClientListenerSocket();
    setupDnsSenderSocket();

    signal(SIGQUIT, sigq_handler);
    signal(SIGINT, SIG_IGN);

    pthread_t clientListenerThread;
    pthread_t dnsListenerThread;

    //print out formatting info
    printf("%-30s%-20s%s\n",
           "Query",
           "First Responder",
           "Time elapsed (micro seconds)");

    if(pthread_mutex_init(&mapLock, NULL))
    {
        perror("pthread_mutex_init");
        exit(EXIT_FAILURE);
    }
    if(pthread_create(&dnsListenerThread, NULL, listenToDnsServers, NULL))
    {
        perror("pthread_create");
        exit(EXIT_FAILURE);
    }
    if(pthread_create(&clientListenerThread, NULL, listenToClients, NULL))
    {
        perror("pthread_create");
        exit(EXIT_FAILURE);
    }

    //
    // Write the active lock file. File path is constructed above.
    // The lock contains one line:
    //          [start start time in us],[replication level]
    //
    if(NULL == (init_file_lock = fopen(abs_lock_path,"w")))
    {
        perror("fopen");
        exit(EXIT_FAILURE);
    }
    if(0 != gettimeofday(&curr_time,NULL))
    {
        perror("gettimeofday");
        exit(EXIT_FAILURE);
    }
    time_usec = curr_time.tv_sec * 1000 * 1000 + curr_time.tv_usec;
    if(-1 == (rv = asprintf(&print_str,
                            "%ld,%ld",
                            time_usec,
                            dnsServers.size())))
    {
        perror("asprintf");
        exit(EXIT_FAILURE);
    }

    if((unsigned)rv != fwrite(print_str, 1, rv, init_file_lock))
    {
        perror("fwrite");
        exit(EXIT_FAILURE);
    }

    if(0 != fclose(init_file_lock))
    {
        perror("fclose");
        exit(EXIT_FAILURE);
    }

    free(print_str);
    free(abs_lock_path);

    pthread_join(dnsListenerThread, NULL);
    pthread_join(clientListenerThread, NULL);
    pthread_mutex_destroy(&mapLock);

    free(hostName);

    // remove the server active file lock
    if(0 != unlink(LOCK_FILE_NAME))
    {
        perror("unlink");
        exit(EXIT_FAILURE);
    }

    cout<<"Proxy terminated"<<endl;
    return 0;
}
