// Read-only metadata work never runs on the CAS/game/render thread.
#pragma once
#include "ApexResourceImage.h"
#include "ApexLiveCatalog.h"
#include <condition_variable>
#include <atomic>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>

namespace td1::search {
using Json = ui::Json;
using Fetch = std::function<Json(const Json&)>;

class Worker {
    struct Job { std::uint64_t ticket=0; std::string context; Json query; };
    std::mutex mutex_;
    std::condition_variable changed_;
    Fetch fetch_;
    std::thread thread_;
    Job current_, pending_;
    std::shared_ptr<const Json> reply_;
    std::shared_ptr<const std::string> wire_;
    bool stopping_=false;
    std::atomic<bool> faulted_{false};
    std::uint64_t next_=0, completed_=0, superseded_=0;

    void Run() noexcept {
        try {
        for(;;) {
            Job job;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                changed_.wait(lock,[&]{return stopping_||pending_.ticket!=0;});
                if(stopping_)return;
                job=std::move(pending_);pending_={};
            }
            Json reply;
            try {
                reply=fetch_(job.query);
                if(!library::Page(reply,job.query)||reply.dump().size()>120*1024)
                    throw std::runtime_error("Metadata page does not match this query or exceeds its bound.");
            } catch(const std::exception& error) {
                reply={{"ok",false},{"message",error.what()},{"query",job.query}};
            } catch(...) {
                reply={{"ok",false},{"message","Metadata worker failed."},{"query",job.query}};
            }
            reply["ticket"]=job.ticket;reply["context"]=job.context;
            auto encoded=reply.dump(-1,' ',true);
            if(encoded.size()>126*1024) {
                reply={{"ok",false},{"message","Encoded metadata page exceeds its bound."},{"ticket",job.ticket}};
                encoded=reply.dump();
            }
            auto wire=std::make_shared<const std::string>(std::move(encoded));
            auto publication=std::make_shared<const Json>(std::move(reply));
            {
                std::lock_guard<std::mutex> lock(mutex_);
                if(stopping_)return;
                if(current_.ticket==job.ticket&&current_.context==job.context) {
                    reply_=std::move(publication);wire_=std::move(wire);++completed_;
                } else ++superseded_;
            }
        }
        } catch(...) {
            // An allocation/encoding failure outside the fetch must never
            // escape a background thread and terminate the game process.
            faulted_.store(true,std::memory_order_release);
        }
    }
public:
    explicit Worker(Fetch fetch):fetch_(std::move(fetch)) { thread_=std::thread([this]{Run();}); }
    Worker(const Worker&)=delete;
    Worker& operator=(const Worker&)=delete;
    ~Worker() { Stop(); }
    void Stop() {
        {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;pending_={};reply_.reset();wire_.reset();}
        changed_.notify_all();if(thread_.joinable())thread_.join();
    }
    std::uint64_t Submit(const std::string& context,const Json& query) {
        if(context.empty()||context.size()>512||!library::Query(query)||query.value("limit",0)>24||
           query.dump().size()>2048)throw std::runtime_error("Bounded native CAS metadata query required.");
        std::lock_guard<std::mutex> lock(mutex_);
        if(stopping_||faulted_.load(std::memory_order_acquire))throw std::runtime_error("Metadata worker is closed.");
        // No unbounded typing queue. An active HTTP read may finish, but only
        // the latest ticket can publish; at most one newer job is retained.
        current_={++next_,context,query};pending_=current_;reply_.reset();wire_.reset();
        changed_.notify_one();return next_;
    }
    std::shared_ptr<const Json> Poll(const std::string& context,std::uint64_t ticket) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(faulted_.load(std::memory_order_acquire))return std::make_shared<const Json>(Json{{"ok",false},{"state","failed"},{"ticket",ticket}});
        if(stopping_||context!=current_.context||ticket!=current_.ticket)
            return std::make_shared<const Json>(Json{{"ok",false},{"state","stale"},{"ticket",ticket}});
        if(reply_)return reply_;
        return std::make_shared<const Json>(Json{{"ok",true},{"state","pending"},{"ticket",ticket}});
    }
    std::shared_ptr<const std::string> PollWire(const std::string& context,std::uint64_t ticket) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(faulted_.load(std::memory_order_acquire))return std::make_shared<const std::string>("{\"ok\":false,\"state\":\"failed\"}");
        // Large JSON encoding belongs to Run(), not the native UI callback.
        if(!stopping_&&context==current_.context&&ticket==current_.ticket&&wire_)return wire_;
        const auto state=stopping_||context!=current_.context||ticket!=current_.ticket?"stale":"pending";
        return std::make_shared<const std::string>("{\"ok\":"+std::string(state==std::string("pending")?"true":"false")+",\"state\":\""+state+"\",\"ticket\":"+std::to_string(ticket)+"}");
    }
    Json Metrics() {
        std::lock_guard<std::mutex> lock(mutex_);
        return {{"submitted",next_},{"completed",completed_},{"superseded",superseded_},
                {"pending",pending_.ticket!=0},{"faulted",faulted_.load()},{"background_only",true}};
    }
};
}
