#include "ApexNativeCasProbe.h"
#include <iostream>
#include <functional>
using namespace td1::nativecas;
void Require(bool value) {if(!value) throw std::runtime_error("Native CAS probe regression.");}
void Refuses(const std::function<void()>& action) {bool caught=false;try{action();}catch(const std::runtime_error&){caught=true;}Require(caught);}
int main() {
 try {
    std::string code(80,'\x90');
    auto lea=[&](unsigned at,unsigned rex,unsigned modrm,int target) {
        code[at]=static_cast<char>(rex);code[at+1]='\x8d';code[at+2]=static_cast<char>(modrm);
        const std::int32_t displacement=target-(0x1000+at+7);std::memcpy(code.data()+at+3,&displacement,4);
    };
    lea(4,0x48,0x0d,0x2000);lea(30,0x4c,0x3d,0x2000);lea(60,0x48,0x15,0x0900);
    Require(RipLeas(code,0x1000,0x4000,0x2000)==std::vector<std::uint32_t>({0x1004,0x101e}));
    Require(RipLeas(code,0x1000,0x4000,0x0900)==std::vector<std::uint32_t>({0x103c}));
    auto copy=code;copy[6]=0x0c;Require(RipLeas(copy,0x1000,0x4000,0x2000).size()==1);
    Require(RipLeas(code.substr(0,10),0x1000,0x4000,0x2000).empty());
    Refuses([&]{RipLeas(code,0x3ff0,0x4000,0x2000);});
    Refuses([&]{RipLeas(code,0x1000,0x4000,0x4000);});
    std::string constants="prefix SetSimOccult";constants.push_back('\0');constants+="SetSimOccultX";
    Require(StringRvas(constants,0x2000,0x4000,"SetSimOccult")==std::vector<std::uint32_t>({0x2007}));
    std::string pointers(40,'\0');const std::uint64_t base=0x140000000ULL,value=base+0x2007;
    std::memcpy(pointers.data()+3,&value,8);std::memcpy(pointers.data()+22,&value,8);
    Require(Pointers(pointers,0x2000,0x4000,base,0x2007)==std::vector<std::uint32_t>({0x2003,0x2016}));
    Refuses([&]{Pointers(pointers,0x2000,0x4000,UINT64_MAX-5,0x2007);});
    Require(CodeWindow(code,0x1000,0x1004).size()==104);
    Refuses([&]{CodeWindow(code,0x1000,0x0fff);});
    const std::string many(500,'\0');Refuses([&]{Pointers(many,0x1000,0x4000,0,0);});
    Require(code[0]=='\x90' && constants.substr(7,12)=="SetSimOccult");
    std::string registration(96,'\x90');
    const unsigned char prefix[]={0x45,0x33,0xc9,0x4c,0x8d,0x05};std::memcpy(registration.data()+30,prefix,6);
    const std::int32_t callbackDelta=0x1040-0x1028,callDelta=0x1200-0x1038;
    std::memcpy(registration.data()+36,&callbackDelta,4);
    const unsigned char suffix[]={0x48,0x8d,0x15,0,0,0,0,0x49,0x8d,0x4f,0x18,0xe8};
    std::memcpy(registration.data()+40,suffix,12);std::memcpy(registration.data()+52,&callDelta,4);
    Require(RegisteredCallback(registration,0x1000,0x4000,0x1028,0x1200)==0x1040);
    Require(RegisteredCallback(registration,0x1000,0x4000,0x1028,0x1300)==0);
    registration[30]='\x90';Require(RegisteredCallback(registration,0x1000,0x4000,0x1028,0x1200)==0);
    Require(RegisteredCallback(registration,0x1000,0x4000,0x1002,0x1200)==0);
    Require(HexBytes(std::string("\x00\xff",2))=="00ff");
    std::cout<<"Bounded native CAS reference tests passed; no process access.\n";return 0;
 } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
