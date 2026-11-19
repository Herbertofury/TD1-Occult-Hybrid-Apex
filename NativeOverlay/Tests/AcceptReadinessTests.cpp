#include "ApexCasAcceptReadiness.h"
#include <functional>
#include <iostream>
using namespace td1::nativecas::acceptance;
void require(bool ok){if(!ok)throw std::runtime_error("readiness invariant");}
void refuses(const std::function<void()>& fn){bool error=false;try{fn();}catch(const std::exception&){error=true;}require(error);}
int main(){
 Intent intent{std::string(32,'b'),std::string(64,'a'),12,34,7,"0","4","2","127","alien/first","91"};
 Observation state{"editor-roster-owner","full-before","context",true,true,0,"scalars"};
 Ledger ledger;int prepares=0,captures=0;
 auto capture=[&]{++captures;return state;};
 auto probe=[&]{return state;};
 auto prepare=[&]{++prepares;state.complete="full-after";return true;};
 require(ledger.Begin(intent,capture,prepare).authoritativeHarvest);require(prepares==1);
 ledger.Begin(intent,capture,prepare);require(prepares==1);
 const auto beforeBusy=captures;for(int i=0;i<50;++i)require(!Ready(ledger.Poll(intent,capture,probe)));require(captures==beforeBusy);
 require(!Ready(ledger.Poll(intent,capture,probe)));state.busy=false;state.phase=1;require(!Ready(ledger.Poll(intent,capture,probe)));
 state.phase=0;require(Ready(ledger.Poll(intent,capture,probe)));
 require(ledger.IntentForSave(intent.id,intent.nonce)==intent);
 require(ledger.Consume(intent,capture,probe).state=="consumed");refuses([&]{ledger.Consume(intent,capture,probe);});
 require(prepares==1);auto foreign=intent;foreign.nonce=std::string(64,'c');refuses([&]{ledger.Begin(foreign,capture,prepare);});
 refuses([&]{ledger.IntentForSave(intent.id,foreign.nonce);});
 for(const std::string mutation:{"unknown appearance","other owner generation","Sim/HH/room","cancel/save serial"}){
   Ledger stale;state={"identity","complete","context",true,true,0,"scalars"};int once=0;
   stale.Begin(intent,capture,[&]{++once;return false;});state.complete=mutation;state.busy=false;
   refuses([&]{stale.Poll(intent,capture,probe);});state.complete="complete";
   refuses([&]{stale.Poll(intent,capture,probe);});require(once==1);
 }
 Ledger dirty;state={"identity","complete","context",false,true,0,"scalars"};
 require(dirty.Begin(intent,capture,[&]{state.identity="changed-other-owner";return true;}).state=="refused");
 refuses([&]{dirty.Poll(intent,capture,probe);});
 Ledger pending;state={"identity","complete","context",true,true,0,"scalars"};pending.Begin(intent,capture,[]{return false;});
 refuses([&]{pending.Consume(intent,capture,probe);});state.busy=false;refuses([&]{pending.Consume(intent,capture,probe);});
 Ledger cancel;state={"identity","complete","context",true,true,0,"scalars"};cancel.Begin(intent,capture,[]{return false;});cancel.Cancel(intent);
 refuses([&]{cancel.Poll(intent,capture,probe);});require(cancel.Begin(intent,capture,prepare).state=="refused");
 Ledger exceptional;require(exceptional.Begin(intent,capture,[]{throw std::runtime_error("harvest fault");return false;}).state=="refused");
 refuses([&]{exceptional.Poll(intent,capture,probe);});
 Ledger bounds;auto bad=intent;bad.id="bad";refuses([&]{bounds.Begin(bad,capture,prepare);});
 std::cout<<"accept readiness: typed admission/once-only prepare/complete stale fences/genuine busy/consume/cancel pass\n";
}
