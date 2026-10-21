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
    Check(s::Numbers(Container({UINT64_MAX,0,256},true),true)==std::vector<std::uint64_t>({UINT64_MAX,0,256}));
    Refuses([&]{s::Numbers(w::Bytes(1,"invalid"),true);});
    const auto voice=s::Merge(target,source,128);
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
