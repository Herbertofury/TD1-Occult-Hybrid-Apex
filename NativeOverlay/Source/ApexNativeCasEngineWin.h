// Version-pinned CAS owner import. Cross-kind conversion is quarantined.
// Separate editable owner graphs are captured independently of EA's pair view.
#pragma once
#include "ApexNativeCasEngine.h"
#include "ApexCasOwnerGraph.h"
#include "ApexCasFormPair.h"
#include "ApexCasPairAction.h"
#include "ApexCasHouseholdWire.h"
#include "ApexNativeOwnerMemory.h"
#include "ApexNativeCasProbeWin.h"
#include "ApexCasNativePipeWin.h"
#include "MinHook.h"
#include <mutex>
#include <array>
#include <memory>
#include <malloc.h>
#include <cmath>
#include <intrin.h>
#include <atomic>

namespace td1::nativecas::engine {
using ImportFn=void(*)(void*,const void*);
using FieldsFn=void(*)(void*,const void*,const void*);
using ConstructFn=void*(*)(void*,std::uint64_t);
using DestroyFn=void(*)(void*);
using SetFn=void(*)(void*,std::uint32_t);
using LookupFn=const void*(*)(const void*,std::uint32_t);
using StoreFn=void(*)(void*,std::uint32_t,const void*);
using MetaFn=void*(*)(void*,const void*);
using AllocateFn=void*(*)(std::size_t,void*,std::uint32_t,std::uint32_t,void*,std::uint32_t);
using FreeFn=void(*)(void*,std::size_t);
using TreeDestroyFn=void(*)(void*,void*);
using HistoryFn=void(*)(void*,std::uint32_t);
using ChangeFn=void(*)(void*,std::uint32_t,const void*,const void*,void**,void**);
struct ByteView {const void* data;std::uint64_t length;};
using ProtoConstructFn=void*(*)(void*);
using ProtoParseFn=bool(*)(void*,const ByteView*);
using AlternateFn=std::uint32_t(*)(std::uint32_t,std::uint32_t);
using NormalizeFn=std::uint32_t(*)(void*,bool);
using AssignDataFn=void(*)(void*,const void*);
using ServiceFn=bool(*)(const void*);
using StringValueFn=void(*)(void*,const char*);
using BoolValueFn=void(*)(void*,bool);
using AvatarFn=void*(*)();
using RefreshFn=void(*)(void*);
using RebindFn=void(*)(void*,const void*,std::uint32_t);
using SyncFn=void(*)(void*);
using BindFn=void(*)(void*,bool);
using ModelBindFn=void(*)(void*,const void*,void*,bool);
using CoreBindFn=void(*)(void*,int,bool);
using ContextFn=void*(*)(void*,std::uint64_t,bool);
using IndexFn=int(*)(void*,std::uint64_t);
using LayerFn=void(*)(void*,bool,bool,bool);
using UndoSelectFn=void(*)(void*,std::uint64_t,bool);
using UndoCreateFn=void(*)(void*,std::uint64_t,bool,bool);
using UndoBindFn=void(*)(void*,void**);
using KindMaskFn=std::uint32_t(*)(const void*);
using ExportProtoFn=void(*)(const void*,void*);
using ProtoSizeFn=int(*)(const void*);
using ProtoArrayFn=char*(*)(const void*,char*);
using PreviewFn=void(*)(void*,bool);
using OutfitHairFn=void(*)(void*,const void*);
using AnimationGenusFn=void(*)(void*,const void*,bool);
using PrepareHouseholdFn=void(*)(void*);
inline thread_local const void* detachedTarget=nullptr;
struct DetachedTarget {
    const void* previous;
    explicit DetachedTarget(const void* data):previous(detachedTarget) {detachedTarget=data;}
    ~DetachedTarget() {detachedTarget=previous;}
};
struct Api {
    AnimationGenusFn animationGenus=nullptr;
    OutfitHairFn outfitHair=nullptr;
    ImportFn import=nullptr;FieldsFn fields=nullptr;ConstructFn construct=nullptr;DestroyFn destroy=nullptr;
    SetFn available=nullptr,current=nullptr,availableData=nullptr;LookupFn lookup=nullptr;StoreFn store=nullptr;MetaFn metadata=nullptr;
    AllocateFn allocate=nullptr;FreeFn free=nullptr;TreeDestroyFn treeDestroy=nullptr;
    HistoryFn history=nullptr;ChangeFn change=nullptr;
    ProtoConstructFn protoConstruct=nullptr;DestroyFn protoDestroy=nullptr;ProtoParseFn protoParse=nullptr;
    AlternateFn alternate=nullptr;
    NormalizeFn normalize=nullptr;AssignDataFn assignData=nullptr;MetaFn copySim=nullptr,assignSim=nullptr;
    ServiceFn service=nullptr,getOccultService=nullptr,saveAndExit=nullptr,cancelCas=nullptr;
    StringValueFn stringValue=nullptr;BoolValueFn boolValue=nullptr;
    HistoryFn controller=nullptr;AvatarFn avatar=nullptr;
    RebindFn rebind=nullptr;SyncFn sync=nullptr;BindFn bind=nullptr;
    ModelBindFn modelBind=nullptr;CoreBindFn coreBind=nullptr;ContextFn context=nullptr;IndexFn index=nullptr;LayerFn layer=nullptr;
    UndoSelectFn undoSelect=nullptr;UndoCreateFn undoCreate=nullptr;UndoBindFn undoBind=nullptr;
    KindMaskFn kindMask=nullptr;
    ExportProtoFn exportProto=nullptr;ProtoSizeFn protoSize=nullptr;ProtoArrayFn protoArray=nullptr;
    PreviewFn hairPreview=nullptr,clothingPreview=nullptr,wingsPreview=nullptr;
    PrepareHouseholdFn prepareHousehold=nullptr;
};
inline void Span(const void* value,std::size_t count) {
    const auto start=reinterpret_cast<std::uintptr_t>(value);
    if(start<0x10000 || !count || count>0x100000 || start>0x00007fffffffffffULL-count)
        throw std::runtime_error("Native form record exceeds its bounded address span.");
    std::uintptr_t at=start;
    while(at<start+count) {
        MEMORY_BASIC_INFORMATION region{};
        if(VirtualQuery(reinterpret_cast<const void*>(at),&region,sizeof(region))!=sizeof(region) ||
           region.State!=MEM_COMMIT || (region.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
           region.RegionSize>UINTPTR_MAX-reinterpret_cast<std::uintptr_t>(region.BaseAddress))
            throw std::runtime_error("Native form record is no longer readable.");
        const auto end=reinterpret_cast<std::uintptr_t>(region.BaseAddress)+region.RegionSize;
        if(end<=at) throw std::runtime_error("Native form span does not advance.");
        at=std::min(start+count,end);
    }
}
template<class T> inline T Read(const void* p,std::size_t offset=0) {
    if(!p) throw std::runtime_error("Native form record is null.");
    const auto address=static_cast<const char*>(p)+offset;Span(address,sizeof(T));T value{};std::memcpy(&value,address,sizeof(T));return value;
}
inline std::string UiString(const void* value) {
    if(Read<std::uint32_t>(value)!=6)throw std::runtime_error("Native CAS pipe requires a string value.");
    const auto object=Read<const void*>(value,8);Span(object,16);
    const auto tail=Read<std::uint8_t>(object,15);
    const auto length=(tail&128)?Read<std::uint32_t>(object,8):15u-tail;
    if(!(tail&128)&&tail>15)throw std::runtime_error("Native short string length differs.");
    if(length>pipe::Limit+128)throw std::runtime_error("Native CAS pipe input exceeds its bound.");
    const auto text=(tail&128)?Read<const char*>(object):static_cast<const char*>(object);
    Span(text,length+1);
    if(text[length]!=0)throw std::runtime_error("Native CAS pipe string lacks its exact terminator.");
    return std::string(text,length);
}
struct NativeOwner {
#ifdef APEX_CAS_OWNER_MEMORY_DIAGNOSTICS
    GuardedOwnerMemory memory{0x830};
#endif
    void* value=nullptr;DestroyFn destroy=nullptr;
    NativeOwner(const Api& api,std::uint64_t id):destroy(api.destroy) {
#ifdef APEX_CAS_OWNER_MEMORY_DIAGNOSTICS
        value=memory.get();api.construct(value,id);memory.Validate();
#else
        value=_aligned_malloc(0x830,16);if(!value) throw std::bad_alloc();
        api.construct(value,id);
#endif
    }
    NativeOwner(const Api& api,const NativeOwner& source):destroy(api.destroy) {
#ifdef APEX_CAS_OWNER_MEMORY_DIAGNOSTICS
        value=memory.get();api.copySim(value,source.value);memory.Validate();
#else
        value=_aligned_malloc(0x830,16);if(!value) throw std::bad_alloc();
        api.copySim(value,source.value);
#endif
    }
    NativeOwner(const NativeOwner&)=delete;NativeOwner& operator=(const NativeOwner&)=delete;
    ~NativeOwner() {
        if(value) {
            destroy(value);
#ifndef APEX_CAS_OWNER_MEMORY_DIAGNOSTICS
            _aligned_free(value);
#endif
        }
    }
    const void* data() const {
#ifdef APEX_CAS_OWNER_MEMORY_DIAGNOSTICS
        memory.Validate();
#endif
        return static_cast<const char*>(value)+0xd0;
    }
};
inline std::string SerializeOwner(const Api& api,const NativeOwner& owner,std::uint64_t id) {
    if(!api.exportProto || !api.protoSize || !api.protoArray || !api.protoConstruct || !api.protoDestroy)
        throw std::runtime_error("The pinned native appearance serializer is unavailable.");
    alignas(16) std::array<char,0x400> proto{};api.protoConstruct(proto.data());
    try {
        api.exportProto(owner.value,proto.data());
        if(Read<std::uint64_t>(proto.data(),0x10)!=id)
            throw std::runtime_error("The native appearance serializer changed its Sim identity.");
        const auto size=api.protoSize(proto.data());
        if(size<=0 || size>512*1024)
            throw std::runtime_error("Native appearance bytes exceed the complete snapshot bound.");
        std::vector<char> bytes(static_cast<std::size_t>(size)+32,char(0x5a));
        const auto end=api.protoArray(proto.data(),bytes.data());
        if(end!=bytes.data()+size || !std::all_of(bytes.begin()+size,bytes.end(),[](char v){return v==char(0x5a);}))
            throw std::runtime_error("Native appearance serialization differs from its measured size.");
        std::string result(bytes.data(),static_cast<std::size_t>(size));
        api.protoDestroy(proto.data());return result;
    } catch(...) {api.protoDestroy(proto.data());throw;}
}
inline std::string SerializeMessage(const Api& api,const void* proto) {
    const auto size=api.protoSize(proto);
    if(size<=0 || size>static_cast<int>(wire::Limit))throw std::runtime_error("Native household message exceeds its complete bound.");
    std::vector<char> bytes(static_cast<std::size_t>(size)+32,char(0x5a));
    if(api.protoArray(proto,bytes.data())!=bytes.data()+size ||
       !std::all_of(bytes.begin()+size,bytes.end(),[](char value){return value==char(0x5a);}))
        throw std::runtime_error("Native household message serialization changed its measured size.");
    return std::string(bytes.data(),static_cast<std::size_t>(size));
}
// Native undo contexts use consuming intrusive references. Own one reference
// per exact form, independently of EA's (Sim, primary/alternate) map.
struct NativeUndo {
    void* value=nullptr;
    explicit NativeUndo(void* pointer):value(pointer) {
        if(!value) throw std::runtime_error("The native form has no undo context.");
        const auto count=Read<std::uint32_t>(value,8);
        if(!count || count==UINT32_MAX) throw std::runtime_error("Invalid native undo reference count.");
        const auto retained=count+1;std::memcpy(static_cast<char*>(value)+8,&retained,4);
    }
    NativeUndo(const NativeUndo&)=delete;NativeUndo& operator=(const NativeUndo&)=delete;
    ~NativeUndo() {
        const auto remaining=Read<std::uint32_t>(value,8)-1;
        std::memcpy(static_cast<char*>(value)+8,&remaining,4);
        if(!remaining) {
            const std::uint32_t one=1;std::memcpy(static_cast<char*>(value)+8,&one,4);
            Read<void(*)(void*,int)>(Read<void*>(value))(value,1);
        }
    }
};
struct Imported {
    std::map<std::uint32_t,std::unique_ptr<NativeOwner>> owners;
    std::unique_ptr<NativeOwner> active;
    std::unique_ptr<NativeOwner> syncScratch;
    std::string comparisonOwner,comparisonBytes;
    std::uint64_t comparisonGeneration=0;
    bool comparisonReady=false;
    unsigned scratchAllocations=0,canonicalWrites=0,comparisonBuilds=0,comparisonReuses=0;
    std::unique_ptr<OwnerGraph<std::unique_ptr<NativeOwner>>> graph;
    std::map<std::uint32_t,std::string> logicalOwners;
    std::map<std::string,std::unique_ptr<NativeUndo>> undoOwners;
    bool initialImport=true,viewBound=false,viewFault=false,activeSourceSeeded=false;void* boundGroup=nullptr;void* boundContext=nullptr;std::string entryOwner=NativeOwnerId(1),partner=NativeOwnerId(2),humanOwner=NativeOwnerId(1);std::map<std::string,std::uint32_t> uiTokens;
    std::uint64_t importedEntity=0;bool editorImported=false;ui::Json householdCanonical;
    std::uint32_t mask=0,preferred=0,canonicalSourceMask=0;unsigned imports=0,switches=0,skippedPackets=0;bool seeded=false;std::string error;
};
struct ViewIntent {
    std::string request,owner;std::uint64_t sim=0,generation=0;std::uint32_t token=0;std::uint8_t layer=0;
};
struct PreparedHouseholdRoot {void* group=nullptr;std::uint64_t entity=0,generation=0;};
struct HouseholdCopy {std::uint64_t sim=0,entity=0,generation=0;unsigned depth=0;};
inline std::uint8_t ConfigurePortraitPair(Imported& bank,const std::string& owner) {
    const auto pair=SelectFormPair(bank.humanOwner,owner,
        Read<std::uint32_t>(bank.graph->appearance(owner)->data(),8),{bank.entryOwner,bank.partner,0});
    bank.graph->appearance(pair.base);bank.graph->appearance(pair.alternate);
    bank.entryOwner=pair.base;bank.partner=pair.alternate;return pair.layer;
}
struct State {
    std::recursive_mutex mutex;Api api;Scope scope;std::map<std::uint64_t,Imported> bank;
    ui::Json pairResult=nullptr;std::set<std::string> pairRequests;
    std::unique_ptr<ViewIntent> viewIntent;ui::Json viewResult=nullptr;std::set<std::uint32_t> viewTokens;std::uint64_t nativeUiSequence=0;std::uint32_t nextUiToken=0x20000000;
    std::map<std::uint32_t,std::pair<std::uint64_t,std::string>> uiOwners;
    std::uint64_t boundSim=0;void* boundController=nullptr;
    ui::Json observedNative={{"available",false}};std::uint64_t observationSequence=0;
    unsigned kindBiasPrevented=0,importOutfitFillsPrevented=0,sessionsRetired=0;
    unsigned animationMembershipScopes=0,animationConstructionScopes=0;
    ui::Json lastAnimationScope=nullptr;
    bool acceptingHousehold=false;
    std::uint64_t cancelSerial=0;
    ui::Json householdAcceptance={{"verified",false},{"native_accepted",false}};
    std::map<std::uint64_t,PreparedHouseholdRoot> preparedRoots;
    std::map<const void*,HouseholdCopy> householdCopies;
    std::atomic<bool> householdCopiesEnabled{false};
    void* exportController=nullptr;std::string preparedScope;
    std::uint64_t householdOutputFaults=0;
    std::map<std::pair<std::uintptr_t,std::uint64_t>,ui::Json> householdOutputCalls;
    void* kindRelay=nullptr;std::int32_t originalKindCall=0,patchedKindCall=0;bool kindCallPatched=false,kindRelayReady=false;
    std::uintptr_t image=0;bool installed=false,armed=false,selectionEnabled=false;unsigned intercepted=0,converted=0,alternateOverrides=0,normalizationsPrevented=0,initialOwnersImported=0,serviceSelections=0,rebindCorrections=0,blockedConversions=0;
};
// The DLL remains loaded for the entire process. Never run game destructors
// from CRT/DllMain teardown after the game's native services have gone away.
inline State& Runtime() {static auto* state=new State;return *state;}
inline void ImportOutfitHair(void* outfit,const void* genus,std::uintptr_t caller) {
    auto& state=Runtime();
    // The inspected helper explicitly inserts 0x24236/0x24237 into an outfit
    // without hair. Preserve the complete supplied outfit only in our detached
    // record import; normal loaders and all other call sites stay native.
    if(detachedTarget && caller==state.image+0x3261f7) {
        ++state.importOutfitFillsPrevented;return;
    }
    state.api.outfitHair(outfit,genus);
}
__declspec(noinline) inline void OutfitHair(void* outfit,const void* genus) {
    ImportOutfitHair(outfit,genus,reinterpret_cast<std::uintptr_t>(_ReturnAddress()));
}
struct Selection {std::uint64_t id=0;std::uint32_t target=0;void* controller=nullptr;};
inline thread_local Selection selected;
struct ViewBinding {void* controller=nullptr;Imported* bank=nullptr;std::string owner;};
inline thread_local ViewBinding* binding=nullptr;
inline void RouteAnimationGenus(void* actor,const void* data,bool notify,std::uintptr_t caller) {
    auto& state=Runtime();
    std::array<std::uint32_t,5> preview{};bool scoped=false;
    // These inspected CAS construction/update calls send the model's own
    // 20-byte genus to its idle actor. It derives isWerewolf/isVampire/etc from
    // membership, even when a different form is selected. Narrow only this
    // borrowed animation argument; never change the Sim, model or owner bank.
    const bool constructing=caller==state.image+0x44903a;
    if(state.selectionEnabled && (constructing || caller==state.image+0x45864d)) {
        try {
            std::lock_guard<std::recursive_mutex> lock(state.mutex);
            const auto controller=binding?binding->controller:state.boundController;
            const auto group=controller?Read<void*>(controller,0x100):nullptr;
            const auto model=controller?Read<void*>(controller,0x1d0):nullptr;
            const auto id=group?Read<std::uint64_t>(group,0xb8):0;
            const auto found=state.bank.find(id);
            if(found!=state.bank.end() && found->second.graph && !found->second.viewFault &&
               found->second.boundGroup==group &&
               model && data==static_cast<const char*>(model)+0x170 &&
               actor==Read<void*>(model,0x48) && actor &&
               (binding?binding->bank==&found->second:
                    found->second.viewBound && state.boundSim==id)) {
                auto& bank=found->second;
                const auto& owner=binding?binding->owner:bank.graph->cursor().owner;
                const auto desired=Read<std::uint32_t>(bank.graph->appearance(owner)->data(),8);
                Span(data,sizeof(preview));std::memcpy(preview.data(),data,sizeof(preview));
                if(Kind(desired) && preview[2]==desired && (preview[3]|1u)==bank.mask &&
                   (preview[3]&desired) && preview[3]!=desired) {
                    state.lastAnimationScope={{"sim_id",std::to_string(id)},{"owner_id",owner},
                        {"native_kind",desired},{"original_owned_mask",preview[3]},
                        {"animation_mask",desired},{"werewolf_animation",desired==32},
                        {"source",constructing?"exact-cas-preview-construction":"exact-cas-preview-actor"},{"appearance_written",false},
                        {"membership_written",false}};
                    preview[3]=desired;++state.animationMembershipScopes;scoped=true;
                    if(constructing)++state.animationConstructionScopes;
                }
            }
        } catch(...) {
            // No game call or write has happened. Unrecognized/foreign CAS
            // contexts retain their original argument and native behavior.
            scoped=false;
        }
    }
    state.api.animationGenus(actor,scoped?preview.data():data,notify);
}
__declspec(noinline) inline void AnimationGenus(void* actor,const void* data,bool notify) {
    RouteAnimationGenus(actor,data,notify,reinterpret_cast<std::uintptr_t>(_ReturnAddress()));
}
inline void RefreshBoundAnimation(State& state,Imported& bank,void* controller) {
    // EA can construct its first actor before the independent view is bound.
    // If the model genus then stays identical, its dirty-bit update need not
    // run again. Settle this exact preview at binding completion as well.
    // This changes only the actor's native animation parameters, never CasData.
    try {
        const auto group=Read<void*>(controller,0x100),model=Read<void*>(controller,0x1d0);
        if(!state.selectionEnabled || !bank.graph || bank.viewFault || !group || !model ||
           group!=bank.boundGroup || Read<std::uint64_t>(group,0xb8)!=state.boundSim) return;
        const auto actor=Read<void*>(model,0x48);if(!actor) return;
        const auto& owner=binding?binding->owner:bank.graph->cursor().owner;
        const auto desired=Read<std::uint32_t>(bank.graph->appearance(owner)->data(),8);
        std::array<std::uint32_t,5> preview{};
        const auto data=static_cast<const char*>(model)+0x170;Span(data,sizeof(preview));
        std::memcpy(preview.data(),data,sizeof(preview));
        if(!Kind(desired) || preview[2]!=desired || (preview[3]|1u)!=bank.mask || !(preview[3]&desired)) return;
        std::array<std::uint32_t,5> before{};const auto cache=static_cast<const char*>(actor)+0xc0;
        Span(cache,sizeof(before));std::memcpy(before.data(),cache,sizeof(before));
        if(before[2]==desired && before[3]==desired) return;
        const auto originalMask=preview[3];preview[3]=desired;
        state.api.animationGenus(actor,preview.data(),true);
        ++state.animationMembershipScopes;
        std::array<std::uint32_t,5> observed{};Span(cache,sizeof(observed));std::memcpy(observed.data(),cache,sizeof(observed));
        state.lastAnimationScope={{"sim_id",std::to_string(state.boundSim)},{"owner_id",owner},
            {"native_kind",desired},{"original_owned_mask",originalMask},{"animation_mask",desired},
            {"werewolf_animation",desired==32},{"source","exact-cas-preview-bind"},
            {"actor_cache_verified",observed[2]==desired && observed[3]==desired},
            {"appearance_written",false},{"membership_written",false}};
    } catch(const std::exception& error) {
        // Optional preview settlement cannot discard an otherwise intact Sim.
        // In particular, never replay an issued native animation update.
        state.lastAnimationScope={{"source","exact-cas-preview-bind"},{"verified",false},
            {"error",error.what()},{"appearance_written",false},{"membership_written",false}};
    }
}
inline std::uint32_t ModelKindMask(const void* data,std::uint32_t observed,std::uintptr_t caller) {
    auto& state=Runtime();
    if(!state.selectionEnabled || !(observed&4u) || caller!=state.image+0x45c32c) return observed;
    std::lock_guard<std::recursive_mutex> lock(state.mutex);
    const auto controller=binding?binding->controller:state.boundController;
    const auto group=controller?Read<void*>(controller,0x100):nullptr;
    const auto id=group?Read<std::uint64_t>(group,0xb8):0;const auto found=state.bank.find(id);
    if(found==state.bank.end() || !found->second.graph || found->second.viewFault ||
       (!binding && (!found->second.viewBound || state.boundSim!=id))) return observed;
    auto& bank=found->second;
    if(binding && binding->bank!=&bank) return observed;
    const auto& owner=binding?binding->owner:bank.graph->cursor().owner;
    const auto desired=Read<std::uint32_t>(bank.graph->appearance(owner)->data(),8);
    if(desired==4 || Read<std::uint32_t>(data,8)!=desired || (observed|1u)!=bank.mask) return observed;
    // This single inspected caller uses the getter ONLY to force Vampire into
    // a temporary rendering-genus header. Keep the real membership everywhere
    // else; this local test must respect the selected independent owner.
    ++state.kindBiasPrevented;return observed&~4u;
}
__declspec(noinline) inline std::uint32_t KindMask(const void* data) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    return ModelKindMask(data,Runtime().api.kindMask(data),caller);
}
inline void KindCallOperand(void* site,std::int32_t expected,std::int32_t desired) {
    auto* operand=reinterpret_cast<volatile LONG*>(static_cast<char*>(site)+1);
    if(reinterpret_cast<std::uintptr_t>(operand)%alignof(LONG) || Read<std::uint8_t>(site)!=0xe8)
        throw std::runtime_error("The inspected native mask call is not an aligned rel32 CALL.");
    DWORD previous=0;
    if(!VirtualProtect(const_cast<LONG*>(operand),sizeof(LONG),PAGE_EXECUTE_READWRITE,&previous))
        throw std::runtime_error("Cannot update the owned rendering call operand.");
    const auto found=InterlockedCompareExchange(operand,desired,expected);
    FlushInstructionCache(GetCurrentProcess(),site,5);
    DWORD ignored=0;const bool restored=VirtualProtect(const_cast<LONG*>(operand),sizeof(LONG),previous,&ignored)!=0;
    if(found!=expected || !restored) throw std::runtime_error("The rendering call changed or its page protection could not be restored.");
}
inline void InstallKindCall(State& state) {
    auto* site=reinterpret_cast<char*>(state.image+0x45c327);
    state.originalKindCall=Read<std::int32_t>(site,1);
    if(state.image+0x45c32c+state.originalKindCall!=state.image+0x297630)
        throw std::runtime_error("The inspected model call no longer targets its native mask getter.");
    if(state.kindRelayReady) {
        try {KindCallOperand(site,state.originalKindCall,state.patchedKindCall);}
        catch(...) {state.kindCallPatched=Read<std::int32_t>(site,1)==state.patchedKindCall;throw;}
        state.kindCallPatched=true;return;
    }
    state.kindRelay=nullptr; // An earlier unsealed allocation was never executable.
    SYSTEM_INFO system{};GetSystemInfo(&system);
    const auto step=static_cast<std::uintptr_t>(system.dwAllocationGranularity);
    const auto origin=reinterpret_cast<std::uintptr_t>(site)&~(step-1);
    // One near relay keeps the replacement CALL within rel32 range. The shared
    // leaf getter remains untouched: no global per-frame detour or extra lock.
    for(std::uintptr_t distance=step;!state.kindRelay && distance<0x7ffe0000;distance+=step) {
        for(const auto candidate:{origin>distance?origin-distance:0,origin+distance}) {
            if(candidate<0x10000 || candidate>0x00007ffffffeffffULL) continue;
            const auto delta=static_cast<std::int64_t>(candidate)-static_cast<std::int64_t>(state.image+0x45c32c);
            if(delta<INT32_MIN || delta>INT32_MAX) continue;
            MEMORY_BASIC_INFORMATION region{};
            if(VirtualQuery(reinterpret_cast<void*>(candidate),&region,sizeof(region))!=sizeof(region) || region.State!=MEM_FREE) continue;
            state.kindRelay=VirtualAlloc(reinterpret_cast<void*>(candidate),4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
            if(state.kindRelay) {state.patchedKindCall=static_cast<std::int32_t>(delta);break;}
        }
    }
    if(!state.kindRelay) throw std::runtime_error("No bounded near relay is available for the rendering call.");
    std::array<unsigned char,14> jump{{0xff,0x25,0,0,0,0}};
    const auto target=reinterpret_cast<std::uintptr_t>(&KindMask);std::memcpy(jump.data()+6,&target,8);
    std::memcpy(state.kindRelay,jump.data(),jump.size());DWORD old=0;
    if(!VirtualProtect(state.kindRelay,4096,PAGE_EXECUTE_READ,&old))
        throw std::runtime_error("Cannot seal the rendering relay as executable/read-only.");
    FlushInstructionCache(GetCurrentProcess(),state.kindRelay,jump.size());
    state.kindRelayReady=true;
    // The displacement is aligned, stays within one instruction-fetch block,
    // and changes atomically. Readers can execute either complete valid CALL.
    try {KindCallOperand(site,state.originalKindCall,state.patchedKindCall);}
    catch(...) {state.kindCallPatched=Read<std::int32_t>(site,1)==state.patchedKindCall;throw;}
    state.kindCallPatched=true;
}
inline void RestoreKindCall(State& state) {
    if(state.kindCallPatched) {
        KindCallOperand(reinterpret_cast<void*>(state.image+0x45c327),state.patchedKindCall,state.originalKindCall);
        state.kindCallPatched=false;
    }
    // Keep any installed relay allocation alive for the process: a thread may
    // still be returning from a call issued just before an atomic rollback.
}
inline void SelectUndo(void* controller,std::uint64_t entity,bool layer) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    const auto group=Read<void*>(controller,0x100);const auto id=group?Read<std::uint64_t>(group,0xb8):0;
    const auto at=state.bank.find(id);
    if(!state.selectionEnabled || at==state.bank.end() ||
       (!at->second.viewBound && (!binding || binding->controller!=controller))) {
        state.api.undoSelect(controller,entity,layer);return;
    }
    auto& bank=at->second;const auto owner=binding && binding->controller==controller?
        binding->owner:bank.graph->cursor().owner;
    const auto model=Read<void*>(controller,0x1d0);
    if(!model || group!=bank.boundGroup || bank.viewFault)
        throw std::runtime_error("Undo selection lost its exact native form owner.");
    const auto prior=bank.undoOwners.find(owner);
    if(prior==bank.undoOwners.end()) {
        // The original factory creates a new context even when this physical
        // layer was used by another form. Never borrow that layer's old stack.
        state.api.undoCreate(controller,entity,layer,true);
        auto saved=std::make_unique<NativeUndo>(Read<void*>(model,0x70));
        for(const auto& row:bank.undoOwners) if(row.second->value==saved->value)
            throw std::runtime_error("Native forms unexpectedly share an undo context.");
        bank.undoOwners.emplace(owner,std::move(saved));
    } else {
        void* consumed=prior->second->value;
        const auto retained=Read<std::uint32_t>(consumed,8)+1;
        std::memcpy(static_cast<char*>(consumed)+8,&retained,4);
        state.api.undoBind(model,&consumed);
        if(Read<void*>(model,0x70)!=prior->second->value)
            throw std::runtime_error("Native undo binding selected another form's history.");
    }
}
inline std::uint64_t GroupId(void* group) {
    using IdFn=std::uint64_t(*)(void*);
    return Read<IdFn>(Read<void*>(static_cast<char*>(group)+0x10))(static_cast<char*>(group)+0x10);
}
inline const std::unique_ptr<NativeOwner>& CloneModel(State& state,Imported& bank,void* controller) {
    const auto model=Read<void*>(controller,0x1d0);
    if(!bank.syncScratch) {bank.syncScratch=std::make_unique<NativeOwner>(state.api,bank.graph->cursor().sim);++bank.scratchAllocations;}
    const auto& copy=bank.syncScratch;
    state.api.assignData(const_cast<void*>(copy->data()),static_cast<char*>(model)+0x170);
    state.api.current(copy->value,bank.graph->cursor().kind);
    state.api.availableData(const_cast<void*>(copy->data()),bank.mask);return copy;
}
inline void StoreCanonical(State& state,Imported& bank,void* controller) {
    using CacheFn=void*(*)(void*,std::uint64_t);
    const auto group=Read<void*>(controller,0x100);
    auto* metadata=Read<CacheFn>(Read<void*>(controller),0x410)(controller,GroupId(group));
    if(!metadata) throw std::runtime_error("Native view lacks its complete appearance cache.");
    // EA and other mods can write this cache without advancing our graph.
    // A matching pointer/generation alone cannot authorize skipping its repair.
    for(const auto& owner:bank.owners)
        state.api.store(metadata,owner.first,bank.graph->appearance(bank.logicalOwners.at(owner.first))->data());
    ++bank.canonicalWrites;
}
inline const std::string& ComparisonBytes(State& state,Imported& bank) {
    const auto cursor=bank.graph->cursor();
    // These detached graph records are owned exclusively by Apex. Every graph
    // edit, link, copy and selection advances its generation. Cache only this
    // immutable baseline, never the mutable EA model or its canonical cache.
    if(!bank.comparisonReady || bank.comparisonGeneration!=cursor.generation || bank.comparisonOwner!=cursor.owner) {
        auto bytes=SerializeOwner(state.api,*bank.graph->appearance(cursor.owner),cursor.sim);
        bank.comparisonBytes=std::move(bytes);bank.comparisonOwner=cursor.owner;
        bank.comparisonGeneration=cursor.generation;bank.comparisonReady=true;++bank.comparisonBuilds;
    } else ++bank.comparisonReuses;
    return bank.comparisonBytes;
}
inline void FinishPreview(State& state,void* controller) {
    const auto model=Read<void*>(controller,0x1d0);
    if(!model || !state.api.hairPreview || !state.api.clothingPreview || !state.api.wingsPreview)
        throw std::runtime_error("Native appearance synchronization lacks its inspected preview cleanup.");
    // These are the stock synchronizer's three reversible preview operations,
    // not its outfit/genetics regeneration or cross-layer copying. Tattoo/body
    // panels temporarily remove actual outfit rows and hold them in the model;
    // copying that preview directly would persist missing clothes. Restore the
    // current owner's held rows before harvesting, then bind another owner.
    if(!Read<std::uint8_t>(model,0xa60)) state.api.hairPreview(model,true);
    if(Read<std::uint8_t>(model,0xbb9)) state.api.clothingPreview(model,false);
    if(Read<std::uint32_t>(model,0x178)==64 && !Read<std::uint8_t>(model,0xbba))
        state.api.wingsPreview(model,true);
}
// Called only inside native CAS callbacks while the engine owns these objects.
// Source/socket workers may read the copied observation, never controller,
// group or model pointers whose lifetime is outside our mutex.
inline void ObserveSelected(State& state,void* controller) {
    state.observedNative={{"available",false}};
    const auto group=Read<void*>(controller,0x100);
    if(!group) return;
    const auto id=Read<std::uint64_t>(group,0xb8);const auto layer=Read<std::uint8_t>(controller,0x242);
    const auto view=layer?Read<void*>(group,0x4c0):group;const auto model=Read<void*>(controller,0x1d0);
    if(layer>1 || !view || !model || !state.scope.members.count(id)) return;
    const auto kind=Read<std::uint32_t>(view,0xd8);
    if(!Kind(kind)) return;
    if(state.observationSequence==UINT64_MAX) throw std::runtime_error("Native observation sequence is exhausted.");
    state.observedNative={{"available",true},{"sim_id",std::to_string(id)},{"occult_type",kind},
        {"all_occult_types",Read<std::uint32_t>(view,0xdc)},{"layer",layer},
        {"model_occult_type",Read<std::uint32_t>(model,0x178)},
        {"model_all_occult_types",Read<std::uint32_t>(model,0x17c)},
        {"model_cache_present",Read<void*>(model,0x518)!=nullptr},
        {"model_avatar_present",Read<void*>(model,0x520)!=nullptr},
        {"source","native-cas-callback-observation"},{"observation_sequence",++state.observationSequence}};
}
inline void Sync(void* controller) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(binding && binding->controller==controller) return; // Never harvest a half-bound view.
    const auto group=Read<void*>(controller,0x100);const auto id=group?Read<std::uint64_t>(group,0xb8):0;
    const auto at=state.bank.find(id);
    if(at!=state.bank.end() && at->second.viewFault) return;
    if(!state.selectionEnabled || at==state.bank.end() || !at->second.viewBound) {state.api.sync(controller);return;}
    if(state.boundSim!=id || state.boundController!=controller) return; // The incoming member cannot harvest the outgoing model.
    auto& bank=at->second;
    try {
        if(bank.boundGroup!=group || !bank.graph) throw std::runtime_error("Native CAS changed its bound form owner.");
        const auto layer=Read<std::uint8_t>(controller,0x242);
        const auto inactive=layer?group:Read<void*>(group,0x4c0);
        FinishPreview(state,controller);
        // CAS setters have already written the selected model's complete
        // CasData. The stock two-slot synchronizer is not a serializer: it
        // changes preview modes, regenerates outfit/genetic parts and copies
        // fields to the other layer. A real Fairy round trip changed every
        // outfit's four body-hair swatches without an edit. Persist the actual
        // current model through the game's deep-copy API instead. No prior
        // appearance, field whitelist or regenerated outfit is substituted.
        const auto& edited=CloneModel(state,bank,controller);
        const auto selected=layer?Read<void*>(group,0x4c0):group;
        if(!selected) throw std::runtime_error("Selected native form has no exact appearance slot.");
        state.api.assignData(static_cast<char*>(selected)+0xd0,edited->data());
        // Reading CAS information and rebinding a view also enter Sync. They
        // are not user edits: committing identical data would copy the entire
        // source through a newly enabled link, or relay a directed Copy into
        // that destination's other links. Compare complete native serialized
        // records, including opaque/future fields; never compare pointer bytes
        // or a subset of appearance fields.
        const auto cursor=bank.graph->cursor();
        if(SerializeOwner(state.api,*edited,id)!=ComparisonBytes(state,bank))
            bank.graph->commit(cursor,edited);
        // The explicit graph, not EA's copied inactive fields, owns the other
        // form. This also honors intentional links while keeping defaults apart.
        if(inactive) state.api.assignData(static_cast<char*>(inactive)+0xd0,
            bank.graph->appearance(layer?bank.entryOwner:bank.partner)->data());
        StoreCanonical(state,bank,controller);
        ObserveSelected(state,controller);
    } catch(const std::exception& error) {
        state.observedNative={{"available",false}};
        bank.viewFault=true;state.viewResult={{"state","unresolved"},{"sim_id",std::to_string(id)},
            {"message",error.what()},{"native_sync_blocked",true}};
    }
}

struct NativePacket {
    const Api& api;alignas(16) std::array<char,0x400> data{};
    explicit NativePacket(const Api& functions):api(functions) {api.protoConstruct(data.data());}
    ~NativePacket() {api.protoDestroy(data.data());}
    NativePacket(const NativePacket&)=delete;
};
struct HouseholdRootTarget {std::uint64_t sim;void* group;Imported* bank;};
inline std::vector<HouseholdRootTarget> EditorHouseholdRoots(State& state,void* controller) {
    // Same bounded list/entity lookup as the pinned native index service.
    // Resolve every group now: never retain a CAS object across transitions.
    const auto sentinel=static_cast<char*>(controller)+0x108;
    auto* node=Read<void*>(sentinel);std::set<void*> nodes;std::set<std::uint64_t> entities;
    std::map<std::uint64_t,void*> groups;
    while(node!=sentinel) {
        if(nodes.size()>=8 || !nodes.insert(node).second)throw std::runtime_error("CAS household list is cyclic or exceeds eight members.");
        auto* group=Read<void*>(node,0x10);const auto entity=GroupId(group);
        const auto sim=Read<std::uint64_t>(group,0xb8);
        if(!entity || !entities.insert(entity).second || !groups.emplace(sim,group).second)
            throw std::runtime_error("CAS household groups have duplicate identities.");
        node=Read<void*>(node);
    }
    std::vector<HouseholdRootTarget> targets;
    for(auto& row:state.bank)if(row.second.editorImported) {
        auto at=groups.find(row.first);
        if(at==groups.end() || GroupId(at->second)!=row.second.importedEntity ||
           !state.scope.members.count(row.first) || !row.second.graph || !row.second.seeded || row.second.viewFault)
            throw std::runtime_error("CAS household root lacks its exact captured entity and graph.");
        targets.push_back({row.first,at->second,&row.second});
    }
    return targets;
}
inline std::string ProjectHouseholdPacket(State& state,const HouseholdRootTarget& target,const std::string& packet) {
    auto& bank=*target.bank;
    if(!bank.graph || !bank.seeded || bank.viewFault || bank.graph->cursor().sim!=target.sim ||
       Read<std::uint64_t>(target.group,0xb8)!=target.sim)
        throw std::runtime_error("CAS output projection lacks its exact independent owner.");
    std::map<std::uint32_t,std::string> owners;
    for(const auto& owner:bank.logicalOwners)
        owners.emplace(owner.first,SerializeOwner(state.api,*bank.graph->appearance(owner.second),target.sim));
    std::string active;
    if(!bank.viewBound) {
        if(!bank.active)throw std::runtime_error("Unselected CAS output has no captured active owner.");
        active=owners.at(Read<std::uint32_t>(bank.active->data(),8));
    }
    return wire::Household(packet,target.sim,bank.mask,owners,bank.viewBound?nullptr:&active);
}
inline std::string CheckedHouseholdPacket(State& state,const std::string& projected) {
    NativePacket checked(state.api);const ByteView input{projected.data(),projected.size()};
    if(!state.api.protoParse(checked.data.data(),&input))throw std::runtime_error("Game parser rejected a projected CAS output.");
    const auto result=SerializeMessage(state.api,checked.data.data());
    if(!wire::Equivalent(projected,result))throw std::runtime_error("Game parser changed a projected or unrelated CAS output field.");
    return result;
}
inline void CanonicalizeHouseholdRoots(State& state,const std::vector<HouseholdRootTarget>& targets) {
    // Preflight every packet. Native CAS roots/children cannot themselves hold
    // every independent form: EA's exporter regenerates records from its pair.
    // Apply the projection only to the final serialized output below.
    state.householdCopiesEnabled.store(false,std::memory_order_release);state.householdCopies.clear();
    state.preparedRoots.clear();state.preparedScope.clear();state.exportController=nullptr;state.householdOutputCalls.clear();
    std::set<std::uint64_t> identities;std::set<void*> groups;
    std::map<std::uint64_t,PreparedHouseholdRoot> prepared;
    for(const auto& target:targets) {
        const auto found=state.bank.find(target.sim);
        if(found==state.bank.end() || &found->second!=target.bank || !state.scope.members.count(target.sim) ||
           target.bank->mask!=state.scope.members.at(target.sim).mask || !identities.insert(target.sim).second ||
           !groups.insert(target.group).second)
            throw std::runtime_error("CAS output preparation contains a duplicate or foreign member.");
        target.bank->householdCanonical={{"verified",false},{"prepared",false}};
        if(!IndependentHybridGenus(target.bank->mask,Read<std::uint32_t>(target.group,0xd8)))continue;
        NativePacket before(state.api);state.api.exportProto(target.group,before.data.data());
        CheckedHouseholdPacket(state,ProjectHouseholdPacket(state,target,SerializeMessage(state.api,before.data.data())));
        prepared.emplace(target.sim,PreparedHouseholdRoot{target.group,target.bank->importedEntity,target.bank->graph->cursor().generation});
    }
    state.preparedRoots=std::move(prepared);state.preparedScope=state.scope.id;
    for(const auto& row:state.preparedRoots)state.bank.at(row.first).householdCanonical={
        {"verified",false},{"prepared",true},{"scope_id",state.scope.id},{"generation",row.second.generation},
        {"native_root_memory_written",false},{"other_sim_graphs_written",false}};
}
inline void PrepareHouseholdRoots(void* controller) {
    auto& state=Runtime();CanonicalizeHouseholdRoots(state,EditorHouseholdRoots(state,controller));state.exportController=controller;
    state.householdCopiesEnabled.store(!state.preparedRoots.empty(),std::memory_order_release);
}
inline bool HouseholdScopeCurrent(const State& state) {
    return state.armed && state.selectionEnabled && state.preparedScope==state.scope.id &&
        (state.acceptingHousehold || (state.householdAcceptance.value("verified",false) && state.householdAcceptance.value("native_accepted",false)));
}
inline void ObserveHouseholdCopy(State& state,const void* destination,const void* source) {
    if(destination==source)return;
    // Assignment or storage reuse always revokes the destination's old proof.
    state.householdCopies.erase(destination);
    if(!HouseholdScopeCurrent(state))return;
    HouseholdCopy proof;bool found=false;
    const auto inherited=state.householdCopies.find(source);
    if(inherited!=state.householdCopies.end()) {proof=inherited->second;found=true;}
    else if(state.acceptingHousehold)for(const auto& root:state.preparedRoots)if(root.second.group==source) {
        proof={root.first,root.second.entity,root.second.generation,0};found=true;break;
    }
    if(!found)return;
    const auto root=state.preparedRoots.find(proof.sim);const auto bank=state.bank.find(proof.sim);
    if(root==state.preparedRoots.end() || bank==state.bank.end() || !bank->second.graph || bank->second.viewFault ||
       root->second.entity!=proof.entity || root->second.generation!=proof.generation ||
       bank->second.graph->cursor().generation!=proof.generation || proof.depth>=16 ||
       Read<std::uint64_t>(source,0xb8)!=proof.sim || Read<std::uint64_t>(destination,0xb8)!=proof.sim ||
       GroupId(const_cast<void*>(source))!=proof.entity || GroupId(const_cast<void*>(destination))!=proof.entity)
        return;
    if(state.householdCopies.size()>=128)throw std::runtime_error("CAS copy provenance exceeds its bounded lifetime set.");
    ++proof.depth;state.householdCopies.emplace(destination,proof);
}
inline void RecordHouseholdCopy(const void* destination,const void* source) {
    auto& state=Runtime();if(!state.householdCopiesEnabled.load(std::memory_order_acquire))return;
    std::lock_guard<std::recursive_mutex> lock(state.mutex);
    try {ObserveHouseholdCopy(state,destination,source);}
    catch(const std::exception&) {
        state.householdCopies.erase(destination);
        if(state.householdOutputFaults!=UINT64_MAX)++state.householdOutputFaults;
        state.householdAcceptance["verified"]=false;
    }
}
inline void* HouseholdCopyConstruct(void* destination,const void* source) {
    auto& state=Runtime();auto* result=state.api.copySim(destination,source);
    RecordHouseholdCopy(destination,source);return result;
}
inline void* HouseholdCopyAssign(void* destination,const void* source) {
    auto& state=Runtime();auto* result=state.api.assignSim(destination,source);
    RecordHouseholdCopy(destination,source);return result;
}
inline void ForgetHouseholdObject(State& state,const void* value) {
    state.householdCopies.erase(value);
    for(const auto& root:state.preparedRoots)if(root.second.group==value) {
        // A reused address is not a continuation of a prepared editor entity.
        state.householdCopiesEnabled.store(false,std::memory_order_release);state.householdCopies.clear();
        state.preparedRoots.clear();state.preparedScope.clear();state.exportController=nullptr;
        if(state.householdOutputFaults!=UINT64_MAX)++state.householdOutputFaults;
        state.householdAcceptance["verified"]=false;break;
    }
}
inline void HouseholdCopyDestroy(void* value) {
    auto& state=Runtime();
    if(state.householdCopiesEnabled.load(std::memory_order_acquire)) {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);ForgetHouseholdObject(state,value);
    }
    state.api.destroy(value);
}
inline void ProjectHouseholdOutput(State& state,const void* source,void* proto,void* controller) {
    if(!HouseholdScopeCurrent(state))return;
    auto target=state.preparedRoots.end();
    for(auto at=state.preparedRoots.begin();at!=state.preparedRoots.end();++at)if(at->second.group==source) {target=at;break;}
    const auto copied=state.householdCopies.find(source);
    if(target==state.preparedRoots.end() && copied!=state.householdCopies.end()) {
        target=state.preparedRoots.find(copied->second.sim);
        if(target!=state.preparedRoots.end() && (target->second.entity!=copied->second.entity ||
           target->second.generation!=copied->second.generation))return;
    }
    if(target==state.preparedRoots.end())return; // Unrelated Live/save objects have no copy provenance.
    auto& bank=state.bank.at(target->first);std::string original;bool attempted=false;
    try {
        if(!controller || controller!=state.exportController || !bank.graph || bank.viewFault ||
           bank.graph->cursor().generation!=target->second.generation)
            throw std::runtime_error("CAS output scope, controller or accepted owner generation changed.");
        const auto roots=EditorHouseholdRoots(state,controller);
        const auto current=std::find_if(roots.begin(),roots.end(),[&](const auto& root) {
            return root.sim==target->first && root.group==target->second.group && GroupId(root.group)==target->second.entity;
        });
        if(current==roots.end())throw std::runtime_error("CAS output source is no longer the exact imported household entity.");
        if(Read<std::uint64_t>(source,0xb8)!=target->first || GroupId(const_cast<void*>(source))!=target->second.entity)
            throw std::runtime_error("CAS output copy changed its native Sim or entity identity.");
        original=SerializeMessage(state.api,proto);
        const auto checked=CheckedHouseholdPacket(state,ProjectHouseholdPacket(state,*current,original));
        const ByteView input{checked.data(),checked.size()};attempted=true;
        if(!state.api.protoParse(proto,&input))throw std::runtime_error("Native output rejected its validated independent forms.");
        const auto actual=SerializeMessage(state.api,proto);
        if(!wire::Equivalent(checked,actual)) {
            auto differences=ui::Json::array();
            for(const auto& delta:wire::Differences(checked,actual))differences.push_back({
                {"path",delta.path},{"expected_bytes",delta.expected.size()},{"actual_bytes",delta.actual.size()},
                {"expected_sha256",resource::HashBytes(delta.expected)},{"actual_sha256",resource::HashBytes(delta.actual)}});
            bank.householdCanonical["differences"]=differences;
            throw std::runtime_error("Native output changed a projected or unrelated field on readback.");
        }
        bank.householdCanonical={{"prepared",true},{"verified",true},{"scope_id",state.scope.id},{"generation",target->second.generation},
            {"source","exact-cas-household-serialized-output"},{"native_forms",bank.logicalOwners.size()},
            {"copied_output",copied!=state.householdCopies.end()},{"copy_depth",copied==state.householdCopies.end()?0:copied->second.depth},
            {"unselected_active_replaced",!bank.viewBound},{"native_root_memory_written",false},
            {"other_sim_graphs_written",false},{"before_sha256",resource::HashBytes(original)},{"after_sha256",resource::HashBytes(checked)}};
    }catch(const std::exception& error) {
        bool restored=!attempted;
        if(attempted && !original.empty()) {
            try {const ByteView before{original.data(),original.size()};
                 restored=state.api.protoParse(proto,&before) && wire::Equivalent(original,SerializeMessage(state.api,proto));}
            catch(...) {restored=false;}
        }
        const auto differences=bank.householdCanonical.value("differences",ui::Json::array());
        bank.householdCanonical={{"prepared",true},{"verified",false},{"scope_id",state.scope.id},
            {"generation",target->second.generation},{"message",error.what()},{"original_output_restored",restored},
            {"native_root_memory_written",false},{"other_sim_graphs_written",false},{"differences",differences}};
        if(state.householdOutputFaults!=UINT64_MAX)++state.householdOutputFaults;
        state.householdAcceptance["verified"]=false;
    }
}
inline void HouseholdOutput(const void* source,void* proto) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    auto& state=Runtime();state.api.exportProto(source,proto);
    std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(state.preparedRoots.empty())return;
    void* controller=nullptr;
    try {if(state.image)controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));}
    catch(const std::exception&) {}
    try {
        const auto id=Read<std::uint64_t>(source,0xb8);
        if(state.scope.members.count(id) && caller>=state.image && caller-state.image<0x4000000 &&
           (state.acceptingHousehold || state.householdAcceptance.value("native_accepted",false))) {
            const auto key=std::make_pair(caller-state.image,id);auto at=state.householdOutputCalls.find(key);
            if(at!=state.householdOutputCalls.end() || state.householdOutputCalls.size()<64) {
                auto& trace=state.householdOutputCalls[key];if(!trace.is_object())trace=ui::Json::object();
                const auto count=trace.value("calls",std::uint64_t(0));trace["calls"]=count==UINT64_MAX?count:count+1;
                trace["return_rva"]=key.first;trace["sim_id"]=std::to_string(id);
                const auto root=state.preparedRoots.find(id);
                trace["source_matches_prepared_root"]=root!=state.preparedRoots.end() && root->second.group==source;
                trace["source_has_copy_provenance"]=state.householdCopies.count(source)!=0;
                trace["source_matches_prepared_entity"]=root!=state.preparedRoots.end() && GroupId(const_cast<void*>(source))==root->second.entity;
                trace["controller_matches"]=controller && controller==state.exportController;
                trace["during_acceptance"]=state.acceptingHousehold;
            }
        }
    }catch(const std::exception&) {}
    ProjectHouseholdOutput(state,source,proto,controller);
}
inline bool SaveAndExit(const void* argument) {
    auto& state=Runtime();std::string scope;unsigned session=0;std::uint64_t cancel=0,outputFaults=0;
    ui::Json generations=ui::Json::object();std::size_t caches=0;
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        const auto controller=(state.armed && state.selectionEnabled && state.image)?
            Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00)):nullptr;
        const auto group=controller?Read<void*>(controller,0x100):nullptr;
        const auto id=group?Read<std::uint64_t>(group,0xb8):0;
        if(state.armed && state.selectionEnabled && state.scope.members.count(id)) {
            if(state.acceptingHousehold) {
                state.api.boolValue(Read<void*>(argument,0x10),false);return true;
            }
            state.householdAcceptance={{"verified",false},{"native_accepted",false}};
            try {
                auto& selectedBank=state.bank.at(id);
                if(binding || !selectedBank.viewBound || selectedBank.viewFault ||
                   state.boundSim!=id || state.boundController!=controller || selectedBank.boundGroup!=group)
                    throw std::runtime_error("CAS acceptance lacks its exact settled selected model.");
                Sync(controller);
                if(selectedBank.viewFault)throw std::runtime_error("CAS acceptance could not retain the current edit.");
                using CacheFn=void*(*)(void*,std::uint64_t);
                const auto getCache=Read<CacheFn>(Read<void*>(controller),0x410);
                struct Target {std::uint64_t sim;void* metadata;Imported* bank;};
                std::vector<Target> targets;std::set<int> indices;std::set<void*> metadataOwners;
                for(const auto& member:state.scope.members) {
                    auto& bank=state.bank.at(member.first);
                    if(!bank.seeded || !bank.graph || bank.graph->cursor().sim!=member.first ||
                       bank.graph->mask()!=member.second.mask || bank.viewFault)
                        throw std::runtime_error("CAS acceptance lacks a complete captured household member.");
                    generations[std::to_string(member.first)]=bank.graph->cursor().generation;
                    // A single-member editor can leave captured companions
                    // unmaterialized. Never manufacture or select their UI.
                    if(!bank.editorImported)continue;
                    if(!bank.importedEntity)throw std::runtime_error("Imported CAS entity identity remains unavailable.");
                    const auto index=state.api.index(controller,bank.importedEntity);
                    if(index<0 || index>7 || !indices.insert(index).second)
                        throw std::runtime_error("Imported CAS household entity is stale or duplicated.");
                    auto* metadata=getCache(controller,bank.importedEntity);
                    if(!metadata && bank.mask==1)continue;
                    if(!metadata || !metadataOwners.insert(metadata).second)
                        throw std::runtime_error("CAS household appearance caches are absent or aliased.");
                    targets.push_back({member.first,metadata,&bank});
                }
                if(!selectedBank.importedEntity)throw std::runtime_error("Selected CAS entity lacks its original import identity.");
                // The normal current-view Sync covers only one Sim. Settle
                // every materialized member's canonical cache without moving
                // selection, constructing outfits or changing another graph.
                for(const auto& target:targets) {
                    auto& bank=*target.bank;
                    for(const auto& owner:bank.owners) {
                        const auto& source=bank.graph->appearance(bank.logicalOwners.at(owner.first));
                        state.api.store(target.metadata,owner.first,source->data());
                        const auto copied=state.api.lookup(target.metadata,owner.first);
                        if(!copied)throw std::runtime_error("Canonical CAS acceptance cache lost a form.");
                        // Compare the copied AppearanceData in the same full
                        // serialization context. A model-sync scratch has a
                        // different constructed Sim shell; its unrelated root
                        // metadata cannot prove a cache copy lost a field.
                        // Retain every source byte outside AppearanceData and
                        // replace only that data through the inspected API.
                        NativeOwner witness(state.api,*source);
                        state.api.assignData(const_cast<void*>(witness.data()),copied);
                        const auto expected=SerializeOwner(state.api,*source,target.sim);
                        const auto actual=SerializeOwner(state.api,witness,target.sim);
                        if(actual!=expected) {
                            state.householdAcceptance={{"cache_failure",{{"sim_id",std::to_string(target.sim)},
                                {"native_kind",owner.first},{"expected_sha256",resource::HashBytes(expected)},
                                {"actual_sha256",resource::HashBytes(actual)},
                                {"expected_bytes",expected.size()},{"actual_bytes",actual.size()}}}};
                            throw std::runtime_error("Canonical CAS acceptance cache changed an appearance field.");
                        }
                    }
                    ++bank.canonicalWrites;++caches;
                }
                if(!state.api.prepareHousehold)throw std::runtime_error("Native household root preparation is unavailable.");
                state.api.prepareHousehold(controller);
                for(const auto& target:targets)if(IndependentHybridGenus(target.bank->mask,target.bank->graph->cursor().kind)) {
                    const auto& receipt=target.bank->householdCanonical;
                    if(!receipt.value("prepared",false) || receipt.at("scope_id")!=state.scope.id ||
                       receipt.at("generation")!=target.bank->graph->cursor().generation)
                        throw std::runtime_error("Native household root preparation lacks a fresh complete receipt.");
                }
                scope=state.scope.id;session=state.sessionsRetired;cancel=state.cancelSerial;outputFaults=state.householdOutputFaults;
                state.acceptingHousehold=true;
                state.householdAcceptance={{"verified",false},{"native_accepted",false},
                    {"scope_id",scope},{"generations",generations},{"canonical_caches",caches}};
            } catch(const std::exception& error) {
                const auto diagnostic=state.householdAcceptance.value("cache_failure",ui::Json(nullptr));
                state.householdAcceptance={{"verified",false},{"native_accepted",false},
                    {"scope_id",state.scope.id},{"message",error.what()},{"cache_failure",diagnostic}};
                state.api.boolValue(Read<void*>(argument,0x10),false);
                return true; // Handled, with an explicit false GFx result. No native acceptance attempted.
            }
        } else {
            state.householdAcceptance={{"verified",false},{"native_accepted",false}};
        }
    }
    // EA may dispatch messages/Source work during transition. Never retain the
    // native graph mutex while calling the real service.
    bool handled=false,accepted=false;
    try {handled=state.api.saveAndExit(argument);}
    catch(...) {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);state.acceptingHousehold=false;
        state.householdAcceptance={{"verified",false},{"native_accepted",false},{"message","Native acceptance raised; not replayed."}};
        throw;
    }
    // The callback returns "handled", even when its actual GFx result is
    // false. Read the same Boolean value the CAS room receives.
    try {
        const auto result=Read<const void*>(argument,0x10);
        accepted=handled && Read<std::uint32_t>(result)==2 && Read<std::uint8_t>(result,8)==1;
    } catch(const std::exception&) {accepted=false;}
    if(!scope.empty()) {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);state.acceptingHousehold=false;
        bool same=state.selectionEnabled && state.scope.id==scope && state.sessionsRetired==session &&
                  state.cancelSerial==cancel && cancel!=UINT64_MAX && outputFaults!=UINT64_MAX && state.householdOutputFaults==outputFaults &&
                  state.bank.size()==generations.size();
        for(const auto& row:state.bank)
            same=same && row.second.graph && generations.contains(std::to_string(row.first)) &&
                 generations.at(std::to_string(row.first))==row.second.graph->cursor().generation;
        state.householdAcceptance={{"verified",accepted&&same},{"native_accepted",accepted},
            {"scope_id",scope},{"generations",generations},{"canonical_caches",caches},
            {"other_sim_graphs_written",false},{"member_selection_submitted",false}};
    }
    return handled;
}

inline bool CancelCas(const void* argument) {
    auto& state=Runtime();
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        if(state.cancelSerial!=UINT64_MAX)++state.cancelSerial;
        state.householdAcceptance={{"verified",false},{"native_accepted",false},{"cancelled",true}};
        state.householdCopiesEnabled.store(false,std::memory_order_release);state.householdCopies.clear();
        state.preparedRoots.clear();state.preparedScope.clear();state.exportController=nullptr;
    }
    return state.api.cancelCas(argument);
}

inline void BindSelected(void* controller,bool notify) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(!binding || binding->controller!=controller) {
        const auto group=Read<void*>(controller,0x100);const auto id=group?Read<std::uint64_t>(group,0xb8):0;
        const auto at=state.bank.find(id);
        if(!state.selectionEnabled || at==state.bank.end() || !at->second.graph) {state.api.bind(controller,notify);return;}
        auto& bank=at->second;
        if(bank.viewFault) return;
        const auto previous=binding;
        try {
            const auto model=Read<void*>(controller,0x1d0);
            if(bank.viewBound && state.boundSim==id && state.boundController==controller &&
               bank.boundGroup==group && Read<void*>(model,0x510)==bank.boundContext)
                Sync(controller); // Same-owner refresh must retain newly edited model data.
            if(bank.viewFault) return;
            const auto owner=bank.graph->cursor().owner;
            const auto layer=ConfigurePortraitPair(bank,owner);
            auto* child=Read<void*>(group,0x4c0);
            if(!child) {
                child=state.api.allocate(0x830,nullptr,0,0,nullptr,0);if(!child) throw std::bad_alloc();
                state.api.copySim(child,bank.graph->appearance(bank.partner)->value);
                const auto references=Read<std::uint32_t>(child,8)+1;
                std::memcpy(static_cast<char*>(child)+8,&references,4);std::memcpy(static_cast<char*>(group)+0x4c0,&child,8);
            }
            state.api.assignData(static_cast<char*>(group)+0xd0,bank.graph->appearance(bank.entryOwner)->data());
            state.api.assignData(static_cast<char*>(child)+0xd0,bank.graph->appearance(bank.partner)->data());
            bank.boundGroup=group;bank.editorImported=true;bank.importedEntity=GroupId(group);
            std::memcpy(static_cast<char*>(controller)+0x242,&layer,1);
            StoreCanonical(state,bank,controller);
            ViewBinding current{controller,&bank,owner};binding=&current;
            BindSelected(controller,notify);binding=previous;bank.viewBound=true;
        } catch(const std::exception& error) {
            state.observedNative={{"available",false}};
            binding=previous;bank.viewFault=true;
            state.viewResult={{"state","unresolved"},{"sim_id",std::to_string(id)},
                {"message",error.what()},{"native_bind_blocked",true}};
        }
        return;
    }
    auto& bank=*binding->bank;
    const auto group=Read<void*>(controller,0x100);const auto layer=Read<std::uint8_t>(controller,0x242);
    const auto view=layer?Read<void*>(group,0x4c0):group;
    const auto model=Read<void*>(controller,0x1d0);
    if(!view || !model || group!=bank.boundGroup) throw std::runtime_error("Native view binding lost its exact owner.");
    state.api.assignData(static_cast<char*>(view)+0xd0,bank.graph->appearance(binding->owner)->data());
    auto* context=state.api.context(controller,GroupId(group),layer!=0);
    if(!context) throw std::runtime_error("Native view binding lacks its model context.");
    // This replaces the stock binder's unconditional primary-to-alternate
    // field copy. Bind this exact owned CasData through the original model API.
    state.api.modelBind(model,static_cast<char*>(view)+0xd0,context,notify);
    if(Read<std::uint32_t>(model,0x178)!=Read<std::uint32_t>(view,0xd8))
        throw std::runtime_error("The native model rewrote the independent form's rendering kind.");
    bank.boundContext=context;
    state.boundSim=bank.graph->cursor().sim;state.boundController=controller;
    RefreshBoundAnimation(state,bank,controller);
    ObserveSelected(state,controller);
}
inline bool SelectView(std::uint32_t token) {
    const auto started=std::chrono::steady_clock::now();
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(!state.viewIntent || state.viewIntent->token!=token) return false;
    const auto intent=*state.viewIntent;state.viewIntent.reset();
    state.viewResult={{"request_id",intent.request},{"sim_id",std::to_string(intent.sim)},
        {"owner_id",intent.owner},{"state","applying"},{"conversion_called",false}};
    auto& result=state.viewResult;Imported* affected=nullptr;
    try {
        auto& bank=state.bank.at(intent.sim);affected=&bank;const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
        const auto group=controller?Read<void*>(controller,0x100):nullptr;
        if(!state.selectionEnabled || !group || !bank.graph || Read<std::uint64_t>(group,0xb8)!=intent.sim ||
           Read<std::uint8_t>(controller,0x242)!=intent.layer || bank.graph->cursor().generation!=intent.generation)
            throw std::runtime_error("Staged form view no longer matches its native owner/context.");
        const auto entity=GroupId(group);const auto index=state.api.index(controller,entity);
        if(index<0 || index>7) throw std::runtime_error("Native form view has no exact household index.");
        Sync(controller);
        if(bank.viewFault) throw std::runtime_error("The native owner synchronization is unresolved.");
        // The initial binder installs the captured entry owner before any UI
        // edit. Never adopt a stock-normalized model as an unobserved edit.
        const auto modelBefore=Read<void*>(controller,0x1d0);
        if(!bank.undoOwners.count(bank.graph->cursor().owner))
            bank.undoOwners.emplace(bank.graph->cursor().owner,
                std::make_unique<NativeUndo>(Read<void*>(modelBefore,0x70)));
        auto* child=Read<void*>(group,0x4c0);
        if(!child) {
            child=state.api.allocate(0x830,nullptr,0,0,nullptr,0);if(!child) throw std::bad_alloc();
            state.api.copySim(child,bank.graph->appearance(intent.owner)->value);
            const auto references=Read<std::uint32_t>(child,8)+1;
            std::memcpy(static_cast<char*>(child)+8,&references,4);std::memcpy(static_cast<char*>(group)+0x4c0,&child,8);
        }
        if(bank.viewFault) throw std::runtime_error("The current native form owner is unresolved.");
        const auto desiredKind=Read<std::uint32_t>(bank.graph->appearance(intent.owner)->data(),8);
        const auto layer=ConfigurePortraitPair(bank,intent.owner);
        if(desiredKind!=1) bank.preferred=desiredKind;
        state.api.assignData(static_cast<char*>(group)+0xd0,bank.graph->appearance(bank.entryOwner)->data());
        state.api.assignData(static_cast<char*>(child)+0xd0,bank.graph->appearance(bank.partner)->data());
        StoreCanonical(state,bank,controller);
        bank.boundGroup=group;bank.viewBound=false;
        ViewBinding current{controller,&bank,intent.owner};const auto previous=binding;binding=&current;
        try {
            // Let EA own an actual physical-layer transition, including its
            // model notification and layer-specific state. Writing its layer
            // byte and calling only the inner binder skipped that lifecycle.
            // Sync above already harvested the outgoing owner; binding keeps
            // the original transition's Sync from harvesting the new pair.
            if(layer!=intent.layer) state.api.layer(controller,layer!=0,true,false);
            else state.api.coreBind(controller,index,false); // Native layer selection would no-op here.
        } catch(...) {binding=previous;throw;}
        binding=previous;
        const auto model=Read<void*>(controller,0x1d0);const auto view=layer?child:group;
        if(Read<std::uint32_t>(view,0xd8)!=desiredKind || Read<std::uint32_t>(model,0x178)!=desiredKind ||
           Read<std::uint64_t>(group,0xb8)!=intent.sim || Read<std::uint8_t>(controller,0x242)!=layer)
            throw std::runtime_error("Native owner view did not bind the requested rendering kind.");
        const auto history=bank.undoOwners.find(intent.owner);
        if(history==bank.undoOwners.end() || Read<void*>(model,0x70)!=history->second->value ||
           Read<void*>(model,0x510)!=bank.boundContext)
            throw std::runtime_error("Native owner view did not bind its independent model/undo context.");
        bank.graph->select(bank.graph->cursor(),intent.owner);bank.viewBound=true;
        auto* avatar=state.api.avatar();if(avatar) Read<RefreshFn>(Read<void*>(avatar),0x360)(avatar);
        result["state"]="applied";result["native_kind"]=desiredKind;result["generation"]=bank.graph->cursor().generation;
        result["layer"]=layer;result["owned_mask"]=bank.mask;
        result["independent_undo_bound"]=true;result["undo_owner_id"]=intent.owner;
        result["native_view_elapsed_ms"]=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
        return true;
    } catch(const std::exception& error) {state.observedNative={{"available",false}};if(affected) affected->viewFault=true;result["state"]="unresolved";result["message"]=error.what();return false;}
}


inline bool NativeUiView(void* controller,const std::string& owner,bool bootstrap=false) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(state.viewIntent) return false;
    const auto group=Read<void*>(controller,0x100);const auto id=group?Read<std::uint64_t>(group,0xb8):0;
    const auto found=state.bank.find(id);
    if(found==state.bank.end() || !found->second.graph || (!found->second.viewBound && !bootstrap) || found->second.viewFault) return false;
    const auto cursor=found->second.graph->cursor();
    state.viewIntent=std::make_unique<ViewIntent>(ViewIntent{"native-ui/"+std::to_string(++state.nativeUiSequence),
        owner,id,cursor.generation,0x10000000,Read<std::uint8_t>(controller,0x242)});
    return SelectView(0x10000000);
}
inline void SelectLayer(void* controller,bool alternate,bool notify,bool refresh) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    const auto group=Read<void*>(controller,0x100);const auto id=group?Read<std::uint64_t>(group,0xb8):0;
    const auto found=state.bank.find(id);
    if(!binding && state.selectionEnabled && found!=state.bank.end() && found->second.viewBound) {
        NativeUiView(controller,alternate?found->second.partner:found->second.entryOwner);return;
    }
    state.api.layer(controller,alternate,notify,refresh);
}
inline void OwnerUiTokens(State& state,std::uint64_t id,Imported& bank) {
    for(const auto& owner:bank.graph->owners()) if(!bank.uiTokens.count(owner.id)) {
        if(state.nextUiToken>0x2fffffff) throw std::runtime_error("Native owner button identities are exhausted.");
        const auto token=state.nextUiToken++;
        bank.uiTokens.emplace(owner.id,token);state.uiOwners.emplace(token,std::make_pair(id,owner.id));
    }
}
inline bool Capture(std::uint64_t id,const void* proto,bool sourceSeed) {
    auto& state=Runtime();
    std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(!state.armed) return false;
    const auto member=state.scope.members.find(id);if(member==state.scope.members.end()) return false;
    auto& bank=state.bank[id];
    // The client can send a narrowed pair even after Source captured all
    // owners. That packet must not replace the complete pre-entry native bank.
    if(bank.seeded && !sourceSeed) {++bank.skippedPackets;return true;}
    if(bank.seeded && sourceSeed && !bank.initialImport)
        throw std::runtime_error("A ready CAS owner graph cannot be reseeded over user edits.");
    try {
        if(Read<std::uint64_t>(proto,0x10)!=id || !(Read<std::uint32_t>(proto,0x1dc)&(1u<<26)))
            throw std::runtime_error("Native import identity or attributes are incomplete.");
        std::map<std::uint32_t,const void*> byKind;std::vector<std::uint32_t> kinds;
        std::uint32_t current=1;
        if(member->second.mask==1) {
            // Special lifestates can use Human rendering without any EA
            // occult membership or stored occult records.
            byKind.emplace(1,nullptr);kinds.push_back(1);
        } else {
            const auto attributes=Read<const void*>(proto,0xc0);
            if(!attributes || !(Read<std::uint8_t>(attributes,0x13a)&1))
                throw std::runtime_error("Native import lacks occult tracker attributes.");
            const auto tracker=Read<const void*>(attributes,0x90);
            if(!tracker || (Read<std::uint32_t>(tracker,0x10)|1u)!=member->second.mask)
                throw std::runtime_error("Imported membership differs from the captured household scope.");
            const auto count=Read<std::int32_t>(tracker,0x20);
            if(count<1 || count>7) throw std::runtime_error("Native import form count is out of bounds.");
            const auto records=Read<const void* const*>(tracker,0x18);Span(records,static_cast<std::size_t>(count)*8);
            for(int i=0;i<count;++i) {
                const auto record=Read<const void*>(records,static_cast<std::size_t>(i)*8);
                if(!(Read<std::uint32_t>(record,0x84)&1)) throw std::runtime_error("Imported form has no native kind field.");
                const auto kind=Read<std::uint32_t>(record,0x18);kinds.push_back(kind);byKind.emplace(kind,record);
            }
            current=Read<std::uint32_t>(tracker,0x14);
        }
        ValidateKinds(member->second.mask,kinds);
        Imported replacement;replacement.imports=bank.imports+1;replacement.seeded=sourceSeed;
        replacement.preferred=Kind(current) && current!=1 && (member->second.mask&current)?current:0;
        for(const auto& row:byKind) {
            auto owner=std::make_unique<NativeOwner>(state.api,id);
            const DetachedTarget target(owner->data());
            state.api.available(owner->value,member->second.mask);
            state.api.current(owner->value,row.first);
            state.api.fields(owner->value,proto,row.second);
            state.api.current(owner->value,row.first);
            state.api.availableData(const_cast<void*>(owner->data()),member->second.mask);
            if(Read<std::uint64_t>(owner->value,0xb8)!=id || Read<std::uint32_t>(owner->data(),8)!=row.first ||
               Read<std::uint32_t>(owner->data(),12)!=member->second.mask)
                throw std::runtime_error("Native form deserializer changed owner identity or membership.");
            replacement.mask|=row.first;replacement.owners.emplace(row.first,std::move(owner));
            if(!replacement.preferred && row.first!=1) replacement.preferred=row.first;
        }
        if(sourceSeed) {
            replacement.active=std::make_unique<NativeOwner>(state.api,id);
            const auto activeKind=current?current:1u;
            if(!Kind(activeKind) || !(member->second.mask&activeKind))
                throw std::runtime_error("Native active entry owner has an unknown or unowned kind.");
            const DetachedTarget target(replacement.active->data());
            state.api.available(replacement.active->value,member->second.mask);
            state.api.current(replacement.active->value,activeKind);
            state.api.fields(replacement.active->value,proto,nullptr);
            // The field loader can classify a multi-kind tracker using its
            // legacy priority rules. The tracker's explicit current field is
            // the active owner identity; restore it after loading appearance.
            state.api.current(replacement.active->value,activeKind);
            state.api.availableData(const_cast<void*>(replacement.active->data()),member->second.mask);
        }
        const auto activeKind=replacement.active?Read<std::uint32_t>(replacement.active->data(),8):
            (Kind(current) && (member->second.mask&current)?current:1u);
        const auto api=state.api;
        replacement.graph=std::make_unique<OwnerGraph<std::unique_ptr<NativeOwner>>>(
            id,member->second.mask,activeKind,replacement.owners,
            [api,id](const std::unique_ptr<NativeOwner>& from,std::uint32_t destination) {
                auto clone=std::make_unique<NativeOwner>(api,id);
                const DetachedTarget target(clone->data());
                api.assignData(const_cast<void*>(clone->data()),from->data());
                api.current(clone->value,destination);
                if(Read<std::uint64_t>(clone->value,0xb8)!=id || Read<std::uint32_t>(clone->data(),8)!=destination)
                    throw std::runtime_error("Cloned appearance changed its exact Sim/form identity.");
                return clone;
            });
        replacement.entryOwner=NativeOwnerId(activeKind);
        for(const auto& owner:replacement.owners) replacement.logicalOwners.emplace(owner.first,NativeOwnerId(owner.first));
        if(replacement.active) {
            replacement.entryOwner="active/"+std::to_string(activeKind);
            replacement.graph->capture(replacement.graph->cursor(),replacement.entryOwner,activeKind,replacement.active);
            replacement.graph->select(replacement.graph->cursor(),replacement.entryOwner);
            replacement.logicalOwners.at(activeKind)=replacement.entryOwner;
        }
        replacement.partner=NativeOwnerId(activeKind==1?(replacement.preferred?replacement.preferred:1u):1u);
        if(activeKind==1) replacement.humanOwner=replacement.entryOwner;
        OwnerUiTokens(state,id,replacement);bank=std::move(replacement);return true;
    } catch(const std::exception& error) {
        // No existing game owner is written by import. Incomplete captures
        // are explicitly unavailable to the native selection hook.
        bank.mask=0;bank.error=error.what();return false;
    }
}
inline void Import(void* output,const void* proto) {
    auto& state=Runtime();state.api.import(output,proto);
    const auto id=Read<std::uint64_t>(output,0xb8);
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        const auto found=state.bank.find(id);
        if(state.selectionEnabled && found!=state.bank.end() && found->second.seeded &&
           found->second.initialImport && found->second.active && found->second.mask) {
            auto& bank=found->second;
            // Retain the game's entity key while the imported object is live.
            // Later acceptance looks it up afresh; no raw group pointer is kept.
            bank.editorImported=true;
            try {bank.importedEntity=GroupId(output);} catch(const std::exception&) {bank.importedEntity=0;}
            // The Source producer supplies the actual active owner separately
            // from its seven stored forms. Apply it at native import, before
            // the client constructs CAS. Never replay it after CAS is ready.
            state.api.assignData(static_cast<char*>(output)+0xd0,bank.active->data());
            const auto current=Read<std::uint32_t>(bank.active->data(),8);
            if(bank.mask==1) {++state.initialOwnersImported;return;}
            const auto alternate=current==1?bank.preferred:1u;
            const auto desired=bank.owners.find(alternate);
            if(desired==bank.owners.end()) throw std::runtime_error("Native initial alternate lacks its captured owner.");
            auto* child=Read<void*>(output,0x4c0);
            if(child) state.api.assignData(static_cast<char*>(child)+0xd0,desired->second->data());
            else {
                child=state.api.allocate(0x830,nullptr,0,0,nullptr,0);
                if(!child) throw std::bad_alloc();
                state.api.copySim(child,desired->second->value);
                const auto references=Read<std::uint32_t>(child,8)+1;
                std::memcpy(static_cast<char*>(child)+8,&references,4);
                std::memcpy(static_cast<char*>(output)+0x4c0,&child,8);
            }
            ++state.initialOwnersImported;
        }
    }
    Capture(id,proto,false);
}
inline std::uint32_t Normalize(void* data,bool alternate) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    const auto mask=Read<std::uint32_t>(data,12),current=Read<std::uint32_t>(data,8);
    bool owned=data==detachedTarget;
    if(!owned && state.selectionEnabled && state.image) {
        const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
        const auto group=controller?Read<void*>(controller,0x100):nullptr;
        const auto id=group?Read<std::uint64_t>(group,0xb8):0;
        if(state.scope.members.count(id)) {
            const auto model=Read<void*>(controller,0x1d0);const auto child=Read<void*>(group,0x4c0);
            owned=data==static_cast<char*>(group)+0xd0 || (child && data==static_cast<char*>(child)+0xd0) ||
                (model && data==static_cast<char*>(model)+0x170);
        }
    }
    if(state.selectionEnabled && owned && IndependentHybridGenus(mask,current)) {
        // EA prioritizes Vampire/Witch whenever their bits are present and
        // overwrites the selected kind. Existing hybrid owners already carry
        // their exact kind; no normalization or membership deletion is needed.
        ++state.normalizationsPrevented;return current;
    }
    return state.api.normalize(data,alternate);
}
inline std::uint32_t Alternate(std::uint32_t mask,std::uint32_t current) {
    auto& state=Runtime();const auto kinds=mask&~1u;
    // EA returns the entire non-Human mask when Human is selected. That is
    // not a valid single form for a hybrid. Resolve its actual selected family.
    if(!(current&~1u) && kinds && (kinds&(kinds-1))) {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        if(state.selectionEnabled && state.image) {
            const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
            const auto group=controller?Read<void*>(controller,0x100):nullptr;
            const auto id=group?Read<std::uint64_t>(group,0xb8):0;
            const auto bank=state.bank.find(id);
            if(bank!=state.bank.end() && bank->second.mask==(mask|1u) && Kind(bank->second.preferred) &&
               bank->second.preferred!=1 && (kinds&bank->second.preferred)) {
                ++state.alternateOverrides;return bank->second.preferred;
            }
        }
    }
    return state.api.alternate(mask,current);
}
inline void History(void* controller,std::uint32_t target) {
    auto& state=Runtime();const auto previous=selected;selected={};
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        if(state.armed && state.selectionEnabled) {
            const auto group=Read<void*>(controller,0x100);
            const auto id=group?Read<std::uint64_t>(group,0xb8):0;
            const auto member=state.scope.members.find(id);const auto bank=state.bank.find(id);
            if(member!=state.scope.members.end() && bank!=state.bank.end() &&
               OwnedTarget(member->second,bank->second.mask,target)) selected={id,target,controller};
        }
    }
    if(selected.id) {
        // This is EA's kind-conversion/history path, not a form-view switch.
        // V155 demonstrated stale kind labels, so never cache edits through it.
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        ++state.blockedConversions;selected=previous;return;
    }
    try {state.api.history(controller,target);} catch(...) {selected=previous;throw;}
    selected=previous;
}
inline std::string FastOwnerState(State& state,std::uint64_t channel) {
    // UI-thread read of the already-bound model. No Python/socket round trip,
    // serialization, synchronization, allocation of EA objects or harvesting.
    if(!state.armed || !state.selectionEnabled || !state.image || state.scope.id.empty()) return "UNAVAILABLE";
    if(!pipe::Channel().Matches(channel,state.scope.id)) return "STALE";
    const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
    const auto group=controller?Read<void*>(controller,0x100):nullptr;
    const auto id=group?Read<std::uint64_t>(group,0xb8):0;
    const auto found=state.bank.find(id);
    if(!state.scope.members.count(id) || found==state.bank.end() || !found->second.graph || !found->second.viewBound ||
       found->second.viewFault || state.boundSim!=id || state.boundController!=controller ||
       found->second.boundGroup!=group) return "WAIT";
    const auto cursor=found->second.graph->cursor();
    const auto layer=Read<std::uint8_t>(controller,0x242);
    const auto view=layer==0?group:layer==1?Read<void*>(group,0x4c0):nullptr;
    const auto model=Read<void*>(controller,0x1d0);
    if(!view || !model || Read<std::uint32_t>(view,0xd8)!=cursor.kind ||
       Read<std::uint32_t>(model,0x178)!=cursor.kind) return "WAIT";
    return "VIEWSTATE|"+std::to_string(id)+"|"+cursor.owner+"|"+std::to_string(cursor.kind)+"|"+
        std::to_string(layer)+"|bound|"+std::to_string(cursor.generation);
}
inline Imported& PairBank(State& state,std::uint64_t channel,void*& controller) {
    if(FastOwnerState(state,channel).rfind("VIEWSTATE|",0)!=0)throw std::runtime_error("Pair controls lack an exact bound native model.");
    controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
    const auto group=Read<void*>(controller,0x100);auto& bank=state.bank.at(Read<std::uint64_t>(group,0xb8));
    if(bank.entryOwner==bank.partner || (bank.entryOwner!=bank.humanOwner&&bank.partner!=bank.humanOwner))
        throw std::runtime_error("Pair controls require the one shared Human and a separate actual form.");
    bank.graph->appearance(bank.entryOwner);bank.graph->appearance(bank.partner);return bank;
}
inline std::string PairState(State& state,std::uint64_t channel) {
    void* controller=nullptr;auto& bank=PairBank(state,channel,controller);const auto cursor=bank.graph->cursor();
    const auto linked=bank.graph->linked(bank.entryOwner,bank.partner)&&bank.graph->linked(bank.partner,bank.entryOwner);
    return "PAIR|"+std::to_string(cursor.sim)+"|"+cursor.owner+"|"+bank.entryOwner+"|"+bank.partner+"|"+
        bank.humanOwner+"|"+(linked?"1":"0")+"|"+std::to_string(cursor.generation);
}
inline std::string ApplyPairAction(State& state,std::uint64_t channel,const std::string& payload) {
    const auto action=ParsePairAction(payload);void* controller=nullptr;auto& bank=PairBank(state,channel,controller);
    const auto cursor=bank.graph->cursor();
    if(cursor.sim!=action.sim || cursor.generation!=action.generation ||
       !((action.source==bank.entryOwner&&action.target==bank.partner)||(action.source==bank.partner&&action.target==bank.entryOwner)) ||
       state.pairRequests.size()>=32768 || !state.pairRequests.insert(action.request).second)
        throw std::runtime_error("Pair action is stale, outside the current pair or already consumed.");
    state.pairResult={{"request_id",action.request},{"sim_id",std::to_string(action.sim)},
        {"operation",action.copy?"copy":"link"},{"source_owner_id",action.source},{"target_owner_id",action.target},
        {"scope","whole-appearance"},{"ok",false},{"appearance_written",false}};
    try {
        if(action.copy) {
            Sync(controller);if(bank.viewFault)throw std::runtime_error("Outgoing form synchronization failed.");
            // Capture edits before reading the source. The destination stays
            // inactive until its explicit graph copy, so rebinding cannot
            // harvest an older visible destination over the requested copy.
            if(bank.graph->cursor().owner!=action.source && !NativeUiView(controller,action.source))
                throw std::runtime_error("Copy source did not bind.");
            bank.graph->copy(bank.graph->cursor(),action.source,action.target);
            state.pairResult["appearance_written"]=true;
            if(!NativeUiView(controller,cursor.owner))throw std::runtime_error("Copied pair did not rebind its original selected form.");
        } else {
            if(action.enabled) {Sync(controller);if(bank.viewFault)throw std::runtime_error("Pre-link synchronization failed.");}
            bank.graph->linkPair(bank.graph->cursor(),action.source,action.target,action.enabled);
            state.pairResult["enabled"]=action.enabled;
        }
        state.pairResult["ok"]=true;state.pairResult["generation"]=bank.graph->cursor().generation;
        return "PAIRDONE|"+action.request;
    } catch(const std::exception& error) {state.pairResult["message"]=error.what();return "PAIRFAILED|"+action.request;}
}
inline bool GetOccultService(const void* arguments) {
    auto& state=Runtime();
    const auto parameter=Read<const void*>(arguments,8);
    if(!parameter||Read<std::uint32_t>(parameter)!=6)return state.api.getOccultService(arguments);
    std::string text;
    try {text=UiString(parameter);}catch(const std::exception&){return state.api.getOccultService(arguments);}
    if(text.rfind("APEXUI1|",0)!=0)return state.api.getOccultService(arguments);
    std::string response="UNAVAILABLE";
    try {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        if(!state.armed||!state.selectionEnabled||state.scope.id.empty())throw std::runtime_error("Native CAS pipe lacks its exact scope.");
        const auto command=text.substr(8);const auto split=command.find('|');
        if(split==std::string::npos)throw std::runtime_error("Native CAS pipe command is incomplete.");
        const auto action=command.substr(0,split);const auto rest=command.substr(split+1);
        const auto end=rest.find('|');const auto identity=rest.substr(0,end);
        const auto number=SimId(ui::Json(identity));
        if(action=="OPEN") {
            if(end!=std::string::npos)throw std::runtime_error("Native CAS open has extra fields.");
            const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
            const auto group=controller?Read<void*>(controller,0x100):nullptr;
            if(!group||Read<std::uint64_t>(group,0xb8)!=number||!state.scope.members.count(number))
                throw std::runtime_error("Native CAS pipe cannot open for another selected Sim.");
            response=pipe::Open(state.scope.id);
        } else if(action=="STATE"&&end==std::string::npos)response=FastOwnerState(state,number);
        else if(action=="PAIR"&&end==std::string::npos)response=PairState(state,number);
        else if(action=="PAIRDO"&&end!=std::string::npos)response=ApplyPairAction(state,number,rest.substr(end+1));
        else if(action=="READ"&&end==std::string::npos)response=pipe::Channel().Poll(number,state.scope.id);
        else if(action=="CLOSE"&&end==std::string::npos)response=pipe::Channel().Close(number,state.scope.id);
        else if(action=="WRITE"&&end!=std::string::npos)response=pipe::Channel().Send(number,state.scope.id,rest.substr(end+1));
        else throw std::runtime_error("Native CAS pipe operation differs.");
    } catch(const std::exception&) {response="REFUSED";}
    state.api.stringValue(Read<void*>(arguments,0x10),response.c_str());return true;
}
inline bool SetOccultService(const void* arguments) {
    auto& state=Runtime();
    const auto argument=Read<const void*>(arguments,8);
    const auto type=Read<std::uint32_t>(argument);
    std::uint32_t target=0;
    if(type==4 || type==5) target=Read<std::uint32_t>(argument,8);
    else if(type==3) {
        const auto number=Read<double>(argument,8);
        if(std::isfinite(number) && number>=1 && number<=0x2fffffff && std::floor(number)==number)
            target=static_cast<std::uint32_t>(number);
    }
    if(target>=0x10000000 && target<=0x1fffffff) return SelectView(target);
    if(target>=0x20000000 && target<=0x2fffffff) {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);const auto at=state.uiOwners.find(target);
        if(at==state.uiOwners.end() || !state.selectionEnabled || !state.image) return false;
        const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
        const auto group=controller?Read<void*>(controller,0x100):nullptr;
        if(!group || Read<std::uint64_t>(group,0xb8)!=at->second.first) return false;
        return NativeUiView(controller,at->second.second,true);
    }
    void* controller=nullptr;
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        if(state.armed && state.selectionEnabled && state.image && Kind(target)) {
            controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
            const auto group=controller?Read<void*>(controller,0x100):nullptr;
            const auto id=group?Read<std::uint64_t>(group,0xb8):0;
            const auto member=state.scope.members.find(id),end=state.scope.members.end();
            const auto bank=state.bank.find(id);
            if(member==end || bank==state.bank.end() || !OwnedTarget(member->second,bank->second.mask,target))
                controller=nullptr;
        }
    }
    if(!controller) return state.api.service(arguments);
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        const auto group=Read<void*>(controller,0x100);const auto id=Read<std::uint64_t>(group,0xb8);
        const auto found=state.bank.find(id);
        if(found!=state.bank.end() && found->second.viewBound) return NativeUiView(controller,NativeOwnerId(target));
    }
    // A request for an existing owner is NOT permission to convert it. The
    // separate owner-view adapter must bind that record on the native UI thread.
    std::lock_guard<std::recursive_mutex> lock(state.mutex);
    ++state.blockedConversions;return false;
}
inline void Rebind(void* controller,const void* metadata,std::uint32_t target) {
    auto& state=Runtime();
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
        const auto group=Read<void*>(controller,0x100);
        const auto id=group?Read<std::uint64_t>(group,0xb8):0;
        const auto at=state.bank.find(id);
        if(state.selectionEnabled && at!=state.bank.end() &&
           (at->second.viewBound || (binding && binding->controller==controller))) {
            auto& bank=at->second;
            if(bank.viewFault) return;
            // This EA function only updates/removes the inactive pair member.
            // A kind-keyed cache cannot distinguish same-kind owners. Keep the
            // exact inactive owner and leave the edited/undone model untouched.
            try {
                if(group!=bank.boundGroup || !bank.graph)
                    throw std::runtime_error("Inactive form binding lost its native group.");
                const auto layer=Read<std::uint8_t>(controller,0x242);
                const auto inactive=layer?group:Read<void*>(group,0x4c0);
                if(!inactive) throw std::runtime_error("The independent inactive form is absent.");
                state.api.assignData(static_cast<char*>(inactive)+0xd0,
                    bank.graph->appearance(layer?bank.entryOwner:bank.partner)->data());
                ++state.rebindCorrections;
            } catch(const std::exception& error) {
                bank.viewFault=true;state.viewResult={{"state","unresolved"},{"sim_id",std::to_string(id)},
                    {"message",error.what()},{"inactive_binding_blocked",true}};
            }
            return;
        }
        if(state.selectionEnabled && !Kind(target)) {
            const auto group=Read<void*>(controller,0x100);
            const auto model=Read<void*>(controller,0x1d0);
            const auto id=group?Read<std::uint64_t>(group,0xb8):0;
            const auto found=state.bank.find(id);
            if(model && found!=state.bank.end() && found->second.mask && found->second.seeded) {
                const auto current=Read<std::uint32_t>(model,0x178);
                const auto expected=current==1?found->second.preferred:1u;
                if(Kind(current) && (found->second.mask&current) && Kind(expected) &&
                   (target==(found->second.mask^current) || target==((found->second.mask&~1u)^current)) &&
                   state.api.lookup(metadata,expected)) {
                    // The history visitor computes mask XOR current. That is
                    // a composite membership, not an alternate owner, for a
                    // hybrid. Bind the actual independent alternate instead.
                    target=expected;++state.rebindCorrections;
                }
            }
        }
    }
    state.api.rebind(controller,metadata,target);
}
inline void* Record(const Api& api,const void* metadata,const void* genus) {
    auto* result=static_cast<char*>(api.allocate(0x58,nullptr,0,0,nullptr,0));
    if(!result) throw std::bad_alloc();
    std::memset(result,0,0x58);api.metadata(result+8,metadata);std::memcpy(result+0x40,genus,20);
    return result;
}
inline void Release(const Api& api,void* record) {
    if(!record) return;auto* tree=static_cast<char*>(record)+0x10;
    api.treeDestroy(tree,Read<void*>(tree,0x18));api.free(record,0x58);
}
inline void Change(void* model,std::uint32_t target,const void* input,const void* metadata,void** before,void** after) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    const auto member=state.scope.members.find(selected.id);const auto found=state.bank.find(selected.id);
    if(!selected.id || selected.target!=target || !before || !after || member==state.scope.members.end() ||
       found==state.bank.end() || !OwnedTarget(member->second,found->second.mask,target) ||
       Read<void*>(selected.controller,0x1d0)!=model) {
        ++state.converted;state.api.change(model,target,input,metadata,before,after);return;
    }
    auto& bank=found->second;
    // Native History has just committed both edited current layers into this
    // cache. Keep those records; seed only owners that EA did not import.
    void* oldRecord=nullptr;void* newRecord=nullptr;
    try {
        const auto group=Read<void*>(selected.controller,0x100);
        const auto current=static_cast<const char*>(group)+0xd0;Span(current,20);
        oldRecord=Record(state.api,metadata,current);
        auto* cache=static_cast<char*>(oldRecord)+8;
        for(const auto& row:bank.owners) {
            if(!state.api.lookup(cache,row.first)) state.api.store(cache,row.first,row.second->data());
            // This cache is our independent history copy. Retain all actual
            // memberships even when EA delivered only a two-kind header.
            state.api.availableData(const_cast<void*>(state.api.lookup(cache,row.first)),member->second.mask);
        }
        const auto desired=state.api.lookup(cache,target);
        if(!desired || Read<std::uint32_t>(desired,8)!=target)
            throw std::runtime_error("Requested native owner is absent from the completed CAS cache.");
        newRecord=Record(state.api,cache,desired);
        // Availability is independent of the selected primary/alternate pair.
        // Preserve every owned kind in both native history snapshots.
        std::memcpy(static_cast<char*>(oldRecord)+0x4c,&member->second.mask,4);
        std::memcpy(static_cast<char*>(newRecord)+0x4c,&member->second.mask,4);
        *before=oldRecord;*after=newRecord;if(target!=1) bank.preferred=target;++bank.switches;++state.intercepted;
    } catch(...) {
        Release(state.api,oldRecord);Release(state.api,newRecord);
        // Never run EA's converter after a partial existing-owner selection.
        // It would generate over the appearance this hook was meant to select.
        throw;
    }
}
inline ui::Json ViewStatus() {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    ui::Json result={{"ok",true},{"pid",GetCurrentProcessId()},{"scope","native-form-view-status"},
        {"available",false},{"game_files_written",false},{"native_patch_qualified",false},{"production_ready",false}};
    if(!state.selectionEnabled || !state.image) return result;
    try {
        if(!state.observedNative.value("available",false)) return result;
        const auto id=SimId(state.observedNative["sim_id"]);const auto at=state.bank.find(id);
        if(at==state.bank.end() || !at->second.graph) return result;
        const auto cursor=at->second.graph->cursor();
        result["available"]=true;result["sim_id"]=std::to_string(id);result["owner_id"]=cursor.owner;
        result["native_kind"]=cursor.kind;result["generation"]=cursor.generation;
        result["layer"]=state.observedNative["layer"];
        result["human_owner_id"]=at->second.humanOwner;
        result["portrait_pair"]={{"base_owner_id",at->second.entryOwner},{"alternate_owner_id",at->second.partner},
            {"base_kind",Read<std::uint32_t>(at->second.graph->appearance(at->second.entryOwner)->data(),8)},
            {"alternate_kind",Read<std::uint32_t>(at->second.graph->appearance(at->second.partner)->data(),8)}};
        result["source"]="native-cas-callback-observation";
        result["state"]=at->second.viewFault?"unresolved":at->second.viewBound?"bound":"unbound";
    } catch(const std::exception&) {result["available"]=false;}
    return result;
}
inline ui::Json Status() {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);auto rows=ui::Json::array();
    auto outputCalls=ui::Json::array();for(const auto& row:state.householdOutputCalls)outputCalls.push_back(row.second);
    for(const auto& member:state.scope.members) {
        const auto found=state.bank.find(member.first);auto kinds=ui::Json::array();
        auto genus=ui::Json::array();
        if(found!=state.bank.end()) for(const auto& owner:found->second.owners) {
            kinds.push_back(owner.first);
            genus.push_back({{"kind",owner.first},{"age",Read<std::uint32_t>(owner.second->data())},
                {"gender",Read<std::uint32_t>(owner.second->data(),4)},
                {"species",Read<std::uint32_t>(owner.second->data(),16)}});
        }
        auto graphOwners=ui::Json::array();auto logicalOwners=ui::Json::object();
        if(found!=state.bank.end()) for(const auto& owner:found->second.logicalOwners)
            logicalOwners[std::to_string(owner.first)]=owner.second;
        if(found!=state.bank.end() && found->second.graph) {
            const auto& graph=*found->second.graph;
            for(const auto& owner:graph.owners()) {
                auto links=ui::Json::array();
                for(const auto& target:graph.linkedTargets(owner.id)) links.push_back(target);
                graphOwners.push_back({{"owner_id",owner.id},{"native_kind",owner.nativeKind},{"revision",owner.revision},
                    {"selected",owner.selected},{"linked_targets",links},{"ui_token",found->second.uiTokens.at(owner.id)}});
            }
        }
        rows.push_back({{"sim_id",std::to_string(member.first)},{"owned_mask",member.second.mask},
            {"imported_mask",found==state.bank.end()?0:found->second.mask},{"kinds",kinds},{"imported_genus",genus},
            {"imports",found==state.bank.end()?0:found->second.imports},{"switches",found==state.bank.end()?0:found->second.switches},
            {"source_seeded",found!=state.bank.end() && found->second.seeded},
            {"editor_materialized",found!=state.bank.end() && found->second.editorImported},
            {"imported_entity_id",found==state.bank.end()?"0":std::to_string(found->second.importedEntity)},
            {"household_canonical",found==state.bank.end()?ui::Json(nullptr):found->second.householdCanonical},
            {"active_entry_captured",found!=state.bank.end() && found->second.active!=nullptr},
            {"active_entry_source_seeded",found!=state.bank.end() && found->second.activeSourceSeeded},
            {"canonical_source_seeded_mask",found==state.bank.end()?0u:found->second.canonicalSourceMask},
            {"active_entry_kind",found!=state.bank.end() && found->second.active?Read<std::uint32_t>(found->second.active->data(),8):0},
            {"narrowed_packets_skipped",found==state.bank.end()?0:found->second.skippedPackets},
            {"independent_owner_graph",found!=state.bank.end() && found->second.graph!=nullptr},
            {"owner_view_ready",false},
            {"separate_owners",graphOwners},
            {"graph_selected_kind",found!=state.bank.end() && found->second.graph?found->second.graph->cursor().kind:0},
            {"graph_generation",found!=state.bank.end() && found->second.graph?found->second.graph->cursor().generation:0},
            {"native_view_bound",found!=state.bank.end() && found->second.viewBound},
            {"sync_scratch_allocations",found==state.bank.end()?0u:found->second.scratchAllocations},
            {"canonical_cache_writes",found==state.bank.end()?0u:found->second.canonicalWrites},
            {"comparison_baseline_builds",found==state.bank.end()?0u:found->second.comparisonBuilds},
            {"comparison_baseline_reuses",found==state.bank.end()?0u:found->second.comparisonReuses},
            {"native_view_fault",found!=state.bank.end() && found->second.viewFault},
            {"undo_owner_count",found==state.bank.end()?0:found->second.undoOwners.size()},
            {"graph_selected_owner_id",found!=state.bank.end() && found->second.graph?found->second.graph->cursor().owner:""},
            {"human_owner_id",found!=state.bank.end()?found->second.humanOwner:NativeOwnerId(1)},
            {"logical_owner_ids",logicalOwners},
            {"error",found==state.bank.end()?"":found->second.error}});
    }
    const auto selectedNative=state.selectionEnabled?state.observedNative:ui::Json{{"available",false}};
    ui::Json pipeStatus;
    {auto& box=pipe::Channel();std::lock_guard<std::mutex> lock(box.mutex);
     pipeStatus={{"transport","native-owned-loopback"},{"generation",box.generation},{"scope_id",box.scope},
        {"connected",box.connected&&!box.stop},{"worker_finished",box.finished.load(std::memory_order_acquire)},
        {"frames_queued",box.queued},{"frames_received",box.received},{"frames_delivered",box.delivered},
        {"frame_in_flight",box.inFlight},{"error",box.error}};}
    return {{"ok",true},{"pid",GetCurrentProcessId()},{"installed",state.installed},{"armed",state.armed},
        {"ui_transport",pipeStatus},
        {"scope_id",state.scope.id},{"selection_enabled",state.selectionEnabled},{"members",rows},{"existing_owner_selections",state.intercepted},
        {"sessions_retired",state.sessionsRetired},
        {"household_acceptance",state.householdAcceptance},
        {"household_output_faults",state.householdOutputFaults},
        {"household_copy_lifetimes",state.householdCopies.size()},
        {"household_output_calls",outputCalls},
        {"native_converter_calls",state.converted},{"game_files_written",false},
        {"alternate_kind_overrides",state.alternateOverrides},
        {"normalizations_prevented",state.normalizationsPrevented},{"initial_active_owners_imported",state.initialOwnersImported},
        {"native_service_selections",state.serviceSelections},
        {"alternate_rebind_corrections",state.rebindCorrections},
        {"blocked_existing_owner_conversions",state.blockedConversions},
        {"conversion_quarantined",true},{"independent_owner_view_ready",false},
        {"owner_view_adapter_available",state.installed},{"owner_view_result",state.viewResult},{"pair_action_result",state.pairResult},
        {"owner_view_staged",state.viewIntent!=nullptr},
        {"native_kind_bias_prevented",state.kindBiasPrevented},
        {"cas_animation_membership_scopes",state.animationMembershipScopes},
        {"cas_animation_construction_scopes",state.animationConstructionScopes},
        {"last_cas_animation_scope",state.lastAnimationScope},
#ifdef APEX_CAS_OWNER_MEMORY_DIAGNOSTICS
        {"diagnostic_owner_memory",{{"enabled",true},{"reserved_bytes",GuardedOwnerMemory::Status().reserved},
            {"live_records",GuardedOwnerMemory::Status().live},{"retired_records",GuardedOwnerMemory::Status().retired}}},
#else
        {"diagnostic_owner_memory",{{"enabled",false}}},
#endif
        {"import_outfit_fills_prevented",state.importOutfitFillsPrevented},
        {"selection_route","quarantined-kind-conversion"},
        {"selected_native",selectedNative},
        {"native_patch_qualified",false},{"production_ready",false}};
}
inline void Install() {
    auto& state=Runtime();if(state.installed) return;
    const auto pinned=OpenPinnedCasImage();state.image=reinterpret_cast<std::uintptr_t>(pinned.module);
    struct Pin {std::uint32_t rva;const char* hash;};
    const Pin pins[]={
        {0x327640,"60bfa3f323ea363eddffe1178a7336a7dca8e7074324d6ef96f55b13f5171147"},
        {0x325640,"bf9bc9774b8b1ef158718743cf257c578d2b88d4cd707d0469f12e7240534997"},
        {0x321f00,"7c815c60d465b48675f7263e858c889891fbec548a51ea966873249b061e5255"},
        {0x3221c0,"683c0b97aeac8ba481288177ff1c2960b364d6ac67f37f83a369ebfb5c9100ff"},
        {0x343ea0,"cb8207a95aa1576905f63b401b8cda00b2dc2c09bdb4626902ef401f433b60dc"},
        {0x343f30,"1ef44ea53a62393261d3b243b39a9cd60c2dc0dece5f082ea0fd9e5e84ecd31a"},
        {0x33ff10,"fa4e21afda05a9b4d72ad3c2acc79bac57ed1b496a9872ed81833f9663a230d5"},
        {0x444510,"cb2c9814f6761ed700ca08df40ed1c3debab6e151394e7f4316b1988fd73afa7"},
        {0x442020,"9db570b4c27464197da8acc11808f0cb9db364675e7f2929a5ddc84bee146dcd"},
        {0x4421c0,"cad6be8df148ea524385195ee20d76e0b5ee71d06841d26488571900c89b6265"},
        {0x3f0af0,"ed77722fd11fbb8be3be115607c33eef5df2f069ab5596cf520ea50eab3f7921"},
        {0x44a9e0,"d67052183c8362fe27071a3801cfc27921331b1631a350313c027211aa708998"},
        {0x6a740,"9f97fdbf058b2d7752bff5ef048976664243f84904be0cb651b86003ec476461"},
        {0xe5f4f0,"259d6a2570eac2609f6edf9c95a3186548c8f06c25e89254f69dd50072c94417"},
        {0x3ebd90,"1e0daf2401b1d1a209e3560ee84117fa9bf19932239728d39a980eab14ebe74b"},
        {0x60fac0,"28b602033d72d6455bec69cb7ce57a81cedaf2620a3508ab0135d875fb840e90"},
        {0x48af80,"c91819d0ab9e7bfab104a641c2e38b4620f284c8d5adeb0d59a69b06b663b6cf"},
        {0x6115a0,"47683cebb30c07fc9c190ee333beb8bee03ba71071302b424b1be644dce2a8f5"},
        {0x342750,"cf506fb4d155e7069f24d9c29bcc62c1ed1da933ed21a50e270694fdba611dbc"},
        {0x3426c0,"23de49b683938982c4ea910bb245b66812f041cb7a5e27c7f8ff010dc4aa07d5"},
        {0x1b1c70,"2b226667354985830fd9d6f425b8558cd2cb133eb900bd254d771e0c5747d978"},
        {0x321c50,"ef90d19307dceb58d454d3d184f69a27c4e80033cebab3d888ac39a9a1f3bb95"},
        {0x322290,"76f877b1c8f9399463a8b827c77e7461eb67a70b39b02cf13b1e6526dc95182d"},
        {0x2096a0,"66ceb6da5d2cbedf26ec3fa013dd0f585c8c72e374deb60d93b49ce9358b785e"},
        {0x2044b0,"0eab5a8c74abfe0d2bb578b8a04f6c37269041d9bc3a8fc7db16ff91450393fc"},
        {0xda6540,"cc712023ad1285bb00a89e1b4901620637bf088a813e59800a28477d1e84bab0"},
        {0x3f5c30,"c70c491f0229d9b9d2582b53a3208c6dfcfdae5432b3aad8b36317a753b46297"},
        {0x2039c0,"9a7ff049ec7f2630868754afc7e0b4bc622e125bb0b3ecbd050c9e3c60507ae0"},
        {0x3e9120,"69cb8818733701549c0596bf8c90067de73203aa2c2b240df7d192a3dba4fbef"},
        {0x3e9480,"8cdf9334ddfc29f00b572493c2ee4242736f1b10f7915308222a794e91d197b0"},
        {0x3eb480,"46e7d30617dd402dc06ba04c8ea8d0af06ddbe5b0d3c93d0485cb192f029588e"},
        {0x3ebfd0,"639d6936e357f174d0e55c9e49c0b39eac38c7e6ce2d56d8e05b0154c8b5b056"},
        {0x44a0a0,"e75abe97e905206f3edb95f5b11f3ff15737f9b60adf45689637b62a1f26ee60"},
        {0x3ed600,"b29cb9ad3e2a95b3efb620b3c6f09cdc10231ea8e5052a55e7ef8b32166d38f1"},
        {0x3ecb20,"1bc5874101cbb56cbf794a6cd4f42117677890b67028d47670f7f883054e957a"},
        {0x3f3730,"f4fbf85065504d3ce6f77add6bd9f1ec9a8d52e0128c95ea9882e192019a84e3"},
        {0x3e5ed0,"8d6659abfab3190040e8cac9c120396d07e312ee7b2a45370823faa012a94360"},
        {0x3e9e50,"0b5fb35aa32c43284217e4942b1c1c5d5617ba01a39468948632b7d34741781f"},
        {0x45ca90,"9ae7bac621428972d4afaf8719b76bc9f1a1a2e3cd225974f105144041693e44"},
        {0x297630,"5c8655909952eb2f05ef98fca6e83c12d0d9d924253716373009ae2f80bec3b5"},
        {0x45c290,"c80209c8928069a2bd8fc5de7da89f1b1f8e386bc3b13f66e94f95c1cbb4d6f4"},
        {0x45c318,"943eb3933a680528b30128f30d47c187046bcd2b629fad58a47fd1ec39b4a3ee"},
        {0x47dd40,"6c2702e1121088c172be84d8c6d1247a7f96e61b1d1c757723d3ffabfd92ad28"},
        {0x47de93,"23e4b4ba4805ed768a18eda0a65353e083a6973df2c7afa38f2b96a5a74b4a09"},
        {0x47e049,"87b616551199e7936bd6e69f604274ccf65527891acf2409fd8ed16a6202fff7"},
        {0x458630,"05fb8e8a89a5bcf029cefb8dba8eaabc9871589f5ac94c566e915845a31ed300"},
        {0x449020,"eb3a3892153e14cf66c4cb13918fd2850c9482f6a94054db1b22cc4118172586"},
        {0x323990,"e90d48dcd731ebb911f40edc9980c774a4b55836c46e82453538a02a3e76e4dc"},
        {0x4103ea,"30bd234b1656fecf4f7886432b1dd6ccbcf2b4b413b0ab43f97a430cc5a22a89"},
        {0x48ae60,"18e24cec017509e7328a076722fb2c38686180f19fb2510cffaf636bcf21719d"},
        {0x7ae500,"8f78ef8bdd8b8b57954bc76403fe9f039d713503ed1f62f76a233d0cb94d14f9"},
        {0x323e7b,"66198be24229ca6d1b809fd9aa912709e2ce139bcaa72a68d47ec5d272791e89"},
        {0x617780,"7551fbeac222a844a6bbcba8332a9795e40da3d486ee4339a8d924d26f8e39d7"},
        {0x63f470,"6322b81000b364019e148ec50a47751e090f93e5000ff266f2e403fdd8bca0bc"},
        {0x45c070,"28bd4e82a8fb688e0addc2808f300afb4aa44068945992641826e703528b5424"},
        {0x44ba00,"e06169b5e5330e8cfe47b23d840e0545987eea134bfaeb82dafdc2dfeee5f431"},
        {0x44bbe0,"c2cf12e18d5385311fc573702461234512a6ddac9e77eeef0ccd1b08e0930f1d"},
        {0x330a40,"acfc08b49e61ba88dc09feea22142fe9dae5368ecc0ca0ba53d209965c4a6e7c"},
        {0x207400,"73257cf51e227b37aeb0470bbba68ebfc5c607563d1f48ba6aea33449df18b23"},
        {0x205c10,"41f55c97889157b758f388a8fe0a140204045101808f060fc88d3472633b160b"},
        {0xda67b0,"46cb06a9233b8fdc9258c2449b4d8fbd69c1e7a7c25bddf5dc9adb493e3d0126"}
    };
    for(const auto& pin:pins)
        if(resource::HashBytes(OwnImageRead(pinned.module,pin.rva,32))!=pin.hash)
            throw std::runtime_error("Native form implementation differs from its inspected function pins.");
    auto at=[&](std::uint32_t rva){return reinterpret_cast<void*>(state.image+rva);};
    state.api.fields=reinterpret_cast<FieldsFn>(at(0x325640));
    state.api.stringValue=reinterpret_cast<StringValueFn>(at(0xda6540));
    state.api.boolValue=reinterpret_cast<BoolValueFn>(at(0xda67b0));
    state.api.construct=reinterpret_cast<ConstructFn>(at(0x321f00));
    state.api.destroy=reinterpret_cast<DestroyFn>(at(0x3221c0));
    state.api.available=reinterpret_cast<SetFn>(at(0x343ea0));state.api.current=reinterpret_cast<SetFn>(at(0x343f30));
    state.api.availableData=reinterpret_cast<SetFn>(at(0x33ff10));
    state.api.lookup=reinterpret_cast<LookupFn>(at(0x442020));state.api.store=reinterpret_cast<StoreFn>(at(0x4421c0));
    state.api.metadata=reinterpret_cast<MetaFn>(at(0x444510));state.api.allocate=reinterpret_cast<AllocateFn>(at(0x6a740));
    state.api.free=reinterpret_cast<FreeFn>(at(0xe5f4f0));state.api.treeDestroy=reinterpret_cast<TreeDestroyFn>(at(0x3ebd90));
    state.api.protoConstruct=reinterpret_cast<ProtoConstructFn>(at(0x60fac0));
    state.api.protoParse=reinterpret_cast<ProtoParseFn>(at(0x48af80));state.api.protoDestroy=reinterpret_cast<DestroyFn>(at(0x6115a0));
    state.api.assignData=reinterpret_cast<AssignDataFn>(at(0x1b1c70));state.api.copySim=reinterpret_cast<MetaFn>(at(0x321c50));
    state.api.assignSim=reinterpret_cast<MetaFn>(at(0x322290));
    state.api.prepareHousehold=PrepareHouseholdRoots;
    state.api.controller=reinterpret_cast<HistoryFn>(at(0x3f5c30));state.api.avatar=reinterpret_cast<AvatarFn>(at(0x2039c0));
    state.api.modelBind=reinterpret_cast<ModelBindFn>(at(0x44a0a0));
    state.api.coreBind=reinterpret_cast<CoreBindFn>(at(0x3ebfd0));
    state.api.context=reinterpret_cast<ContextFn>(at(0x3ed600));state.api.index=reinterpret_cast<IndexFn>(at(0x3ecb20));
    state.api.undoCreate=reinterpret_cast<UndoCreateFn>(at(0x3e9e50));
    state.api.undoBind=reinterpret_cast<UndoBindFn>(at(0x45ca90));
    state.api.kindMask=reinterpret_cast<KindMaskFn>(at(0x297630));
    state.api.exportProto=reinterpret_cast<ExportProtoFn>(at(0x323990));
    state.api.protoSize=reinterpret_cast<ProtoSizeFn>(at(0x617780));
    state.api.protoArray=reinterpret_cast<ProtoArrayFn>(at(0x63f470));
    state.api.hairPreview=reinterpret_cast<PreviewFn>(at(0x45c070));
    state.api.clothingPreview=reinterpret_cast<PreviewFn>(at(0x44ba00));
    state.api.wingsPreview=reinterpret_cast<PreviewFn>(at(0x44bbe0));
    const auto init=MH_Initialize();if(init!=MH_OK && init!=MH_ERROR_ALREADY_INITIALIZED)
        throw std::runtime_error("Native form hook registry is unavailable.");
    struct Hook {void* target;void* detour;void** original;};
    Hook hooks[]={
        {at(0x321c50),reinterpret_cast<void*>(&HouseholdCopyConstruct),reinterpret_cast<void**>(&state.api.copySim)},
        {at(0x322290),reinterpret_cast<void*>(&HouseholdCopyAssign),reinterpret_cast<void**>(&state.api.assignSim)},
        {at(0x3221c0),reinterpret_cast<void*>(&HouseholdCopyDestroy),reinterpret_cast<void**>(&state.api.destroy)},
        {at(0x323990),reinterpret_cast<void*>(&HouseholdOutput),reinterpret_cast<void**>(&state.api.exportProto)},
        {at(0x207400),reinterpret_cast<void*>(&SaveAndExit),reinterpret_cast<void**>(&state.api.saveAndExit)},
        {at(0x205c10),reinterpret_cast<void*>(&CancelCas),reinterpret_cast<void**>(&state.api.cancelCas)},
        {at(0x47dd40),reinterpret_cast<void*>(&AnimationGenus),reinterpret_cast<void**>(&state.api.animationGenus)},
        {at(0x330a40),reinterpret_cast<void*>(&OutfitHair),reinterpret_cast<void**>(&state.api.outfitHair)},
        {at(0x327640),reinterpret_cast<void*>(&Import),reinterpret_cast<void**>(&state.api.import)},
        {at(0x3f0af0),reinterpret_cast<void*>(&History),reinterpret_cast<void**>(&state.api.history)},
        {at(0x44a9e0),reinterpret_cast<void*>(&Change),reinterpret_cast<void**>(&state.api.change)},
        {at(0x342750),reinterpret_cast<void*>(&Alternate),reinterpret_cast<void**>(&state.api.alternate)},
        {at(0x3426c0),reinterpret_cast<void*>(&Normalize),reinterpret_cast<void**>(&state.api.normalize)},
        {at(0x2096a0),reinterpret_cast<void*>(&SetOccultService),reinterpret_cast<void**>(&state.api.service)},
        {at(0x2044b0),reinterpret_cast<void*>(&GetOccultService),reinterpret_cast<void**>(&state.api.getOccultService)},
        {at(0x3e9120),reinterpret_cast<void*>(&Rebind),reinterpret_cast<void**>(&state.api.rebind)},
        {at(0x3e9480),reinterpret_cast<void*>(&Sync),reinterpret_cast<void**>(&state.api.sync)},
        {at(0x3eb480),reinterpret_cast<void*>(&BindSelected),reinterpret_cast<void**>(&state.api.bind)},
        {at(0x3f3730),reinterpret_cast<void*>(&SelectLayer),reinterpret_cast<void**>(&state.api.layer)},
        {at(0x3e5ed0),reinterpret_cast<void*>(&SelectUndo),reinterpret_cast<void**>(&state.api.undoSelect)}
    };
    std::vector<void*> created;
    try {
        InstallKindCall(state);
        for(auto& hook:hooks) {
            if(MH_CreateHook(hook.target,hook.detour,hook.original)!=MH_OK)
                throw std::runtime_error("Native form hook target is unavailable or already patched.");
            created.push_back(hook.target);
        }
        for(auto* target:created) if(MH_QueueEnableHook(target)!=MH_OK)
            throw std::runtime_error("Native form hook activation could not be queued.");
        if(MH_ApplyQueued()!=MH_OK) throw std::runtime_error("Native form hook activation failed.");
        state.installed=true;
    } catch(...) {
        for(auto* target:created) {MH_DisableHook(target);MH_RemoveHook(target);}
        RestoreKindCall(state);
        throw;
    }
}
inline std::string SeedAppearanceBytes(const ui::Json& request) {
    const auto encoded=request["native_hex"].get<std::string>();
    if(encoded.empty() || encoded.size()>8u*1024u*1024u || encoded.size()%2 ||
       encoded.find_first_not_of("0123456789abcdef")!=std::string::npos)
        throw std::runtime_error("Native appearance bytes are not bounded canonical hexadecimal.");
    auto nibble=[](char c){return c<='9'?c-'0':c-'a'+10;};std::string bytes(encoded.size()/2,'\0');
    for(std::size_t i=0;i<bytes.size();++i) bytes[i]=static_cast<char>((nibble(encoded[i*2])<<4)|nibble(encoded[i*2+1]));
    if(resource::HashBytes(bytes)!=request["sha256"].get<std::string>())
        throw std::runtime_error("Native appearance bytes differ from their captured SHA-256.");
    return bytes;
}
inline std::unique_ptr<NativeOwner> ReadAppearanceRecord(State& state,std::uint64_t id,std::uint32_t kind,
                                                       std::uint32_t mask,const std::string& bytes) {
    alignas(16) std::array<char,0x400> proto{};state.api.protoConstruct(proto.data());
    try {
        const ByteView view{bytes.data(),static_cast<std::uint64_t>(bytes.size())};
        if(!state.api.protoParse(proto.data(),&view) || Read<std::uint64_t>(proto.data(),0x10)!=id ||
           !(Read<std::uint32_t>(proto.data(),0x1dc)&(1u<<26)))
            throw std::runtime_error("Full appearance record belongs to another Sim or lacks attributes.");
        const auto attributes=Read<const void*>(proto.data(),0xc0);
        if(!attributes || !(Read<std::uint8_t>(attributes,0x13a)&1))
            throw std::runtime_error("Full appearance record lacks its detached tracker message.");
        const auto tracker=Read<const void*>(attributes,0x90);
        const auto count=Read<std::int32_t>(tracker,0x20);
        if(count<1 || count>7) throw std::runtime_error("Full appearance record inventory is out of bounds.");
        const auto records=Read<const void* const*>(tracker,0x18);Span(records,static_cast<std::size_t>(count)*8);
        const void* selectedRecord=nullptr;
        for(int i=0;i<count;++i) {
            const auto record=Read<const void*>(records,static_cast<std::size_t>(i)*8);
            if(!(Read<std::uint32_t>(record,0x84)&1)) throw std::runtime_error("Full appearance record has no typed kind.");
            if(Read<std::uint32_t>(record,0x18)==kind) {
                if(selectedRecord) throw std::runtime_error("Full appearance record kind is duplicated.");
                selectedRecord=record;
            }
        }
        if(!selectedRecord) throw std::runtime_error("The exact full appearance record is missing.");
        auto owner=std::make_unique<NativeOwner>(state.api,id);
        const DetachedTarget target(owner->data());
        state.api.available(owner->value,mask);state.api.current(owner->value,kind);
        // The primary/null-record path regenerates genetics and omits Fairy
        // wings. The record path imports the complete supplied genetic payload.
        state.api.fields(owner->value,proto.data(),selectedRecord);
        state.api.current(owner->value,kind);state.api.availableData(const_cast<void*>(owner->data()),mask);
        if(Read<std::uint64_t>(owner->value,0xb8)!=id || Read<std::uint32_t>(owner->data(),8)!=kind ||
           Read<std::uint32_t>(owner->data(),12)!=mask)
            throw std::runtime_error("Full appearance import changed its Sim, rendering kind or membership.");
        state.api.protoDestroy(proto.data());return owner;
    } catch(...) {state.api.protoDestroy(proto.data());throw;}
}
inline ui::Json Control(const ui::Json& request) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(request.is_object() && request.size()==1 && request.value("operation","")=="status") return Status();
    if(request.is_object() && request.size()==1 && request.value("operation","")=="view-status") return ViewStatus();
    if(request.is_object() && request.size()==3 && request.value("operation","")=="retire-committed-session") {
        // Internal Source completion only; not part of the public research
        // argument API. Every member's exact graph generation is required.
        if(!state.armed || !state.selectionEnabled || state.viewIntent || binding ||
           !request.contains("scope_id") || !request["scope_id"].is_string() ||
           request["scope_id"].get<std::string>()!=state.scope.id ||
           !request.contains("members") || !request["members"].is_array() ||
           request["members"].size()!=state.scope.members.size())
            throw std::runtime_error("CAS retirement requires the complete committed session scope.");
        {auto& box=pipe::Channel();std::lock_guard<std::mutex> channelLock(box.mutex);
         if(!box.finished.load(std::memory_order_acquire) || !box.stop || box.connected)
            throw std::runtime_error("An attached CAS transport still owns its appearance graph.");}
        std::set<std::uint64_t> members;
        for(const auto& row:request["members"]) {
            if(!row.is_object() || row.size()!=2 || !row.contains("sim_id") || !row["sim_id"].is_string() ||
               !row.contains("generation") || !row["generation"].is_number_unsigned())
                throw std::runtime_error("CAS retirement needs exact member identities and generations.");
            const auto id=SimId(row["sim_id"]);const auto found=state.bank.find(id);
            if(!members.insert(id).second || state.scope.members.find(id)==state.scope.members.end() ||
               found==state.bank.end() || !found->second.graph || found->second.viewFault ||
               found->second.graph->cursor().generation!=row["generation"].get<std::uint64_t>())
                throw std::runtime_error("CAS retirement graph changed or a committed member is missing.");
        }
        // The whole check precedes disposal. Keep the installed hooks and
        // armed roster ready for a new, freshly checkpointed import.
        state.selectionEnabled=false;state.boundSim=0;state.boundController=nullptr;
        state.observedNative={{"available",false}};state.viewResult=nullptr;
        state.householdCopiesEnabled.store(false,std::memory_order_release);state.householdCopies.clear();
        state.uiOwners.clear();state.viewTokens.clear();state.bank.clear();++state.sessionsRetired;
        state.preparedRoots.clear();state.preparedScope.clear();state.exportController=nullptr;state.householdOutputCalls.clear();
        state.householdAcceptance={{"verified",false},{"native_accepted",false}};
        return Status();
    }
    if(request.is_object() && request.size()==5 && request.value("operation","")=="export-owner-page") {
        if(!request.contains("scope_id") || !request["scope_id"].is_string() ||
           request["scope_id"].get<std::string>()!=state.scope.id || !state.selectionEnabled ||
           !request.contains("sim_id") || !request["sim_id"].is_string() ||
           !request.contains("after_owner_id") || !request["after_owner_id"].is_string() ||
           !request.contains("expected_generation") || !request["expected_generation"].is_number_unsigned())
            throw std::runtime_error("Owner export page requires its exact native scope and generation.");
        const auto id=SimId(request["sim_id"]);const auto at=state.bank.find(id);
        if(at==state.bank.end() || !at->second.graph)
            throw std::runtime_error("The complete captured appearance graph is unavailable.");
        const auto& graph=*at->second.graph;const auto cursor=graph.cursor();
        if(cursor.generation!=request["expected_generation"].get<std::uint64_t>())
            throw std::runtime_error("The appearance graph changed before its export page.");
        std::vector<std::string> ids;for(const auto& owner:graph.owners()) ids.push_back(owner.id);
        if(ids.empty() || ids.size()>2048) throw std::runtime_error("Owner export inventory exceeds its complete bound.");
        std::sort(ids.begin(),ids.end());const auto after=request["after_owner_id"].get<std::string>();
        std::size_t start=0;
        if(!after.empty()) {
            const auto found=std::find(ids.begin(),ids.end(),after);
            if(found==ids.end()) throw std::runtime_error("Owner export cursor is outside the exact graph.");
            start=static_cast<std::size_t>(found-ids.begin())+1;
        }
        auto rows=ui::Json::array();std::size_t used=0,wire=0,index=start;
        // Bound both work and wire bytes. A single serializer result is already
        // capped at 512 KiB; hexadecimal expansion stays below the 2 MiB ABI.
        for(;index<ids.size() && rows.size()<8;++index) {
            const auto& captured=graph.appearance(ids[index]);const auto bytes=SerializeOwner(state.api,*captured,id);
            if(!rows.empty() && used+bytes.size()>512*1024) break;
            auto links=ui::Json::array();for(const auto& target:graph.linkedTargets(ids[index])) links.push_back(target);
            auto row=ui::Json{{"owner_id",ids[index]},
                {"native_kind",Read<std::uint32_t>(captured->data(),8)},
                {"revision",graph.revision(ids[index])},{"linked_targets",links},
                {"native_hex",HexBytes(bytes)},{"sha256",resource::HashBytes(bytes)},{"bytes",bytes.size()}};
            const auto size=row.dump().size();
            if(size>1536*1024) throw std::runtime_error("One complete form exceeds the bounded page wire budget.");
            if(!rows.empty() && wire+size>1536*1024) break;
            used+=bytes.size();wire+=size;rows.push_back(std::move(row));
        }
        return {{"ok",true},{"schema",1},{"scope","native-owner-export-page"},{"pid",GetCurrentProcessId()},
            {"scope_id",state.scope.id},{"sim_id",std::to_string(id)},{"generation",cursor.generation},
            {"owned_mask",graph.mask()},{"selected_owner_id",cursor.owner},
            {"after_owner_id",after},{"start_index",start},{"total_owners",ids.size()},
            {"owners",rows},{"complete",index==ids.size()},
            {"next_owner_id",index==ids.size()?ui::Json(nullptr):ui::Json(ids[index-1])},
            {"appearance_written",false},{"model_harvested",false},{"game_files_written",false},
            {"native_patch_qualified",false},{"production_ready",false},
            {"source","committed-native-appearance"}};
    }
    if(request.is_object() && request.size()==5 && request.value("operation","")=="export-owner") {
        if(!request.contains("scope_id") || !request["scope_id"].is_string() ||
           request["scope_id"].get<std::string>()!=state.scope.id || !state.selectionEnabled ||
           !request.contains("sim_id") || !request["sim_id"].is_string() ||
           !request.contains("owner_id") || !request["owner_id"].is_string() ||
           !FormOwnerId(request["owner_id"].get<std::string>()) ||
           !request.contains("expected_generation") || !request["expected_generation"].is_number_unsigned())
            throw std::runtime_error("Appearance snapshot requires its exact native scope and generation.");
        const auto id=SimId(request["sim_id"]);const auto at=state.bank.find(id);
        if(at==state.bank.end() || !at->second.graph)
            throw std::runtime_error("The complete captured appearance is unavailable.");
        const auto& graph=*at->second.graph;const auto cursor=graph.cursor();
        if(cursor.generation!=request["expected_generation"].get<std::uint64_t>())
            throw std::runtime_error("The captured appearance changed before its snapshot.");
        const auto owner=request["owner_id"].get<std::string>();const auto& captured=graph.appearance(owner);
        const auto bytes=SerializeOwner(state.api,*captured,id);
        auto result=Status();result["owner_export"]={{"schema",1},{"sim_id",std::to_string(id)},
            {"owner_id",owner},{"generation",cursor.generation},{"native_kind",Read<std::uint32_t>(captured->data(),8)},
            {"native_hex",HexBytes(bytes)},{"sha256",resource::HashBytes(bytes)},{"bytes",bytes.size()},
            {"appearance_written",false},{"model_harvested",false},{"source","committed-native-appearance"},
            {"scope","Appearance DTO; nonappearance metadata can contain construction defaults."}};
        return result;
    }
    if(request.is_object() && request.size()==8 && request.value("operation","")=="stage-view") {
        for(const auto* name:{"scope_id","sim_id","request_id","expected_owner_id","owner_id"})
            if(!request.contains(name) || !request[name].is_string()) throw std::runtime_error("Untyped form view intent.");
        if(!request.contains("expected_generation") || !request["expected_generation"].is_number_unsigned() ||
           !request.contains("expected_layer") || !request["expected_layer"].is_number_unsigned())
            throw std::runtime_error("A form view requires its exact generation and native layer.");
        const auto id=SimId(request["sim_id"]);const auto member=state.bank.find(id);
        const auto rid=request["request_id"].get<std::string>();const auto owner=request["owner_id"].get<std::string>();
        const auto layer=request["expected_layer"].get<std::uint64_t>();
        if(!state.selectionEnabled || request["scope_id"].get<std::string>()!=state.scope.id ||
           state.viewIntent || (state.viewResult.is_object() && state.viewResult.value("state","")=="unresolved") ||
           member==state.bank.end() || !member->second.graph || rid.size()!=32 ||
           rid.find_first_not_of("0123456789abcdef")!=std::string::npos || !FormOwnerId(owner) || layer>1)
            throw std::runtime_error("Form view intent lacks an idle exact native scope.");
        auto& graph=*member->second.graph;const auto cursor=graph.cursor();
        if(cursor.owner!=request["expected_owner_id"].get<std::string>() || cursor.generation!=request["expected_generation"].get<std::uint64_t>())
            throw std::runtime_error("Form view intent belongs to a stale owner selection.");
        graph.appearance(owner);
        if(!state.observedNative.value("available",false) ||
           state.observedNative.value("sim_id","")!=std::to_string(id) ||
           state.observedNative["layer"].get<std::uint64_t>()!=layer)
            throw std::runtime_error("Form view intent belongs to a different observed native Sim or layer.");
        // SelectView checks the actual engine objects in the native CAS
        // callback before any edit. This worker only stages typed intent.
        const auto token=0x10000000u|static_cast<std::uint32_t>(std::stoul(rid.substr(0,7),nullptr,16));
        if(!state.viewTokens.insert(token).second) throw std::runtime_error("Form view intent token was already consumed; no replay.");
        state.viewIntent=std::make_unique<ViewIntent>(ViewIntent{rid,owner,id,cursor.generation,token,static_cast<std::uint8_t>(layer)});
        auto response=Status();response["view_stage"]={{"request_id",rid},{"token",token},
            {"sim_id",std::to_string(id)},{"owner_id",owner},{"staged_only",true}};
        response["token"]=token;return response;
    }
    if(request.is_object() && request.size()==3 && request.value("operation","")=="entry-ready" &&
       request.contains("scope_id") && request["scope_id"].is_string() && request.contains("sim_id")) {
        if(!state.selectionEnabled || request["scope_id"].get<std::string>()!=state.scope.id ||
           !state.scope.members.count(SimId(request["sim_id"])))
            throw std::runtime_error("Native CAS ready signal does not match its complete entry scope.");
        for(auto& row:state.bank) row.second.initialImport=false;
        return Status();
    }
    if(request.is_object() && request.size()==6 && request.value("operation","")=="seed-canonical") {
        for(const auto* name:{"scope_id","sim_id","native_hex","sha256"})
            if(!request.contains(name) || !request[name].is_string()) throw std::runtime_error("Untyped canonical appearance import.");
        if(!request.contains("native_kind") || !request["native_kind"].is_number_unsigned())
            throw std::runtime_error("Canonical appearance requires its exact kind.");
        const auto id=SimId(request["sim_id"]),kind=request["native_kind"].get<std::uint64_t>();
        const auto found=state.bank.find(id);
        if(!state.armed || state.selectionEnabled || request["scope_id"].get<std::string>()!=state.scope.id ||
           kind>64 || !Kind(static_cast<std::uint32_t>(kind)) || found==state.bank.end() || !found->second.seeded ||
           !found->second.initialImport || found->second.viewBound || !found->second.graph ||
           !(found->second.mask&kind) || (found->second.canonicalSourceMask&kind))
            throw std::runtime_error("Canonical appearance import lacks its exact unused entry scope.");
        const auto nativeKind=static_cast<std::uint32_t>(kind);
        auto owner=ReadAppearanceRecord(state,id,nativeKind,found->second.mask,SeedAppearanceBytes(request));
        found->second.graph->replace(found->second.graph->cursor(),NativeOwnerId(nativeKind),owner);
        found->second.owners.at(nativeKind)=std::move(owner);found->second.canonicalSourceMask|=nativeKind;
        return Status();
    }
    if(request.is_object() && request.size()==6 && request.value("operation","")=="seed-active") {
        for(const auto* name:{"scope_id","sim_id","native_hex","sha256"})
            if(!request.contains(name) || !request[name].is_string()) throw std::runtime_error("Untyped active appearance import.");
        if(!request.contains("native_kind") || !request["native_kind"].is_number_unsigned())
            throw std::runtime_error("An active appearance requires its exact rendering kind.");
        const auto id=SimId(request["sim_id"]);const auto kind=request["native_kind"].get<std::uint64_t>();
        const auto found=state.bank.find(id);
        if(!state.armed || state.selectionEnabled || request["scope_id"].get<std::string>()!=state.scope.id ||
           kind>64 || !Kind(static_cast<std::uint32_t>(kind)) || found==state.bank.end() || !found->second.seeded ||
           !found->second.initialImport || found->second.activeSourceSeeded || found->second.viewBound || !found->second.active || !found->second.graph ||
           found->second.entryOwner!="active/"+std::to_string(kind) ||
           found->second.graph->cursor().owner!=found->second.entryOwner ||
           Read<std::uint32_t>(found->second.active->data(),8)!=kind)
            throw std::runtime_error("Active appearance import lacks its exact unused entry scope.");
        auto owner=ReadAppearanceRecord(state,id,static_cast<std::uint32_t>(kind),found->second.mask,SeedAppearanceBytes(request));
        found->second.graph->commit(found->second.graph->cursor(),owner);
        found->second.active=std::move(owner);found->second.activeSourceSeeded=true;return Status();
    }
    if(request.is_object() && request.size()==7 && request.value("operation","")=="seed-appearance") {
        for(const auto* name:{"scope_id","sim_id","owner_id","native_hex","sha256"})
            if(!request.contains(name) || !request[name].is_string()) throw std::runtime_error("Untyped named appearance import.");
        if(!request.contains("native_kind") || !request["native_kind"].is_number_unsigned())
            throw std::runtime_error("A named appearance requires its existing native rendering kind.");
        const auto id=SimId(request["sim_id"]);const auto ownerId=request["owner_id"].get<std::string>();
        const auto kind64=request["native_kind"].get<std::uint64_t>();
        const auto found=state.bank.find(id);
        if(!state.armed || request["scope_id"].get<std::string>()!=state.scope.id || !FormOwnerId(ownerId) ||
           ownerId.compare(0,7,"native/")==0 || kind64>64 || !Kind(static_cast<std::uint32_t>(kind64)) ||
           found==state.bank.end() || !found->second.graph || !found->second.seeded || !found->second.initialImport ||
           !(found->second.mask&static_cast<std::uint32_t>(kind64)))
            throw std::runtime_error("Named appearance import lacks its exact pre-entry Sim/form scope.");
        const auto kind=static_cast<std::uint32_t>(kind64);
        auto owner=ReadAppearanceRecord(state,id,kind,found->second.mask,SeedAppearanceBytes(request));
        found->second.graph->capture(found->second.graph->cursor(),ownerId,kind,owner);
        OwnerUiTokens(state,id,found->second);return Status();
    }
    if(request.is_object() && request.size()==5 && request.value("operation","")=="seed" &&
       request.contains("scope_id") && request["scope_id"].is_string() &&
       request.contains("sim_id") && request.contains("native_hex") && request["native_hex"].is_string() &&
       request.contains("sha256") && request["sha256"].is_string()) {
        if(!state.armed || request["scope_id"].get<std::string>()!=state.scope.id)
            throw std::runtime_error("Native full-owner import does not match its armed scope.");
        const auto id=SimId(request["sim_id"]);if(!state.scope.members.count(id))
            throw std::runtime_error("Native full-owner import contains a foreign Sim.");
        const auto encoded=request["native_hex"].get<std::string>();
        if(encoded.empty() || encoded.size()>8u*1024u*1024u || encoded.size()%2 ||
           encoded.find_first_not_of("0123456789abcdef")!=std::string::npos)
            throw std::runtime_error("Native full-owner bytes are not bounded canonical hexadecimal.");
        std::string bytes(encoded.size()/2,'\0');
        auto nibble=[](char c){return c<='9'?c-'0':c-'a'+10;};
        for(std::size_t i=0;i<bytes.size();++i) bytes[i]=static_cast<char>((nibble(encoded[i*2])<<4)|nibble(encoded[i*2+1]));
        if(resource::HashBytes(bytes)!=request["sha256"].get<std::string>())
            throw std::runtime_error("Native full-owner bytes differ from their captured SHA-256.");
        const auto existing=state.bank.find(id);
        if(existing!=state.bank.end() && existing->second.seeded && !existing->second.initialImport)
            throw std::runtime_error("A ready CAS owner graph cannot be reseeded over user edits.");
        alignas(16) std::array<char,0x400> proto{};state.api.protoConstruct(proto.data());
        try {
            const ByteView view{bytes.data(),static_cast<std::uint64_t>(bytes.size())};
            if(!state.api.protoParse(proto.data(),&view)) throw std::runtime_error("Native full-owner protobuf parser refused this Sim.");
            if(!Capture(id,proto.data(),true)) throw std::runtime_error(state.bank[id].error);
        } catch(...) {state.api.protoDestroy(proto.data());throw;}
        state.api.protoDestroy(proto.data());return Status();
    }
    if(request.is_object() && request.size()==2 && request.value("operation","")=="activate" &&
       request.contains("scope_id") && request["scope_id"].is_string()) {
        if(!state.armed || request["scope_id"].get<std::string>()!=state.scope.id)
            throw std::runtime_error("Native owner activation does not match its armed scope.");
        for(const auto& row:state.scope.members) {
            const auto found=state.bank.find(row.first);
            if(found==state.bank.end() || found->second.mask!=row.second.mask || !found->second.seeded ||
               !found->second.active || !found->second.activeSourceSeeded || found->second.canonicalSourceMask!=row.second.mask)
                throw std::runtime_error("Every scoped Sim requires all stored and separate active native owners before selection.");
        }
        state.householdAcceptance={{"verified",false},{"native_accepted",false}};
        state.selectionEnabled=true;return Status();
    }
    const auto scope=ParseScope(request);
    if(state.armed) {
        if(scope.id!=state.scope.id || request["members"].size()!=state.scope.members.size())
            throw std::runtime_error("A different native form scope is already armed for this process.");
        for(const auto& row:scope.members) {
            const auto old=state.scope.members.find(row.first);
            if(old==state.scope.members.end() || old->second.mask!=row.second.mask)
                throw std::runtime_error("Native form scope replay changed its roster.");
        }
        return Status();
    }
    Install();state.scope=scope;state.armed=true;
    state.householdCopiesEnabled.store(false,std::memory_order_release);state.householdCopies.clear();
    state.preparedRoots.clear();state.preparedScope.clear();state.exportController=nullptr;state.householdOutputCalls.clear();
    state.householdAcceptance={{"verified",false},{"native_accepted",false}};return Status();
}
}
