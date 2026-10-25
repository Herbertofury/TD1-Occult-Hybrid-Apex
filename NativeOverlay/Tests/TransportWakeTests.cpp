#include "ApexTransportWake.h"
#include <atomic>
#include <chrono>
#include <deque>
#include <future>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

using td1::transport::WorkerWake;
using td1::transport::WakeResult;
using td1::transport::IdleWaitMilliseconds;
using td1::transport::InfiniteWait;
static void Check(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }

int main() {
    try {
        {
            // The first command is deliberately blocked while a whole burst is
            // queued. SetEvent coalesces that burst into one notification. The
            // production idle predicate must drain every queued command before
            // waiting again; no new producer notification rescues this test.
            WorkerWake wake; std::mutex mutex; std::deque<int> queue{0};
            std::vector<int> consumed; std::promise<void> entered, release;
            auto released=release.get_future(); std::atomic<bool> timedOut{false};
            std::thread worker([&] {
                for (;;) {
                    int value=-1;
                    { std::lock_guard<std::mutex> lock(mutex); if(!queue.empty()) {value=queue.front();queue.pop_front();} }
                    if(value<0) break;
                    if(value==0) {entered.set_value();released.wait();}
                    consumed.push_back(value);
                    if(value==32) break;
                    bool pending;
                    { std::lock_guard<std::mutex> lock(mutex); pending=!queue.empty(); }
                    if(!pending && wake.Wait(100)==WakeResult::Deadline) {timedOut=true;break;}
                }
            });
            entered.get_future().wait();
            for(int i=1;i<=32;++i) {
                std::lock_guard<std::mutex> lock(mutex); queue.push_back(i); wake.Notify();
            }
            release.set_value(); worker.join();
            Check(!timedOut && consumed.size()==33, "Coalesced burst left queued commands asleep");
            for(int i=0;i<=32;++i) Check(consumed[static_cast<std::size_t>(i)]==i, "Burst reordered commands");
        }
        {
            WorkerWake wake; Check(wake.Available(), "Native wake unavailable");
            Check(wake.Notify(), "Initial notification failed");
            Check(wake.Wait(0) == WakeResult::Notified, "Notification before wait was lost");
            Check(wake.Wait(0) == WakeResult::Deadline, "Consumed notification became a busy loop");
            for (int i = 0; i < 1000; ++i) Check(wake.Notify(), "Coalesced notify failed");
            Check(wake.Wait(0) == WakeResult::Notified, "Coalesced notifications lost all work");
            Check(wake.Wait(0) == WakeResult::Deadline, "Notifications counted work instead of coalescing");
        }
        {
            WorkerWake wake; std::promise<void> started; std::promise<WakeResult> finished;
            auto result = finished.get_future();
            std::thread worker([&] { started.set_value(); finished.set_value(wake.Wait(InfiniteWait)); });
            started.get_future().wait(); wake.Notify();
            const bool observed = result.wait_for(std::chrono::seconds(2)) == std::future_status::ready;
            if (!observed) wake.Notify();
            worker.join(); Check(observed && result.get() == WakeResult::Notified, "Blocked hidden worker did not wake");
        }
        {
            WorkerWake disabled(false); Check(!disabled.Available(), "Disabled fixture remained available");
            Check(!disabled.Notify(), "Disabled event accepted notification");
            Check(disabled.Wait(InfiniteWait) == WakeResult::Unavailable, "Unavailable event could hang");
            Check(IdleWaitMilliseconds(100,0,true,false,false,false)==120, "Visible fallback changed");
            Check(IdleWaitMilliseconds(100,0,false,false,false,false)==250, "Hidden fallback changed");
        }
        {
            Check(IdleWaitMilliseconds(1000,0,true,false,false,true)==300, "Metadata deadline was postponed");
            Check(IdleWaitMilliseconds(1300,0,true,false,false,true)==0, "Due metadata was delayed");
            Check(IdleWaitMilliseconds(1400,0,true,false,false,true)==0, "Overdue metadata was delayed");
            Check(IdleWaitMilliseconds(100,100,true,false,false,true)==1300, "Fresh metadata deadline differs");
            Check(IdleWaitMilliseconds(99,100,true,false,false,true)==1300, "Clock rollback spun");
            Check(IdleWaitMilliseconds(100,0,false,false,false,true)==InfiniteWait, "Hidden mode polled HTTP");
            Check(IdleWaitMilliseconds(100,0,true,true,false,true)==InfiniteWait, "CAS pane polled Live metadata");
            Check(IdleWaitMilliseconds(100,0,true,false,true,true)==InfiniteWait, "Unresolved owner polled metadata");
        }
        {
            WorkerWake wake; std::mutex mutex; std::deque<int> queue; std::vector<int> consumed;
            std::atomic<bool> stop{false};
            std::thread worker([&] {
                for (;;) {
                    int value=-1;
                    { std::lock_guard<std::mutex> lock(mutex); if(!queue.empty()) {value=queue.front();queue.pop_front();} }
                    if(value>=0) {consumed.push_back(value);continue;}
                    if(stop.load()) break;
                    wake.Wait(InfiniteWait);
                }
            });
            for(int i=0;i<4000;++i) {
                { std::lock_guard<std::mutex> lock(mutex); queue.push_back(i); wake.Notify(); }
                if(i%17==0) std::this_thread::yield();
            }
            stop=true; wake.Notify(); worker.join();
            Check(consumed.size()==4000, "Queue lost a notification or command");
            for(int i=0;i<4000;++i) Check(consumed[static_cast<std::size_t>(i)]==i, "Wake changed FIFO order");
        }
        {
            // Visibility/mode/selection/shutdown notifications all use the
            // same retained signal; an earlier notification is never cleared
            // merely because a later mode computed an indefinite idle wait.
            WorkerWake wake;
            for(int transition=0;transition<5;++transition) {
                wake.Notify(); Check(wake.Wait(InfiniteWait)==WakeResult::Notified, "Mode transition wake was lost");
                Check(wake.Wait(0)==WakeResult::Deadline, "Mode transition caused an idle spin");
            }
        }
        std::cout << "PASS transport wake: prewait, coalescing, blocked-command burst, hidden wait, fallback, deadlines, FIFO and lifecycle\n";
        return 0;
    } catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
