#include "SnapshotPointerPagePool.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <future>
#include <functional>
#include <iostream>
#include <memory>
#include <new>
#include <stdexcept>
#include <thread>
#include <unordered_map>
#include <vector>

using namespace apex::gfx_snapshot_experiment;
#define CHECK(x) do { if(!(x)) throw std::runtime_error(#x); } while(false)
using Pool = SnapshotPointerPagePool<4, 8>;

struct NativeHeapFixture {
    struct Allocation { std::uintptr_t heap{}; };
    std::mutex mutex;
    std::unordered_map<void*, Allocation> live;
    std::size_t allocations{}, frees{};
    bool invalid_free{};
    std::function<void()> during_free;

    void* allocate(std::uintptr_t heap) {
        void* result = ::operator new(PointerPageBytes, std::align_val_t(PointerPageAlignment));
        std::memset(result, 0xcd, PointerPageBytes);
        std::lock_guard<std::mutex> guard(mutex);
        live.emplace(result, Allocation{heap}); ++allocations;
        return result;
    }
    static void free_callback(void* user, std::uintptr_t heap, void* page) noexcept {
        auto& self = *static_cast<NativeHeapFixture*>(user);
        if(self.during_free) self.during_free();
        bool found = false;
        {
            std::lock_guard<std::mutex> guard(self.mutex);
            auto it = self.live.find(page);
            if(it == self.live.end() || it->second.heap != heap) self.invalid_free = true;
            else { self.live.erase(it); ++self.frees; found = true; }
        }
        if(found) ::operator delete(page, std::align_val_t(PointerPageAlignment));
    }
    NativeFree callback() noexcept { return {this, free_callback}; }
    std::size_t outstanding() { std::lock_guard<std::mutex> guard(mutex); return live.size(); }
    ~NativeHeapFixture() { for(const auto& item : live) ::operator delete(item.first, std::align_val_t(PointerPageAlignment)); }
};

AllocationObservation allocation(ContextKey key, std::uint32_t thread) {
    return {key.context, key.heap, thread, PointerPageBytes, PointerPageAlignment, nullptr, true, true};
}
ReleaseObservation release(ContextKey key, std::uint32_t thread, void* page) {
    return {key.context, key.heap, thread, page, true, true, true, true};
}
void original_free(NativeHeapFixture& heap, std::uintptr_t owner, void* page) {
    heap.callback().invoke(&heap, owner, page);
}
void finish(Pool& pool, ContextKey key, NativeHeapFixture& heap) {
    CHECK(pool.begin_close(key, heap.callback()));
    // The actual adapter calls the original Context destructor HERE.
    CHECK(pool.finish_close(key));
}

void native_accounting_and_payload() {
    Pool pool; NativeHeapFixture heap;
    CHECK(!pool.register_context(1, 2, 7));
    CHECK(pool.enable_after_native_authentication());
    auto key = pool.register_context(0x1000, 0x2000, 7); CHECK(key);
    auto capture = pool.begin_capture(key, 7, true); CHECK(capture);
    void* first = heap.allocate(key.heap);
    std::array<unsigned char, PointerPageBytes> before{};
    for(std::size_t i = 0; i < before.size(); ++i) before[i] = static_cast<unsigned char>(i * 17 + 5);
    std::memcpy(first, before.data(), before.size());
    CHECK(pool.try_retain(capture, release(key, 7, first)));
    CHECK(heap.outstanding() == 1 && heap.allocations == 1 && heap.frees == 0);
    CHECK(pool.stats().retained_bytes == PointerPageBytes);
    CHECK(pool.try_take(capture, allocation(key, 7)) == first);
    CHECK(std::memcmp(first, before.data(), before.size()) == 0); // Core never reads/writes game payload.
    CHECK(heap.allocations == 1 && heap.frees == 0);
    CHECK(pool.stats().retained_bytes == 0 && pool.stats().takes == 1);
    CHECK(pool.try_retain(capture, release(key, 7, first)));
    pool.end_capture(capture);
    finish(pool, key, heap);
    CHECK(heap.outstanding() == 0 && heap.frees == 1 && !heap.invalid_free);
    CHECK(pool.stats().drains == 1);
}

void all_evidence_gates() {
    Pool pool; NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    auto key = pool.register_context(0x1000, 0x2000, 7);
    CHECK(!pool.begin_capture(key, 7, false));
    CHECK(!pool.begin_capture(key, 8, true));
    auto capture = pool.begin_capture(key, 7, true); CHECK(capture);
    void* page = heap.allocate(key.heap);
    auto valid = release(key, 7, page);
    std::vector<ReleaseObservation> bad(9, valid);
    bad[0].context++; bad[1].heap++; bad[2].thread++;
    bad[3].authenticated_pointer_page_free_site = false;
    bad[4].native_finalization_complete = false;
    bad[5].native_neighbor_unlink_complete = false;
    bad[6].native_heap_has_no_release_on_free_marker = false;
    bad[7].page = nullptr;
    bad[8].page = static_cast<unsigned char*>(page) + 1;
    for(const auto& evidence : bad) CHECK(!pool.try_retain(capture, evidence));
    CHECK(pool.try_retain(capture, valid));
    auto good = allocation(key, 7);
    std::vector<AllocationObservation> invalid(9, good);
    invalid[0].context++; invalid[1].heap++; invalid[2].thread++;
    invalid[3].bytes--; invalid[4].alignment *= 2;
    invalid[5].allocation_info = page;
    invalid[6].authenticated_capture_allocation_site = false;
    invalid[7].native_heap_has_no_release_on_free_marker = false;
    invalid[8].bytes = 0;
    for(const auto& evidence : invalid) CHECK(pool.try_take(capture, evidence) == nullptr);
    CHECK(pool.stats().retained_pages == 1);
    auto foreign = capture; foreign.owner.nonce++;
    CHECK(!pool.try_take(foreign, good));
    pool.end_capture(capture);
    CHECK(!pool.try_take(capture, good));
    auto fresh = pool.begin_capture(key, 7, true); CHECK(fresh.serial != capture.serial);
    CHECK(!pool.try_take(capture, good));
    CHECK(pool.try_take(fresh, good) == page);
    original_free(heap, key.heap, page);
    finish(pool, key, heap);
    CHECK(!heap.invalid_free);
}

void bounded_contexts_and_pages() {
    Pool pool({2, 3}); NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    std::array<ContextKey, 4> keys{};
    for(std::size_t i = 0; i < keys.size(); ++i) { keys[i] = pool.register_context(0x1000 + i, 0x2000, 7 + static_cast<std::uint32_t>(i)); CHECK(keys[i]); }
    CHECK(!pool.register_context(0x9999, 0x2000, 99));
    CHECK(!pool.register_context(keys[0].context, keys[0].heap, 7));
    auto a = pool.begin_capture(keys[0], 7, true);
    for(unsigned i = 0; i < 3; ++i) {
        void* p = heap.allocate(keys[0].heap);
        bool retained = pool.try_retain(a, release(keys[0], 7, p));
        CHECK(retained == (i < 2)); if(!retained) original_free(heap, keys[0].heap, p);
    }
    auto b = pool.begin_capture(keys[1], 8, true);
    for(unsigned i = 0; i < 2; ++i) {
        void* p = heap.allocate(keys[1].heap);
        bool retained = pool.try_retain(b, release(keys[1], 8, p));
        CHECK(retained == (i == 0)); if(!retained) original_free(heap, keys[1].heap, p);
    }
    CHECK(pool.stats().retained_pages == 3 && pool.stats().high_water_pages == 3);
    CHECK(pool.stats().retained_bytes == 3 * PointerPageBytes);
    CHECK(pool.disable_and_drain_before_heap_shutdown(heap.callback()));
    CHECK(heap.outstanding() == 0 && heap.allocations == heap.frees && !heap.invalid_free);
    CHECK(!pool.enable_after_native_authentication());
    CHECK(!pool.begin_capture(keys[2], 9, true));
}

void close_tombstone_nonce_and_reentrancy() {
    Pool pool; NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    auto old = pool.register_context(0x1000, 0x2000, 7);
    auto capture = pool.begin_capture(old, 7, true);
    void* page = heap.allocate(old.heap); CHECK(pool.try_retain(capture, release(old, 7, page)));
    bool callback_checks_passed = false;
    heap.during_free = [&] {
        // These calls also prove original Free executes OUTSIDE the pool mutex.
        const auto current = pool.stats();
        callback_checks_passed = Pool::in_native_callback() && current.retained_pages == 0 &&
            !pool.begin_capture(old, 7, true) && !pool.register_context(old.context, old.heap, 7) &&
            !pool.begin_close(old, heap.callback()) && !pool.finish_close(old) &&
            !pool.disable_and_drain_before_heap_shutdown(heap.callback()) &&
            !pool.try_retain(capture, release(old, 7, page));
    };
    CHECK(pool.begin_close(old, heap.callback())); CHECK(callback_checks_passed);
    heap.during_free = {};
    CHECK(!pool.register_context(old.context, old.heap, 7));
    CHECK(!pool.try_take(capture, allocation(old, 7)));
    CHECK(pool.finish_close(old));
    auto next = pool.register_context(old.context, old.heap, 7);
    CHECK(next && next.nonce != old.nonce);
    auto next_capture = pool.begin_capture(next, 7, true);
    page = heap.allocate(next.heap); CHECK(pool.try_retain(next_capture, release(next, 7, page)));
    CHECK(!pool.begin_close(old, heap.callback()));
    CHECK(!pool.finish_close(old));
    CHECK(!pool.try_take(capture, allocation(old, 7)));
    CHECK(pool.stats().retained_pages == 1);
    finish(pool, next, heap);
    CHECK(heap.outstanding() == 0 && !heap.invalid_free);
}

void nested_and_cross_thread_rejection() {
    Pool pool; NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    auto a = pool.register_context(0x1000, 0x2000, 7);
    auto b = pool.register_context(0x1100, 0x2000, 7);
    auto scope = pool.begin_capture(a, 7, true); CHECK(scope);
    CHECK(!pool.begin_capture(a, 7, true));
    CHECK(!pool.begin_capture(b, 7, true));
    void* page = heap.allocate(a.heap); CHECK(pool.try_retain(scope, release(a, 7, page)));
    auto worker = std::async(std::launch::async, [&] {
        return !pool.begin_capture(a, 8, true) && !pool.try_take(scope, allocation(a, 8));
    });
    CHECK(worker.get());
    pool.end_capture(scope); CHECK(pool.begin_capture(b, 7, true));
    finish(pool, a, heap); finish(pool, b, heap);
}

void duplicate_or_foreign_free_does_not_leave_dangling_cache() {
    Pool pool; NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    auto key = pool.register_context(0x1000, 0x2000, 7);
    auto scope = pool.begin_capture(key, 7, true);
    void* page = heap.allocate(key.heap); CHECK(pool.try_retain(scope, release(key, 7, page)));
    CHECK(!pool.try_retain(scope, release(key, 7, page)));
    original_free(heap, key.heap, page); // Sole cached ownership was revoked first.
    CHECK(pool.stats().retained_pages == 0 && pool.stats().duplicate_releases == 1);
    CHECK(!pool.try_take(scope, allocation(key, 7)));
    pool.end_capture(scope); CHECK(!pool.begin_capture(key, 7, true)); // Suspended, not silently reused.
    finish(pool, key, heap);
    CHECK(heap.frees == 1 && !heap.invalid_free);
}

void concurrent_global_shutdown_waits_for_native_frees() {
    Pool pool; NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    auto key = pool.register_context(0x1000, 0x2000, 7);
    auto scope = pool.begin_capture(key, 7, true);
    void* page = heap.allocate(key.heap); CHECK(pool.try_retain(scope, release(key, 7, page)));
    std::promise<void> inside_native_free, release_native_free;
    auto unblock = release_native_free.get_future().share();
    heap.during_free = [&] { inside_native_free.set_value(); unblock.wait(); };
    auto close = std::async(std::launch::async, [&] { return pool.begin_close(key, heap.callback()); });
    inside_native_free.get_future().wait();
    CHECK(!pool.finish_close(key)); // A callback still owns the detached batch.
    auto shutdown = std::async(std::launch::async, [&] { return pool.disable_and_drain_before_heap_shutdown(heap.callback()); });
    CHECK(shutdown.wait_for(std::chrono::milliseconds(30)) == std::future_status::timeout);
    release_native_free.set_value();
    CHECK(close.get()); CHECK(shutdown.get());
    heap.during_free = {};
    CHECK(pool.finish_close(key));
    CHECK(heap.outstanding() == 0 && !heap.invalid_free);
}

void independent_context_concurrency() {
    using ManyPool = SnapshotPointerPagePool<16, 8>;
    ManyPool pool({8, 128}); NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    std::atomic<unsigned> failures{};
    std::vector<std::thread> threads;
    for(unsigned i = 0; i < 16; ++i) threads.emplace_back([&, i] {
        const auto tid = 100 + i;
        auto key = pool.register_context(0x1000 + i, 0x2000 + i, tid);
        auto scope = pool.begin_capture(key, tid, true);
        if(!key || !scope) { ++failures; return; }
        for(unsigned j = 0; j < 200; ++j) {
            void* page = pool.try_take(scope, allocation(key, tid));
            if(!page) page = heap.allocate(key.heap);
            std::memset(page, static_cast<int>(i + j), PointerPageBytes);
            if(!pool.try_retain(scope, release(key, tid, page))) original_free(heap, key.heap, page);
        }
        pool.end_capture(scope);
        if(!pool.begin_close(key, heap.callback()) || !pool.finish_close(key)) ++failures;
    });
    for(auto& thread : threads) thread.join();
    CHECK(failures == 0);
    CHECK(pool.stats().retained_pages == 0 && heap.outstanding() == 0);
    CHECK(heap.allocations == heap.frees && !heap.invalid_free);
}

void zero_limits_forward_every_call() {
    Pool pool({0, 0}); NativeHeapFixture heap;
    CHECK(pool.enable_after_native_authentication());
    auto key = pool.register_context(1, 2, 7);
    auto capture = pool.begin_capture(key, 7, true);
    void* page = heap.allocate(key.heap);
    CHECK(!pool.try_retain(capture, release(key, 7, page)));
    original_free(heap, key.heap, page);
    CHECK(!pool.try_take(capture, allocation(key, 7)));
    finish(pool, key, heap);
    CHECK(!heap.invalid_free);
}

int main() {
    const std::pair<const char*, void(*)()> cases[] = {
        {"native accounting and payload", native_accounting_and_payload},
        {"all ABI/evidence gates", all_evidence_gates},
        {"bounded contexts and pages", bounded_contexts_and_pages},
        {"close tombstone/nonce/reentrancy", close_tombstone_nonce_and_reentrancy},
        {"nested/cross-thread rejection", nested_and_cross_thread_rejection},
        {"duplicate/foreign release", duplicate_or_foreign_free_does_not_leave_dangling_cache},
        {"concurrent global shutdown", concurrent_global_shutdown_waits_for_native_frees},
        {"independent context concurrency", independent_context_concurrency},
        {"zero limits", zero_limits_forward_every_call},
    };
    try {
        for(const auto& item : cases) { item.second(); std::cout << "PASS " << item.first << '\n'; }
    } catch(const std::exception& error) { std::cerr << "FAIL " << error.what() << '\n'; return 1; }
    std::cout << "9 isolated contract tests passed; no game hooks or performance claim.\n";
}
