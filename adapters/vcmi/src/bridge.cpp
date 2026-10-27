#include "h3/bridge.hpp"
#include <stdexcept>
#include <limits>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#endif

namespace h3
{
namespace
{
#ifdef _WIN32
using Socket = SOCKET;
constexpr Socket invalid_socket = INVALID_SOCKET;
struct Network
{
    Network() { WSADATA data{}; if(WSAStartup(MAKEWORD(2,2), &data)) throw std::runtime_error("WSAStartup failed"); }
    ~Network() { WSACleanup(); }
};
void close_socket(Socket s) { closesocket(s); }
#else
using Socket = int;
constexpr Socket invalid_socket = -1;
struct Network {};
void close_socket(Socket s) { close(s); }
#endif
struct Connection
{
    Socket value = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    ~Connection() { if(value != invalid_socket) close_socket(value); }
};
constexpr std::size_t max_frame = 4 * 1024 * 1024;
}

static nlohmann::json exchange(const nlohmann::json & observation, std::uint16_t port, int timeout_seconds, bool await_reply)
{
    if(timeout_seconds <= 0 || timeout_seconds > 3600) throw std::runtime_error("Invalid socket timeout");
    Network network;
    Connection connection;
    if(connection.value == invalid_socket) throw std::runtime_error("Cannot create adapter socket");
#ifdef _WIN32
    DWORD timeout = static_cast<DWORD>(timeout_seconds * 1000);
    if(setsockopt(connection.value, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char *>(&timeout), sizeof(timeout)) ||
       setsockopt(connection.value, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char *>(&timeout), sizeof(timeout)))
        throw std::runtime_error("Cannot set socket timeouts");
#else
    timeval timeout{timeout_seconds, 0};
    if(setsockopt(connection.value, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
       setsockopt(connection.value, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        throw std::runtime_error("Cannot set socket timeouts");
#ifdef SO_NOSIGPIPE
    int no_sigpipe = 1;
    setsockopt(connection.value, SOL_SOCKET, SO_NOSIGPIPE, &no_sigpipe, sizeof(no_sigpipe));
#endif
#endif
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if(connect(connection.value, reinterpret_cast<sockaddr *>(&address), sizeof(address)))
        throw std::runtime_error("Cannot connect to Python adapter service on loopback");
    std::string frame = observation.dump() + "\n";
    if(frame.size() > max_frame) throw std::runtime_error("Observation exceeds frame limit");
    for(std::size_t offset = 0; offset < frame.size();)
    {
        int flags = 0;
#ifdef MSG_NOSIGNAL
        flags = MSG_NOSIGNAL;
#endif
        const auto sent = send(connection.value, frame.data() + offset, static_cast<int>(frame.size() - offset), flags);
        if(sent <= 0) throw std::runtime_error("Adapter send failed or timed out");
        offset += sent;
    }
    if(!await_reply) return nullptr;
    std::string reply;
    while(reply.size() < max_frame)
    {
        char byte;
        const auto received = recv(connection.value, &byte, 1, 0);
        if(received <= 0) throw std::runtime_error("Adapter reply missing or timed out");
        if(byte == '\n')
        {
            auto action = nlohmann::json::parse(reply);
            for(const auto * key : {"schema_version", "battle_id", "revision", "decision_id"})
                if(action.at(key) != observation.at(key)) throw std::runtime_error("Stale or incompatible action reply");
            if(action.at("type") != "action") throw std::runtime_error("Expected action reply");
            const auto & id = action.at("action_id");
            for(const auto & offered : observation.at("legal_actions"))
                if(offered.at("id") == id) return offered;
            throw std::runtime_error("Action was not offered for this decision");
        }
        reply += byte;
    }
    throw std::runtime_error("Action reply exceeds frame limit");
}
nlohmann::json request_action(const nlohmann::json & observation, std::uint16_t port, int timeout_seconds)
{
    return exchange(observation, port, timeout_seconds, true);
}

void send_observation(const nlohmann::json & observation, std::uint16_t port, int timeout_seconds)
{
    exchange(observation, port, timeout_seconds, false);
}

}
