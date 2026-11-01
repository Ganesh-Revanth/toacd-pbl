#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <map>
#include <queue>
#include <mutex>
#include <sstream>
#include <chrono>
#include <iomanip>

struct ChatMessage {
    std::string sender;
    std::string targetChannel;
    std::string content;
    std::string timestamp;

    ChatMessage(std::string s, std::string ch, std::string txt, std::string ts)
        : sender(std::move(s)), targetChannel(std::move(ch)), content(std::move(txt)), timestamp(std::move(ts)) {}
};

class SimulatedSocketClient {
private:
    int clientId;
    std::string username;
    std::queue<ChatMessage> incomingQueue;
    std::mutex socketMutex;
    bool active;

public:
    SimulatedSocketClient(int id, std::string name)
        : clientId(id), username(std::move(name)), active(true) {}

    int getId() const { return clientId; }
    const std::string& getUsername() const { return username; }
    bool isActive() const { return active; }
    void disconnect() { active = false; }

    void deliverMessage(const ChatMessage& msg) {
        std::lock_guard<std::mutex> lock(socketMutex);
        incomingQueue.push(msg);
    }

    std::vector<ChatMessage> flushInbox() {
        std::lock_guard<std::mutex> lock(socketMutex);
        std::vector<ChatMessage> flushed;
        while (!incomingQueue.empty()) {
            flushed.push_back(incomingQueue.front());
            incomingQueue.pop();
        }
        return flushed;
    }
};

class ChatRoomChannel {
private:
    std::string channelName;
    std::string topic;
    std::map<int, std::shared_ptr<SimulatedSocketClient>> participants;
    std::vector<ChatMessage> history;
    std::mutex channelMutex;

public:
    ChatRoomChannel(std::string name, std::string top = "General")
        : channelName(std::move(name)), topic(std::move(top)) {}

    void join(const std::shared_ptr<SimulatedSocketClient>& client) {
        std::lock_guard<std::mutex> lock(channelMutex);
        participants[client->getId()] = client;
        broadcastSystemMessage(client->getUsername() + " joined #" + channelName);
    }

    void leave(int clientId) {
        std::lock_guard<std::mutex> lock(channelMutex);
        auto it = participants.find(clientId);
        if (it != participants.end()) {
            std::string user = it->second->getUsername();
            participants.erase(it);
            broadcastSystemMessage(user + " departed from #" + channelName);
        }
    }

    void postMessage(const std::string& sender, const std::string& text) {
        std::lock_guard<std::mutex> lock(channelMutex);
        ChatMessage msg(sender, channelName, text, "2026-11-01 14:00");
        history.push_back(msg);
        for (const auto& pair : participants) {
            pair.second->deliverMessage(msg);
        }
    }

    void broadcastSystemMessage(const std::string& announcement) {
        ChatMessage msg("SYSTEM", channelName, announcement, "2026-11-01 14:00");
        history.push_back(msg);
        for (const auto& pair : participants) {
            pair.second->deliverMessage(msg);
        }
    }

    size_t getParticipantCount() const { return participants.size(); }
    const std::string& getName() const { return channelName; }
};

class ChatServerEngine {
private:
    std::map<int, std::shared_ptr<SimulatedSocketClient>> activeClients;
    std::map<std::string, std::unique_ptr<ChatRoomChannel>> channels;
    int nextClientId;
    std::mutex serverMutex;

public:
    ChatServerEngine() : nextClientId(1) {
        createChannel("lobby", "Public open discussion");
        createChannel("dev", "Engineering and architecture");
    }

    bool createChannel(const std::string& name, const std::string& topic) {
        std::lock_guard<std::mutex> lock(serverMutex);
        if (channels.find(name) != channels.end()) return false;
        channels[name] = std::make_unique<ChatRoomChannel>(name, topic);
        return true;
    }

    std::shared_ptr<SimulatedSocketClient> connectClient(const std::string& username) {
        std::lock_guard<std::mutex> lock(serverMutex);
        int cid = nextClientId++;
        auto client = std::make_shared<SimulatedSocketClient>(cid, username);
        activeClients[cid] = client;
        if (channels.find("lobby") != channels.end()) {
            channels["lobby"]->join(client);
        }
        return client;
    }

    void routeCommand(const std::shared_ptr<SimulatedSocketClient>& client, const std::string& raw) {
        if (raw.empty() || !client) return;

        if (raw[0] == '/') {
            std::istringstream iss(raw);
            std::string cmd;
            iss >> cmd;
            if (cmd == "/join") {
                std::string target;
                if (iss >> target) {
                    std::lock_guard<std::mutex> lock(serverMutex);
                    auto it = channels.find(target);
                    if (it != channels.end()) it->second->join(client);
                }
            } else if (cmd == "/msg") {
                std::string target, rest;
                if (iss >> target && std::getline(iss, rest)) {
                    std::lock_guard<std::mutex> lock(serverMutex);
                    auto it = channels.find(target);
                    if (it != channels.end()) it->second->postMessage(client->getUsername(), rest);
                }
            }
        }
    }

    void dumpServerMetrics() const {
        std::cout << "\n================ CHAT SERVER METRICS ================\n";
        std::cout << "Connected Sockets: " << activeClients.size() << "\n";
        for (const auto& pair : channels) {
            std::cout << "  Channel #" << std::setw(10) << std::left << pair.first
                      << " | Users: " << pair.second->getParticipantCount() << "\n";
        }
        std::cout << "=====================================================\n";
    }
};

int main() {
    ChatServerEngine server;
    auto alice = server.connectClient("alice_kernel");
    auto bob = server.connectClient("bob_dev");
    auto charlie = server.connectClient("charlie_arch");

    server.routeCommand(alice, "/join dev");
    server.routeCommand(bob, "/join dev");
    server.routeCommand(alice, "/msg dev Hello team, ready for compiler design sprint.");
    server.routeCommand(bob, "/msg dev Acknowledged, running integration test suite.");

    for (const auto& c : {alice, bob, charlie}) {
        auto inbox = c->flushInbox();
        std::cout << "User " << c->getUsername() << " received " << inbox.size() << " packet(s):\n";
        for (const auto& m : inbox) {
            std::cout << "  [" << m.targetChannel << "] " << m.sender << ": " << m.content << "\n";
        }
    }

    server.dumpServerMetrics();
    return 0;
}
