#pragma once

// EXPERIMENT ONLY. This owns no game hooks and never dereferences a game object.
// The future adapter must supply all observations from sealed native call sites.
#include <array>
#include <cstddef>
#include <cstdint>
#include <condition_variable>
#include <limits>
#include <mutex>

namespace apex::gfx_snapshot_experiment {

inline constexpr std::size_t PointerPageBytes = 0x268;
inline constexpr std::size_t PointerPageAlignment = 16;
inline thread_local unsigned NativeFreeCallbackDepth{};

struct ContextKey {
    std::uintptr_t context{};
    std::uintptr_t heap{};
    std::uint64_t nonce{};
    explicit operator bool() const noexcept { return nonce != 0; }
};
struct CaptureKey {
    ContextKey owner{};
    std::uint64_t serial{};
    std::uint32_t thread{};
    explicit operator bool() const noexcept { return serial != 0 && bool(owner); }
};
struct AllocationObservation {
    std::uintptr_t context{};
    std::uintptr_t heap{};
    std::uint32_t thread{};
    std::size_t bytes{};
    std::size_t alignment{};
    const void* allocation_info{};
    bool authenticated_capture_allocation_site{};
    bool native_heap_has_no_release_on_free_marker{};
};
struct ReleaseObservation {
    std::uintptr_t context{};
    std::uintptr_t heap{};
    std::uint32_t thread{};
    void* page{};
    bool authenticated_pointer_page_free_site{};
    bool native_finalization_complete{};
    bool native_neighbor_unlink_complete{};
    bool native_heap_has_no_release_on_free_marker{};
};
struct NativeFree {
    void* user{};
    void (*invoke)(void*, std::uintptr_t, void*) noexcept{};
    explicit operator bool() const noexcept { return invoke != nullptr; }
};
struct PoolStats {
    std::size_t retained_pages{};
    // Requested pointer-page bytes only. The real native heap still accounts
    // for these allocations plus its rounding/metadata/segment footprint.
    std::size_t retained_bytes{};
    std::size_t high_water_pages{};
    std::uint64_t takes{};
    std::uint64_t retains{};
    std::uint64_t forwards{};
    std::uint64_t drains{};
    std::uint64_t duplicate_releases{};
};

// Fixed metadata only: no operator new, native allocation, VirtualAlloc, worker,
// appearance data, async callback, or cached game-object dereference. Deliberately
// returns nullptr/false when the original allocation/free must run unchanged.
template<std::size_t MaxContexts = 8, std::size_t MaxPagesPerContext = 256>
class SnapshotPointerPagePool final {
    static_assert(MaxContexts > 0 && MaxPagesPerContext > 0, "nonempty bounds");
    static_assert(MaxContexts <= 64 && MaxPagesPerContext <= 4096, "bounded experiment metadata");
public:
    struct Limits {
        std::size_t pages_per_context{64};
        std::size_t total_pages{256};
    };

    explicit SnapshotPointerPagePool(Limits limits = {}) noexcept : limits_(limits) {
        if(limits_.pages_per_context > MaxPagesPerContext) limits_.pages_per_context = MaxPagesPerContext;
        if(limits_.total_pages > MaxContexts * MaxPagesPerContext) limits_.total_pages = MaxContexts * MaxPagesPerContext;
    }
    SnapshotPointerPagePool(const SnapshotPointerPagePool&) = delete;
    SnapshotPointerPagePool& operator=(const SnapshotPointerPagePool&) = delete;

    // No automatic destructor drain: the adapter must drain while the native
    // heap is alive, before its own teardown/leak check. A C++ destructor cannot
    // safely guess whether an external game's allocator has already gone away.
    bool enable_after_native_authentication() noexcept {
        if(in_native_callback()) return false;
        std::lock_guard<std::mutex> guard(mutex_);
        if(global_shutdown_) return false;
        enabled_ = true;
        return true;
    }

    ContextKey register_context(std::uintptr_t context, std::uintptr_t heap,
                                std::uint32_t advance_thread) noexcept {
        if(in_native_callback() || !context || !heap || !advance_thread) return {};
        std::lock_guard<std::mutex> guard(mutex_);
        if(!enabled_ || global_shutdown_) return {};
        for(const auto& slot : slots_) if(slot.key.context == context && slot.key) return {};
        for(auto& slot : slots_) if(!slot.key) {
            if(nonce_ == std::numeric_limits<std::uint64_t>::max()) return {};
            slot = Slot{};
            slot.key = {context, heap, ++nonce_};
            slot.thread = advance_thread;
            return slot.key;
        }
        return {};
    }

    CaptureKey begin_capture(ContextKey key, std::uint32_t thread,
                             bool authenticated_native_capture_site) noexcept {
        if(in_native_callback() || !authenticated_native_capture_site) return {};
        std::lock_guard<std::mutex> guard(mutex_);
        Slot* slot = find(key);
        if(!enabled_ || global_shutdown_ || !slot || slot->closing || slot->suspended ||
           !thread || thread != slot->thread || scope_serial_ == std::numeric_limits<std::uint64_t>::max()) return {};
        // Native callbacks may recursively enter Capture. Reentrant captures on
        // this thread receive no pooling scope, including a different Context.
        for(const auto& other : slots_) if(other.active_serial && other.thread == thread) return {};
        slot->active_serial = ++scope_serial_;
        return {key, slot->active_serial, thread};
    }

    void end_capture(CaptureKey capture) noexcept {
        std::lock_guard<std::mutex> guard(mutex_);
        Slot* slot = find(capture.owner);
        if(slot && capture.serial && slot->active_serial == capture.serial && slot->thread == capture.thread)
            slot->active_serial = 0;
    }

    void* try_take(CaptureKey capture, const AllocationObservation& observed) noexcept {
        if(in_native_callback()) return nullptr;
        std::lock_guard<std::mutex> guard(mutex_);
        Slot* slot = eligible(capture, observed.context, observed.heap, observed.thread);
        if(!slot || !observed.authenticated_capture_allocation_site ||
           !observed.native_heap_has_no_release_on_free_marker || observed.bytes != PointerPageBytes ||
           observed.alignment != PointerPageAlignment || observed.allocation_info != nullptr || !slot->count) {
            increment(stats_.forwards); return nullptr;
        }
        void* page = slot->pages[--slot->count];
        slot->pages[slot->count] = nullptr;
        --stats_.retained_pages;
        stats_.retained_bytes -= PointerPageBytes;
        increment(stats_.takes);
        return page;
    }

    bool try_retain(CaptureKey capture, const ReleaseObservation& observed) noexcept {
        if(in_native_callback()) return false;
        std::lock_guard<std::mutex> guard(mutex_);
        // A duplicate/foreign release must never leave a freed block retained in
        // our metadata. Relinquish its sole cached claim, suspend that Context,
        // and let this actual call run the original native Free exactly once.
        // This is a fail-closed corruption route, not a normal reuse operation.
        if(observed.page && relinquish_duplicate(observed.page)) {
            increment(stats_.duplicate_releases); increment(stats_.forwards); return false;
        }
        Slot* slot = eligible(capture, observed.context, observed.heap, observed.thread);
        if(!slot || !observed.page || reinterpret_cast<std::uintptr_t>(observed.page) % PointerPageAlignment ||
           !observed.authenticated_pointer_page_free_site || !observed.native_finalization_complete ||
           !observed.native_neighbor_unlink_complete || !observed.native_heap_has_no_release_on_free_marker ||
           slot->count >= limits_.pages_per_context || stats_.retained_pages >= limits_.total_pages) {
            increment(stats_.forwards); return false;
        }
        slot->pages[slot->count++] = observed.page;
        ++stats_.retained_pages;
        stats_.retained_bytes += PointerPageBytes;
        if(stats_.retained_pages > stats_.high_water_pages) stats_.high_water_pages = stats_.retained_pages;
        increment(stats_.retains);
        return true;
    }

    // Called BEFORE the real Context destructor. Keep a closing tombstone until
    // finish_close AFTER the original destructor, preventing address reuse or a
    // callback from registering a new lifetime during the old destructor.
    bool begin_close(ContextKey key, NativeFree native_free) noexcept {
        if(in_native_callback() || !native_free) return false;
        DrainBatch batch;
        {
            std::lock_guard<std::mutex> guard(mutex_);
            Slot* slot = find(key);
            if(!slot || slot->closing) return false;
            slot->closing = true;
            slot->active_serial = 0;
            extract(*slot, batch);
        }
        drain(batch, native_free);
        std::unique_lock<std::mutex> guard(mutex_);
        drained_.wait(guard, [&] { const Slot* slot = find(key); return !slot || slot->pending_drains == 0; });
        return true;
    }
    bool finish_close(ContextKey key) noexcept {
        if(in_native_callback()) return false;
        std::lock_guard<std::mutex> guard(mutex_);
        Slot* slot = find(key);
        if(!slot || !slot->closing || slot->count || slot->pending_drains) return false;
        *slot = Slot{};
        return true;
    }

    // Called BEFORE the native global-heap teardown's leak check and release.
    // It is terminal. Disable, extract and unlock before original Free callbacks.
    bool disable_and_drain_before_heap_shutdown(NativeFree native_free) noexcept {
        if(in_native_callback() || !native_free) return false;
        DrainBatch batch;
        {
            std::lock_guard<std::mutex> guard(mutex_);
            enabled_ = false;
            global_shutdown_ = true;
            for(auto& slot : slots_) {
                slot.suspended = true;
                slot.active_serial = 0;
                extract(slot, batch);
            }
        }
        drain(batch, native_free);
        std::unique_lock<std::mutex> guard(mutex_);
        drained_.wait(guard, [&] { return pending_drains_ == 0; });
        return true;
    }

    PoolStats stats() const noexcept {
        std::lock_guard<std::mutex> guard(mutex_);
        return stats_;
    }
    static bool in_native_callback() noexcept { return NativeFreeCallbackDepth != 0; }

private:
    struct Slot {
        ContextKey key{};
        std::uint32_t thread{};
        std::uint64_t active_serial{};
        bool closing{};
        bool suspended{};
        std::size_t count{};
        std::size_t pending_drains{};
        std::array<void*, MaxPagesPerContext> pages{};
    };
    struct DrainedPage { ContextKey owner{}; void* page{}; };
    struct DrainBatch {
        std::size_t count{};
        std::array<DrainedPage, MaxContexts * MaxPagesPerContext> pages{};
    };
    static bool same(ContextKey a, ContextKey b) noexcept {
        return a.nonce && a.context == b.context && a.heap == b.heap && a.nonce == b.nonce;
    }
    static void increment(std::uint64_t& counter) noexcept {
        if(counter != std::numeric_limits<std::uint64_t>::max()) ++counter;
    }
    Slot* find(ContextKey key) noexcept {
        for(auto& slot : slots_) if(same(slot.key, key)) return &slot;
        return nullptr;
    }
    Slot* eligible(CaptureKey capture, std::uintptr_t context, std::uintptr_t heap,
                   std::uint32_t thread) noexcept {
        Slot* slot = find(capture.owner);
        if(!enabled_ || global_shutdown_ || !slot || slot->closing || slot->suspended || !capture.serial ||
           slot->active_serial != capture.serial || !thread || thread != slot->thread || thread != capture.thread ||
           context != slot->key.context || heap != slot->key.heap) return nullptr;
        return slot;
    }
    bool relinquish_duplicate(void* page) noexcept {
        for(auto& slot : slots_) for(std::size_t i = 0; i < slot.count; ++i) if(slot.pages[i] == page) {
            slot.pages[i] = slot.pages[--slot.count];
            slot.pages[slot.count] = nullptr;
            slot.suspended = true;
            --stats_.retained_pages;
            stats_.retained_bytes -= PointerPageBytes;
            return true;
        }
        return false;
    }
    void extract(Slot& slot, DrainBatch& batch) noexcept {
        for(std::size_t i = 0; i < slot.count; ++i) batch.pages[batch.count++] = {slot.key, slot.pages[i]};
        slot.pending_drains += slot.count;
        pending_drains_ += slot.count;
        stats_.retained_pages -= slot.count;
        stats_.retained_bytes -= slot.count * PointerPageBytes;
        slot.count = 0;
        slot.pages.fill(nullptr);
    }
    void drain(const DrainBatch& batch, NativeFree native_free) noexcept {
        struct CallbackScope {
            CallbackScope() noexcept { ++NativeFreeCallbackDepth; }
            ~CallbackScope() { --NativeFreeCallbackDepth; }
        } scope;
        for(std::size_t i = 0; i < batch.count; ++i)
            native_free.invoke(native_free.user, batch.pages[i].owner.heap, batch.pages[i].page);
        std::lock_guard<std::mutex> guard(mutex_);
        for(std::size_t i = 0; i < batch.count; ++i) {
            Slot* slot = find(batch.pages[i].owner);
            if(slot && slot->pending_drains) --slot->pending_drains;
            --pending_drains_;
            increment(stats_.drains);
        }
        drained_.notify_all();
    }
    Limits limits_;
    mutable std::mutex mutex_;
    std::condition_variable drained_;
    std::array<Slot, MaxContexts> slots_{};
    std::uint64_t nonce_{};
    std::uint64_t scope_serial_{};
    std::size_t pending_drains_{};
    PoolStats stats_{};
    bool enabled_{};
    bool global_shutdown_{};
};

} // namespace apex::gfx_snapshot_experiment
