#include "ApexNativeCasProbe.h"
#include "ApexNativeCasOwners.h"
#include <map>
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
    Require(SectionPointer(base+0x2200,base,0x2000,0x1000,0x1e8)==0x2200);
    Require(SectionPointer(base+0x2ff8,base,0x2000,0x1000,8)==0x2ff8);
    Refuses([&]{SectionPointer(base+0x2ff9,base,0x2000,0x1000,8);});
    Refuses([&]{SectionPointer(base+0x1fff,base,0x2000,0x1000,8);});
    Refuses([&]{SectionPointer(base+0x3000,base,0x2000,0x1000,1);});
    Refuses([&]{SectionPointer(base,UINT64_MAX-2,8,8,8);});
    Refuses([&]{SectionPointer(base,base,0,0x1000,0);});
    std::string loads(40,'\x90');loads[4]='\x48';loads[5]='\x8b';loads[6]='\x35';
    const std::int32_t delta=0x2948f00-0x100b;std::memcpy(loads.data()+7,&delta,4);
    Require(RipLoadTarget(loads,0x1000,0x1004)==0x2948f00);
    loads[6]='\x0d';Require(RipLoadTarget(loads,0x1000,0x1004)==0x2948f00);
    loads[5]='\x8d';Refuses([&]{RipLoadTarget(loads,0x1000,0x1004);});
    Refuses([&]{RipLoadTarget(loads,0x1000,0x0fff);});
    Refuses([&]{RipLoadTarget(loads.substr(0,10),0x1000,0x1004);});
    // Embedded E8 bytes in an immediate are not calls. An unreachable suffix
    // after RET is not inspected; a conditional target still gets decoded.
    std::string graph("\xb8\xe8\x90\x90\x90\x74\x06\xe8\x14\0\0\0\xc3\xe9\x1e\0\0\0",18);
    const auto edges=CodeEdges(graph,0x1000);
    Require(edges.size()==2 && edges[0].instruction==0x1007 && edges[0].target==0x1020 && edges[0].call &&
        edges[1].instruction==0x100d && edges[1].target==0x1030 && !edges[1].call);
    Require(CodeEdges(std::string("\xc3\xe8\0\0\0\0",6),0x1000).empty());
    Require(CodeEdges(std::string("\xe8\0",2),0x1000).empty());
    Refuses([&]{CodeEdges(std::string(4097,'\x90'),0x1000);});
    // Captured-layout fixtures cover empty caches, disjoint Sim identities,
    // all seven kind records and malformed native links without a process.
    std::map<std::uint64_t,std::uint64_t> memory;
    auto read=[&](std::uint64_t at) {
        const auto found=memory.find(at);
        if(found==memory.end()) throw std::runtime_error("Fixture address unavailable.");
        return found->second;
    };
    constexpr std::uint64_t controller=0x10000,first=0x20000,second=0x21000;
    memory[controller+0x138]=0;Require(ReadKindCacheMetadata(controller,read).empty());
    memory[controller+0x138]=first;
    memory[first]=0;memory[first+8]=second;memory[first+0x20]=101;memory[first+0xd0]=0x30000;
    memory[second]=0;memory[second+8]=0;memory[second+0x20]=202;memory[second+0xd0]=0x40000;
    for(unsigned i=0;i<7;++i) {
        const auto node=0x30000ULL+i*0x100;
        memory[node]=0;memory[node+8]=i<6?node+0x100:0;
        memory[node+0x20]=memory[node+0x38]=1u<<i;
    }
    memory[0x40000]=0;memory[0x40008]=0;memory[0x40020]=memory[0x40038]=4;
    const auto good=memory;const auto owners=ReadKindCacheMetadata(controller,read);
    Require(owners.size()==2 && owners[0].simId==101 && owners[1].simId==202 &&
        owners[0].kinds==std::vector<std::uint32_t>({1,2,4,8,16,32,64}) && owners[1].kinds==std::vector<std::uint32_t>({4}));
    memory[first]=first;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    memory[second+0x20]=101;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    memory[0x30038]=4;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    memory[second+0xd0]=0x30000;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    memory[0x30008]=0x30000;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    memory[0x30120]=memory[0x30138]=1;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    memory[controller+0x138]=0x20001;Refuses([&]{ReadKindCacheMetadata(controller,read);});memory=good;
    Refuses([&]{ReadKindCacheMetadata(0xfffffffffffffff8ULL,read);});
    std::cout<<"Bounded native CAS reference tests passed; no process access.\n";return 0;
 } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
