#pragma once
#include <cstdint>
#include <limits>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <chrono>
#include <condition_variable>
#include <mutex>
#endif

namespace td1::transport {
inline constexpr std::uint32_t InfiniteWait = (std::numeric_limits<std::uint32_t>::max)();
inline constexpr std::uint64_t StatusIntervalMs = 1300;
enum class WakeResult { Notified, Deadline, Unavailable };

// One retained notification represents queued work, not a count of commands.
// Queue ownership, FIFO order and UUID/admission rules remain with the caller.
// Production allocates this object once before starting its detached transport
// worker and intentionally retains it until process exit. DllMain notification
// therefore never allocates, locks a C++ mutex or closes a waited-on handle.
class WorkerWake {
#ifdef _WIN32
    HANDLE event_ = nullptr;
#else
    std::mutex mutex_;
    std::condition_variable condition_;
    bool pending_ = false;
    bool enabled_ = true;
#endif
public:
    explicit WorkerWake(bool enabled = true) {
#ifdef _WIN32
        if (enabled) event_ = CreateEventW(nullptr, FALSE, FALSE, nullptr);
#else
        enabled_ = enabled;
#endif
    }
    WorkerWake(const WorkerWake&) = delete;
    WorkerWake& operator=(const WorkerWake&) = delete;
    ~WorkerWake() {
#ifdef _WIN32
        // Tests close only after their waiter joins. The process-lifetime
        // production instance is never destroyed during DLL/CRT teardown.
        if (event_) CloseHandle(event_);
#endif
    }
    bool Available() const noexcept {
#ifdef _WIN32
        return event_ != nullptr;
#else
        return enabled_;
#endif
    }
    bool Notify() noexcept {
#ifdef _WIN32
        return event_ && SetEvent(event_) != FALSE;
#else
        if (!enabled_) return false;
        { std::lock_guard<std::mutex> lock(mutex_); pending_ = true; }
        condition_.notify_one(); return true;
#endif
    }
    WakeResult Wait(std::uint32_t milliseconds) noexcept {
#ifdef _WIN32
        if (!event_) return WakeResult::Unavailable;
        const auto value = WaitForSingleObject(event_, milliseconds);
        return value == WAIT_OBJECT_0 ? WakeResult::Notified :
            value == WAIT_TIMEOUT ? WakeResult::Deadline : WakeResult::Unavailable;
#else
        if (!enabled_) return WakeResult::Unavailable;
        std::unique_lock<std::mutex> lock(mutex_);
        if (milliseconds == InfiniteWait) condition_.wait(lock, [&] { return pending_; });
        else if (!condition_.wait_for(lock, std::chrono::milliseconds(milliseconds), [&] { return pending_; }))
            return WakeResult::Deadline;
        pending_ = false; return WakeResult::Notified;
#endif
    }
};

inline std::uint32_t IdleWaitMilliseconds(std::uint64_t now, std::uint64_t lastStatus,
    bool visible, bool nativeCasPaneVisible, bool ownerBlocked, bool wakeAvailable) noexcept {
    // An unavailable event retains the previous bounded polling behavior.
    if (!wakeAvailable) return visible ? 120 : 250;
    if (!visible || nativeCasPaneVisible || ownerBlocked) return InfiniteWait;
    const auto elapsed = now >= lastStatus ? now - lastStatus : 0;
    return elapsed >= StatusIntervalMs ? 0 : static_cast<std::uint32_t>(StatusIntervalMs - elapsed);
}
}
