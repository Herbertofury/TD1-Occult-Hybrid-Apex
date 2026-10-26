#include "ApexOwnerMailbox.h"
#include <future>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <thread>
using namespace td1::ownerbridge;
static void Check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
static std::string Id(unsigned number){std::ostringstream s;s<<std::hex<<std::setfill('0')<<std::setw(32)<<number;return s.str();}
int main(){try{
 {Mailbox m;Check(m.Offer(Id(1),"request",5).admission==Admission::Unready,"Unready admission was accepted");
  const auto r=m.Bind(Id(99),100,200);Check(r.epoch==1&&m.Ready(),"Runtime did not bind");
  auto a=m.Offer(Id(1),"request",5);Check(a.admission==Admission::Accepted&&m.Pending(),"Offer missing");
  Check(m.Offer(Id(1),"request",5).admission==Admission::Duplicate,"Duplicate was replayed");
  Check(m.Offer(Id(1),"other",5).admission==Admission::Rejected,"Changed bytes accepted");
  Check(m.Offer(Id(1),"request",6).admission==Admission::Rejected,"Changed generation accepted");
  Check(m.Take(r,201).ticket==0,"Foreign thread claimed");auto foreign=r;foreign.pid=101;
  Check(m.Take(foreign,200).ticket==0,"Foreign runtime claimed");
  const auto q=m.Take(r,200);Check(q.ticket==a.record.ticket&&!m.Pending(),"Claim differs");
  Check(!m.Authorize(r,200,q.ticket,q.id,5),"Claim was executable before submission");
  Check(m.Publish(r,200,q.ticket,q.id,"pending",Phase::Submitted),"Submission missing");
  Check(!m.Authorize(r,200,q.ticket,q.id,6),"Stale selection authorized");
  Check(m.Authorize(r,200,q.ticket,q.id,5),"Current selection not authorized");
  Check(m.Publish(r,200,q.ticket,q.id,"running",Phase::Running),"Running receipt missing");
  Check(!m.Publish(foreign,200,q.ticket,q.id,"done",Phase::Terminal),"Foreign result accepted");
  Check(!m.Publish(r,200,q.ticket,Id(2),"done",Phase::Terminal),"Foreign UUID result accepted");
  Check(m.Publish(r,200,q.ticket,q.id,"done",Phase::Terminal),"Completion missing");
  const auto result=m.Read(q.ticket,q.id,true);Check(result.phase==Phase::Terminal&&*result.receipt=="done"&&!m.Unresolved(),"Completion differs");
  Check(result.request==q.request,"Immutable request was copied/replaced");
  Check(m.Publish(r,200,q.ticket,q.id,"done",Phase::Terminal),"Exact completion retry rejected");
  Check(!m.Publish(r,200,q.ticket,q.id,"changed",Phase::Terminal),"Completion overwritten");
 }
 {Mailbox m;auto r=m.Bind(Id(99),100,200);for(unsigned i=1;i<=Capacity;++i)Check(m.Offer(Id(i),"r",0).admission==Admission::Accepted,"Capacity dropped accepted work");
  Check(m.Offer(Id(100),"overflow",0).admission==Admission::Rejected,"Capacity overflow accepted");
  for(unsigned i=1;i<=Capacity;++i){auto q=m.Take(r,200);Check(q.id==Id(i),"Ingress FIFO changed");
   Check(m.Publish(r,200,q.ticket,q.id,"cancelled-before-execution",Phase::Terminal),"Cancellation receipt lost");}
  Check(!m.Pending()&&!m.Unresolved(),"Finished FIFO remained active");
 }
 {Mailbox m;auto r=m.Bind(Id(99),100,200);auto q=m.Offer(Id(1),"unknown-outcome",7).record;
  auto a=m.Take(r,200);m.Publish(r,200,a.ticket,a.id,"pending",Phase::Submitted);
  Check(m.Retire(r,200),"Runtime did not retire");Check(!m.Ready(),"Retired runtime stayed ready");
  Check(m.Read(q.ticket,q.id).phase==Phase::Uncertain,"Retirement fabricated cancellation");
  Check(m.Offer(q.id,"unknown-outcome",7).admission==Admission::Duplicate,"Uncertain identity was readmitted");
  auto next=m.Bind(Id(100),100,200);Check(next.epoch==2,"Zone epoch did not advance");
  Check(!m.Publish(next,200,q.ticket,q.id,"fake",Phase::Terminal),"New runtime completed an old command");
  Check(!m.Authorize(r,200,q.ticket,q.id,7),"Retired command remained executable");
 }
 {Mailbox m;auto r=m.Bind(Id(99),100,200);auto a=m.Offer(Id(1),"request",0);std::promise<Snapshot> completed;
  auto f=completed.get_future();std::thread waiter([&]{completed.set_value(m.Wait(a.record.ticket,a.record.id,a.record.version,std::chrono::steady_clock::now()+std::chrono::seconds(2)));});
  auto q=m.Take(r,200);waiter.join();Check(f.get().version>1,"Retained receipt wake lost");
  std::promise<Snapshot> stopped;auto sf=stopped.get_future();auto before=m.Read(q.ticket,q.id);
  std::thread shutdownWaiter([&]{stopped.set_value(m.Wait(q.ticket,q.id,before.version,std::chrono::steady_clock::now()+std::chrono::seconds(2)));});
  m.Shutdown();shutdownWaiter.join();Check(sf.get().phase==Phase::Uncertain,"Shutdown fabricated outcome");
  Check(m.Offer(Id(2),"never",0).admission==Admission::Unready,"Shutdown accepted new work");
  Check(m.Bind(Id(100),100,200).epoch==0,"Stopped mailbox rebound");
 }
 {Mailbox m;auto r=m.Bind(Id(99),100,200);
  Check(m.Offer("invalid","r",0).admission==Admission::Rejected,"Invalid UUID accepted");
  Check(m.Offer(Id(1),std::string(MaxBytes+1,'x'),0).admission==Admission::Rejected,"Oversize bytes accepted");
  for(unsigned i=1;i<=Retained+50;++i){auto q=m.Offer(Id(i),"request",i).record;Check(q.ticket!=0,"Observed receipt retention exhausted");
   auto a=m.Take(r,200);Check(m.Publish(r,200,a.ticket,a.id,"complete",Phase::Terminal),"Terminal receipt rejected");m.Read(a.ticket,a.id,true);}
  Check(m.Bind(Id(101),100,201).epoch==0,"Foreign owner rebound runtime");
 }
 std::cout<<"PASS owner mailbox: admission/FIFO/UUID/capacity/runtime/generation/retention/uncertain/shutdown\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
