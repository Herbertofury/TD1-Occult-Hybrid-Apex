#include "ApexCasSelectiveAppearance.h"
#include "ApexResourceImage.h"
#include <chrono>
#include <thread>
#include <iostream>
extern "C" {
std::uint64_t ApexAppearanceSubmit(const char*,const unsigned char*,std::size_t);
char* ApexAppearancePoll(const char*,std::uint64_t);
void ApexCatalogFree(char*);
}
namespace s=td1::nativecas::selective;
namespace w=td1::nativecas::wire;
using td1::ui::Json;
void Check(bool v){if(!v)throw std::runtime_error("Rust appearance worker regression.");}
std::string Var(unsigned n,std::uint64_t v){return w::Var(std::uint64_t(n)<<3)+w::Var(v);}
std::string Fixed(unsigned n,std::uint64_t v){auto b=w::Var((std::uint64_t(n)<<3)|1);for(unsigned i=0;i<8;++i)b+=char(v>>(8*i));return b;}
Json Poll(const std::string& context,std::uint64_t ticket){
    char* raw=ApexAppearancePoll(context.c_str(),ticket);Check(raw!=nullptr);
    Json result;try{result=Json::parse(raw);}catch(...){ApexCatalogFree(raw);throw;}ApexCatalogFree(raw);return result;
}
Json Wait(const std::string& context,std::uint64_t ticket){
    Check(ticket!=0);const auto end=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    for(;;){auto r=Poll(context,ticket);if(r.value("state",std::string())!="pending")return r;
        Check(std::chrono::steady_clock::now()<end);std::this_thread::sleep_for(std::chrono::milliseconds(1));}
}
std::uint64_t Submit(const std::string& context,const std::string& bytes){
    return ApexAppearanceSubmit(context.c_str(),reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size());
}
std::string Packet(unsigned seed,bool packed){
    std::string ids,types,layers;
    for(auto v:{0ull,127ull,128ull,UINT64_MAX}) {
        if(packed){for(unsigned n=0;n<8;++n)ids+=char(v>>(8*n));types+=w::Var(v);}
        else {ids+=Fixed(1,v);types+=Var(1,v);}
    }
    if(packed){ids=w::Bytes(1,ids);types=w::Bytes(1,types);}
    ids+=Var(90,seed);types+=w::Bytes(91,"unknown-array");
    const auto outfit=Var(98,seed)+w::Bytes(15,types)+w::Bytes(5,ids)+w::Bytes(7,types)+w::Bytes(12,types)+w::Bytes(14,types);
    const auto part=Var(99,seed)+Var(2,45)+Fixed(1,UINT64_MAX);
    const auto genetics=w::Bytes(6,w::Bytes(1,part))+w::Bytes(1,Var(91,seed)+Var(3,seed+1))+w::Bytes(5,w::Bytes(1,part));
    return Var(999,seed)+w::Bytes(76,"unknown-appearance-bytes")+w::Bytes(28,genetics)+
        w::Bytes(21,w::Bytes(1,outfit)+w::Bytes(1,outfit)+Var(97,seed))+
        w::Bytes(18,Var(94,seed)+w::Bytes(3,"opaque-morph"))+Var(62,UINT64_MAX)+Var(9,seed);
}
int main(){try{
    double submitMax=0,computeMax=0;
    for(unsigned seed=0;seed<32;++seed)for(bool packed:{false,true}){
        auto bytes=Packet(seed,packed);const auto expected=td1::resource::HashBytes(s::Canonical(bytes,s::Schema::Root));
        const auto started=std::chrono::steady_clock::now();const auto ticket=Submit("oracle",bytes);
        submitMax=std::max(submitMax,std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count());
        const auto result=Wait("oracle",ticket);Check(result["state"]=="ready"&&result["sha256"]==expected);
        Check(result["worker_threads"].get<unsigned>()>=1&&result["worker_threads"].get<unsigned>()<=2);
        computeMax=std::max(computeMax,result["compute_ms"].get<double>());
        Check(Poll("foreign-context",ticket)["state"]=="stale");
    }
    auto bad=Wait("malformed",Submit("malformed",std::string(11,char(0xff))));Check(bad["state"]=="failed");
    const auto first=Submit("replace",Packet(1,true));Wait("replace",first);
    const auto second=Submit("replace",Packet(2,false));Check(Poll("replace",first)["state"]=="stale");Check(Wait("replace",second)["state"]=="ready");
    std::string large=w::Bytes(9,std::string(4*1024*1024,'x'));
    const auto before=std::chrono::steady_clock::now();const auto ticket=Submit("large",large);
    const auto submitMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-before).count();
    auto result=Wait("large",ticket);
    const auto legacyStarted=std::chrono::steady_clock::now();
    const auto legacyHash=td1::resource::HashBytes(s::Canonical(large,s::Schema::Root));
    const auto legacyMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-legacyStarted).count();
    Check(result["sha256"]==legacyHash);
    Check(Submit("oversize",std::string(w::Limit+1,'x'))==0);
    std::cout<<"64 differential packets, malformed/stale/replaced/oversize tests passed; max small submit ms="<<submitMax
        <<", max small worker ms="<<computeMax<<", 4MiB submit ms="<<submitMs<<", worker ms="<<result["compute_ms"]
        <<", prior synchronous canonical+SHA ms="<<legacyMs<<"\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
