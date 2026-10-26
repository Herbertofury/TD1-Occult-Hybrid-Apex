#include "ApexServiceTiming.h"
#include <stdexcept>
#include <thread>
#include <vector>

void Check(bool value) {if(!value)throw std::runtime_error("Native service timing regression.");}

int main() {
    td1::performance::ServiceTiming<2> timing;std::uint64_t now=100,clocks=0;
    auto clock=[&](){++clocks;return now;};
    for(unsigned i=0;i<100000;++i)timing.End(timing.Begin(0,clock),clock);
    Check(clocks==0 && timing.Read().rows[0].calls==0);
    Check(timing.Start(now,100));auto a=timing.Begin(0,clock);now+=7;timing.End(a,clock);
    auto b=timing.Begin(1,clock);timing.Stop();Check(!timing.Start(now,20));now+=11;timing.End(b,clock);
    auto snapshot=timing.Read();Check(!snapshot.enabled && snapshot.rows[0].calls==1 && snapshot.rows[0].maximum==7);
    Check(snapshot.rows[1].calls==1 && snapshot.rows[1].total==11 && snapshot.inflight==0);
    Check(timing.Start(now,20));now+=20;Check(!timing.Begin(0,clock).active);Check(!timing.Read().enabled);
    Check(!timing.Start(UINT64_MAX-4,5));Check(!timing.Start(1,0));
    Check(timing.Start(1,100));std::vector<decltype(timing.Begin(0,clock))> held;
    for(unsigned i=0;i<64;++i)held.push_back(timing.Begin(0,[]{return std::uint64_t(2);}));
    Check(!timing.Begin(0,[]{return std::uint64_t(2);}).active);
    Check(timing.Read().inflight==64 && timing.Read().skipped==1);
    Check(!timing.Start(3,100));
    for(auto ticket:held)timing.End(ticket,[]{return std::uint64_t(3);});
    Check(timing.Read().rows[0].calls==64 && timing.Read().skipped==1 && timing.Read().inflight==0);
    now=1;Check(timing.Start(now,10000));Check(timing.Read().skipped==0);
    std::vector<std::thread> threads;
    for(unsigned n=0;n<8;++n)threads.emplace_back([&](){for(unsigned i=0;i<1000;++i){auto t=timing.Begin(0,[]{return std::uint64_t(2);});timing.End(t,[]{return std::uint64_t(3);});}});
    for(auto& thread:threads)thread.join();snapshot=timing.Read();Check(snapshot.rows[0].calls==8000 && snapshot.rows[0].total==8000 && snapshot.inflight==0);
    timing.Stop();const auto before=clocks;timing.End(timing.Begin(0,clock),clock);Check(clocks==before);
}
