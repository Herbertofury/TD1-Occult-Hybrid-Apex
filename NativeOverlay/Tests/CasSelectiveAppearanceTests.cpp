#include "ApexCasSelectiveAppearance.h"
#include "ApexCasOwnerGraph.h"
#include <iostream>
#include <memory>
namespace s=td1::nativecas::selective;
namespace w=td1::nativecas::wire;
using namespace td1::nativecas::engine;
using J=td1::ui::Json;
void Check(bool x){if(!x)throw std::runtime_error("Selective form isolation regression.");}
template<class F>void Refuses(F f){bool caught=false;try{f();}catch(const std::exception&){caught=true;}Check(caught);}
std::string V(unsigned n,std::uint64_t v){return w::Var(std::uint64_t(n)<<3)+w::Var(v);}
std::string Fixed(unsigned n,std::uint64_t v){auto out=w::Var((std::uint64_t(n)<<3)|1);for(unsigned i=0;i<8;++i)out+=char(v>>(8*i));return out;}
std::string Container(std::initializer_list<std::uint64_t> values,bool fixed=false){std::string b;for(auto v:values){if(fixed)for(unsigned n=0;n<8;++n)b+=char(v>>(8*n));else b+=w::Var(v);}return w::Bytes(1,b)+V(90,777);}
std::string Outfit(unsigned seed,unsigned category,unsigned ordinal){
    return V(1,10000+category*10+ordinal)+V(2,category)+
        w::Bytes(5,Container({seed+2,seed+10,seed+39,seed+45,seed+45+500},true))+V(6,123)+
        w::Bytes(7,Container({2,10,39,45,45}))+w::Bytes(12,Container({11,22,33,44,55}))+
        w::Bytes(14,Container({101,102,103,104,105}))+w::Bytes(15,Container({0,0,0,1,2}))+V(98,seed);
}
std::string Packet(unsigned seed){
    std::string parts;for(unsigned body:{2u,10u,39u,45u})parts+=w::Bytes(1,V(1,seed+body)+V(2,body)+V(99,seed));
    const auto morph=V(1,seed)+w::Bytes(2,V(1,seed+1))+w::Bytes(3,V(1,seed+2))+V(91,seed);
    const auto genetics=w::Bytes(1,morph)+w::Bytes(2,"physique-"+std::to_string(seed))+V(4,seed%3)+
        w::Bytes(5,parts)+w::Bytes(6,parts)+V(92,seed);
    const auto outfits=w::Bytes(1,Outfit(seed,0,0))+w::Bytes(1,Outfit(seed,0,1))+w::Bytes(1,Outfit(seed,1,0))+V(93,seed);
    const auto record=V(1,2)+V(88,seed);
    return Fixed(1,123)+V(10,seed)+w::Bytes(12,"physique-"+std::to_string(seed))+w::Bytes(18,morph)+
        w::Bytes(21,outfits)+w::Bytes(28,genetics)+w::Bytes(30,w::Bytes(17,V(1,2)+w::Bytes(3,record)))+
        w::Bytes(75,V(1,45)+V(2,seed))+V(99,seed);
}
std::string F(const std::string& p,unsigned n){return w::One(w::Fields(p),n,2).value;}
int main(){try{
    const auto target=Packet(1000),source=Packet(2000);
    const auto inventory=s::EquippedInventory(target);
    Check(inventory.size()==3 && inventory[0].category==0 && inventory[1].ordinal==1 &&
        inventory[1].id==10001 && inventory[2].category==1 && inventory[2].ordinal==0 &&
        inventory[0].parts.rows[4][4]==2 && inventory[0].parts.rows[4][3]==105);
    const auto empty=s::EquippedInventory(w::Bytes(21,w::Bytes(1,V(2,0))));
    Check(empty.size()==1 && empty[0].id==0 && empty[0].parts.rows.empty());
    Refuses([&]{s::EquippedInventory(w::Bytes(21,w::Bytes(1,V(2,256))));});
    const auto equipped=s::Equipped(target,0,1);
    Check(equipped.rows.size()==5 && equipped.rows[0][0]==1002 && equipped.rows[3][1]==45 && equipped.rows[4][4]==2);
    Check(s::Equipped(target,1,0).rows.size()==5);
    Refuses([&]{s::Equipped(target,0,2);});
    Refuses([&]{s::Equipped(target,256,0);});
    Refuses([&]{s::Equipped(w::Bytes(21,w::Bytes(1,w::Bytes(5,Container({1,2},true)))),0,0);});
    Check(s::Numbers(Container({UINT64_MAX,0,256},true),true)==std::vector<std::uint64_t>({UINT64_MAX,0,256}));
    Refuses([&]{s::Numbers(w::Bytes(1,"invalid"),true);});
    const auto voice=s::Merge(target,source,128);
    const auto furTarget=target+V(62,900)+w::Bytes(63,"retained fur paint");
    const auto furSource=source+V(62,800)+w::Bytes(63,"chosen fur paint");
    const auto withoutFur=s::Merge(furTarget,furSource,s::ClearFur|16);
    Check(w::Scalar(w::One(w::Fields(withoutFur),62,0))==0 && !s::Optional(w::Fields(withoutFur),63));
    Check(w::One(w::Fields(withoutFur),10,0).raw==w::One(w::Fields(furSource),10,0).raw);
    Check(F(withoutFur,18)==F(furTarget,18) && s::Canonical(F(withoutFur,28),s::Schema::Genetics)==s::Canonical(F(furTarget,28),s::Schema::Genetics) &&
        s::Canonical(F(withoutFur,21),s::Schema::Outfits)==s::Canonical(F(furTarget,21),s::Schema::Outfits) && F(withoutFur,75)==F(furTarget,75));
    const auto withFur=s::Merge(withoutFur,furSource,s::Fur|16);
    Check(F(withFur,63)==F(furSource,63) && w::Scalar(w::One(w::Fields(withFur),62,0))==800);
    Check(F(withFur,18)==F(furTarget,18) && s::Canonical(F(withFur,28),s::Schema::Genetics)==s::Canonical(F(furTarget,28),s::Schema::Genetics));
    const auto furParts=w::Bytes(1,V(1,111)+V(2,3))+w::Bytes(1,V(1,222)+V(2,60))+w::Bytes(1,V(1,333)+V(2,59));
    Check(s::PartList(furParts,furParts,s::ClearFur)==w::Bytes(1,V(1,111)+V(2,3))+w::Bytes(1,V(1,222)+V(2,60)));
    const std::uint64_t bodyDefaults[][3]={{6,0x4c9e1,0x198c},{7,0x4c9d1,0x1990},{8,0x4c9d7,0x198f},
        {6,0x4cbc0,0x19a2},{7,0x4c9d3,0x19ae},{8,0x4c9df,0x19a3}};
    for(const auto& row:bodyDefaults) {
        Check(s::FurNudePart(row[1],row[0],s::ClearFur)==row[2]);
        Check(s::FurNudePart(row[2],row[0],s::Fur,row[1])==row[1]);
        Check(s::FurNudePart(0xabcd1234567890ULL,row[0],s::ClearFur)==0xabcd1234567890ULL);
        const auto original=w::Bytes(1,V(1,row[1])+V(2,row[0])+V(99,17))+furParts;
        const auto changed=s::PartList(original,"",s::ClearFur);
        Check(changed==w::Bytes(1,V(2,row[0])+V(99,17)+V(1,row[2]))+
            w::Bytes(1,V(1,111)+V(2,3))+w::Bytes(1,V(1,222)+V(2,60)));
        const auto nudeOutfit=w::Bytes(5,Container({row[1],777},true))+w::Bytes(7,Container({row[0],3}));
        const auto clean=s::Parts(s::Outfit(nudeOutfit,"",s::ClearFur)).rows;
        const auto clothingDefault=row[1]==0x4c9e1?0x5f69:row[1]==0x4c9d1?0x5f71:row[2];
        Check(clean.size()==2 && clean[0][0]==777 && clean[1][0]==clothingDefault);
        Check(s::Parts(s::Outfit(s::Outfit(nudeOutfit,"",s::ClearFur),nudeOutfit,s::Fur)).rows[1][0]==clothingDefault);
    }
    for(auto id:{0x5f69ULL,0x5f71ULL,0xabcd1234567890ULL})for(auto body:{6u,7u,8u}) {
        Check(s::FurOutfitPart(id,body,s::Fur)==id);
        Check(s::FurOutfitPart(id,body,s::ClearFur)==id);
    }
    Check(s::FurNudePart(0x4c9e1,3,s::ClearFur)==0x4c9e1); // Never reinterpret a chosen head by its ID alone.
    Check(F(voice,21)==F(target,21) && F(voice,18)==F(target,18));
    auto skin=s::Merge(target,source,4096);auto a=w::Fields(target),b=w::Fields(skin);
    Check(w::One(a,99,0).raw==w::One(b,99,0).raw && w::One(a,10,0).raw==w::One(b,10,0).raw);
    Check(F(target,18)==F(skin,18) && F(target,12)==F(skin,12) && F(target,75)==F(skin,75));
    auto rows=s::Parts(w::Fields(F(skin,21)).front().value).rows;
    Check(rows.size()==5 && rows[0][0]==1002 && rows[1][0]==1010 && rows[2][0]==2039 && rows[3][0]==1045);
    Check(F(F(skin,28),1)==F(F(target,28),1));
    Check(w::One(w::Fields(F(skin,28)),92,0).raw==w::One(w::Fields(F(target,28)),92,0).raw);
    const auto jewelry=s::Merge(target,source,16384);rows=s::Parts(w::Fields(F(jewelry,21)).front().value).rows;
    Check(rows[0][0]==1002 && rows[1][0]==2010 && rows[2][0]==1039);
    const auto tattoos=s::Merge(target,source,1024);rows=s::Parts(w::Fields(F(tattoos,21)).front().value).rows;
    Check(rows.size()==5 && rows[3][0]==2045 && rows[4][0]==2545 && rows[3][4]==1 && rows[4][4]==2);
    Check(F(tattoos,75)==F(source,75));
    auto body=s::Merge(target,source,2);Check(F(body,12)==F(source,12));
    Check(w::One(w::Fields(F(body,18)),1,0).raw==w::One(w::Fields(F(target,18)),1,0).raw);
    Check(w::One(w::Fields(F(body,18)),3,2).raw==w::One(w::Fields(F(source,18)),3,2).raw);
    auto face=s::Merge(target,source,8);Check(w::One(w::Fields(F(face,18)),1,0).raw==w::One(w::Fields(F(source,18)),1,0).raw);
    Check(w::One(w::Fields(F(face,18)),3,2).raw==w::One(w::Fields(F(target,18)),3,2).raw);
    Refuses([&]{s::Merge(target,source,1);});
    auto foreign=source;foreign.replace(1,8,std::string(8,'x'));Refuses([&]{s::Merge(target,foreign,32);});
    Check(s::Equivalent(target,target) && !s::Equivalent(target,skin));
    Check(s::DifferenceFields(target,skin)=="21,28");
    Check(s::DifferenceFields(target,target).empty());
    Check(s::OutfitDifference(target,target).empty());
    const auto changedId=s::SwapFields(Outfit(1000,0,0),V(1,99999),{1});
    Check(s::OutfitDifference(w::Bytes(21,w::Bytes(1,Outfit(1000,0,0))),
        w::Bytes(21,w::Bytes(1,changedId)))=="0.1(10000/99999)");
    Check(s::OutfitDifference(w::Bytes(21,""),target)=="outfit-count:0/3");
    // The actual importer may repack fixed64 CASP IDs. All values, ordering
    // and unknown metadata must still match; a wire-layout difference alone
    // cannot reject a correct detached copy.
    const auto packedIds=Container({7,UINT64_MAX,2000000000000ULL},true);
    const auto unpackedIds=Fixed(1,7)+Fixed(1,UINT64_MAX)+Fixed(1,2000000000000ULL)+V(90,777);
    const auto mixedIds=Fixed(1,7)+w::Bytes(1,std::string(8,char(255)))+Fixed(1,2000000000000ULL)+V(90,777);
    const auto withIds=[&](const std::string& ids){return w::Bytes(21,w::Bytes(1,
        s::SwapFields(Outfit(1000,0,0),w::Bytes(5,ids),{5})));};
    Check(s::Equivalent(withIds(packedIds),withIds(unpackedIds)));
    Check(s::Equivalent(withIds(packedIds),withIds(mixedIds)));
    Check(!s::Equivalent(withIds(packedIds),withIds(Container({8,UINT64_MAX,2000000000000ULL},true))));
    Check(!s::Equivalent(withIds(packedIds),withIds(Container({UINT64_MAX,7,2000000000000ULL},true))));
    Check(!s::Equivalent(withIds(packedIds),withIds(unpackedIds+V(91,1))));
    Refuses([&]{s::Canonical(w::Bytes(1,"misaligned"),s::Schema::FixedArray);});
    Check(s::Canonical(V(1,5)+V(1,130)+V(90,777),s::Schema::Array)==
        s::Canonical(Container({5,130}),s::Schema::Array));
    const auto furPacket=target+V(62,1234)+w::Bytes(63,
        w::Bytes(1,V(1,9001)+V(2,0xff887766))+w::Bytes(1,V(1,9002)+V(2,0)));
    const auto material=s::ReadFurMaterial(furPacket);std::vector<std::string> applied;
    Check(material.texture==1234 && material.layers.size()==2 && material.layers[0].second==0xff887766);
    s::ApplyFurMaterial(material,[&]{applied.push_back("clear");},
        [&](auto id,auto color){applied.push_back(std::to_string(id)+":"+std::to_string(color));},
        [&](auto texture){applied.push_back("texture:"+std::to_string(texture));});
    Check(applied.size()==4 && applied.front()=="clear" && applied.back()=="texture:1234");
    Check(s::ReadFurMaterial(withoutFur).layers.empty());
    Refuses([&]{s::ReadFurMaterial(target+w::Bytes(63,w::Bytes(2,"future")));});
    Refuses([&]{s::ReadFurMaterial(target+w::Bytes(63,w::Bytes(1,V(1,1)+V(1,2))));});
    Refuses([&]{s::ReadFurMaterial(target+w::Bytes(63,w::Bytes(1,V(2,UINT64_MAX))));});
    // A fur-only removal leaves outfits without a fur part byte-identical,
    // including unsorted parallel arrays and optional empty containers.
    const auto noFurOutfit=s::SwapFields(Outfit(1000,0,0),w::Bytes(15,""),{15});
    Check(s::Outfit(noFurOutfit,Outfit(2000,0,0),s::ClearFur)==noFurOutfit);
    // Selective linking does not relay Human edits from an Alien operation
    // into the separately configured Human/Vampire edge, nor another Sim.
    using D=std::unique_ptr<J>;std::map<unsigned,D> captured;
    for(unsigned k:{1u,2u,4u})captured[k]=std::make_unique<J>(J{{"skin",k},{"hair",k+100},{"opaque",k+200}});
    OwnerGraph<D> graph(123,7,2,captured,
        [](const D& a,unsigned){return std::make_unique<J>(*a);},
        [](const D& to,const D& from,unsigned,unsigned flags){auto p=std::make_unique<J>(*to);if(flags&4096)(*p)["skin"]=(*from)["skin"];return p;});
    graph.linkPairSelected(graph.cursor(),"native/1","native/2",true,4096);
    graph.linkPairSelected(graph.cursor(),"native/1","native/4",true,4096);
    D edit=std::make_unique<J>(*graph.appearance(2));(*edit)["skin"]=900;(*edit)["hair"]=901;
    graph.commit(graph.cursor(),edit);
    Check((*graph.appearance(1))["skin"]==900 && (*graph.appearance(1))["hair"]==101 && (*graph.appearance(4))["skin"]==4);
    graph.linkPairSelected(graph.cursor(),"native/1","native/2",false,4096);(*edit)["skin"]=999;graph.commit(graph.cursor(),edit);
    Check((*graph.appearance(1))["skin"]==900 && graph.linkScope("native/1","native/2")==4096);
    graph.copySelected(graph.cursor(),"native/2","native/4",4096);
    Check((*graph.appearance(4))["skin"]==999 && (*graph.appearance(4))["hair"]==104 && (*graph.appearance(1))["skin"]==900);
    std::cout<<"Selective category copies, metadata, layered tattoos, scoped links and unlink isolation passed.\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
