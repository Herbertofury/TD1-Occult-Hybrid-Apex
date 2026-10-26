#pragma once
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace td1::nativecas::gfxprofile {
enum class Boundary : std::uint32_t {Capture,SnapshotDestructor,PointerAllocate,PointerFree,MovieAdvance,Count};
inline constexpr std::size_t BoundaryCount=static_cast<std::size_t>(Boundary::Count);
struct TimingRow {std::uint64_t started{},returned{},unwound{},null_returns{},qualified{},ticks{},maximum_ticks{};};
struct TimingTicket {std::uint64_t generation{},started{};Boundary boundary{};bool active{},timed{};};
struct CaptureRecord {
    std::uint64_t generation{},serial{},context_fingerprint{},native_frame_id{},started_ticks{},elapsed_ticks{};
    std::uint64_t allocations{},allocation_nulls{},frees{},retired_frees{},merged_frees{},allocation_ticks{},free_ticks{};
    std::uint32_t thread{};
    bool heap_verified{},native_return{},unwound{};
};
struct TimingSnapshot {
    std::array<TimingRow,BoundaryCount> rows{};
    std::array<CaptureRecord,64> records{};
    std::uint64_t generation{},deadline{},inflight{},skipped{},dropped_records{},record_count{};
    bool enabled{},detail_timing{},records_contended{};
};

// Observation only. No native object/page access, allocation, native callback,
// mutex, spin-wait or retained game handle occurs in a measured boundary.
class SnapshotTiming final {
    static constexpr std::uint64_t Enabled=std::uint64_t{1}<<63;
    static constexpr std::uint64_t GenerationMask=0x7fffffff00000000ull;
    static constexpr std::uint64_t CountMask=0xffffffffull;
    struct AtomicRow {
        std::atomic<std::uint64_t> started{},returned{},unwound{},null_returns{},qualified{},ticks{},maximum_ticks{};
        void Reset() noexcept {started=0;returned=0;unwound=0;null_returns=0;qualified=0;ticks=0;maximum_ticks=0;}
        TimingRow Read() const noexcept {return {started.load(),returned.load(),unwound.load(),null_returns.load(),qualified.load(),ticks.load(),maximum_ticks.load()};}
    };
    std::atomic<std::uint64_t> gate_{},deadline_{},skipped_{},record_serial_{},dropped_records_{};
    std::atomic<bool> detail_{};
    std::array<AtomicRow,BoundaryCount> rows_{};
    mutable std::atomic_flag record_lock_=ATOMIC_FLAG_INIT;
    std::array<CaptureRecord,64> records_{};
    std::size_t record_count_{},record_cursor_{};
    static void Add(std::atomic<std::uint64_t>& target,std::uint64_t value=1) noexcept {
        auto old=target.load(std::memory_order_relaxed);
        while(!target.compare_exchange_weak(old,value>UINT64_MAX-old?UINT64_MAX:old+value,std::memory_order_relaxed)){}
    }
    static void Maximum(std::atomic<std::uint64_t>& target,std::uint64_t value) noexcept {
        auto old=target.load(std::memory_order_relaxed);
        while(old<value&&!target.compare_exchange_weak(old,value,std::memory_order_relaxed)){}
    }
    void ReleaseTicket() noexcept {gate_.fetch_sub(1,std::memory_order_release);}
public:
    bool Active() const noexcept {return (gate_.load(std::memory_order_acquire)&Enabled)!=0;}
    bool Detail() const noexcept {return detail_.load(std::memory_order_relaxed);}
    // Control operations are externally serialized. A combined gate makes the
    // generation transition atomic with respect to all entering native calls.
    bool Start(std::uint64_t now,std::uint64_t duration,bool detail) noexcept {
        auto expected=gate_.load(std::memory_order_acquire);
        if((expected&(Enabled|CountMask))||!duration||duration>UINT64_MAX-now||(expected&GenerationMask)==GenerationMask)return false;
        if(record_lock_.test_and_set(std::memory_order_acquire))return false;
        for(auto& row:rows_)row.Reset();records_={};record_count_=0;record_cursor_=0;
        skipped_=0;dropped_records_=0;record_serial_=0;detail_=detail;deadline_=now+duration;
        record_lock_.clear(std::memory_order_release);
        const auto next=((expected&GenerationMask)+(std::uint64_t{1}<<32))|Enabled;
        return gate_.compare_exchange_strong(expected,next,std::memory_order_release,std::memory_order_relaxed);
    }
    void Stop() noexcept {gate_.fetch_and(~Enabled,std::memory_order_release);}
    template<class Clock> TimingTicket Begin(Boundary boundary,bool timed,Clock&& clock) noexcept {
        const auto index=static_cast<std::size_t>(boundary);if(index>=BoundaryCount)return {};
        auto state=gate_.load(std::memory_order_acquire);
        for(;;) {
            if(!(state&Enabled))return {};
            if((state&CountMask)>=4096){Add(skipped_);return {};}
            if(gate_.compare_exchange_weak(state,state+1,std::memory_order_acq_rel,std::memory_order_acquire))break;
        }
        const auto now=timed?clock():0;
        if(timed&&now>=deadline_.load(std::memory_order_relaxed)){Stop();ReleaseTicket();return {};}
        Add(rows_[index].started);
        return {(state&GenerationMask)>>32,now,boundary,true,timed};
    }
    template<class Clock> void End(TimingTicket ticket,bool unwind,bool null_return,bool qualified,Clock&& clock) noexcept {
        if(!ticket.active)return;
        const auto now=ticket.timed?clock():0;
        auto& row=rows_[static_cast<std::size_t>(ticket.boundary)];
        Add(unwind?row.unwound:row.returned);if(null_return&&!unwind)Add(row.null_returns);if(qualified)Add(row.qualified);
        if(ticket.timed){const auto elapsed=now>=ticket.started?now-ticket.started:0;Add(row.ticks,elapsed);Maximum(row.maximum_ticks,elapsed);}
        ReleaseTicket();
    }
    std::uint64_t NextRecordSerial() noexcept {return record_serial_.fetch_add(1,std::memory_order_relaxed)+1;}
    void Record(const CaptureRecord& value) noexcept {
        if(value.generation!=((gate_.load(std::memory_order_acquire)&GenerationMask)>>32))return;
        if(record_lock_.test_and_set(std::memory_order_acquire)){Add(dropped_records_);return;}
        records_[record_cursor_]=value;record_cursor_=(record_cursor_+1)%records_.size();
        if(record_count_<records_.size())++record_count_;
        record_lock_.clear(std::memory_order_release);
    }
    TimingSnapshot Read() const noexcept {
        TimingSnapshot result;const auto gate=gate_.load(std::memory_order_acquire);
        result.enabled=(gate&Enabled)!=0;result.generation=(gate&GenerationMask)>>32;result.inflight=gate&CountMask;
        result.deadline=deadline_.load();result.detail_timing=detail_.load();result.skipped=skipped_.load();result.dropped_records=dropped_records_.load();
        for(std::size_t i=0;i<rows_.size();++i)result.rows[i]=rows_[i].Read();
        if(record_lock_.test_and_set(std::memory_order_acquire))result.records_contended=true;
        else {result.records=records_;result.record_count=record_count_;record_lock_.clear(std::memory_order_release);}
        return result;
    }
};
} // namespace td1::nativecas::gfxprofile
