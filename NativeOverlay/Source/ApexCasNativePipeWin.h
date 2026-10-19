// CAS UI transport. The network worker owns only CRT/Winsock memory; it never
// touches an EA object, GFx Value, movie heap, controller or ActionScript VM.
#pragma once
#include <winsock2.h>
#include <ws2tcpip.h>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <string>
#include <thread>
#include <stdexcept>
#include <cstdint>
#include <algorithm>

namespace td1::nativecas::pipe {
constexpr std::size_t Limit=131072;
inline bool Ascii(const std::string& value) {
    if(value.empty()||value.size()>Limit+8)return false;
    for(const auto c:value)if(static_cast<unsigned char>(c)>127||c==0)return false;
    return true;
}
inline std::size_t FrameSize(const std::string& header) {
    if(header.size()!=8)throw std::runtime_error("Native CAS frame header differs.");
    std::size_t size=0;
    for(const auto c:header){if(c<'0'||c>'9')throw std::runtime_error("Native CAS frame length is not decimal.");size=size*10+c-'0';}
    if(!size||size>Limit)throw std::runtime_error("Native CAS frame exceeds its bound.");
    return size;
}
inline void ValidateFrame(const std::string& frame) {
    if(!Ascii(frame)||frame.size()<9||FrameSize(frame.substr(0,8))!=frame.size()-8)
        throw std::runtime_error("Native CAS transport requires one complete ASCII frame.");
}
struct Mailbox {
    std::mutex mutex;std::condition_variable changed;
    std::uint64_t generation=0,queued=0,received=0,delivered=0;std::string scope,outgoing,incoming,error;
    bool stop=true,connected=false,announced=false,inFlight=false;
    std::atomic<bool> finished{true};std::thread worker;
    bool Matches(std::uint64_t expected,const std::string& currentScope) {
        std::lock_guard<std::mutex> lock(mutex);
        return expected==generation && currentScope==scope && !stop && connected;
    }
    std::string Poll(std::uint64_t expected,const std::string& currentScope) {
        std::lock_guard<std::mutex> lock(mutex);
        if(expected!=generation||currentScope!=scope)return "STALE";
        if(stop)return "CLOSED";
        if(!connected)return "WAIT";
        if(!announced){announced=true;return "CONNECTED";}
        if(incoming.empty())return "WAIT";
        auto frame=std::move(incoming);incoming.clear();inFlight=false;++delivered;
        return "DATA|"+frame;
    }
    std::string Send(std::uint64_t expected,const std::string& currentScope,std::string frame) {
        ValidateFrame(frame);std::lock_guard<std::mutex> lock(mutex);
        if(expected!=generation||currentScope!=scope)return "STALE";
        if(stop||!connected)return "CLOSED";
        if(inFlight||!outgoing.empty()||!incoming.empty())return "BUSY";
        outgoing=std::move(frame);inFlight=true;++queued;changed.notify_one();return "QUEUED";
    }
    std::string Close(std::uint64_t expected,const std::string& currentScope) {
        std::lock_guard<std::mutex> lock(mutex);
        if(expected!=generation||currentScope!=scope)return "STALE";
        stop=true;changed.notify_one();return "CLOSED";
    }
};
inline Mailbox& Channel(){static auto* channel=new Mailbox;return *channel;}
inline bool Stopping(Mailbox& box,std::uint64_t generation) {
    std::lock_guard<std::mutex> lock(box.mutex);return box.stop||box.generation!=generation;
}
inline void Transfer(SOCKET socket,Mailbox& box,std::uint64_t generation,char* bytes,std::size_t size,bool writing,
                     std::chrono::steady_clock::time_point until) {
    while(size) {
        if(Stopping(box,generation)||std::chrono::steady_clock::now()>=until)
            throw std::runtime_error("Native CAS transfer closed or expired.");
        fd_set read{},write{},errors{};FD_ZERO(&read);FD_ZERO(&write);FD_ZERO(&errors);
        FD_SET(socket,writing?&write:&read);FD_SET(socket,&errors);timeval wait{0,100000};
        const auto ready=select(0,&read,&write,&errors,&wait);
        if(ready==SOCKET_ERROR||FD_ISSET(socket,&errors))throw std::runtime_error("Native CAS socket failed.");
        if(!ready)continue;
        const int chunk=static_cast<int>((std::min)(size,std::size_t(16384)));
        const auto count=writing?send(socket,bytes,chunk,0):recv(socket,bytes,chunk,0);
        if(count==SOCKET_ERROR&&WSAGetLastError()==WSAEWOULDBLOCK)continue;
        if(count<=0)throw std::runtime_error("Native CAS peer closed before a complete frame.");
        bytes+=count;size-=static_cast<std::size_t>(count);
    }
}
inline void Worker(Mailbox& box,std::uint64_t generation) noexcept {
    SOCKET socket=INVALID_SOCKET;bool initialized=false;
    try {
        WSADATA data{};if(WSAStartup(MAKEWORD(2,2),&data))throw std::runtime_error("Winsock unavailable.");initialized=true;
        socket=::socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
        if(socket==INVALID_SOCKET)throw std::runtime_error("Native CAS connection unavailable.");
        u_long nonblocking=1;if(ioctlsocket(socket,FIONBIO,&nonblocking))throw std::runtime_error("Native CAS socket mode unavailable.");
        sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(8021);address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
        if(connect(socket,reinterpret_cast<const sockaddr*>(&address),sizeof(address))==SOCKET_ERROR) {
            if(WSAGetLastError()!=WSAEWOULDBLOCK)throw std::runtime_error("Native CAS listener refused connection.");
            const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(2);bool connected=false;
            while(!connected&&std::chrono::steady_clock::now()<until&&!Stopping(box,generation)) {
                fd_set write{},errors{};FD_ZERO(&write);FD_ZERO(&errors);FD_SET(socket,&write);FD_SET(socket,&errors);timeval wait{0,100000};
                const auto ready=select(0,nullptr,&write,&errors,&wait);
                if(ready==SOCKET_ERROR||FD_ISSET(socket,&errors))throw std::runtime_error("Native CAS connect failed.");
                if(ready&&FD_ISSET(socket,&write)) {
                    int error=0,length=sizeof(error);if(getsockopt(socket,SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&error),&length)||error)
                        throw std::runtime_error("Native CAS connection failed.");
                    connected=true;
                }
            }
            if(!connected)throw std::runtime_error("Native CAS connect expired.");
        }
        {std::lock_guard<std::mutex> lock(box.mutex);if(box.stop||box.generation!=generation)throw std::runtime_error("Native CAS opening was cancelled.");box.connected=true;}
        auto idleUntil=std::chrono::steady_clock::now()+std::chrono::seconds(30);
        while(!Stopping(box,generation)) {
            std::string frame;
            {std::unique_lock<std::mutex> lock(box.mutex);box.changed.wait_for(lock,std::chrono::milliseconds(100),[&]{return box.stop||!box.outgoing.empty();});
             if(box.stop)break;if(box.outgoing.empty()) {
                 if(std::chrono::steady_clock::now()>=idleUntil)throw std::runtime_error("Native CAS idle lease expired.");
                 continue;
             }
             frame=std::move(box.outgoing);box.outgoing.clear();}
            Transfer(socket,box,generation,frame.data(),frame.size(),true,std::chrono::steady_clock::now()+std::chrono::seconds(30));
            const auto replyUntil=std::chrono::steady_clock::now()+std::chrono::seconds(30);
            std::string header(8,'\0');Transfer(socket,box,generation,header.data(),header.size(),false,replyUntil);
            std::string reply(FrameSize(header),'\0');Transfer(socket,box,generation,reply.data(),reply.size(),false,replyUntil);
            frame=header+reply;ValidateFrame(frame);
            std::lock_guard<std::mutex> lock(box.mutex);
            if(box.stop||box.generation!=generation)break;
            if(!box.incoming.empty()||!box.inFlight)throw std::runtime_error("Native CAS response lost its one-frame owner.");
            box.incoming=std::move(frame);++box.received;idleUntil=std::chrono::steady_clock::now()+std::chrono::seconds(30);
        }
    } catch(const std::exception& error) {
        std::lock_guard<std::mutex> lock(box.mutex);if(box.generation==generation)box.error=error.what();
    }
    if(socket!=INVALID_SOCKET)closesocket(socket);if(initialized)WSACleanup();
    {std::lock_guard<std::mutex> lock(box.mutex);if(box.generation==generation){box.stop=true;box.connected=false;}}
    box.finished.store(true,std::memory_order_release);
}
inline std::string Open(const std::string& scope) {
    auto& box=Channel();
    if(!box.finished.load(std::memory_order_acquire)) {
        std::lock_guard<std::mutex> lock(box.mutex);
        if(box.scope!=scope){box.stop=true;box.changed.notify_one();}
        return "BUSY";
    }
    if(box.worker.joinable())box.worker.join();
    std::lock_guard<std::mutex> lock(box.mutex);
    if(box.generation==UINT64_MAX)return "EXHAUSTED";
    ++box.generation;box.scope=scope;box.outgoing.clear();box.incoming.clear();box.error.clear();
    box.stop=false;box.connected=false;box.announced=false;box.inFlight=false;box.queued=0;box.received=0;box.delivered=0;
    box.finished.store(false,std::memory_order_release);
    const auto generation=box.generation;
    try {box.worker=std::thread([&box,generation]{Worker(box,generation);});}
    catch(...){box.stop=true;box.finished.store(true,std::memory_order_release);throw;}
    return "OPEN|"+std::to_string(generation);
}
}
