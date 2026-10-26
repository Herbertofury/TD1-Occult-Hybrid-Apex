#include <windows.h>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include <iostream>
static void Span(const void* p,std::size_t size) {
    if(!p || !size)throw std::runtime_error("bad fixture span");
}
template<class T> static T Read(const void* p,std::size_t offset=0) {
    Span(p,sizeof(T));T result;std::memcpy(&result,static_cast<const char*>(p)+offset,sizeof(T));return result;
}
static bool OriginalPeltGenus(const void* p) {return Read<std::uint32_t>(p,8)==32;}
struct FixtureRuntime {struct {bool(*peltGenus)(const void*)=OriginalPeltGenus;} api;};
static FixtureRuntime& Runtime() {static FixtureRuntime value;return value;}
#include "../Source/ApexCasHumanCCMaterialWin.h"
static void Require(bool b,const char* message) {if(!b)throw std::runtime_error(message);}
template<class T> static void Put(void* p,std::size_t offset,T value) {std::memcpy(static_cast<char*>(p)+offset,&value,sizeof(T));}
int main() {
    try {
        std::vector<char> model(0x530),renderer(0x140),assembly(0x160),otherAssembly(0x220),pelt(24);
        Put(model.data(),0x520,static_cast<const void*>(renderer.data()));
        Put(renderer.data(),0x10,static_cast<const void*>(assembly.data()));
        Put(renderer.data(),0x18,static_cast<const void*>(otherAssembly.data()));
        Put(renderer.data(),0xc0,reinterpret_cast<std::uintptr_t>(pelt.data()));
        Put(renderer.data(),0xc8,reinterpret_cast<std::uintptr_t>(pelt.data()+24));
        auto* genus=assembly.data()+0x120;
        const std::array<std::uint32_t,5> human{{0x1020,0x1000,1,127,1}};
        std::memcpy(genus,human.data(),20);std::array<std::uint32_t,5> temporary=human;
        BindHumanCCMaterial(model.data(),"werewolf/werewolf_human_cc");
        Require(PeltGenus(genus),"Exact Human/CC pelt did not enable the pelt shader");
        Require(ComposeHumanCCPelt(temporary.data(),genus),"Temporary composition did not use the wolf pelt path");
        Require(temporary[2]==32,"Temporary material genus differs");
        Require(Read<std::uint32_t>(genus,8)==1 && std::memcmp(genus,human.data(),20)==0,"Stored Human geometry changed");
        temporary[2]=1;Require(std::memcmp(temporary.data(),human.data(),20)==0,"Unrelated temporary genus fields changed");
        Require(!ComposeHumanCCPelt(genus,genus),"An aliased retained genus was modified");
        temporary=human;temporary[0]^=1;
        Require(!ComposeHumanCCPelt(temporary.data(),genus),"A mismatched temporary was changed");
        Require(temporary[2]==1,"Mismatched temporary material kind changed");
        temporary=human;Require(!PeltGenus(temporary.data()),"Another Sim's matching genus acquired fur");
        Put(renderer.data(),0xc8,reinterpret_cast<std::uintptr_t>(pelt.data()));
        Require(!PeltGenus(genus),"Empty pelt replaced Human skin");
        Put(renderer.data(),0xc8,reinterpret_cast<std::uintptr_t>(pelt.data()+24));
        for(const auto* other:{"native/1","native/32","native/64","fairy/primary"}) {
            BindHumanCCMaterial(model.data(),other);
            Require(!PeltGenus(genus),"Foreign form acquired the Human/CC texture policy");
        }
        BindHumanCCMaterial(model.data(),"werewolf/werewolf_human_cc");ClearHumanCCMaterial();
        Require(!PeltGenus(genus),"Retired context acquired fur");
        Put(renderer.data(),0x10,static_cast<const void*>(nullptr));
        BindHumanCCMaterial(model.data(),"werewolf/werewolf_human_cc");
        Require(!PeltGenus(genus),"A secondary assembly was mistaken for the texture genus");
        std::cout<<"Human/CC material routing: temporary-only, alias refusal, empty/foreign/retired isolation passed\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
