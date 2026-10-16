#include "ApexNativeCasEngineWin.h"
#include <functional>
#include <iostream>
using namespace td1::nativecas::engine;
using Json=td1::ui::Json;
void Require(bool v) {if(!v) throw std::runtime_error("Native owner selection regression.");}
void Refuses(const std::function<void()>& call) {bool caught=false;try {call();}catch(const std::exception&) {caught=true;}Require(caught);}
template<class T> void Write(void* p,std::size_t offset,T value) {std::memcpy(static_cast<char*>(p)+offset,&value,sizeof(value));}
using Cache=std::map<unsigned,std::array<char,32>>;
unsigned destroyed=0,converted=0,allocated=0,freed=0;
const void* sourceProto=nullptr;unsigned protoDestroyed=0;
unsigned serviceFallbacks=0,controllerCalls=0,avatarRefreshes=0;
std::array<void*,0x368/8> avatarTable{};void* avatarTablePointer=avatarTable.data();
bool OriginalService(const void*) {++serviceFallbacks;return false;}
void* Avatar() {return &avatarTablePointer;}
void RefreshAvatar(void*) {++avatarRefreshes;}
void Controller(void* controller,unsigned target) {
    ++controllerCalls;Write(Read<void*>(controller,0x100),0xd8,target);
}
Cache& Map(const void* p) {return **reinterpret_cast<Cache* const*>(static_cast<const char*>(p)+8);}
void* Construct(void* p,std::uint64_t id) {std::memset(p,0,0x830);Write(p,0xb8,id);return p;}
void Destroy(void*) {++destroyed;}
void Available(void* p,std::uint32_t v) {Write(p,0xdc,v);}
void Current(void* p,std::uint32_t v) {Write(p,0xd8,v);}
void AvailableData(void* p,std::uint32_t v) {Write(p,12,v);}
void OriginalImport(void* output,const void* proto) {Write(output,0xb8,Read<std::uint64_t>(proto,0x10));}
void Fields(void* output,const void* proto,const void* record) {
    Write(output,0xb8,Read<std::uint64_t>(proto,0x10));
    if(record) Write(output,0xe8,Read<unsigned>(record,0x1c));
    else {Current(output,4);Available(output,126);Write(output,0xe8,9999u);}
}
void AssignData(void* output,const void* input) {std::memcpy(output,input,32);}
void* CopySim(void* output,const void* input) {std::memcpy(output,input,0x830);return output;}
unsigned OriginalNormalize(void* data,bool alternate) {
    const auto current=Read<unsigned>(data,8),mask=Read<unsigned>(data,12);
    if(mask&4) Write(data,8,alternate?4u:1u);return current;
}
void* Meta(void* output,const void* source) {std::memset(output,0,0x38);Write(output,8,new Cache(Map(source)));return output;}
const void* Lookup(const void* metadata,unsigned kind) {auto& c=Map(metadata);const auto f=c.find(kind);return f==c.end()?nullptr:f->second.data();}
void Store(void* metadata,unsigned kind,const void* data) {std::memcpy(Map(metadata)[kind].data(),data,32);}
void* Allocate(std::size_t n,void*,unsigned,unsigned,void*,unsigned) {++allocated;return std::malloc(n);}
void Free(void* p,std::size_t) {++freed;std::free(p);}
void TreeDestroy(void* p,void*) {delete *reinterpret_cast<Cache**>(p);}
void OriginalChange(void*,unsigned,const void*,const void*,void**,void**) {++converted;}
unsigned OriginalAlternate(unsigned mask,unsigned current) {return current&~1u?1u:mask&~1u;}
void* ProtoConstruct(void* value) {std::memcpy(value,sourceProto,0x1e8);return value;}
bool ProtoParse(void*,const ByteView* bytes) {return bytes->length==2 && std::memcmp(bytes->data,"\1\2",2)==0;}
void ProtoDestroy(void*) {++protoDestroyed;}
int main() {
 try {
    Json request={{"operation","arm"},{"scope_id",std::string(32,'a')},
        {"members",Json::array({{{"sim_id","123"},{"owned_mask",127u}}})}};
    const auto scope=ParseScope(request);Require(scope.members.size()==1 && scope.members.at(123).mask==127);
    for(const auto bad:Json::array({"0","01","18446744073709551616",123,true,"-1"})) Refuses([&]{SimId(bad);});
    Require(SimId("18446744073709551615")==UINT64_MAX);
    auto changed=request;changed["members"].push_back(changed["members"][0]);Refuses([&]{ParseScope(changed);});
    for(const auto mask:Json::array({0,1,2,128,true,"127"})) {changed=request;changed["members"][0]["owned_mask"]=mask;Refuses([&]{ParseScope(changed);});}
    ValidateKinds(127,{1,2,4,8,16,32,64});Refuses([&]{ValidateKinds(127,{1,2,4,8,16,32});});
    Refuses([&]{ValidateKinds(127,{1,2,4,8,16,32,32});});Refuses([&]{ValidateKinds(3,{1,2,4});});
    Require(OwnedTarget(scope.members.at(123),127,4));Require(!OwnedTarget(scope.members.at(123),3,4));
    Require(!OwnedTarget(scope.members.at(123),127,3));
    Require(IndependentHybridGenus(127,2) && IndependentHybridGenus(126,1));
    Require(!IndependentHybridGenus(3,2) && !IndependentHybridGenus(259,2) && !IndependentHybridGenus(127,3));
    auto& runtime=Runtime();runtime.scope=scope;runtime.armed=true;
    auto& api=runtime.api;api.import=OriginalImport;api.fields=Fields;api.construct=Construct;api.destroy=Destroy;
    api.available=Available;api.current=Current;api.availableData=AvailableData;api.lookup=Lookup;api.store=Store;api.metadata=Meta;
    api.allocate=Allocate;api.free=Free;api.treeDestroy=TreeDestroy;api.change=OriginalChange;
    api.alternate=OriginalAlternate;api.protoConstruct=ProtoConstruct;api.protoParse=ProtoParse;api.protoDestroy=ProtoDestroy;
    api.assignData=AssignData;api.copySim=CopySim;api.normalize=OriginalNormalize;
    api.service=OriginalService;api.controller=Controller;api.avatar=Avatar;
    avatarTable[0x360/8]=reinterpret_cast<void*>(&RefreshAvatar);
    std::array<char,0x1e8> proto{};std::array<char,0x140> attributes{};std::array<char,0x38> tracker{};
    std::array<std::array<char,0x88>,7> records{};std::array<const void*,7> pointers{};
    Write(proto.data(),0x10,std::uint64_t(123));Write(proto.data(),0x1dc,1u<<26);Write(proto.data(),0xc0,attributes.data());
    Write(attributes.data(),0x13a,std::uint8_t(1));Write(attributes.data(),0x90,tracker.data());
    Write(tracker.data(),0x10,126u);Write(tracker.data(),0x14,2u);Write(tracker.data(),0x18,pointers.data());Write(tracker.data(),0x20,7);
    for(unsigned i=0;i<7;++i) {pointers[i]=records[i].data();Write(records[i].data(),0x18,1u<<i);Write(records[i].data(),0x1c,(1u<<i)*100u);Write(records[i].data(),0x84,1u);}
    std::array<char,0x830> output{};Import(output.data(),proto.data());
    auto& bank=runtime.bank.at(123);Require(bank.mask==127 && bank.owners.size()==7 && bank.error.empty());
    Require(Read<unsigned>(bank.owners.at(4)->data(),0x18)==400);
    Require(Read<unsigned>(output.data(),0xd8)==0); // Import did not overwrite the game's current appearance.
    Import(output.data(),proto.data());Require(destroyed==7 && bank.imports==2);
    std::array<char,0x250> controller{};std::array<char,0x830> group{};std::array<char,0x38> metadata{};
    int model=0;Write(controller.data(),0x100,group.data());Write(controller.data(),0x1d0,&model);
    Write(group.data(),0xb8,std::uint64_t(123));Write(group.data(),0xd8,2u);Write(group.data(),0xdc,127u);
    Cache original;Write(metadata.data(),8,&original);
    original[2].fill(0);Write(original[2].data(),8,2u);Write(original[2].data(),12,127u);Write(original[2].data(),0x18,222u);
    selected={123,4,controller.data()};void* before=nullptr;void* after=nullptr;
    Change(&model,4,group.data()+0xd0,metadata.data(),&before,&after);
    Require(before && after && converted==0 && runtime.intercepted==1 && bank.switches==1);
    Require(Read<unsigned>(before,0x48)==2 && Read<unsigned>(after,0x48)==4);
    Require(Read<unsigned>(after,0x4c)==127 && Map(static_cast<char*>(after)+8).size()==7);
    void* controllerPointer=controller.data();runtime.image=reinterpret_cast<std::uintptr_t>(&controllerPointer)-0x2948f00;
    runtime.selectionEnabled=true;Require(Alternate(127,1)==4 && Alternate(126,1)==4);
    Require(Alternate(3,1)==2 && Alternate(127,2)==1);runtime.selectionEnabled=false;
    Require(Read<unsigned>(Lookup(static_cast<char*>(after)+8,2),0x18)==222); // Current edits outrank imported preimages.
    Require(Read<unsigned>(Lookup(static_cast<char*>(after)+8,4),0x18)==400); // Target appearance never comes from Alien.
    Write(Map(static_cast<char*>(after)+8).at(2).data(),0x18,999u);
    Require(Read<unsigned>(Lookup(static_cast<char*>(before)+8,2),0x18)==222 && Read<unsigned>(original.at(2).data(),0x18)==222);
    Release(api,before);Release(api,after);Require(allocated==freed);
    selected={};Change(&model,4,group.data()+0xd0,metadata.data(),&before,&after);Require(converted==1);
    Write(records[6].data(),0x18,32u);Import(output.data(),proto.data());
    Require(bank.mask==0 && !bank.error.empty());
    Refuses([&]{Control({{"operation","activate"},{"scope_id",scope.id}});});
    Write(records[6].data(),0x18,64u);sourceProto=proto.data();
    const auto seed=Json({{"operation","seed"},{"scope_id",scope.id},{"sim_id","123"},
        {"native_hex","0102"},{"sha256",td1::resource::HashBytes(std::string("\1\2",2))}});
    Require(Control(seed).value("ok",false) && bank.seeded && bank.mask==127 && protoDestroyed==1);
    Require(bank.active && Read<unsigned>(bank.active->data(),8)==2 && Read<unsigned>(bank.active->data(),0x18)==9999);
    runtime.selectionEnabled=true;
    std::array<char,24> arguments{},argument{};Write(arguments.data(),8,argument.data());
    Write(argument.data(),0,4u);Write(argument.data(),8,2u);Write(group.data(),0xd8,4u);
    Require(SetOccultService(arguments.data()) && controllerCalls==1 && avatarRefreshes==1 &&
        Read<unsigned>(group.data(),0xd8)==2 && serviceFallbacks==0); // First membership is already Alien; displayed form was Vampire.
    Write(argument.data(),0,3u);Write(argument.data(),8,8.0);
    Require(SetOccultService(arguments.data()) && controllerCalls==2 && Read<unsigned>(group.data(),0xd8)==8);
    Write(argument.data(),8,8.5);Require(!SetOccultService(arguments.data()) && serviceFallbacks==1 && controllerCalls==2);
    Write(argument.data(),0,4u);Write(argument.data(),8,3u);
    Require(!SetOccultService(arguments.data()) && serviceFallbacks==2 && controllerCalls==2);
    runtime.selectionEnabled=false;Write(argument.data(),8,2u);
    Require(!SetOccultService(arguments.data()) && serviceFallbacks==3 && controllerCalls==2);
    runtime.selectionEnabled=true;
    std::array<char,32> genus{};Write(genus.data(),8,2u);Write(genus.data(),12,127u);
    Require(Normalize(genus.data(),true)==2 && Read<unsigned>(genus.data(),8)==2 && runtime.normalizationsPrevented==1);
    Write(genus.data(),8,4u);Write(genus.data(),12,5u);Normalize(genus.data(),false);Require(Read<unsigned>(genus.data(),8)==1);
    Write(output.data(),0xd8,4u);Write(output.data(),0xe8,4000u);
    Write(tracker.data(),0x10,3u);Import(output.data(),proto.data());
    Require(bank.mask==127 && bank.skippedPackets==1); // A narrowed client packet cannot replace the complete Source import.
    Require(Read<unsigned>(output.data(),0xd8)==2 && Read<unsigned>(output.data(),0xe8)==9999);
    const auto child=Read<void*>(output.data(),0x4c0);
    Require(child && Read<unsigned>(child,0xd8)==1 && Read<unsigned>(child,0xe8)==100 && Read<unsigned>(child,8)==1);
    Control({{"operation","entry-ready"},{"scope_id",scope.id},{"sim_id","123"}});
    Write(output.data(),0xe8,7777u);Import(output.data(),proto.data());Require(Read<unsigned>(output.data(),0xe8)==7777);
    Free(child,0x830);Write(output.data(),0x4c0,static_cast<void*>(nullptr));
    auto badSeed=seed;badSeed["sha256"]=std::string(64,'a');Refuses([&]{Control(badSeed);});Require(protoDestroyed==1);
    std::cout<<"Native existing-owner capture and selection contracts passed\n";return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
