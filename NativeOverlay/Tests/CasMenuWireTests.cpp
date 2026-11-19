#include "../Source/ApexCasMenuWire.h"
#include <functional>
using namespace td1::nativecas::menu;
inline void Check(bool value){if(!value)throw std::runtime_error("Prepared CAS menu regression failed.");}
int main() {
    const std::map<std::string,Owner> owners={{"native/1",{1,536870913}},{"active/1",{1,536870914}},
        {"native/4",{4,536870915}},{"ghost/ghost_ghost",{1,536870916}}};
    const std::map<std::uint32_t,std::string> logical={{1,"native/1"},{4,"native/4"}};
    const std::string human="native/1,1,536870913,human/shared,Human,human,,,Shared%20Human,Human";
    const std::string vampire="native/4,4,536870915,vampire/dark,Vampire,vampire,,,Dark%20form,Vampire";
    const std::string ghost="ghost/ghost_ghost,1,536870916,ghost/ghost_ghost,Ghost,ghost,,,Ghost%20appearance,Ghost";
    auto make=[&](const std::string& a,const std::string& b,const std::string& c){return std::vector<std::string>{"OWNERS|0|3|"+a+";"+b+";"+c};};
    const auto good=make(human,vampire,ghost);Check(Validate(good,owners,logical,"native/1").count==3);
    auto reject=[&](std::vector<std::string> pages){bool failed=false;try{Validate(pages,owners,logical,"native/1");}catch(const std::exception&){failed=true;}Check(failed);};
    reject(make(human,vampire,vampire));reject(make(ghost,vampire,ghost));
    reject(make(human,"native/4,1,536870915,vampire/dark,Vampire,vampire,,,Dark,Vampire",ghost));
    reject(make(human,"native/4,4,536870916,vampire/dark,Vampire,vampire,,,Dark,Vampire",ghost));
    reject(make(human,vampire,"active/1,1,536870914,human/shared,Human,human,,,Human,Human"));
    reject(make(human,vampire,"ghost/ghost_ghost,1,536870916,human/shared,Human,human,,,Ghost,Ghost"));
    reject({"OWNERS|1|3|"+human+";"+vampire+";"+ghost});reject({"OWNERS|0|4|"+human+";"+vampire+";"+ghost});
    reject({"OWNERS|0|3|"+human+";"+vampire+";"+ghost+"\n"});
    const auto pages=std::vector<std::string>{"OWNERS|0|3|"+human,"OWNERS|1|3|"+vampire+";"+ghost};
    Check(Validate(pages,owners,logical,"native/1").pages==pages);
    reject({pages[1],pages[0]});reject({pages[0],pages[0]});
}
