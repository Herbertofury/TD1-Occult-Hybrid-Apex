#include "ApexNativeCasEngineWin.h"
#include <functional>
#include <iostream>
using namespace td1::nativecas::engine;
using Json=td1::ui::Json;
void Check(bool v,int line) {if(!v) throw std::runtime_error("Native owner selection regression at line "+std::to_string(line));}
#define Require(...) Check((__VA_ARGS__),__LINE__)
void Refuses(const std::function<void()>& call) {bool caught=false;try {call();}catch(const std::exception&) {caught=true;}Require(caught);}
template<class T> void Write(void* p,std::size_t offset,T value) {std::memcpy(static_cast<char*>(p)+offset,&value,sizeof(value));}
using Cache=std::map<unsigned,std::array<char,32>>;
unsigned destroyed=0,converted=0,allocated=0,freed=0;
const void* sourceProto=nullptr;unsigned protoDestroyed=0;
std::map<const void*,std::string> protoExports;
int exportSizeOverride=0;bool exportWrongId=false,exportWrongLength=false;
std::size_t exportPadding=0;
unsigned serviceFallbacks=0,controllerCalls=0,avatarRefreshes=0;
unsigned reboundKind=0,nativeSyncCalls=0;
unsigned nativeLayerTransitions=0;
unsigned previewRestores=0;
unsigned outfitHairCalls=0;
std::array<std::uint32_t,5> animationArgument{};const void* animationPointer=nullptr;
void NativeAnimationGenus(void* actor,const void* genus,bool notify) {
    Require(notify);animationPointer=genus;std::memcpy(animationArgument.data(),genus,sizeof(animationArgument));
    std::memcpy(static_cast<char*>(actor)+0xc0,genus,sizeof(animationArgument));
}
void ExerciseAnimationIsolation(void* controller) {
    auto& runtime=Runtime();auto& bank=runtime.bank.at(123);auto* model=Read<char*>(controller,0x1d0);
    const auto originalCursor=bank.graph->cursor();const auto originalGenus=std::array<std::uint32_t,5>{
        Read<unsigned>(model,0x170),Read<unsigned>(model,0x174),Read<unsigned>(model,0x178),
        Read<unsigned>(model,0x17c),Read<unsigned>(model,0x180)};
    const auto oldActor=Read<void*>(model,0x48);std::array<char,0xe0> actor{};Write(model,0x48,actor.data());
    runtime.api.animationGenus=NativeAnimationGenus;
    const std::vector<std::string> owners={"native/1","native/2","native/4","native/8",
        "native/16","native/32","native/64","ghost/manifested"};
    for(const auto& owner:owners) {
        bank.graph->select(bank.graph->cursor(),owner);const auto kind=bank.graph->cursor().kind;Write(model,0x178,kind);
        const auto ownerBefore=SerializeOwner(runtime.api,*bank.graph->appearance(owner),123);
        // Real first-entry timing: binding can finish without an actor. Its
        // later construction must settle animation without any form switch.
        Write(model,0x48,static_cast<void*>(nullptr));
        const auto beforeConstruction=runtime.animationMembershipScopes;
        RefreshBoundAnimation(runtime,bank,controller);
        Require(runtime.animationMembershipScopes==beforeConstruction);
        Write(model,0x48,actor.data());
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x44903a);
        Require(animationArgument[2]==kind && animationArgument[3]==kind);
        Require(Read<unsigned>(model,0x17c)==127);
        const auto count=runtime.animationMembershipScopes;
        std::memcpy(actor.data()+0xc0,model+0x170,sizeof(animationArgument));
        RefreshBoundAnimation(runtime,bank,controller);
        Require(animationArgument[3]==kind && runtime.lastAnimationScope["actor_cache_verified"]==true);
        Require(runtime.lastAnimationScope["source"]=="exact-cas-preview-bind");
        Require(runtime.animationMembershipScopes==count+1);
        RefreshBoundAnimation(runtime,bank,controller); // Already settled; no repeated native call.
        Require(runtime.animationMembershipScopes==count+1);
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x45864d);
        Require(animationArgument[2]==kind && animationArgument[3]==kind);
        Require(bool(animationArgument[3]&32u)==(kind==32)); // Vampire/Alien/Human never howl as Werewolf.
        Require(animationArgument[0]==originalGenus[0] && animationArgument[1]==originalGenus[1] && animationArgument[4]==originalGenus[4]);
        Require(Read<unsigned>(model,0x17c)==127 && bank.mask==127);
        Require(SerializeOwner(runtime.api,*bank.graph->appearance(owner),123)==ownerBefore);
        Require(runtime.animationMembershipScopes==count+2 && runtime.lastAnimationScope["owner_id"]==owner);
        const auto constructions=runtime.animationConstructionScopes;
        // The first native actor is created after binding; the usual dirty
        // update need not run when the selected genus has not changed.
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x44903a);
        Require(animationArgument[2]==kind && animationArgument[3]==kind);
        Require(runtime.lastAnimationScope["source"]=="exact-cas-preview-construction");
        Require(runtime.animationConstructionScopes==constructions+1);
        // Construction during an in-progress exact binding is also valid,
        // before the outer binder publishes the new bound Sim/view flag.
        const auto previous=binding;const auto viewBound=bank.viewBound;
        ViewBinding initial{controller,&bank,owner};binding=&initial;
        bank.viewBound=false;runtime.boundSim=456;
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x44903a);
        Require(animationArgument[3]==kind && runtime.lastAnimationScope["owner_id"]==owner);
        binding=previous;bank.viewBound=viewBound;runtime.boundSim=123;
        Require(runtime.animationConstructionScopes==constructions+2);
        Require(SerializeOwner(runtime.api,*bank.graph->appearance(owner),123)==ownerBefore);
        // A different call site, actor or detached record cannot authorize
        // changing animation flags. These paths still receive the original.
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x45864e);
        Require(animationArgument[3]==127 && animationPointer==model+0x170);
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x44903b);
        Require(animationArgument[3]==127 && animationPointer==model+0x170);
        std::array<char,0xe0> otherActor{};
        RouteAnimationGenus(otherActor.data(),model+0x170,true,runtime.image+0x45864d);Require(animationArgument[3]==127);
        auto detached=originalGenus;detached[2]=kind;
        RouteAnimationGenus(actor.data(),detached.data(),true,runtime.image+0x45864d);Require(animationArgument[3]==127);
        const auto exactGroup=bank.boundGroup;bank.boundGroup=otherActor.data();
        RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x44903a);Require(animationArgument[3]==127);
        bank.boundGroup=exactGroup;
        bank.viewFault=true;RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x45864d);
        Require(animationArgument[3]==127);bank.viewFault=false;
        runtime.selectionEnabled=false;RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x45864d);
        Require(animationArgument[3]==127);runtime.selectionEnabled=true;
        runtime.boundSim=456;RouteAnimationGenus(actor.data(),model+0x170,true,runtime.image+0x45864d);
        Require(animationArgument[3]==127);runtime.boundSim=123;
        Require(runtime.animationMembershipScopes==count+4);
    }
    bank.graph->select(bank.graph->cursor(),originalCursor.owner);
    std::memcpy(model+0x170,originalGenus.data(),sizeof(originalGenus));Write(model,0x48,oldActor);
}
void OriginalOutfitHair(void* outfit,const void* genus) {
    ++outfitHairCalls;Require(genus==outfit);Write(outfit,24,148023u);
}
void OriginalRebind(void*,const void*,unsigned target) {reboundKind=target;}
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
void Available(void* p,std::uint32_t v) {
    // All pre-entry detached owners must enter the normalization scope before
    // the first setter, matching the canonical full-record import contract.
    Require(detachedTarget==static_cast<char*>(p)+0xd0);Write(p,0xdc,v);
}
void Current(void* p,std::uint32_t v) {Write(p,0xd8,v);}
void AvailableData(void* p,std::uint32_t v) {Write(p,12,v);}
void OriginalImport(void* output,const void* proto) {Write(output,0xb8,Read<std::uint64_t>(proto,0x10));}
void Fields(void* output,const void* proto,const void* record) {
    const auto initialKind=Read<unsigned>(output,0xd8),initialMask=Read<unsigned>(output,0xdc);
    Require(Kind(initialKind) && (initialMask&initialKind));
    Write(output,0xb8,Read<std::uint64_t>(proto,0x10));
    if(record) {
        Write(output,0xe8,Read<unsigned>(record,0x1c));
        Write(output,0x360,0xface0000u+initialKind); // Complete inherited payload read only by record loader.
    }
    else {Current(output,4);Available(output,126);Write(output,0xe8,9999u);}
}
void AssignData(void* output,const void* input) {std::memcpy(output,input,0x300);}
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
void ProtoDestroy(void* value) {++protoDestroyed;protoExports.erase(value);}
void ExportProto(const void* owner,void* proto) {
    const auto id=Read<std::uint64_t>(owner,0xb8);Write(proto,0x10,exportWrongId?std::uint64_t(999):id);
    std::string bytes(1,'\x09');bytes.append(reinterpret_cast<const char*>(&id),8);
    bytes.append("\x12\x80\x06",3);bytes.append(static_cast<const char*>(owner)+0xd0,0x300);
    bytes.append(exportPadding,'\x5a');
    protoExports[proto]=std::move(bytes);
}
int ProtoSize(const void* proto) {return exportSizeOverride?exportSizeOverride:static_cast<int>(protoExports.at(proto).size());}
char* ProtoArray(const void* proto,char* output) {
    const auto& bytes=protoExports.at(proto);std::memcpy(output,bytes.data(),bytes.size());
    return output+bytes.size()+(exportWrongLength?1:0);
}
std::array<void*,0x500/8> viewControllerTable{},groupInterfaceTable{};
void* viewMetadata=nullptr;
std::uint64_t NativeGroupId(void*) {return 123;}
void* NativeCache(void*,std::uint64_t) {return viewMetadata;}
void* NativeContext(void*,std::uint64_t,bool) {return viewMetadata;}
int NativeIndex(void*,std::uint64_t) {return 0;}
void NativeSync(void* controller) {
    ++nativeSyncCalls;
    auto group=Read<void*>(controller,0x100);auto child=Read<void*>(group,0x4c0);
    auto layer=Read<std::uint8_t>(controller,0x242);auto model=Read<void*>(controller,0x1d0);
    AssignData(static_cast<char*>(layer?child:group)+0xd0,static_cast<char*>(model)+0x170);
    if(child) Write(layer?group:child,0xe8,876543u); // Stock cross-owner propagation must be removed.
    Write(model,0x188,987654u); // Stock normalization mutates the edited model too.
    Write(model,0x3b0,0xdeadu); // Reproduce loss of a field outside the short header.
}
void HairPreview(void* model,bool show) {Write(model,0xa60,std::uint8_t(show));}
void ClothingPreview(void* model,bool undress) {
    if(Read<std::uint8_t>(model,0xbb9) && !undress) {
        Write(model,0x3c0,Read<unsigned>(model,0xb20));++previewRestores;
    }
    Write(model,0xbb9,std::uint8_t(undress));
}
void WingsPreview(void* model,bool show) {Write(model,0xbba,std::uint8_t(show));}
void NativeModelBind(void* model,const void* data,void* context,bool) {
    AssignData(static_cast<char*>(model)+0x170,data);Write(model,0x510,context);
    // Reproduce the actual setter's Vampire-membership CMOV. Removing this
    // protection must fail initial Alien binding and every other form switch.
    const auto mask=ModelKindMask(data,Read<unsigned>(data,12),Runtime().image+0x45c32c);
    if(mask&4) Write(model,0x178,4u);
}
struct UndoFixture {void* table=nullptr;unsigned references=1,padding=0;unsigned marker=0;};
std::array<void*,1> undoTable{};
std::vector<std::unique_ptr<UndoFixture>> undoFixtures;
void UndoDestroyed(void* pointer,int) {static_cast<UndoFixture*>(pointer)->references=0;}
void* NewUndo(unsigned marker=0) {
    auto result=std::make_unique<UndoFixture>();result->table=undoTable.data();result->marker=marker;
    auto pointer=result.get();undoFixtures.push_back(std::move(result));return pointer;
}
void UndoBind(void* model,void** consumed) {
    auto pointer=static_cast<UndoFixture*>(*consumed);auto old=Read<UndoFixture*>(model,0x70);
    if(pointer!=old) {
        ++pointer->references;Write(model,0x70,pointer);
        if(old && !--old->references) UndoDestroyed(old,1);
    }
    if(!--pointer->references) UndoDestroyed(pointer,1);
}
void UndoCreate(void* controller,std::uint64_t,bool,bool) {
    auto pointer=NewUndo();UndoBind(Read<void*>(controller,0x1d0),&pointer);
}
void OriginalUndoSelect(void*,std::uint64_t,bool) {throw std::runtime_error("Shared pair undo selection ran for an owned form.");}
void NativeCoreBind(void* controller,int,bool) {
    BindSelected(controller,false);
    SelectUndo(controller,123,Read<std::uint8_t>(controller,0x242)!=0);
}
void NativeLayerTransition(void* controller,bool alternate,bool notify,bool refresh) {
    Require(Read<std::uint8_t>(controller,0x242)!=static_cast<std::uint8_t>(alternate));
    Require(notify && !refresh && binding && binding->controller==controller);
    const auto generation=binding->bank->graph->cursor().generation;
    Sync(controller); // The stock handler's outgoing Sync must not harvest the newly assigned pair.
    Require(binding->bank->graph->cursor().generation==generation);
    ++nativeLayerTransitions;Write(controller,0x242,static_cast<std::uint8_t>(alternate));
    NativeCoreBind(controller,0,false);
}
void NativeOriginalBind(void*,bool) {throw std::runtime_error("Stock merging binder must not run for explicit owner views.");}
unsigned RelayResult(const void*) {return 13;}
void ExerciseLocalCallsite() {
    auto* image=static_cast<unsigned char*>(VirtualAlloc(nullptr,0x460000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    Require(image!=nullptr);
    const unsigned char getter[]={0x8b,0x41,0x0c,0xc3};std::memcpy(image+0x297630,getter,sizeof(getter));
    unsigned char caller[]={0x48,0x83,0xec,0x28,0x90,0x90,0x90,0xe8,0,0,0,0,0x48,0x83,0xc4,0x28,0xc3};
    const auto displacement=std::int32_t(0x297630-0x45c32c);std::memcpy(caller+8,&displacement,4);
    std::memcpy(image+0x45c320,caller,sizeof(caller));DWORD old=0;
    Require(VirtualProtect(image+0x297000,4096,PAGE_EXECUTE_READ,&old)!=0);
    Require(VirtualProtect(image+0x45c000,4096,PAGE_EXECUTE_READ,&old)!=0);
    FlushInstructionCache(GetCurrentProcess(),image,0x460000);
    const auto invoke=reinterpret_cast<KindMaskFn>(image+0x45c320);
    const auto leaf=reinterpret_cast<KindMaskFn>(image+0x297630);
    std::array<unsigned,4> data{{0,0,1,127}};
    Require(invoke(data.data())==127 && leaf(data.data())==127);
    auto& runtime=Runtime();const auto previous=runtime.api.kindMask;runtime.api.kindMask=RelayResult;
    State local;local.image=reinterpret_cast<std::uintptr_t>(image);InstallKindCall(local);
    Require(local.kindCallPatched && invoke(data.data())==13 && leaf(data.data())==127);
    RestoreKindCall(local);Require(!local.kindCallPatched && invoke(data.data())==127);
    InstallKindCall(local);Require(invoke(data.data())==13); // Safe reuse after a rolled-back install.
    RestoreKindCall(local);runtime.api.kindMask=previous;
    MEMORY_BASIC_INFORMATION page{};VirtualQuery(image+0x45c328,&page,sizeof(page));
    Require(page.Protect==PAGE_EXECUTE_READ);
    Require(VirtualFree(image,0,MEM_RELEASE)!=0);
}
int main() {
 try {
    std::array<char,16> shortText{};std::memcpy(shortText.data(),"APEXUI1|READ|7",14);shortText[15]=1;
    std::array<char,16> stringValue{};Write(stringValue.data(),0,6u);Write(stringValue.data(),8,shortText.data());
    Require(UiString(stringValue.data())=="APEXUI1|READ|7");
    const std::string longText="APEXUI1|WRITE|7|00000004WAIT";
    std::array<char,16> longObject{};Write(longObject.data(),0,longText.c_str());
    Write(longObject.data(),8,static_cast<std::uint32_t>(longText.size()));longObject[15]=char(128);
    Write(stringValue.data(),8,longObject.data());Require(UiString(stringValue.data())==longText);
    Write(longObject.data(),8,static_cast<std::uint32_t>(td1::nativecas::pipe::Limit+129));Refuses([&]{UiString(stringValue.data());});
    Write(stringValue.data(),8,shortText.data());shortText[15]=20;Refuses([&]{UiString(stringValue.data());});
    shortText[15]=1;shortText[14]='x';Refuses([&]{UiString(stringValue.data());});
    Write(stringValue.data(),0,5u);Refuses([&]{UiString(stringValue.data());});
    ExerciseLocalCallsite();
    Json request={{"operation","arm"},{"scope_id",std::string(32,'a')},
        {"members",Json::array({{{"sim_id","123"},{"owned_mask",127u}}})}};
    const auto scope=ParseScope(request);Require(scope.members.size()==1 && scope.members.at(123).mask==127);
    for(const auto bad:Json::array({"0","01","18446744073709551616",123,true,"-1"})) Refuses([&]{SimId(bad);});
    Require(SimId("18446744073709551615")==UINT64_MAX);
    auto changed=request;changed["members"].push_back(changed["members"][0]);Refuses([&]{ParseScope(changed);});
    for(const auto mask:Json::array({0,2,128,true,"127"})) {changed=request;changed["members"][0]["owned_mask"]=mask;Refuses([&]{ParseScope(changed);});}
    ValidateKinds(127,{1,2,4,8,16,32,64});Refuses([&]{ValidateKinds(127,{1,2,4,8,16,32});});
    Refuses([&]{ValidateKinds(127,{1,2,4,8,16,32,32});});Refuses([&]{ValidateKinds(3,{1,2,4});});
    auto humanScope=request;humanScope["members"][0]["owned_mask"]=1u;
    Require(ParseScope(humanScope).members.at(123).mask==1);
    Require(OwnedTarget(scope.members.at(123),127,4));Require(!OwnedTarget(scope.members.at(123),3,4));
    Require(!OwnedTarget(scope.members.at(123),127,3));
    Require(IndependentHybridGenus(127,2) && IndependentHybridGenus(126,1));
    Require(!IndependentHybridGenus(3,2) && !IndependentHybridGenus(259,2) && !IndependentHybridGenus(127,3));
    auto& runtime=Runtime();runtime.scope=scope;runtime.armed=true;
    auto& api=runtime.api;api.import=OriginalImport;api.fields=Fields;api.construct=Construct;api.destroy=Destroy;
    api.outfitHair=OriginalOutfitHair;
    std::array<char,32> importData{};
    {const DetachedTarget owned(importData.data());
        ImportOutfitHair(importData.data(),importData.data(),runtime.image+0x3261f7);
        Require(Read<unsigned>(importData.data(),24)==0 && outfitHairCalls==0);
        ImportOutfitHair(importData.data(),importData.data(),runtime.image+0x3261f8);}
    ImportOutfitHair(importData.data(),importData.data(),runtime.image+0x3261f7);
    Require(outfitHairCalls==2 && runtime.importOutfitFillsPrevented==1);
    api.available=Available;api.current=Current;api.availableData=AvailableData;api.lookup=Lookup;api.store=Store;api.metadata=Meta;
    api.allocate=Allocate;api.free=Free;api.treeDestroy=TreeDestroy;api.change=OriginalChange;
    api.alternate=OriginalAlternate;api.protoConstruct=ProtoConstruct;api.protoParse=ProtoParse;api.protoDestroy=ProtoDestroy;
    api.assignData=AssignData;api.copySim=CopySim;api.normalize=OriginalNormalize;
    api.service=OriginalService;api.controller=Controller;api.avatar=Avatar;
    api.rebind=OriginalRebind;
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
    Import(output.data(),proto.data());Require(destroyed==14 && bank.imports==2);
    std::array<char,0x250> controller{};std::array<char,0x830> group{};std::array<char,0x38> metadata{};
    std::array<char,0xc40> model{};Write(controller.data(),0x100,group.data());Write(controller.data(),0x1d0,&model);
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
    Refuses([&]{Control({{"operation","activate"},{"scope_id",scope.id}});}); // Root regeneration is not full active import.
    for(unsigned kind=1;kind<=64;kind*=2) {
        auto canonicalSeed=seed;canonicalSeed["operation"]="seed-canonical";canonicalSeed["native_kind"]=kind;
        Require(Control(canonicalSeed).value("ok",false));Refuses([&]{Control(canonicalSeed);});
        Require(bank.graph->cursor().owner=="active/2" &&
            Read<unsigned>(bank.graph->appearance(kind)->data(),0x290)==0xface0000u+kind);
    }
    Require(bank.canonicalSourceMask==127);
    auto activeSeed=seed;activeSeed["operation"]="seed-active";activeSeed["native_kind"]=2u;
    Write(records[1].data(),0x1c,9999u);Require(Control(activeSeed).value("ok",false));Write(records[1].data(),0x1c,200u);
    Refuses([&]{Control(activeSeed);}); // No second active seed can replace an imported entry.
    Require(bank.activeSourceSeeded && Read<unsigned>(bank.graph->appearance("active/2")->data(),0x290)==0xface0002u);
    runtime.selectionEnabled=true;
    std::array<char,0xc40> currentModel{};Write(controller.data(),0x1d0,currentModel.data());
    Write(currentModel.data(),0x178,2u);original[1].fill(0);
    Rebind(controller.data(),metadata.data(),125);
    Require(reboundKind==1 && runtime.rebindCorrections==1);
    Rebind(controller.data(),metadata.data(),124);
    Require(reboundKind==1 && runtime.rebindCorrections==2);
    Rebind(controller.data(),metadata.data(),1);Require(reboundKind==1 && runtime.rebindCorrections==2);
    Rebind(controller.data(),metadata.data(),0);Require(reboundKind==0 && runtime.rebindCorrections==2);
    Write(currentModel.data(),0x178,1u);
    Rebind(controller.data(),metadata.data(),126);Require(reboundKind==2 && runtime.rebindCorrections==3);
    runtime.selectionEnabled=false;Rebind(controller.data(),metadata.data(),126);
    Require(reboundKind==126 && runtime.rebindCorrections==3);runtime.selectionEnabled=true;
    std::array<char,24> arguments{},argument{};Write(arguments.data(),8,argument.data());
    Write(argument.data(),0,4u);Write(argument.data(),8,2u);Write(group.data(),0xd8,4u);
    Require(!SetOccultService(arguments.data()) && controllerCalls==0 && avatarRefreshes==0 &&
        Read<unsigned>(group.data(),0xd8)==4 && serviceFallbacks==0 && runtime.blockedConversions==1);
    Write(argument.data(),0,3u);Write(argument.data(),8,8.0);
    Require(!SetOccultService(arguments.data()) && controllerCalls==0 && Read<unsigned>(group.data(),0xd8)==4 && runtime.blockedConversions==2);
    Write(argument.data(),8,8.5);Require(!SetOccultService(arguments.data()) && serviceFallbacks==1 && controllerCalls==0);
    Write(argument.data(),0,4u);Write(argument.data(),8,3u);
    Require(!SetOccultService(arguments.data()) && serviceFallbacks==2 && controllerCalls==0);
    runtime.selectionEnabled=false;Write(argument.data(),8,2u);
    Require(!SetOccultService(arguments.data()) && serviceFallbacks==3 && controllerCalls==0);
    runtime.selectionEnabled=true;
    std::array<char,32> genus{};Write(genus.data(),8,2u);Write(genus.data(),12,127u);
    { const DetachedTarget owned(genus.data());
      Require(Normalize(genus.data(),true)==2 && Read<unsigned>(genus.data(),8)==2 && runtime.normalizationsPrevented==1); }
    Normalize(genus.data(),false);Require(Read<unsigned>(genus.data(),8)==1 && runtime.normalizationsPrevented==1);
    Write(genus.data(),8,4u);Write(genus.data(),12,5u);Normalize(genus.data(),false);Require(Read<unsigned>(genus.data(),8)==1);
    Write(output.data(),0xd8,4u);Write(output.data(),0xe8,4000u);
    Write(tracker.data(),0x10,3u);Import(output.data(),proto.data());
    Require(bank.mask==127 && bank.skippedPackets==1); // A narrowed client packet cannot replace the complete Source import.
    Require(Read<unsigned>(output.data(),0xd8)==2 && Read<unsigned>(output.data(),0xe8)==9999);
    const auto child=Read<void*>(output.data(),0x4c0);
    Require(child && Read<unsigned>(child,0xd8)==1 && Read<unsigned>(child,0xe8)==100 && Read<unsigned>(child,8)==1);
    const auto namedSeed=Json({{"operation","seed-appearance"},{"scope_id",scope.id},{"sim_id","123"},
        {"owner_id","ghost/manifested"},{"native_kind",1u},{"native_hex","0102"},
        {"sha256",td1::resource::HashBytes(std::string("\1\2",2))}});
    Write(records[0].data(),0x1c,9999u);Require(Control(namedSeed).value("ok",false));Write(records[0].data(),0x1c,100u);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x290)==0xface0001u);
    Require(bank.graph->owners().size()==9 && Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),8)==1);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x18)==9999);
    Require(Read<unsigned>(bank.graph->appearance(1)->data(),0x18)==100);
    auto badNamed=namedSeed;badNamed["owner_id"]="native/1";Refuses([&]{Control(badNamed);});
    badNamed=namedSeed;badNamed["sim_id"]="124";Refuses([&]{Control(badNamed);});
    Refuses([&]{Control(namedSeed);}); // No duplicate named owner replacement.
    Control({{"operation","entry-ready"},{"scope_id",scope.id},{"sim_id","123"}});
    Write(output.data(),0xe8,7777u);Import(output.data(),proto.data());Require(Read<unsigned>(output.data(),0xe8)==7777);
    Require(bank.graph && bank.graph->cursor().kind==2 && bank.graph->mask()==127);
    Require(Read<unsigned>(bank.graph->appearance(2)->data(),0x18)==200);
    Require(Read<unsigned>(bank.graph->appearance("active/2")->data(),0x18)==9999);
    Require(Read<unsigned>(bank.graph->appearance(4)->data(),0x18)==400);
    Refuses([&]{Control(seed);}); // A CAS-ready graph cannot be reset over pending edits.
    Refuses([&]{Control(namedSeed);});
    Free(child,0x830);Write(output.data(),0x4c0,static_cast<void*>(nullptr));
    const auto beforeBadSeed=protoDestroyed;
    auto badSeed=seed;badSeed["sha256"]=std::string(64,'a');Refuses([&]{Control(badSeed);});Require(protoDestroyed==beforeBadSeed);
    // Execute the actual adapter with native-shaped records and the original
    // game's destructive inactive-copy behavior represented by NativeSync.
    api.sync=NativeSync;api.bind=NativeOriginalBind;api.modelBind=NativeModelBind;
    api.hairPreview=HairPreview;api.clothingPreview=ClothingPreview;api.wingsPreview=WingsPreview;
    api.coreBind=NativeCoreBind;api.layer=NativeLayerTransition;api.context=NativeContext;api.index=NativeIndex;
    api.undoSelect=OriginalUndoSelect;api.undoCreate=UndoCreate;api.undoBind=UndoBind;
    undoTable[0]=reinterpret_cast<void*>(&UndoDestroyed);
    Write(currentModel.data(),0x70,NewUndo(9999));
    viewMetadata=metadata.data();viewControllerTable[0x410/8]=reinterpret_cast<void*>(&NativeCache);
    groupInterfaceTable[0]=reinterpret_cast<void*>(&NativeGroupId);
    Write(controller.data(),0,viewControllerTable.data());Write(group.data(),0x10,groupInterfaceTable.data());
    Write(controller.data(),0x1d0,currentModel.data());Write(controller.data(),0x242,std::uint8_t(0));
    Write(group.data(),0xd8,4u);Write(group.data(),0xdc,127u);
    Write(currentModel.data(),0x178,4u);Write(currentModel.data(),0x17c,127u);Write(currentModel.data(),0x188,9999u);
    NativeCoreBind(controller.data(),0,false); // Initial household binding bypasses the stock copying binder too.
    Require(bank.viewBound && !bank.viewFault && Read<unsigned>(currentModel.data(),0x178)==2);
    // The visible actual entry appearance must also be the one EA serializes.
    // Its older stored native/2 look remains archived in the complete graph.
    Require(Read<unsigned>(Map(metadata.data()).at(2).data(),0x18)==9999);
    Require(Read<unsigned>(bank.graph->appearance("native/2")->data(),0x18)==200);
    Require(Status()["members"][0]["logical_owner_ids"]["2"]=="active/2");
    const auto capturedSelection=Status()["selected_native"];
    Require(capturedSelection["source"]=="native-cas-callback-observation" && capturedSelection["occult_type"]==2);
    // The CAS engine can dispose its controller without taking our mutex.
    // Worker status must only read the callback's value snapshot, even when
    // the singleton points at unreadable memory; no pointer probing or Sync.
    controllerPointer=reinterpret_cast<void*>(1);
    Require(Status()["selected_native"]==capturedSelection);
    Require(ViewStatus()["available"]==true && ViewStatus()["native_kind"]==2);
    controllerPointer=controller.data();
    api.exportProto=ExportProto;api.protoSize=ProtoSize;api.protoArray=ProtoArray;
    auto* exportedData=const_cast<void*>(bank.graph->appearance("native/4")->data());
    Write(exportedData,0x240,0x11223344u); // Opaque field beyond the short fixture header survives export.
    const auto exportCursor=bank.graph->cursor();const auto exportModel=currentModel;
    Json exportRequest={{"operation","export-owner"},{"scope_id",scope.id},{"sim_id","123"},
        {"owner_id","native/4"},{"expected_generation",exportCursor.generation}};
    const auto exported=Control(exportRequest)["owner_export"];
    Require(exported["source"]=="committed-native-appearance" && exported["model_harvested"]==false);
    const std::string rawExport="44332211";
    Require(exported["native_hex"].get<std::string>().find(rawExport)!=std::string::npos);
    Require(bank.graph->cursor().generation==exportCursor.generation && currentModel==exportModel);
    const auto destroyedBefore=protoDestroyed;
    exportWrongId=true;Refuses([&]{Control(exportRequest);});exportWrongId=false;
    exportWrongLength=true;Refuses([&]{Control(exportRequest);});exportWrongLength=false;
    exportSizeOverride=1024*1024;Refuses([&]{Control(exportRequest);});exportSizeOverride=0;
    Require(protoDestroyed==destroyedBefore+3 && protoExports.empty());
    Json pageRequest={{"operation","export-owner-page"},{"scope_id",scope.id},{"sim_id","123"},
        {"expected_generation",exportCursor.generation},{"after_owner_id",""}};
    const auto page=Control(pageRequest);
    Require(page["scope"]=="native-owner-export-page" && page["owners"].size()==8 && page["complete"]==false);
    std::vector<std::string> pageIds;
    for(const auto& row:page["owners"]) pageIds.push_back(row["owner_id"].get<std::string>());
    Require(std::is_sorted(pageIds.begin(),pageIds.end()));
    auto nextPage=pageRequest;nextPage["after_owner_id"]=page["next_owner_id"];
    const auto tail=Control(nextPage);
    Require(tail["owners"].size()==1 && tail["complete"]==true && tail["next_owner_id"].is_null());
    pageIds.push_back(tail["owners"][0]["owner_id"].get<std::string>());
    Require(pageIds.size()==bank.graph->owners().size() && std::adjacent_find(pageIds.begin(),pageIds.end())==pageIds.end());
    Require(page["selected_owner_id"]==exportCursor.owner && page["owned_mask"]==127);
    for(const auto& row:page["owners"]) {
        Require(row["revision"]==bank.graph->revision(row["owner_id"].get<std::string>()));
        Require(row["linked_targets"].empty());
    }
    exportPadding=128*1024;const auto largePage=Control(pageRequest);exportPadding=0;
    Require(largePage["owners"].size()==3 && largePage["complete"]==false && protoExports.empty());
    Require(bank.graph->cursor().generation==exportCursor.generation && currentModel==exportModel && nativeSyncCalls==0);
    auto invalidPage=pageRequest;invalidPage["after_owner_id"]="unknown/other";Refuses([&]{Control(invalidPage);});
    invalidPage=pageRequest;invalidPage["expected_generation"]=exportCursor.generation+1;Refuses([&]{Control(invalidPage);});
    invalidPage=pageRequest;invalidPage["scope_id"]="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";Refuses([&]{Control(invalidPage);});
    auto staleExport=exportRequest;staleExport["expected_generation"]=exportCursor.generation+1;
    Refuses([&]{Control(staleExport);});staleExport=exportRequest;staleExport.erase("sim_id");staleExport["extra"]=true;
    Refuses([&]{Control(staleExport);});
    Require(runtime.kindBiasPrevented>0);
    Require(ModelKindMask(nullptr,127,runtime.image+0x45c32d)==127); // Other callers retain every membership bit.
    Require(bank.partner=="native/1" && Read<unsigned>(group.data(),0xe8)==9999);
    Require(Read<unsigned>(Read<void*>(group.data(),0x4c0),0xe8)==100);
    ExerciseAnimationIsolation(controller.data());
    auto stageView=[&](const char* rid,const char* owner) {
        const auto cursor=bank.graph->cursor();
        auto staged=Control({{"operation","stage-view"},{"scope_id",scope.id},{"sim_id","123"},
            {"request_id",rid},{"owner_id",owner},{"expected_owner_id",cursor.owner},
            {"expected_generation",cursor.generation},{"expected_layer",static_cast<unsigned>(Read<std::uint8_t>(controller.data(),0x242))}});
        const auto token=staged["token"].get<unsigned>();
        Write(argument.data(),0,4u);Write(argument.data(),8,token);
        Require(SetOccultService(arguments.data()));
        Require(runtime.viewResult["state"]=="applied" && runtime.viewResult["owner_id"]==owner);
    };
    stageView("11111111111111111111111111111111","native/2");
    Require(nativeLayerTransitions==0); // Same-layer owner changes must rebind, not call EA's no-op selector.
    Require(Read<unsigned>(currentModel.data(),0x188)==200);
    Require(Read<unsigned>(bank.graph->appearance("active/2")->data(),0x18)==9999);
    const auto alienUndo=Read<UndoFixture*>(currentModel.data(),0x70);
    Require(alienUndo->marker==0);alienUndo->marker=22222;
    Write(currentModel.data(),0x188,22222u);
    stageView("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","native/4");
    Require(nativeLayerTransitions==1); // Alien base -> occult alternate uses the full original lifecycle.
    Require(Read<unsigned>(currentModel.data(),0x178)==4 && Read<unsigned>(currentModel.data(),0x188)==400);
    Require(bank.entryOwner=="native/1" && bank.partner=="native/4");
    Require(Read<unsigned>(group.data(),0xd8)==1 && Read<unsigned>(group.data(),0xe8)==100);
    Require(Read<unsigned>(Read<void*>(group.data(),0x4c0),0xd8)==4);
    Require(Read<unsigned>(bank.graph->appearance(2)->data(),0x18)==22222);
    Require(Read<unsigned>(bank.graph->appearance(1)->data(),0x18)==100);
    const auto vampireUndo=Read<UndoFixture*>(currentModel.data(),0x70);
    Require(vampireUndo!=alienUndo && vampireUndo->marker==0);vampireUndo->marker=44444;
    Write(currentModel.data(),0x188,44444u);
    stageView("cccccccccccccccccccccccccccccccc","ghost/manifested");
    Require(nativeLayerTransitions==1); // Two different top forms share the physical layer, not their data.
    Require(Read<unsigned>(currentModel.data(),0x178)==1 && Read<unsigned>(currentModel.data(),0x188)==9999);
    Require(Read<unsigned>(bank.graph->appearance(4)->data(),0x18)==44444);
    Require(Read<unsigned>(bank.graph->appearance(1)->data(),0x18)==100);
    Require(bank.entryOwner=="native/1" && bank.partner=="ghost/manifested");
    Require(ViewStatus()["portrait_pair"]["alternate_owner_id"]=="ghost/manifested");
    Require(Read<unsigned>(currentModel.data(),0x178)==1); // No Vampire substitute.
    const auto ghostUndo=Read<UndoFixture*>(currentModel.data(),0x70);
    Require(ghostUndo!=alienUndo && ghostUndo!=vampireUndo);
    stageView("dddddddddddddddddddddddddddddddd","native/2");
    Require(nativeLayerTransitions==2);
    Require(Read<unsigned>(currentModel.data(),0x188)==22222);
    Require(Read<UndoFixture*>(currentModel.data(),0x70)==alienUndo && alienUndo->marker==22222);
    stageView("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","native/1");
    Require(Read<unsigned>(currentModel.data(),0x188)==100 && Read<std::uint8_t>(controller.data(),0x242)==1);
    const auto humanUndo=Read<UndoFixture*>(currentModel.data(),0x70);
    Require(humanUndo!=ghostUndo && humanUndo!=alienUndo && humanUndo!=vampireUndo);
    const auto independentChild=Read<void*>(group.data(),0x4c0);
    Require(Read<unsigned>(independentChild,0xd8)==1 && Read<unsigned>(independentChild,0xe8)==100);
    Require(Read<unsigned>(group.data(),0xe8)==22222);
    stageView("ffffffffffffffffffffffffffffffff","ghost/manifested");
    Write(currentModel.data(),0x188,77777u);Write(currentModel.data(),0x3b0,0x55667788u);Sync(controller.data());
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x18)==77777);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x240)==0x55667788u);
    Require(Read<unsigned>(currentModel.data(),0x188)==77777 && Read<unsigned>(currentModel.data(),0x3b0)==0x55667788u);
    // A body/tattoo preview hides held outfit parts without a user deletion.
    // Finish the original reversible preview before copying complete data.
    Write(currentModel.data(),0xbb9,std::uint8_t(1));Write(currentModel.data(),0xb20,0x1234abcdu);
    Write(currentModel.data(),0x3c0,0u);Sync(controller.data());
    Require(previewRestores==1 && Read<std::uint8_t>(currentModel.data(),0xbb9)==0);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x250)==0x1234abcdu);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x18)==77777);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x240)==0x55667788u);
    Sync(controller.data());Require(previewRestores==1); // No second restoration or stale cache replay.
    Require(Read<unsigned>(bank.graph->appearance(1)->data(),0x18)==100 && Read<unsigned>(group.data(),0xe8)==100);
    Require(Read<unsigned>(bank.graph->appearance(4)->data(),0x18)==44444);
    Require(Read<UndoFixture*>(currentModel.data(),0x70)==ghostUndo);
    // Native history may ask for an invalid/composite opposite kind. It must
    // neither replace this same-kind owner nor delete/overwrite the entry form.
    const auto oldRebound=reboundKind;
    for(const auto target:{0u,1u,4u,126u}) {
        Write(group.data(),0xe8,123456u);Rebind(controller.data(),metadata.data(),target);
        Require(Read<unsigned>(group.data(),0xe8)==100 && Read<unsigned>(currentModel.data(),0x188)==77777);
        Require(reboundKind==oldRebound && !bank.viewFault);
    }
    Require(bank.undoOwners.size()==5 && bank.undoOwners.at("active/2")->value!=alienUndo);
    Write(currentModel.data(),0x188,88888u);
    NativeCoreBind(controller.data(),0,false); // Ordinary same-owner refresh retains edits.
    Require(!bank.viewFault && Read<unsigned>(currentModel.data(),0x188)==88888);
    Require(Read<unsigned>(bank.graph->appearance("ghost/manifested")->data(),0x18)==88888);
    for(const auto& row:bank.undoOwners) Require(Read<unsigned>(row.second->value,8)>0);
    // One native model is reused across household members. Even a shared
    // context pointer must never let the incoming member harvest its data.
    runtime.scope.members.emplace(456,Member{456,127});
    Write(proto.data(),0x10,std::uint64_t(456));
    Write(tracker.data(),0x10,126u);
    for(unsigned i=0;i<7;++i) Write(records[i].data(),0x1c,(1u<<i)*100u+1000u);
    auto secondSeed=seed;secondSeed["sim_id"]="456";Require(Control(secondSeed).value("ok",false));
    std::array<char,0x830> secondGroup{};Write(secondGroup.data(),0xb8,std::uint64_t(456));
    Write(secondGroup.data(),0x10,groupInterfaceTable.data());Write(controller.data(),0x100,secondGroup.data());
    NativeCoreBind(controller.data(),1,false);
    Require(runtime.boundSim==456 && Read<unsigned>(currentModel.data(),0x188)==9999);
    Require(NativeUiView(controller.data(),"native/2"));
    Require(Read<unsigned>(currentModel.data(),0x188)==1200);
    Write(currentModel.data(),0x188,456456u);Sync(controller.data());
    Write(controller.data(),0x100,group.data());
    Sync(controller.data()); // A late incoming sync must not write member 456 into member 123.
    NativeCoreBind(controller.data(),0,false);
    Require(runtime.boundSim==123 && Read<unsigned>(currentModel.data(),0x188)==88888);
    Require(NativeUiView(controller.data(),"native/2"));
    Require(Read<unsigned>(currentModel.data(),0x188)==22222 && Read<UndoFixture*>(currentModel.data(),0x70)==alienUndo);
    Require(Read<unsigned>(runtime.bank.at(456).graph->appearance(2)->data(),0x18)==456456);
    // The portrait controls act on the exact bound pair on the UI thread.
    // A late worker response is not needed and cannot authorize another Sim.
    auto& pairChannel=td1::nativecas::pipe::Channel();pairChannel.generation=71;pairChannel.scope=runtime.scope.id;
    pairChannel.connected=true;pairChannel.stop=false;
    Require(FastOwnerState(runtime,70)=="STALE");
    Require(FastOwnerState(runtime,71).rfind("VIEWSTATE|123|native/2|2|0|bound|",0)==0);
    Require(PairState(runtime,71).rfind("PAIR|123|native/2|native/2|native/1|native/1|0|",0)==0);
    const auto humanBeforeLink=Read<unsigned>(bank.graph->appearance("native/1")->data(),0x18);
    const auto vampireBeforeCopy=Read<unsigned>(bank.graph->appearance("native/4")->data(),0x18);
    auto pairCommand=[&](char nonce,const std::string& operation,bool enabled) {
        return std::string(32,nonce)+"|123|"+std::to_string(bank.graph->cursor().generation)+"|native/2|native/1|"+operation+"|"+(enabled?"1":"0");
    };
    const auto linkCommand=pairCommand('a',"link",true);
    Require(ApplyPairAction(runtime,71,linkCommand)=="PAIRDONE|"+std::string(32,'a'));
    Require(bank.graph->linked("native/1","native/2")&&bank.graph->linked("native/2","native/1"));
    Require(Read<unsigned>(bank.graph->appearance("native/1")->data(),0x18)==humanBeforeLink);
    const auto linkedGeneration=bank.graph->cursor().generation;
    Sync(controller.data()); // Status and a no-edit view refresh are not edits.
    Require(!bank.viewFault && bank.graph->cursor().generation==linkedGeneration);
    Require(Read<unsigned>(bank.graph->appearance("native/1")->data(),0x18)==humanBeforeLink);
    Refuses([&]{ApplyPairAction(runtime,71,linkCommand);}); // Original UUID is never replayed.
    Write(currentModel.data(),0x3b0,0xabcdef12u);Sync(controller.data());
    Require(Read<unsigned>(bank.graph->appearance("native/2")->data(),0x240)==0xabcdef12u);
    Require(Read<unsigned>(bank.graph->appearance("native/1")->data(),0x240)==0xabcdef12u);
    Require(Read<unsigned>(bank.graph->appearance("native/4")->data(),0x18)==vampireBeforeCopy);
    Require(ApplyPairAction(runtime,71,pairCommand('b',"link",false))=="PAIRDONE|"+std::string(32,'b'));
    Require(!bank.graph->linked("native/1","native/2")&&!bank.graph->linked("native/2","native/1"));
    Write(currentModel.data(),0x3b0,0xabcdef13u);Sync(controller.data());
    Require(Read<unsigned>(bank.graph->appearance("native/1")->data(),0x240)==0xabcdef12u);
    // Copy has one destination even when it is linked to a third form.
    bank.graph->linkPair(bank.graph->cursor(),"native/1","native/4",true);
    Require(ApplyPairAction(runtime,71,pairCommand('c',"copy",false))=="PAIRDONE|"+std::string(32,'c'));
    Sync(controller.data());
    Require(Read<unsigned>(bank.graph->appearance("native/1")->data(),0x18)==22222);
    Require(Read<unsigned>(bank.graph->appearance("native/4")->data(),0x18)==vampireBeforeCopy);
    Require(bank.graph->cursor().owner=="native/2"&&Read<unsigned>(currentModel.data(),0x188)==22222);
    Require(Read<unsigned>(runtime.bank.at(456).graph->appearance(2)->data(),0x18)==456456);
    Refuses([&]{ParsePairAction(std::string(32,'d')+"|123|1|native/2|native/2|copy|0");});
    Refuses([&]{ParsePairAction(std::string(32,'d')+"|123|1|native/2|native/1|copy|1");});
    Refuses([&]{ParsePairAction(std::string(32,'d')+"|123|1|native/2|native/1|link|1|extra");});
    pairChannel.connected=false;pairChannel.stop=true;
    Require(nativeSyncCalls==0); // Owned forms never enter the destructive two-slot synchronizer.
    runtime.selectionEnabled=false;Sync(controller.data());Require(nativeSyncCalls==1);
    runtime.selectionEnabled=true; // Unscoped CAS keeps the game's ordinary path.
    Free(Read<void*>(secondGroup.data(),0x4c0),0x830);
    Require(controllerCalls==0); // No converter/controller transaction was called.
    Write(argument.data(),8,0x1fffffffu);Require(!SetOccultService(arguments.data())); // No token replay.
    Free(independentChild,0x830);Write(group.data(),0x4c0,static_cast<void*>(nullptr));
    Json retire={{"operation","retire-committed-session"},{"scope_id",scope.id},{"members",Json::array()}};
    for(const auto& row:runtime.scope.members)
        retire["members"].push_back({{"sim_id",std::to_string(row.first)},
            {"generation",runtime.bank.at(row.first).graph->cursor().generation}});
    auto invalidRetire=retire;invalidRetire["members"].erase(0);Refuses([&]{Control(invalidRetire);});
    invalidRetire=retire;invalidRetire["members"][0]["generation"]=
        retire["members"][0]["generation"].get<std::uint64_t>()+1u;
    Refuses([&]{Control(invalidRetire);});Require(runtime.bank.size()==2 && runtime.selectionEnabled);
    {auto& channel=td1::nativecas::pipe::Channel();channel.connected=true;channel.stop=false;
     Refuses([&]{Control(retire);});channel.connected=false;channel.stop=true;}
    const auto retired=Control(retire);
    Require(retired["armed"]==true && retired["selection_enabled"]==false && runtime.bank.empty());
    Require(runtime.sessionsRetired==1 && runtime.uiOwners.empty() && runtime.boundController==nullptr);
    Refuses([&]{Control(retire);});Require(runtime.sessionsRetired==1); // No retirement replay.
    Write(proto.data(),0x10,std::uint64_t(123));
    const auto reopened=Control(seed); // A later checkpoint can import fresh owners in this process.
    Require(reopened.value("ok",false) && runtime.bank.at(123).mask==127 && !runtime.selectionEnabled);
    std::cout<<"Native existing-owner capture and selection contracts passed\n";return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
