#include "ApexCasOwnerGraph.h"
#include <iostream>
#include <memory>
using namespace td1::nativecas::engine;
using Json=td1::ui::Json;
using Data=std::unique_ptr<Json>;
using Graph=OwnerGraph<Data>;
void Require(bool value) {if(!value) throw std::runtime_error("Separate form ownership regression.");}
template<class F> void Refuses(F call) {bool failed=false;try {call();}catch(const std::exception&) {failed=true;}Require(failed);}
Data Clone(const Data& source,unsigned target) {
    auto result=std::make_unique<Json>(*source);(*result)["kind"]=target;return result;
}
std::map<unsigned,Data> Captured(std::uint64_t sim) {
    std::map<unsigned,Data> result;
    for(unsigned kind=1;kind<=64;kind*=2) {
        Json data={{"sim",std::to_string(sim)},{"kind",kind},{"skin",kind+100},
            {"tattoos",Json::array({kind,kind+1})},{"skin_details",Json::array({kind+500})},
            {"jewelry",Json::array({kind+900})},{"presets",Json::array({kind+1300})},
            {"slider",{{"18446744073709551600",0.15*kind}}},
            {"outfits",{{"everyday_1",{{"hair",kind+2000},{"swatch",kind+3000}}},
                        {"everyday_2",{{"hair",kind+4000},{"swatch",kind+5000}}}}},
            {"future_unrecognized_field",{{"opaque",Json::array({0,255,kind})}}}};
        result.emplace(kind,std::make_unique<Json>(std::move(data)));
    }
    return result;
}
int main() {
 try {
    std::map<std::uint64_t,std::unique_ptr<Graph>> household;
    for(std::uint64_t sim=101;sim<=105;++sim) {
        auto seed=Captured(sim);auto graph=std::make_unique<Graph>(sim,127,2,seed,Clone);
        // Entry owners, different forms and different Sims never share data.
        for(unsigned kind=1;kind<=64;kind*=2) {
            Require(graph->appearance(kind).get()!=seed.at(kind).get());
            for(unsigned other=1;other<kind;other*=2)
                Require(graph->appearance(kind).get()!=graph->appearance(other).get());
        }
        (*seed.at(2))["skin"]=0;Require((*graph->appearance(2))["skin"]==102);
        household.emplace(sim,std::move(graph));
    }
    std::map<std::uint64_t,std::map<unsigned,Json>> expected;
    for(auto& member:household) for(unsigned kind=1;kind<=64;kind*=2)
        expected[member.first].emplace(kind,*member.second->appearance(kind));
    // Edit every captured field of every owner of every household member.
    for(auto& member:household) {
        auto& graph=*member.second;
        for(unsigned kind=1;kind<=64;kind*=2) {
            const auto before=graph.cursor();const auto old=*graph.appearance(kind);
            const auto selected=graph.select(before,kind);
            Require(*graph.appearance(kind)==old && graph.revision(kind)==0);
            auto edit=Clone(graph.appearance(kind),kind);
            (*edit)["skin"]=kind+7000;(*edit)["tattoos"].push_back(member.first);
            (*edit)["skin_details"].push_back(member.first+1);(*edit)["jewelry"].push_back(member.first+2);
            (*edit)["presets"].push_back(member.first+3);
            (*edit)["slider"]["18446744073709551600"]=0.42;
            (*edit)["outfits"]["everyday_1"]["hair"]=kind+8000;
            (*edit)["future_unrecognized_field"]["added_by_future_patch"]=Json::array({1,7,99,255});
            expected[member.first][kind]=*edit;
            const auto committed=graph.commit(selected,edit);
            Refuses([&]{graph.commit(selected,edit);}); // No stale-owner or repeated mutation.
            Require(graph.revision(kind)==1 && committed.kind==kind);
            for(const auto& other:household) for(unsigned otherKind=1;otherKind<=64;otherKind*=2)
                Require(*other.second->appearance(otherKind)==expected.at(other.first).at(otherKind));
        }
    }
    // Real owner-selection regression: Alien -> Vampire -> Alien -> Human,
    // repeated across every member, without merging or altering any owner.
    for(auto& member:household) for(unsigned round=0;round<20;++round) {
        auto& graph=*member.second;
        for(const auto kind:{2u,4u,2u,1u,64u,32u,8u,16u}) {
            graph.select(graph.cursor(),kind);
            Require(*graph.appearance(kind)==expected.at(member.first).at(kind));
        }
    }
    auto& graph=*household.at(101);auto cursor=graph.select(graph.cursor(),2);
    Refuses([&]{graph.commit(household.at(102)->cursor(),graph.appearance(2));});
    Refuses([&]{graph.select(cursor,128);});Refuses([&]{graph.select(cursor,3);});
    Refuses([&]{graph.link(cursor,2,4,true);});
    const auto originalHuman=*graph.appearance(1),originalAlien=*graph.appearance(2),originalVampire=*graph.appearance(4);
    cursor=graph.link(cursor,1,4,true);
    Require(*graph.appearance(1)==originalHuman && *graph.appearance(4)==originalVampire);
    cursor=graph.copy(cursor,2,4); // Explicit cross-kind copy retags the destination.
    auto copied=originalAlien;copied["kind"]=4;
    Require(*graph.appearance(4)==copied && *graph.appearance(2)==originalAlien && *graph.appearance(1)==originalHuman);
    cursor=graph.select(cursor,1);auto human=Clone(graph.appearance(1),1);(*human)["skin"]=12345;
    cursor=graph.commit(cursor,human);
    Require((*graph.appearance(4))["skin"]==12345 && (*graph.appearance(4))["kind"]==4);
    Require(*graph.appearance(2)==originalAlien); // Unlinked Alien is untouched.
    cursor=graph.link(cursor,1,4,false);(*human)["skin"]=777;cursor=graph.commit(cursor,human);
    Require((*graph.appearance(4))["skin"]==12345 && (*graph.appearance(1))["skin"]==777);
    // A native deep-copy allocation failure must not partially replace forms.
    auto seed=Captured(999);bool fail=false;
    Graph atomic(999,127,1,seed,[&](const Data& data,unsigned kind) {
        if(fail && kind==4) throw std::bad_alloc();return Clone(data,kind);
    });
    auto ac=atomic.link(atomic.cursor(),1,4,true);auto oldHuman=*atomic.appearance(1),oldVampire=*atomic.appearance(4);
    auto changed=Clone(atomic.appearance(1),1);(*changed)["skin"]=99999;fail=true;
    Refuses([&]{atomic.commit(ac,changed);});
    Require(*atomic.appearance(1)==oldHuman && *atomic.appearance(4)==oldVampire && atomic.cursor().generation==ac.generation);
    std::cout<<"Five Sims, seven separate form owners, every fixture field, explicit copy/link and atomic edits passed\n";
    return 0;
 } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
