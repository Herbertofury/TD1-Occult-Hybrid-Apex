// Version-pinned CAS owner import. Cross-kind conversion is quarantined.
// Separate editable owner graphs are captured independently of EA's pair view.
#pragma once
#include "ApexNativeCasEngine.h"
#include "ApexCasOwnerGraph.h"
#include "ApexNativeCasProbeWin.h"
#include "MinHook.h"
#include <mutex>
#include <array>
#include <memory>
#include <malloc.h>
#include <cmath>
#include <intrin.h>

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
inline thread_local const void* detachedTarget=nullptr;
struct DetachedTarget {
    const void* previous;
    explicit DetachedTarget(const void* data):previous(detachedTarget) {detachedTarget=data;}
    ~DetachedTarget() {detachedTarget=previous;}
};
struct Api {
    ImportFn import=nullptr;FieldsFn fields=nullptr;ConstructFn construct=nullptr;DestroyFn destroy=nullptr;
    SetFn available=nullptr,current=nullptr,availableData=nullptr;LookupFn lookup=nullptr;StoreFn store=nullptr;MetaFn metadata=nullptr;
    AllocateFn allocate=nullptr;FreeFn free=nullptr;TreeDestroyFn treeDestroy=nullptr;
    HistoryFn history=nullptr;ChangeFn change=nullptr;
    ProtoConstructFn protoConstruct=nullptr;DestroyFn protoDestroy=nullptr;ProtoParseFn protoParse=nullptr;
    AlternateFn alternate=nullptr;
    NormalizeFn normalize=nullptr;AssignDataFn assignData=nullptr;MetaFn copySim=nullptr;
    ServiceFn service=nullptr;HistoryFn controller=nullptr;AvatarFn avatar=nullptr;
    RebindFn rebind=nullptr;SyncFn sync=nullptr;BindFn bind=nullptr;
    ModelBindFn modelBind=nullptr;CoreBindFn coreBind=nullptr;ContextFn context=nullptr;IndexFn index=nullptr;LayerFn layer=nullptr;
    UndoSelectFn undoSelect=nullptr;UndoCreateFn undoCreate=nullptr;UndoBindFn undoBind=nullptr;
    KindMaskFn kindMask=nullptr;
    ExportProtoFn exportProto=nullptr;ProtoSizeFn protoSize=nullptr;ProtoArrayFn protoArray=nullptr;
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
struct NativeOwner {
    void* value=nullptr;DestroyFn destroy=nullptr;
    NativeOwner(const Api& api,std::uint64_t id):destroy(api.destroy) {
        value=_aligned_malloc(0x830,16);if(!value) throw std::bad_alloc();
        api.construct(value,id);
    }
    NativeOwner(const NativeOwner&)=delete;NativeOwner& operator=(const NativeOwner&)=delete;
    ~NativeOwner() {if(value) {destroy(value);_aligned_free(value);}}
    const void* data() const {return static_cast<const char*>(value)+0xd0;}
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
    std::unique_ptr<OwnerGraph<std::unique_ptr<NativeOwner>>> graph;
    std::map<std::string,std::unique_ptr<NativeUndo>> undoOwners;
    bool initialImport=true,viewBound=false,viewFault=false;void* boundGroup=nullptr;void* boundContext=nullptr;std::string entryOwner=NativeOwnerId(1),partner=NativeOwnerId(2);std::map<std::string,std::uint32_t> uiTokens;
    std::uint32_t mask=0,preferred=0;unsigned imports=0,switches=0,skippedPackets=0;bool seeded=false;std::string error;
};
struct ViewIntent {
    std::string request,owner;std::uint64_t sim=0,generation=0;std::uint32_t token=0;std::uint8_t layer=0;
};
struct State {
    std::recursive_mutex mutex;Api api;Scope scope;std::map<std::uint64_t,Imported> bank;
    std::unique_ptr<ViewIntent> viewIntent;ui::Json viewResult=nullptr;std::set<std::uint32_t> viewTokens;std::uint64_t nativeUiSequence=0;std::uint32_t nextUiToken=0x20000000;
    std::map<std::uint32_t,std::pair<std::uint64_t,std::string>> uiOwners;
    std::uint64_t boundSim=0;void* boundController=nullptr;
    unsigned kindBiasPrevented=0;
    void* kindRelay=nullptr;std::int32_t originalKindCall=0,patchedKindCall=0;bool kindCallPatched=false,kindRelayReady=false;
    std::uintptr_t image=0;bool installed=false,armed=false,selectionEnabled=false;unsigned intercepted=0,converted=0,alternateOverrides=0,normalizationsPrevented=0,initialOwnersImported=0,serviceSelections=0,rebindCorrections=0,blockedConversions=0;
};
// The DLL remains loaded for the entire process. Never run game destructors
// from CRT/DllMain teardown after the game's native services have gone away.
inline State& Runtime() {static auto* state=new State;return *state;}
struct Selection {std::uint64_t id=0;std::uint32_t target=0;void* controller=nullptr;};
inline thread_local Selection selected;
struct ViewBinding {void* controller=nullptr;Imported* bank=nullptr;std::string owner;};
inline thread_local ViewBinding* binding=nullptr;
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
inline std::unique_ptr<NativeOwner> CloneModel(State& state,Imported& bank,void* controller) {
    const auto model=Read<void*>(controller,0x1d0);
    auto copy=std::make_unique<NativeOwner>(state.api,bank.graph->cursor().sim);
    state.api.assignData(const_cast<void*>(copy->data()),static_cast<char*>(model)+0x170);
    state.api.current(copy->value,bank.graph->cursor().kind);
    state.api.availableData(const_cast<void*>(copy->data()),bank.mask);return copy;
}
inline void StoreCanonical(State& state,Imported& bank,void* controller) {
    using CacheFn=void*(*)(void*,std::uint64_t);
    const auto group=Read<void*>(controller,0x100);
    auto* metadata=Read<CacheFn>(Read<void*>(controller),0x410)(controller,GroupId(group));
    if(!metadata) throw std::runtime_error("Native view lacks its complete appearance cache.");
    for(const auto& owner:bank.owners) state.api.store(metadata,owner.first,bank.graph->appearance(owner.first)->data());
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
        // CAS setters have already written the selected model's complete
        // CasData. The stock two-slot synchronizer is not a serializer: it
        // changes preview modes, regenerates outfit/genetic parts and copies
        // fields to the other layer. A real Fairy round trip changed every
        // outfit's four body-hair swatches without an edit. Persist the actual
        // current model through the game's deep-copy API instead. No prior
        // appearance, field whitelist or regenerated outfit is substituted.
        auto edited=CloneModel(state,bank,controller);
        const auto selected=layer?Read<void*>(group,0x4c0):group;
        if(!selected) throw std::runtime_error("Selected native form has no exact appearance slot.");
        state.api.assignData(static_cast<char*>(selected)+0xd0,edited->data());
        bank.graph->commit(bank.graph->cursor(),edited);
        // The explicit graph, not EA's copied inactive fields, owns the other
        // form. This also honors intentional links while keeping defaults apart.
        if(inactive) state.api.assignData(static_cast<char*>(inactive)+0xd0,
            bank.graph->appearance(layer?bank.entryOwner:bank.partner)->data());
        StoreCanonical(state,bank,controller);
    } catch(const std::exception& error) {
        bank.viewFault=true;state.viewResult={{"state","unresolved"},{"sim_id",std::to_string(id)},
            {"message",error.what()},{"native_sync_blocked",true}};
    }
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
            const auto layer=static_cast<std::uint8_t>(owner==bank.entryOwner?0:1);
            if(layer) bank.partner=owner;
            auto* child=Read<void*>(group,0x4c0);
            if(!child) {
                child=state.api.allocate(0x830,nullptr,0,0,nullptr,0);if(!child) throw std::bad_alloc();
                state.api.copySim(child,bank.graph->appearance(bank.partner)->value);
                const auto references=Read<std::uint32_t>(child,8)+1;
                std::memcpy(static_cast<char*>(child)+8,&references,4);std::memcpy(static_cast<char*>(group)+0x4c0,&child,8);
            }
            state.api.assignData(static_cast<char*>(group)+0xd0,bank.graph->appearance(bank.entryOwner)->data());
            state.api.assignData(static_cast<char*>(child)+0xd0,bank.graph->appearance(bank.partner)->data());
            bank.boundGroup=group;std::memcpy(static_cast<char*>(controller)+0x242,&layer,1);
            StoreCanonical(state,bank,controller);
            ViewBinding current{controller,&bank,owner};binding=&current;
            BindSelected(controller,notify);binding=previous;bank.viewBound=true;
        } catch(const std::exception& error) {
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
}
inline bool SelectView(std::uint32_t token) {
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
        const auto layer=static_cast<std::uint8_t>(intent.owner==bank.entryOwner?0:1);
        if(layer) bank.partner=intent.owner;
        if(desiredKind!=1) bank.preferred=desiredKind;
        state.api.assignData(static_cast<char*>(group)+0xd0,bank.graph->appearance(bank.entryOwner)->data());
        state.api.assignData(static_cast<char*>(child)+0xd0,bank.graph->appearance(bank.partner)->data());
        StoreCanonical(state,bank,controller);
        bank.boundGroup=group;bank.viewBound=false;std::memcpy(static_cast<char*>(controller)+0x242,&layer,1);
        ViewBinding current{controller,&bank,intent.owner};const auto previous=binding;binding=&current;
        try {state.api.coreBind(controller,index,false);} catch(...) {binding=previous;throw;}
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
        result["independent_undo_bound"]=true;result["undo_owner_id"]=intent.owner;return true;
    } catch(const std::exception& error) {if(affected) affected->viewFault=true;result["state"]="unresolved";result["message"]=error.what();return false;}
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
            const DetachedTarget target(replacement.active->data());
            state.api.fields(replacement.active->value,proto,nullptr);
            // The field loader can classify a multi-kind tracker using its
            // legacy priority rules. The tracker's explicit current field is
            // the active owner identity; restore it after loading appearance.
            const auto activeKind=current?current:1u;
            if(!Kind(activeKind) || !(member->second.mask&activeKind))
                throw std::runtime_error("Native active entry owner has an unknown or unowned kind.");
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
        if(replacement.active) {
            replacement.entryOwner="active/"+std::to_string(activeKind);
            replacement.graph->capture(replacement.graph->cursor(),replacement.entryOwner,activeKind,replacement.active);
            replacement.graph->select(replacement.graph->cursor(),replacement.entryOwner);
        }
        replacement.partner=NativeOwnerId(activeKind==1?(replacement.preferred?replacement.preferred:1u):1u);
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
        const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
        const auto group=controller?Read<void*>(controller,0x100):nullptr;
        if(!group) return result;const auto id=Read<std::uint64_t>(group,0xb8);const auto at=state.bank.find(id);
        if(at==state.bank.end() || !at->second.graph) return result;
        const auto cursor=at->second.graph->cursor();
        result["available"]=true;result["sim_id"]=std::to_string(id);result["owner_id"]=cursor.owner;
        result["native_kind"]=cursor.kind;result["generation"]=cursor.generation;
        result["layer"]=Read<std::uint8_t>(controller,0x242);
        result["state"]=at->second.viewFault?"unresolved":at->second.viewBound?"bound":"unbound";
    } catch(const std::exception&) {result["available"]=false;}
    return result;
}
inline ui::Json Status() {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);auto rows=ui::Json::array();
    for(const auto& member:state.scope.members) {
        const auto found=state.bank.find(member.first);auto kinds=ui::Json::array();
        auto genus=ui::Json::array();
        if(found!=state.bank.end()) for(const auto& owner:found->second.owners) {
            kinds.push_back(owner.first);
            genus.push_back({{"kind",owner.first},{"age",Read<std::uint32_t>(owner.second->data())},
                {"gender",Read<std::uint32_t>(owner.second->data(),4)},
                {"species",Read<std::uint32_t>(owner.second->data(),16)}});
        }
        auto graphOwners=ui::Json::array();
        if(found!=state.bank.end() && found->second.graph) {
            const auto& graph=*found->second.graph;
            for(const auto& owner:graph.owners()) {
                auto links=ui::Json::array();
                for(const auto& target:graph.owners())
                    if(graph.linked(owner.id,target.id)) links.push_back(target.id);
                graphOwners.push_back({{"owner_id",owner.id},{"native_kind",owner.nativeKind},{"revision",owner.revision},
                    {"selected",owner.selected},{"linked_targets",links},{"ui_token",found->second.uiTokens.at(owner.id)}});
            }
        }
        rows.push_back({{"sim_id",std::to_string(member.first)},{"owned_mask",member.second.mask},
            {"imported_mask",found==state.bank.end()?0:found->second.mask},{"kinds",kinds},{"imported_genus",genus},
            {"imports",found==state.bank.end()?0:found->second.imports},{"switches",found==state.bank.end()?0:found->second.switches},
            {"source_seeded",found!=state.bank.end() && found->second.seeded},
            {"active_entry_captured",found!=state.bank.end() && found->second.active!=nullptr},
            {"active_entry_kind",found!=state.bank.end() && found->second.active?Read<std::uint32_t>(found->second.active->data(),8):0},
            {"narrowed_packets_skipped",found==state.bank.end()?0:found->second.skippedPackets},
            {"independent_owner_graph",found!=state.bank.end() && found->second.graph!=nullptr},
            {"owner_view_ready",false},
            {"separate_owners",graphOwners},
            {"graph_selected_kind",found!=state.bank.end() && found->second.graph?found->second.graph->cursor().kind:0},
            {"graph_generation",found!=state.bank.end() && found->second.graph?found->second.graph->cursor().generation:0},
            {"native_view_bound",found!=state.bank.end() && found->second.viewBound},
            {"native_view_fault",found!=state.bank.end() && found->second.viewFault},
            {"undo_owner_count",found==state.bank.end()?0:found->second.undoOwners.size()},
            {"graph_selected_owner_id",found!=state.bank.end() && found->second.graph?found->second.graph->cursor().owner:""},
            {"error",found==state.bank.end()?"":found->second.error}});
    }
    ui::Json selectedNative={{"available",false}};
    if(state.image && state.selectionEnabled) try {
        const auto address=reinterpret_cast<void*>(state.image+0x2948f00);
        const auto controller=Read<void*>(address);const auto group=controller?Read<void*>(controller,0x100):nullptr;
        if(group) {
            const auto id=Read<std::uint64_t>(group,0xb8);const auto layer=Read<std::uint8_t>(controller,0x242);
            const auto view=layer?Read<void*>(group,0x4c0):group;
            if(layer<=1 && view && state.scope.members.count(id)) {
                const auto kind=Read<std::uint32_t>(view,0xd8),mask=Read<std::uint32_t>(view,0xdc);
                if(Kind(kind) && Read<void*>(address)==controller && Read<void*>(controller,0x100)==group &&
                   Read<std::uint8_t>(controller,0x242)==layer && Read<std::uint64_t>(group,0xb8)==id)
                    selectedNative={{"available",true},{"sim_id",std::to_string(id)},{"occult_type",kind},
                        {"all_occult_types",mask},{"layer",layer}};
                const auto model=Read<void*>(controller,0x1d0);
                if(model && selectedNative.value("available",false)) {
                    selectedNative["model_occult_type"]=Read<std::uint32_t>(model,0x178);
                    selectedNative["model_all_occult_types"]=Read<std::uint32_t>(model,0x17c);
                    selectedNative["model_cache_present"]=Read<void*>(model,0x518)!=nullptr;
                    selectedNative["model_avatar_present"]=Read<void*>(model,0x520)!=nullptr;
                }
            }
        }
    } catch(const std::exception&) {selectedNative={{"available",false}};}
    return {{"ok",true},{"pid",GetCurrentProcessId()},{"installed",state.installed},{"armed",state.armed},
        {"scope_id",state.scope.id},{"selection_enabled",state.selectionEnabled},{"members",rows},{"existing_owner_selections",state.intercepted},
        {"native_converter_calls",state.converted},{"game_files_written",false},
        {"alternate_kind_overrides",state.alternateOverrides},
        {"normalizations_prevented",state.normalizationsPrevented},{"initial_active_owners_imported",state.initialOwnersImported},
        {"native_service_selections",state.serviceSelections},
        {"alternate_rebind_corrections",state.rebindCorrections},
        {"blocked_existing_owner_conversions",state.blockedConversions},
        {"conversion_quarantined",true},{"independent_owner_view_ready",false},
        {"owner_view_adapter_available",state.installed},{"owner_view_result",state.viewResult},
        {"owner_view_staged",state.viewIntent!=nullptr},
        {"native_kind_bias_prevented",state.kindBiasPrevented},
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
        {0x2096a0,"66ceb6da5d2cbedf26ec3fa013dd0f585c8c72e374deb60d93b49ce9358b785e"},
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
        {0x323990,"e90d48dcd731ebb911f40edc9980c774a4b55836c46e82453538a02a3e76e4dc"},
        {0x617780,"7551fbeac222a844a6bbcba8332a9795e40da3d486ee4339a8d924d26f8e39d7"},
        {0x63f470,"6322b81000b364019e148ec50a47751e090f93e5000ff266f2e403fdd8bca0bc"}
    };
    for(const auto& pin:pins)
        if(resource::HashBytes(OwnImageRead(pinned.module,pin.rva,32))!=pin.hash)
            throw std::runtime_error("Native form implementation differs from its inspected function pins.");
    auto at=[&](std::uint32_t rva){return reinterpret_cast<void*>(state.image+rva);};
    state.api.fields=reinterpret_cast<FieldsFn>(at(0x325640));
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
    const auto init=MH_Initialize();if(init!=MH_OK && init!=MH_ERROR_ALREADY_INITIALIZED)
        throw std::runtime_error("Native form hook registry is unavailable.");
    struct Hook {void* target;void* detour;void** original;};
    Hook hooks[]={
        {at(0x327640),reinterpret_cast<void*>(&Import),reinterpret_cast<void**>(&state.api.import)},
        {at(0x3f0af0),reinterpret_cast<void*>(&History),reinterpret_cast<void**>(&state.api.history)},
        {at(0x44a9e0),reinterpret_cast<void*>(&Change),reinterpret_cast<void**>(&state.api.change)},
        {at(0x342750),reinterpret_cast<void*>(&Alternate),reinterpret_cast<void**>(&state.api.alternate)},
        {at(0x3426c0),reinterpret_cast<void*>(&Normalize),reinterpret_cast<void**>(&state.api.normalize)},
        {at(0x2096a0),reinterpret_cast<void*>(&SetOccultService),reinterpret_cast<void**>(&state.api.service)},
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
inline ui::Json Control(const ui::Json& request) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(request.is_object() && request.size()==1 && request.value("operation","")=="status") return Status();
    if(request.is_object() && request.size()==1 && request.value("operation","")=="view-status") return ViewStatus();
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
        const auto controller=Read<void*>(reinterpret_cast<void*>(state.image+0x2948f00));
        const auto group=controller?Read<void*>(controller,0x100):nullptr;
        if(!group || Read<std::uint64_t>(group,0xb8)!=id || Read<std::uint8_t>(controller,0x242)!=layer)
            throw std::runtime_error("Form view intent belongs to a different native Sim or layer.");
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
        const auto encoded=request["native_hex"].get<std::string>();
        if(encoded.empty() || encoded.size()>8u*1024u*1024u || encoded.size()%2 ||
           encoded.find_first_not_of("0123456789abcdef")!=std::string::npos)
            throw std::runtime_error("Named native appearance bytes are not bounded canonical hexadecimal.");
        auto nibble=[](char c){return c<='9'?c-'0':c-'a'+10;};std::string bytes(encoded.size()/2,'\0');
        for(std::size_t i=0;i<bytes.size();++i) bytes[i]=static_cast<char>((nibble(encoded[i*2])<<4)|nibble(encoded[i*2+1]));
        if(resource::HashBytes(bytes)!=request["sha256"].get<std::string>())
            throw std::runtime_error("Named appearance bytes differ from their captured SHA-256.");
        alignas(16) std::array<char,0x400> proto{};state.api.protoConstruct(proto.data());
        try {
            const ByteView view{bytes.data(),static_cast<std::uint64_t>(bytes.size())};
            if(!state.api.protoParse(proto.data(),&view) || Read<std::uint64_t>(proto.data(),0x10)!=id)
                throw std::runtime_error("Named appearance's native message belongs to a different Sim.");
            auto owner=std::make_unique<NativeOwner>(state.api,id);
            const DetachedTarget target(owner->data());
            state.api.fields(owner->value,proto.data(),nullptr);
            const auto kind=static_cast<std::uint32_t>(kind64);
            state.api.current(owner->value,kind);state.api.availableData(const_cast<void*>(owner->data()),found->second.mask);
            if(Read<std::uint64_t>(owner->value,0xb8)!=id) throw std::runtime_error("Named appearance deserializer changed its Sim identity.");
            found->second.graph->capture(found->second.graph->cursor(),ownerId,kind,owner);
            OwnerUiTokens(state,id,found->second);
        } catch(...) {state.api.protoDestroy(proto.data());throw;}
        state.api.protoDestroy(proto.data());return Status();
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
            if(found==state.bank.end() || found->second.mask!=row.second.mask || !found->second.seeded || !found->second.active)
                throw std::runtime_error("Every scoped Sim requires all stored and separate active native owners before selection.");
        }
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
    Install();state.scope=scope;state.armed=true;return Status();
}
}
