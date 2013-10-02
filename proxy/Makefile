CC = g++
INC = -I.
FLAGS = -W -Wall -ggdb
LIBS = -lpthread
EXTRAS = -D VERBOSE
DNS_PORT = -D DNS_PORT=53

all: proxy

proxy: proxy.cpp ClientInfo.o
	$(CC) $(FLAGS) $(DNS_PORT) $(INC) $(EXTRAS) $^ -o $@ $(LIBS)

ClientInfo.o: ClientInfo.cpp ClientInfo.h
	$(CC) -c $(FLAGS) $(DNS_PORT) $(INC) $(EXTRAS) $< -o $@ $(LIBS)

clean:
	$(RM) *.o proxy
