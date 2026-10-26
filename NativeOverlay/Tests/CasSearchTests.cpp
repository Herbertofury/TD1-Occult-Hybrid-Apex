#include "ApexCasSearchWin.h"
#include <future>
#include <iostream>
#include <fstream>
#include <filesystem>

using td1::ui::Json;
void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char** argv) {
    try {
        if((argc==6&&std::string(argv[5])=="catalog")||argc==9) {
            std::ifstream input(std::filesystem::u8path(argv[1]));Json query;input>>query;
            std::unique_ptr<td1::search::OfflineMetadata> offline;
            if(argc==9)offline=std::make_unique<td1::search::OfflineMetadata>(argv[3],argv[4],argv[5],argv[6],argv[7]);
            else offline=std::make_unique<td1::search::OfflineMetadata>(argv[3],argv[4]);
            const auto result=offline->Read(query);Check(td1::library::Page(result,query),"F11 local metadata page differs from its exact query.");
            std::ofstream output(std::filesystem::u8path(argv[2]));output<<result.dump(2);output.flush();
            Check(output.good(),"F11 catalogue probe output could not be retained.");return 0;
        }
        if(argc==3||argc==5) {
            std::ifstream input(std::filesystem::u8path(argv[1]));Json query;input>>query;
            std::unique_ptr<td1::search::OfflineMetadata> offline;
            if(argc==5)offline=std::make_unique<td1::search::OfflineMetadata>(argv[3],argv[4]);
            td1::search::Worker worker([&](const Json& q){return offline?offline->Read(q):td1::search::FetchMetadata(q);});
            const auto ticket=worker.Submit("read-only-native-metadata-probe",query);
            const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(10);
            std::shared_ptr<const Json> result;
            do {result=worker.Poll("read-only-native-metadata-probe",ticket);std::this_thread::sleep_for(std::chrono::milliseconds(2));}
            while(result->value("state","")=="pending"&&std::chrono::steady_clock::now()<deadline);
            std::ofstream output(std::filesystem::u8path(argv[2]));output<<result->dump(2);output.flush();
            Check(output.good(),"Metadata probe output could not be retained.");
            return result->value("ok",false)&&result->contains("items")?0:1;
        }
        Check(argc==1,"Use no arguments for tests, or query.json output.json for the read-only broker probe.");
        const Json query={{"text","eyeborws"},{"body_type",34},{"origin",nullptr},{"name_mode","preferred"},
                          {"offset",0},{"limit",24},{"view","all"},{"author",""},{"sort","name"},
                          {"grouped",true},{"fuzzy",true}};
        Check(td1::library::Query(query),"Fuzzy native query must be accepted.");
        Check(td1::search::UiError("Typed refusal")=="SEARCHERROR|Typed refusal","Read-only UI refusal lost its reason.");
        Check(td1::search::UiError(std::string(2000,'x')).size()==524,"UI refusal diagnostic is not bounded.");
        const std::string hash(64,'a');
        Json page={{"ok",true},{"index_sha256",hash},{"query",query},{"grouped",true},
            {"items",Json::array()},{"categories",Json::array()},{"total",0},{"offset",0},{"next_offset",nullptr},
            {"snapshot",{{"parts",0},{"complete",true}}}};
        Check(td1::search::UiPage(page,query,17)=="SEARCHPAGE|17|"+hash+"|0|0|-|","Empty UI page differs.");
        Json row={{"part_id",hash},{"resource_sha256",hash},{"package_sha256",hash},
            {"resource_tgi","034AEECB:00000000:123456789ABCDEF0"},{"body_type",34},{"favorite",false},
            {"name","Unicode label \xE4\xB8\xAD | ; ,"},{"package_name","Creator.package"},{"status","indexed"},{"origin","mod"}};
        page["items"]=Json::array({row});page["total"]=1;
        Check(td1::search::UiPage(page,query,18)=="SEARCHPAGE|18|"+hash+"|1|0|-|034AEECB:00000000:123456789ABCDEF0,34",
            "UI projection changed an exact 64-bit key or leaked labels.");
        auto folders=page;folders["folder_matches"]=Json::array({"Makeup/Lips","Unicode \xE4\xB8\xAD | ; %"});folders["folder_corrected"]=true;
        Check(td1::search::UiPage(folders,query,18).find("|Makeup%2FLips;Unicode%20%E4%B8%AD%20%7C%20%3B%20%25|1")!=std::string::npos,
            "Folder labels can inject delimiters or lose Unicode.");
        folders["folder_matches"]=Json::array({17});bool refusedFolder=false;
        try{td1::search::UiPage(folders,query,18);}catch(const std::exception&){refusedFolder=true;}
        Check(refusedFolder,"Untyped folder suggestions accepted.");
        auto folderQuery=query;folderQuery["folder"]="Makeup";folderQuery["added_days"]=7;folderQuery["sort"]="newest";
        Check(td1::library::Query(folderQuery),"Bounded folder/date query rejected.");
        folderQuery["added_days"]=-1;Check(!td1::library::Query(folderQuery),"Negative added-date query accepted.");
        page["total"]=2;page["next_offset"]=1;
        Check(td1::search::UiPage(page,query,19).find("|2|0|1|")!=std::string::npos,"UI continuation was lost.");
        auto lastQuery=query;lastQuery["offset"]=1;page["query"]=lastQuery;page["offset"]=1;page["next_offset"]=nullptr;
        page["items"][0]["body_type"]=nullptr;
        Check(td1::search::UiPage(page,lastQuery,20).find("ABCDEF0,-")!=std::string::npos,"Unknown body type was invented.");
        for(unsigned mode=0;mode<6;mode++) {
            auto bad=page;
            if(mode==0)bad["index_sha256"]="invalid";
            if(mode==1)bad["items"][0]["resource_tgi"]="034AEECB:00000000:1|injection";
            if(mode==2)bad["items"][0]["body_type"]=0x80000000ULL;
            if(mode==3)bad["total"]=0;
            if(mode==4)bad["next_offset"]=2;
            if(mode==5)bad["query"]["text"]="another query";
            bool rejected=false;try{td1::search::UiPage(bad,lastQuery,20);}catch(const std::exception&){rejected=true;}
            Check(rejected,"Malformed compact UI page accepted.");
        }
        td1::search::Worker successful([&](const Json&){return page;});
        const auto goodTicket=successful.Submit("memberC/alien",lastQuery);
        const auto goodDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        std::shared_ptr<const std::string> goodWire;
        do {goodWire=successful.PollUiWire("memberC/alien",goodTicket);std::this_thread::yield();}
        while(goodWire->rfind("SEARCHWAIT|",0)==0&&std::chrono::steady_clock::now()<goodDeadline);
        Check(*goodWire==td1::search::UiPage(page,lastQuery,goodTicket),"Background UI publication differs.");
        Check(successful.PollUiWire("memberC/alien",goodTicket)==goodWire,"Ready UI projection was rebuilt on poll.");
        Check(successful.PollUiWire("memberD/fairy",goodTicket)->rfind("SEARCHERROR|",0)==0,"UI page leaked to another owner.");
        successful.Stop();
        td1::search::Worker foreign([&](const Json&){auto other=page;other["equipped_snapshot"]={{"source_epoch","another-session"}};return other;});
        const auto foreignTicket=foreign.Submit("current-session|memberC|alien",lastQuery);
        const auto foreignDeadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        std::shared_ptr<const std::string> foreignWire;
        do{foreignWire=foreign.PollUiWire("current-session|memberC|alien",foreignTicket);std::this_thread::yield();}
        while(foreignWire->rfind("SEARCHWAIT|",0)==0&&std::chrono::steady_clock::now()<foreignDeadline);
        Check(foreignWire->rfind("SEARCHERROR|Refresh equipped references",0)==0,"Another CAS session's usage snapshot was published.");foreign.Stop();
        Check(successful.PollUiWire("memberC/alien",goodTicket)->rfind("SEARCHERROR|",0)==0,"Closed UI worker retained a page.");
        auto invalid=query;invalid["fuzzy"]="yes";
        Check(!td1::library::Query(invalid),"Untyped fuzzy flag accepted.");
        std::promise<void> entered, release;
        auto allowed=release.get_future().share();std::atomic<unsigned> calls{0};
        td1::search::Worker worker([&](const Json&) -> Json {
            if(++calls==1){entered.set_value();allowed.wait();}
            throw std::runtime_error("Typed transport failure");
        });
        const auto first=worker.Submit("memberA/alien",query);
        Check(entered.get_future().wait_for(std::chrono::seconds(2))==std::future_status::ready,"Worker did not start.");
        Check(worker.Poll("memberA/alien",first)->value("state","")=="pending","Polling blocked behind network.");
        Check(*worker.PollUiWire("memberA/alien",first)=="SEARCHWAIT|"+std::to_string(first),"UI polling blocked or lost the ticket.");
        const auto second=worker.Submit("memberA/alien",query);
        const auto third=worker.Submit("memberB/fairy",query);
        Check(worker.Poll("memberA/alien",second)->value("state","")=="stale","Old member ticket leaked.");
        Check(worker.Poll("memberB/fairy",second)->value("state","")=="stale","Old ticket acquired new context.");
        release.set_value();
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        std::shared_ptr<const Json> result;
        do {result=worker.Poll("memberB/fairy",third);std::this_thread::yield();}
        while(result->value("state","")=="pending"&&std::chrono::steady_clock::now()<deadline);
        Check(result->value("message","")=="Typed transport failure","Latest error was not delivered.");
        Check(result->value("ticket",0ULL)==third,"Latest result lost its ticket.");
        const auto wire=worker.PollWire("memberB/fairy",third);
        Check(Json::parse(*wire)==*result,"Worker-encoded wire differs from its exact result.");
        Check(*worker.PollUiWire("memberB/fairy",third)=="SEARCHERROR|Typed transport failure","UI worker lost the bounded error.");
        Check(worker.PollWire("memberB/fairy",third)==wire,"UI poll re-encoded a ready metadata page.");
        Check(calls==2,"Typing created an unbounded request queue.");
        Check(worker.Metrics()["superseded"]==1,"Superseded read published.");
        bool refused=false;
        try {invalid=query;invalid["limit"]=25;worker.Submit("memberB/fairy",invalid);}catch(const std::exception&){refused=true;}
        Check(refused,"Large native search page was accepted.");
        worker.Stop();
        Check(worker.Poll("memberB/fairy",third)->value("state","")=="stale","Closed worker retained active page.");
        std::cout<<"Latest-only native search, nonblocking poll and member isolation passed.\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
