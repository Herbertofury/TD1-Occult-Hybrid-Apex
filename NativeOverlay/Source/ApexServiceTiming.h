#pragma once
#include <array>
#include <atomic>
#include <cstdint>
#include <limits>
#include <mutex>
#include <stdexcept>

namespace td1::performance {
// Explicit, bounded diagnostic window. Disabled dispatch does not read a clock,
// acquire this mutex, allocate, inspect arguments or touch engine objects.
template<std::size_t Count> class ServiceTiming {
public:
    struct Row {std::uint64_t calls=0,total=0,maximum=0;};
    struct Ticket {std::uint64_t generation=0,started=0;std::size_t slot=0;bool active=false;};
    struct Snapshot {std::array<Row,Count> rows{};std::uint64_t generation=0,started=0,deadline=0,skipped=0;unsigned inflight=0;bool enabled=false;};
private:
    mutable std::mutex mutex_;
    std::atomic<bool> enabled_{false};
    Snapshot data_;
    static std::uint64_t Add(std::uint64_t a,std::uint64_t b) noexcept {
        return b>std::numeric_limits<std::uint64_t>::max()-a?std::numeric_limits<std::uint64_t>::max():a+b;
    }
public:
    bool Start(std::uint64_t now,std::uint64_t duration) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(!duration || duration>std::numeric_limits<std::uint64_t>::max()-now || data_.inflight ||
           data_.generation==std::numeric_limits<std::uint64_t>::max())return false;
        enabled_.store(false,std::memory_order_release);
        auto generation=data_.generation+1;data_={};data_.generation=generation;
        data_.started=now;data_.deadline=now+duration;data_.enabled=true;
        enabled_.store(true,std::memory_order_release);return true;
    }
    void Stop() {
        enabled_.store(false,std::memory_order_release);
        std::lock_guard<std::mutex> lock(mutex_);data_.enabled=false;
    }
    template<class Clock> Ticket Begin(std::size_t slot,Clock&& clock) {
        if(slot>=Count || !enabled_.load(std::memory_order_acquire))return {};
        const auto now=clock();std::lock_guard<std::mutex> lock(mutex_);
        if(!enabled_.load(std::memory_order_acquire) || now<data_.started)return {};
        if(now>=data_.deadline) {data_.enabled=false;enabled_.store(false,std::memory_order_release);return {};}
        if(data_.inflight>=64) {data_.skipped=Add(data_.skipped,1);return {};}
        ++data_.inflight;return {data_.generation,now,slot,true};
    }
    template<class Clock> void End(Ticket ticket,Clock&& clock) noexcept {
        if(!ticket.active)return;
        const auto now=clock();std::lock_guard<std::mutex> lock(mutex_);
        if(ticket.generation!=data_.generation || !data_.inflight)return;
        --data_.inflight;auto& row=data_.rows[ticket.slot];const auto elapsed=now>=ticket.started?now-ticket.started:0;
        row.calls=Add(row.calls,1);row.total=Add(row.total,elapsed);if(elapsed>row.maximum)row.maximum=elapsed;
    }
    Snapshot Read() const {
        std::lock_guard<std::mutex> lock(mutex_);return data_;
    }
};
}
