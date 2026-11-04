#include "ApexEquippedCategoryIndex.h"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
using td1::ui::Json;
using td1::ui::Scalar;
using td1::ui::EquippedCategoryIndex;
using Projection=std::vector<std::string>;
static volatile size_t sink=0;

Projection baseline(const Json* categories,const Json& parts,bool show) {
    Projection result;
    for (const auto& part:parts) {
        const Json* found=nullptr;
        if(categories) for(const auto& category:*categories)
            if(Scalar(category,"body_type")==Scalar(part,"body_type")){found=&category;break;}
        result.push_back(found?Scalar(*found,"group"):"Runtime discovered");
    }
    if(show && categories) for(const auto& category:*categories) {
        bool equipped=false;
        for(const auto& part:parts)
            if(Scalar(part,"body_type")==Scalar(category,"body_type"))equipped=true;
        if(!equipped)result.push_back("empty:"+Scalar(category,"label")+"/"+Scalar(category,"group"));
    }
    return result;
}
Projection indexed(const Json* categories,const Json& parts,bool show) {
    EquippedCategoryIndex index(categories,parts,show);Projection result;
    for(const auto& part:parts){const auto* group=index.Group(part);result.push_back(group?*group:"Runtime discovered");}
    if(show && categories)for(const auto& category:*categories)
        if(!index.Equipped(category))result.push_back("empty:"+Scalar(category,"label")+"/"+Scalar(category,"group"));
    return result;
}
void require(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
Json category(int n){return {{"body_type",n},{"label","label-"+std::to_string(n)},{"group","group-"+std::to_string(n%7)}};}
Json part(int n){return {{"body_type",n}};}
int main(int argc, char** argv){
  try {
    const bool benchmark=argc==2 && std::string(argv[1])=="--benchmark";
    require(argc==1 || benchmark,"only optional --benchmark is supported");
    size_t checks=0;
    Json empty=Json::array(), parts=Json::array({part(2),part(99)});
    require(baseline(nullptr,parts,true)==indexed(nullptr,parts,true),"null catalog");checks++;
    Json categories=Json::array({category(2),category(2),category(3)});
    categories[1]["group"]="second duplicate";
    require(baseline(&categories,parts,true)==indexed(&categories,parts,true),"duplicate first");checks++;
    require(indexed(&categories,parts,true)[0]=="group-2","first category selected");checks++;
    require(baseline(&categories,empty,true)==indexed(&categories,empty,true),"empty outfit");checks++;
    Json special=Json::array({Json::object(),{{"body_type","2"},{"group","string-two"},{"label","a"}},
        {{"body_type",uint64_t(18446744073709551615ull)},{"group","wide"},{"label","b"}},
        {{"body_type",nullptr},{"group","null"},{"label","c"}}});
    Json specialParts=Json::array({Json::object(),{{"body_type",2}},{{"body_type","2"}},
        {{"body_type",uint64_t(18446744073709551615ull)}},{{"body_type",nullptr}}});
    for(bool show:{false,true}){require(baseline(&special,specialParts,show)==indexed(&special,specialParts,show),"scalar variants");checks++;}
    // Each draw gets the current source; no stale group or equipped membership
    // survives a catalog or outfit replacement between draws.
    categories[0]["group"]="changed group";
    require(indexed(&categories,parts,true)[0]=="changed group","new draw reads changed category");checks++;
    parts=Json::array({part(3)});
    require(baseline(&categories,parts,true)==indexed(&categories,parts,true),"new draw reads changed outfit");checks++;
    std::mt19937 rng(1234567);
    for(int trial=0;trial<600;++trial){
      Json cats=Json::array(), pp=Json::array();int nc=rng()%100,np=rng()%80;
      for(int i=0;i<nc;++i){auto c=category(rng()%120);c["label"]=std::to_string(i);cats.push_back(c);}
      for(int i=0;i<np;++i)pp.push_back(part(rng()%120));
      for(bool show:{false,true}){require(baseline(&cats,pp,show)==indexed(&cats,pp,show),"random projection");checks++;}
    }
    if(benchmark)for(int sz:{20,100,256})for(bool show:{false,true}){
      Json cats=Json::array(),pp=Json::array();int nc=sz==20?60:(sz==100?256:1024);
      for(int i=0;i<nc;++i)cats.push_back(category(i));
      for(int i=0;i<sz;++i)pp.push_back(part((i*7)%nc));
      require(baseline(&cats,pp,show)==indexed(&cats,pp,show),"benchmark fixture");
      std::vector<double> old,newer;
      for(int i=0;i<40;++i){
        auto measure=[&](bool useNew){auto start=std::chrono::steady_clock::now();
          auto result=useNew?indexed(&cats,pp,show):baseline(&cats,pp,show);sink+=result.size();
          auto dt=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
          (useNew?newer:old).push_back(dt);};
        if(i%2){measure(true);measure(false);}else{measure(false);measure(true);}
      }
      auto median=[](std::vector<double> v){std::sort(v.begin(),v.end());return (v[19]+v[20])/2;};
      std::vector<double> delta;for(size_t i=0;i<old.size();++i)delta.push_back(newer[i]-old[i]);
      std::printf("synthetic parts=%d categories=%d showEmpty=%d old_median_us=%.3f new_median_us=%.3f paired_delta_median_us=%+.3f\n",
                  sz,nc,show?1:0,median(old),median(newer),median(delta));
    }
    std::printf("PASS %zu differential checks; synthetic host only\n",checks);return 0;
  } catch(const std::exception& e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}
}
