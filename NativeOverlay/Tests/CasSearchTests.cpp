#include "ApexCasSearchWin.h"
#include <future>
#include <iostream>
#include <fstream>
#include <filesystem>

using td1::ui::Json;
void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char** argv) {
    try {
        if(argc==3) {
            std::ifstream input(std::filesystem::u8path(argv[1]));Json query;input>>query;
            td1::search::Worker worker(td1::search::FetchMetadata);
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
