#pragma once
#include <atomic>
#include <chrono>
#include "ApexTransportWake.h"
#include <cstdint>
#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace td1::ownerbridge {
inline constexpr std::size_t Capacity=48, Retained=128, MaxBytes=4*1024*1024, TotalBytes=64*1024*1024;
inline bool Identity(const std::string& value) {
    if(value.size()!=32)return false;
    for(const auto c:value)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
    return true;
}
struct Runtime {
    std::string nonce;std::uint64_t epoch=0;std::uint32_t pid=0,owner=0;
    bool operator==(const Runtime& other)const{return nonce==other.nonce&&epoch==other.epoch&&pid==other.pid&&owner==other.owner;}
    bool operator!=(const Runtime& other)const{return !(*this==other);}
};
enum class Admission { Unready, Accepted, Duplicate, Rejected };
enum class Phase { Queued, Claimed, Submitted, Running, Terminal, Uncertain };
struct Snapshot {
    Runtime runtime;std::string id;std::shared_ptr<const std::string> request,receipt;std::uint64_t ticket=0,selection=0,version=0,deadline=UINT64_MAX;
    Phase phase=Phase::Uncertain;bool observed=false;
};
struct OfferResult {Admission admission=Admission::Rejected;Snapshot record;std::string reason;};
struct Metrics {bool ready=false;std::uint64_t epoch=0,accepted=0,claimed=0,completed=0;std::size_t pending=0,unresolved=0,retained=0,bytes=0;};

// Owns copied UTF-8 packets only. No worker thread or game/Python/GFx object is
// created here. Source's canonical owner claims ingress; the existing F11
// transport worker waits for changed receipts. Accepted identities cannot be
// routed to a second transport by this state machine.
class Mailbox {
    mutable std::mutex mutex_;
    transport::WorkerWake changed_;
    std::map<std::uint64_t,Snapshot> records_;
    std::map<std::string,std::uint64_t> ids_;
    std::deque<std::uint64_t> ingress_;
    Runtime runtime_;std::uint64_t next_=0;std::size_t bytes_=0;
    std::uint64_t claimed_=0,completed_=0;
    std::atomic<bool> ready_{false},stopped_{false};
    std::atomic<std::size_t> pending_{0},unresolved_{0};
    bool Current(const Runtime& runtime,std::uint32_t caller)const {
        return ready_.load(std::memory_order_relaxed)&&!stopped_.load(std::memory_order_relaxed)&&
            runtime==runtime_&&caller==runtime_.owner;
    }
    void Prune(std::size_t reserve=0) {
        for(auto it=records_.begin();it!=records_.end() &&
                (records_.size()>=Retained || reserve>TotalBytes-bytes_);) {
            if(it->second.phase==Phase::Terminal&&it->second.observed) {
                bytes_-=it->second.request->size()+(it->second.receipt?it->second.receipt->size():0);ids_.erase(it->second.id);it=records_.erase(it);
            } else ++it;
        }
    }
public:
    bool Ready()const noexcept{return ready_.load(std::memory_order_acquire)&&!stopped_.load(std::memory_order_acquire);}
    bool Pending()const noexcept{return pending_.load(std::memory_order_acquire)!=0;}
    bool Unresolved()const noexcept{return unresolved_.load(std::memory_order_acquire)!=0;}
    Runtime Bind(const std::string& nonce,std::uint32_t pid,std::uint32_t caller) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(!Identity(nonce)||!pid||!caller||stopped_||!changed_.Available())return {};
        if(runtime_.owner && (runtime_.owner!=caller || runtime_.pid!=pid))return {};
        if(Ready())return runtime_.nonce==nonce?runtime_:Runtime{};
        if(runtime_.epoch==UINT64_MAX)return {};
        runtime_={nonce,runtime_.epoch+1,pid,caller};ready_.store(true,std::memory_order_release);return runtime_;
    }
    Runtime Context()const {std::lock_guard<std::mutex> lock(mutex_);return Ready()?runtime_:Runtime{};}
    Metrics Status()const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {Ready(),runtime_.epoch,next_,claimed_,completed_,ingress_.size(),unresolved_.load(),records_.size(),bytes_};
    }
    OfferResult Offer(const std::string& id,const std::string& request,std::uint64_t selection,std::uint64_t deadline=UINT64_MAX) {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto previous=ids_.find(id);
        if(previous!=ids_.end()) {
            const auto& row=records_.at(previous->second);
            if(*row.request!=request||row.selection!=selection)return {Admission::Rejected,row,"UUID already owns different bytes or selection"};
            return {Admission::Duplicate,row,{}};
        }
        if(!Ready())return {Admission::Unready,{},"Owner mailbox is not ready; no identity accepted"};
        if(!Identity(id)||request.empty()||request.size()>MaxBytes)return {Admission::Rejected,{},"Bounded immutable request required"};
        if(unresolved_.load()>=Capacity||next_==UINT64_MAX)return {Admission::Rejected,{},"Owner mailbox capacity exhausted; no identity accepted"};
        Prune(request.size());
        if(records_.size()>=Retained||request.size()>TotalBytes-bytes_)return {Admission::Rejected,{},"Receipt/byte retention is full; no identity accepted"};
        Snapshot row;row.runtime=runtime_;row.id=id;row.request=std::make_shared<const std::string>(request);row.selection=selection;row.deadline=deadline;row.ticket=next_+1;row.phase=Phase::Queued;row.version=1;
        records_.emplace(row.ticket,row);
        try {ids_.emplace(id,row.ticket);ingress_.push_back(row.ticket);}
        catch(...){ids_.erase(id);records_.erase(row.ticket);throw;}
        next_=row.ticket;bytes_+=request.size();
        pending_.store(ingress_.size(),std::memory_order_release);unresolved_.fetch_add(1,std::memory_order_release);
        changed_.Notify();return {Admission::Accepted,row,{}};
    }
    Snapshot Take(const Runtime& runtime,std::uint32_t caller) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(!Current(runtime,caller)||ingress_.empty())return {};
        const auto ticket=ingress_.front();ingress_.pop_front();pending_.store(ingress_.size(),std::memory_order_release);
        auto& row=records_.at(ticket);row.phase=Phase::Claimed;++row.version;++claimed_;changed_.Notify();return row;
    }
    bool Publish(const Runtime& runtime,std::uint32_t caller,std::uint64_t ticket,const std::string& id,
                 const std::string& receipt,Phase phase) {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto found=records_.find(ticket);
        if(!Current(runtime,caller)||found==records_.end()||found->second.runtime!=runtime||found->second.id!=id||
                receipt.empty()||receipt.size()>MaxBytes||
                (phase!=Phase::Submitted&&phase!=Phase::Running&&phase!=Phase::Terminal&&phase!=Phase::Uncertain))return false;
        auto& row=found->second;
        if(row.phase==Phase::Terminal)return phase==Phase::Terminal&&row.receipt&&receipt==*row.receipt;
        if(row.phase==Phase::Uncertain)return phase==Phase::Uncertain&&row.receipt&&receipt==*row.receipt;
        if(row.phase==Phase::Queued)return false;
        if(phase==Phase::Submitted && row.phase!=Phase::Claimed)return false;
        if(phase==Phase::Running && row.phase!=Phase::Submitted && row.phase!=Phase::Running)return false;
        const auto old=row.receipt?row.receipt->size():0;
        Prune(receipt.size()>old?receipt.size()-old:0);
        if(receipt.size()>TotalBytes-(bytes_-old))return false;
        auto immutable=std::make_shared<const std::string>(receipt);
        bytes_=bytes_-old+receipt.size();row.receipt=std::move(immutable);row.phase=phase;++row.version;
        if(phase==Phase::Terminal){unresolved_.fetch_sub(1,std::memory_order_release);++completed_;}
        changed_.Notify();return true;
    }
    bool Authorize(const Runtime& runtime,std::uint32_t caller,std::uint64_t ticket,const std::string& id,std::uint64_t currentSelection,std::uint64_t now=0)const {
        std::lock_guard<std::mutex> lock(mutex_);const auto found=records_.find(ticket);
        return Current(runtime,caller)&&found!=records_.end()&&found->second.runtime==runtime&&found->second.id==id&&
            found->second.phase==Phase::Submitted&&found->second.selection==currentSelection&&now<found->second.deadline;
    }
    Snapshot Read(std::uint64_t ticket,const std::string& id,bool observed=false) {
        std::lock_guard<std::mutex> lock(mutex_);const auto found=records_.find(ticket);
        if(found==records_.end()||found->second.id!=id)return {};
        if(observed&&found->second.phase==Phase::Terminal)found->second.observed=true;
        return found->second;
    }
    Snapshot ById(const std::string& id)const {
        std::lock_guard<std::mutex> lock(mutex_);const auto found=ids_.find(id);
        return found==ids_.end()?Snapshot{}:records_.at(found->second);
    }
    Snapshot Wait(std::uint64_t ticket,const std::string& id,std::uint64_t version,std::chrono::steady_clock::time_point deadline) {
        for(;;) {
            auto row=Read(ticket,id);
            if(!row.ticket||row.version!=version||stopped_)return row;
            const auto now=std::chrono::steady_clock::now();
            if(now>=deadline)return row;
            const auto remaining=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-now).count()+1;
            const auto bounded=remaining>=UINT32_MAX?UINT32_MAX-1:static_cast<std::uint32_t>(remaining);
            if(changed_.Wait(bounded)==transport::WakeResult::Unavailable)return row;
        }
    }
    bool Retire(const Runtime& runtime,std::uint32_t caller) {
        std::lock_guard<std::mutex> lock(mutex_);if(!Current(runtime,caller))return false;
        ready_.store(false,std::memory_order_release);ingress_.clear();pending_=0;
        for(auto& entry:records_)if(entry.second.runtime==runtime && entry.second.phase!=Phase::Terminal) {
            entry.second.phase=Phase::Uncertain;++entry.second.version;
        }
        // No unproved cancellation is inferred. Prior accepted UUIDs and their
        // last real receipts remain available; no new runtime may publish them.
        unresolved_=0;changed_.Notify();return true;
    }
    void Shutdown() {
        std::lock_guard<std::mutex> lock(mutex_);stopped_=true;ready_=false;ingress_.clear();pending_=0;
        for(auto& entry:records_)if(entry.second.phase!=Phase::Terminal){entry.second.phase=Phase::Uncertain;++entry.second.version;}
        unresolved_=0;changed_.Notify();
    }
    // Windows DllMain may signal the process-lifetime object without allocation,
    // C++ locking or closing a handle still used by the transport worker.
    void SignalShutdown()noexcept {stopped_=true;ready_=false;changed_.Notify();}
};
}
