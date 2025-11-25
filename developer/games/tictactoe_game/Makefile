# Makefile for Tic-Tac-Toe Online Game

CXX = g++
CXXFLAGS = -std=c++11 -pthread -Wall

all: lobby_server playerA playerB

lobby_server: lobby_server.cpp
	$(CXX) $(CXXFLAGS) -o lobby_server lobby_server.cpp

playerA: game_client.cpp
	$(CXX) $(CXXFLAGS) -o playerA game_client.cpp

playerB: playerB_client.cpp
	$(CXX) $(CXXFLAGS) -o playerB playerB_client.cpp

clean:
	rm -f lobby_server playerA playerB account.txt

.PHONY: all clean
