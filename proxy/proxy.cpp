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
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>
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

/**
 * Prints out usage info
 */
void usage(char *execName){
	cerr<<"Usage:\n\t"<<execName<<" -f <DNS file>"<<endl;
}

/**
 * stores all given DNS servers
 * struct sockaddr_in	- the socket struct corresponding to that DNS server
 */
static vector<struct sockaddr_in> dnsServers;

/**
 * uint16_t	- all pending queries' transaction ID
 * ClientInfo	- the corresponding ClientInfo object pointer
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

	//receive packets from the clients
	while(1){
		memset((void *)&buf, 0x00, BUF_SIZE);
		bzero((char *) &otherHostAddr, sizeof(otherHostAddr)); 

		int pktSize = recvfrom(proxySocket, buf, BUF_SIZE, 0, (struct sockaddr* )&otherHostAddr, &slen);
		if(pktSize == -1){
			perror("recvfrom");
			exit(-1);
		}
		if(0 == pktSize)
			pthread_exit(NULL);

		int clientPort = ntohs(otherHostAddr.sin_port);
		string clientIp(inet_ntoa(otherHostAddr.sin_addr));
		//cerr<<"Client's IP is "<<clientIp<<endl;
		string question = rebuildQueryName(buf);
		ClientInfo *newClient = new ClientInfo(clientIp, question, clientPort, *(uint16_t*)buf);
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
					exit(-1);
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

	while(1){
		char responseBuf[BUF_SIZE];
		memset(responseBuf, 0x00, BUF_SIZE);
		if((pktSize = recvfrom(socketToDNSServers, responseBuf, BUF_SIZE, 0, (struct sockaddr* )&otherHostAddr, &slen)) == -1)
		{
			perror("recvfrom");
			exit(-1);
		}
		if(0 == pktSize)
			pthread_exit(NULL);
		string serverIP(inet_ntoa(otherHostAddr.sin_addr));
		uint16_t responseTransacId = *(uint16_t*)responseBuf;
		//cerr<<"Got response from "<<serverIP<<"!"<<endl;

        LOCK_MUTEX(&mapLock);
		map<uint16_t, ClientInfo*>::iterator res = pendingQueries.find(responseTransacId);
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

		*(uint16_t*)responseBuf = target->originalId; // restore the transaction ID

		struct sockaddr_in client_addr;
		bzero(&client_addr, sizeof(client_addr));

		client_addr.sin_family = AF_INET;
		client_addr.sin_port = htons(target->port);
		
		socklen_t slen_t= sizeof(client_addr);
		//cout<<target->question<<"\t"<<serverIP;
		if (inet_aton((target->ip).c_str(), &client_addr.sin_addr)==0){
			perror("inet_aton");
			exit(1);
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
				exit(1);
			}
			bytesSent += ret;
		}
        printf("%-30s%-20s%lu\n",target->question.c_str(),serverIP.c_str(),(unsigned long)target->getQueryDuration());
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
		exit(-1);
	}
	//bind the socket to the port
	if( bind(proxySocket, (struct sockaddr* )&proxyAddr, sizeof(proxyAddr))  == -1){
		perror("proxyAddr bind");
		exit(-1);
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
		exit(-1);
	}

	//bind the socket to the port
	if( bind(socketToDNSServers, (struct sockaddr* )&proxySenderAddr, sizeof(proxySenderAddr)) == -1){
		perror("proxySender bind");
		exit(-1);
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
	char c, *dnsFile = NULL;
	
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
				exit(1);
		}
	}

	if(!dnsFile)
	{
		cerr<<"Missing DNS file"<<endl;
		usage(argv[0]);
		exit(1);
	}
	
	if(optind < argc)
	{
		cerr<<"Too many argument(s)"<<endl;
		usage(argv[0]);
		exit(1);
	}

	/*
	 * start to read from file
	 */
	ifstream dnsServFile(dnsFile);
	if(!dnsServFile.is_open()){
		cout<<"Cannot open DNS Server file: "<<argv[1]<<endl;
		exit(-1);
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
			exit(1);  
		}
		dnsServers.push_back(serv_addr);
	}

	if(!(hostName = (char*)malloc(sizeof(char) * MAX_HOSTNAME_LEN)))
	{
		cerr<<"Error mallocing memory for hostname"<<endl;
		exit(1);
	}
	if(gethostname(hostName, MAX_HOSTNAME_LEN))
	{
		cerr<<"Error getting host name"<<endl;
		exit(1);
	}

	setupClientListenerSocket();
	setupDnsSenderSocket();

	signal(SIGQUIT, sigq_handler);
	signal(SIGINT, SIG_IGN);

	pthread_t clientListenerThread;
	pthread_t dnsListenerThread;

	//print out formatting info
    printf("%-30s%-20s%s\n","Query","First Responder","Time elapsed (micro seconds)");

    if(pthread_mutex_init(&mapLock, NULL))
    {
        perror("pthread_mutex_init");
        exit(-1);
    }
	if(pthread_create(&dnsListenerThread, NULL, listenToDnsServers, NULL))
	{
		perror("pthread_create");
		exit(-1);
	}
	if(pthread_create(&clientListenerThread, NULL, listenToClients, NULL))
	{
		perror("pthread_create");
		exit(-1);
	}

	pthread_join(dnsListenerThread, NULL);
	pthread_join(clientListenerThread, NULL);
    pthread_mutex_destroy(&mapLock);

	free(hostName);
	
	cout<<"Proxy terminated normally"<<endl;

	return 0;
}
