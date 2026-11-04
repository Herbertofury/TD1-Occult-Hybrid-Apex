#include "ApexOwnerMailboxApi.h"
#include <iostream>
#include <stdexcept>
using namespace td1::ownerbridge;
static void Check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
int main(){try{
 Mailbox m;const std::string nonce(32,'a'),id(32,'1');
 auto status=ControlWithSelection(m,"{\"operation\":\"status\"}",100,200,[]()->std::uint64_t{throw std::runtime_error("Status must not lock render selection");},1000);
 Check(status["ok"]==true,"Metadata status read selection authority");
 auto call=[&](Json request){return Control(m,request.dump(),100,200,7,1000);};
 auto bound=call({{"operation","bind"},{"pid",100},{"nonce",nonce}});Check(bound["ok"]==true,"Bind refused");auto runtime=bound["runtime"];
 const auto accepted=m.Offer(id,"/api/command?action=status",7,2000);Check(accepted.admission==Admission::Accepted,"Offer refused");
 auto taken=call({{"operation","take"},{"runtime",runtime}});Check(taken["job"]["request_id"]==id,"Claimed identity differs");
 const auto ticket=taken["job"]["ticket"];
 Json publish={{"operation","publish"},{"runtime",runtime},{"ticket",ticket},{"request_id",id},{"phase","submitted"},
     {"receipt",Json{{"ok",true},{"request_id",id},{"state","pending"},{"result",nullptr}}.dump()}};
 Check(call(publish)["ok"]==true,"Exact queue submission refused");
 Json authorize={{"operation","authorize"},{"runtime",runtime},{"ticket",ticket},{"request_id",id}};
 Check(call(authorize)["ok"]==true,"Current job not authorized");
 Check(Control(m,authorize.dump(),100,200,8,1000)["ok"]==false,"Stale generation authorized");
 Check(Control(m,authorize.dump(),100,200,7,2000)["ok"]==false,"Expired job authorized");
 Check(Control(m,authorize.dump(),101,200,7,1000)["ok"]==false,"Foreign process authorized");
 Check(Control(m,authorize.dump(),100,201,7,1000)["ok"]==false,"Foreign thread authorized");
 auto bad=publish;bad["phase"]="terminal";Check(call(bad)["ok"]==false,"Pending receipt claimed completion");
 bad=publish;bad["receipt"]="{\"ok\":true,\"ok\":false,\"state\":\"pending\",\"request_id\":\""+id+"\"}";
 Check(call(bad)["ok"]==false,"Duplicate receipt fields accepted");
 bad=publish;bad["receipt"]=Json{{"ok",true},{"request_id",nonce},{"state","pending"}}.dump();
 Check(call(bad)["ok"]==false,"Foreign receipt UUID accepted");
 auto complete=publish;complete["phase"]="terminal";complete["receipt"]=Json{{"ok",true},{"request_id",id},{"state","completed"},{"result",{{"ok",true},{"complete_field",UINT64_MAX}}}}.dump();
 Check(ControlWithSelection(m,complete.dump(),100,200,[]()->std::uint64_t{throw std::runtime_error("Completed write must not recheck later UI selection");},1000)["ok"]==true,"Complete queue result refused after later selection changed");auto result=m.Read(ticket.get<std::uint64_t>(),id);
 Check(Strict(*result.receipt)["result"]["complete_field"].get<std::uint64_t>()==UINT64_MAX,"Complete result uint64 changed");
 Check(Control(m,"{\"operation\":\"take\",\"operation\":\"bind\"}",100,200,7,1000)["ok"]==false,"Duplicate control intent accepted");
 auto unknown=authorize;unknown["unexpected"]=true;Check(call(unknown)["ok"]==false,"Unknown control fields accepted");
 Check(Uint(Json(UINT64_MAX))&&!Uint(Json(-1))&&!Uint(Json(1.0)),"Full uint64 identity contract differs");
 Check(call({{"operation","retire"},{"runtime",runtime}})["ok"]==true,"Retirement refused");
 std::cout<<"PASS strict owner mailbox facade: UUID/phase/expiry/runtime/duplicates/complete numbers\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
