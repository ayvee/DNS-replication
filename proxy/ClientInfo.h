#ifndef __CLIENTINFO_H__
#define __CLIENTINFO_H__

#include <stdlib.h>
#include <netinet/in.h>
#include <sys/time.h>
#include <stdint.h>
#include <iostream>
#include <vector>
#include <map>
#include <assert.h>

using namespace std;

class ClientInfo{
	public:
		ClientInfo(string clientIp, string q, unsigned clientPort, uint16_t transactionId) : ip(clientIp),
            question(q),
            port(clientPort),
            originalId(transactionId),
            id(transactionId) {;};
		const string ip;
		const string question;
		const unsigned int port;
		const uint16_t originalId;

		uint16_t getId(void);
		void reassignId(uint16_t newId);
        void setTimeOfQuery(void);
        void setTimeOfReply(void);
        uint64_t getQueryDuration(void);

	private:
		uint16_t id;
        uint64_t toq_us;
        uint64_t tor_us;
};

#endif
