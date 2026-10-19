#include "ApexCasOwnerGraph.h"
#include "ApexCasFormPair.h"
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
    // One Human, actual non-Vampire identities, and EA's Alien orientation.
    FormPair pair=SelectFormPair("native/1","native/2",2,{});
    Require(pair.base=="native/2" && pair.alternate=="native/1" && pair.layer==0);
    pair=SelectFormPair("native/1","native/1",1,pair);
    Require(pair.base=="native/2" && pair.alternate=="native/1" && pair.layer==1);
    pair=SelectFormPair("native/1","native/4",4,pair);
    Require(pair.base=="native/1" && pair.alternate=="native/4" && pair.layer==1);
    for(const auto* special:{"ghost/manifested","servo/robot","imaginary_friend/pegacorn"}) {
        pair=SelectFormPair("native/1",special,1,pair);
        Require(pair.base=="native/1" && pair.alternate==special && pair.layer==1);
        pair=SelectFormPair("native/1","native/1",1,pair);
        Require(pair.base=="native/1" && pair.alternate==special && pair.layer==0);
    }
    pair=SelectFormPair("native/1","native/2",2,pair);
    Require(pair.base=="native/2" && pair.alternate=="native/1" && pair.layer==0);
    pair=SelectFormPair("active/1","active/1",1,{});
    Require(pair.base=="active/1" && pair.alternate=="active/1" && pair.layer==0);
    Refuses([&]{SelectFormPair("bad","native/1",1,{});});
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
    Refuses([&]{graph.link(cursor,2,2,true);});
    const auto originalHuman=*graph.appearance(1),originalAlien=*graph.appearance(2),originalVampire=*graph.appearance(4);
    cursor=graph.link(cursor,1,4,true);
    Require(graph.linkedTargets("native/1")==std::set<std::string>{"native/4"});
    Require(graph.linkedTargets("native/4").empty()); // Links stay directed.
    Refuses([&]{graph.linkedTargets("native/128");});
    Require(*graph.appearance(1)==originalHuman && *graph.appearance(4)==originalVampire);
    cursor=graph.copy(cursor,2,4); // Explicit cross-kind copy retags the destination.
    auto copied=originalAlien;copied["kind"]=4;
    Require(*graph.appearance(4)==copied && *graph.appearance(2)==originalAlien && *graph.appearance(1)==originalHuman);
    cursor=graph.select(cursor,1);auto human=Clone(graph.appearance(1),1);(*human)["skin"]=12345;
    cursor=graph.commit(cursor,human);
    Require((*graph.appearance(4))["skin"]==12345 && (*graph.appearance(4))["kind"]==4);
    Require(*graph.appearance(2)==originalAlien); // Unlinked Alien is untouched.
    cursor=graph.link(cursor,1,4,false);(*human)["skin"]=777;cursor=graph.commit(cursor,human);
    Require(graph.linkedTargets("native/1").empty());
    Require((*graph.appearance(4))["skin"]==12345 && (*graph.appearance(1))["skin"]==777);
    // Links describe explicit edit scopes, not a transitive appearance merge.
    cursor=graph.link(cursor,2,1,true);
    cursor=graph.link(cursor,1,4,true);
    cursor=graph.select(cursor,2);
    const auto vampireBeforeIndirect=*graph.appearance(4);
    auto alien=Clone(graph.appearance(2),2);(*alien)["skin"]=24680;
    cursor=graph.commit(cursor,alien);
    Require((*graph.appearance(1))["skin"]==24680 && *graph.appearance(4)==vampireBeforeIndirect);
    cursor=graph.link(cursor,2,1,false);
    (*alien)["skin"]=24681;cursor=graph.commit(cursor,alien);
    Require((*graph.appearance(1))["skin"]==24680 && (*graph.appearance(2))["skin"]==24681);
    // Editing Human itself still honors the explicitly selected Human/Vampire link.
    cursor=graph.select(cursor,1);
    auto humanDirect=Clone(graph.appearance(1),1);(*humanDirect)["skin"]=35790;
    cursor=graph.commit(cursor,humanDirect);
    Require((*graph.appearance(4))["skin"]==35790 && (*graph.appearance(2))["skin"]==24681);
    cursor=graph.link(cursor,1,4,false);
    // A pre-entry complete import replaces one exact owner without selecting
    // it, copying the active owner or changing any other canonical appearance.
    auto replacement=Clone(graph.appearance(2),4);(*replacement)["pelt"]="independent source pelt";
    const auto sourceCursor=graph.cursor();const auto untouchedAlien=*graph.appearance(2);
    const auto replaced=graph.replace(sourceCursor,"native/4",replacement);
    Require(replaced.owner==sourceCursor.owner && (*graph.appearance(4))["pelt"]=="independent source pelt");
    Require(*graph.appearance(2)==untouchedAlien);
    Refuses([&]{graph.replace(sourceCursor,"native/4",replacement);});
    Refuses([&]{graph.replace(replaced,"native/128",replacement);});
    // Every family and alternate has its OWN ID, even if EA renders many
    // of them with kind Human (1) or uses kind Fairy (64) for both variants.
    auto everySeed=Captured(700);
    Graph every(700,127,1,everySeed,Clone);
    const std::vector<std::pair<std::string,unsigned>> allForms={
        {"human/primary",1},{"alien/alien",2},{"alien/disguise",1},
        {"vampire/base",1},{"vampire/dark",4},{"mermaid/human",1},{"mermaid/mermaid",8},
        {"spellcaster/primary",16},{"spellcaster/human",1},{"werewolf/beast",32},
        {"werewolf/human",1},{"werewolf/human_cc",32},{"fairy/primary",64},{"fairy/alternate",64},
        {"plantsim/plant",1},{"plantsim/human",1},{"servo/robot",1},{"servo/human_cc",1},
        {"ghost/ghost",1},{"ghost/living",1},{"reaper/reaper",1},{"reaper/unrobed",1},
        {"skeleton/skeleton",1},{"skeleton/human_cc",1},{"scarecrow/scarecrow",1},{"scarecrow/human_cc",1},
        {"imaginary_friend/lil_monster",1},{"imaginary_friend/pegacorn",1},
        {"imaginary_friend/spooky_kid",1},{"imaginary_friend/wild_child",1},{"imaginary_friend/real",1},
        {"future_mod/custom_alternate",1}};
    for(const auto& slot:allForms) every.capture(every.cursor(),slot.first,slot.second,everySeed.at(slot.second));
    std::map<std::string,Json> expectedEvery;
    for(const auto& owner:every.owners()) expectedEvery.emplace(owner.id,*every.appearance(owner.id));
    for(const auto& slot:allForms) {
        const auto ec=every.select(every.cursor(),slot.first);
        auto edit=Clone(every.appearance(slot.first),slot.second);
        (*edit)["skin_details"]=Json::array({slot.first});(*edit)["tattoos"]=Json::array({slot.first});
        (*edit)["future_unrecognized_field"]["owner"]=slot.first;
        (*edit)["outfits"]["everyday_2"]["hair"]=slot.first;
        expectedEvery[slot.first]=*edit;every.commit(ec,edit);
        for(const auto& row:expectedEvery) Require(*every.appearance(row.first)==row.second);
    }
    for(unsigned round=0;round<25;++round) for(const auto& slot:allForms) {
        const auto ec=every.select(every.cursor(),slot.first);
        Require(ec.owner==slot.first && ec.kind==slot.second && *every.appearance(slot.first)==expectedEvery.at(slot.first));
    }
    auto ec=every.select(every.cursor(),"plantsim/plant");auto forged=ec;forged.owner="skeleton/skeleton";
    Refuses([&]{every.commit(forged,every.appearance("plantsim/plant"));}); // Both render as Human; still different owners.
    for(const auto& bad:{"ghost", "Ghost/primary", "../human", "human/../plant", "human/", "/human"})
        Refuses([&]{every.capture(ec,bad,1,everySeed.at(1));});
    Refuses([&]{every.capture(ec,"fairy/alternate",64,everySeed.at(64));});
    // Explicit linking/copying is allowed between ANY two forms, including
    // unrelated specials; selection alone never creates a link.
    ec=every.link(ec,"plantsim/plant","imaginary_friend/real",true);
    auto plant=Clone(every.appearance("plantsim/plant"),1);(*plant)["skin"]=314159;
    ec=every.commit(ec,plant);
    Require((*every.appearance("imaginary_friend/real"))["skin"]==314159);
    Require(*every.appearance("ghost/ghost")==expectedEvery.at("ghost/ghost"));
    ec=every.link(ec,"plantsim/plant","imaginary_friend/real",false);
    ec=every.copy(ec,"fairy/alternate","servo/robot");
    auto servoExpected=expectedEvery.at("fairy/alternate");servoExpected["kind"]=1;
    Require(*every.appearance("servo/robot")==servoExpected);
    Require(*every.appearance("fairy/primary")==expectedEvery.at("fairy/primary"));
    // A native deep-copy allocation failure must not partially replace forms.
    auto seed=Captured(999);bool fail=false;
    Graph atomic(999,127,1,seed,[&](const Data& data,unsigned kind) {
        if(fail && kind==4) throw std::bad_alloc();return Clone(data,kind);
    });
    auto ac=atomic.link(atomic.cursor(),1,4,true);auto oldHuman=*atomic.appearance(1),oldVampire=*atomic.appearance(4);
    auto changed=Clone(atomic.appearance(1),1);(*changed)["skin"]=99999;fail=true;
    Refuses([&]{atomic.commit(ac,changed);});
    Require(*atomic.appearance(1)==oldHuman && *atomic.appearance(4)==oldVampire && atomic.cursor().generation==ac.generation);
    Graph paired(999,127,1,Captured(999),Clone);
    const auto untouchedHuman=*paired.appearance(1),pairedAlienBeforeLink=*paired.appearance(2),untouchedVampire=*paired.appearance(4);
    auto pc=paired.linkPair(paired.cursor(),"native/1","native/2",true);
    Require(paired.linked("native/1","native/2")&&paired.linked("native/2","native/1"));
    Require(*paired.appearance(1)==untouchedHuman&&*paired.appearance(2)==pairedAlienBeforeLink);
    Refuses([&]{paired.linkPair(pc,"native/1","ghost/absent",true);});
    Require(paired.cursor().generation==pc.generation&&!paired.linked("native/1","native/4"));
    auto alienEdit=Clone(paired.appearance(2),2);(*alienEdit)["skin"]=7654321;
    pc=paired.select(pc,2);pc=paired.commit(pc,alienEdit);
    Require((*paired.appearance(1))["skin"]==7654321&&*paired.appearance(4)==untouchedVampire);
    pc=paired.linkPair(pc,"native/1","native/2",false);
    Require(!paired.linked("native/1","native/2")&&!paired.linked("native/2","native/1"));
    auto isolated=Clone(paired.appearance(2),2);(*isolated)["skin"]=1234567;pc=paired.commit(pc,isolated);
    Require((*paired.appearance(1))["skin"]==7654321&&(*paired.appearance(2))["skin"]==1234567);
    std::cout<<"Five Sims, seven separate form owners, every fixture field, explicit copy/link and atomic edits passed\n";
    return 0;
 } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
