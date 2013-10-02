#include "ClientInfo.h"

uint16_t ClientInfo::getId(void)
{
	return id;
}

void ClientInfo::reassignId(uint16_t newId)
{
	id = newId;
}

void ClientInfo::setTimeOfQuery(void)
{
    struct timeval tv;
    if(0 != (gettimeofday(&tv, NULL)))
    {
        cerr<<"gettimeofday failed"<<endl;
        exit(EXIT_FAILURE);
    }
    toq_us = 1000 * 1000 * tv.tv_sec + tv.tv_usec;
}

void ClientInfo::setTimeOfReply(void)
{
    struct timeval tv;
    if(0 != (gettimeofday(&tv, NULL)))
    {
        cerr<<"gettimeofday failed"<<endl;
        exit(EXIT_FAILURE);
    }
    tor_us = 1000 * 1000 * tv.tv_sec + tv.tv_usec;
}

uint64_t ClientInfo::getQueryDuration(void)
{
    assert(tor_us > toq_us);
    return tor_us - toq_us;
}
