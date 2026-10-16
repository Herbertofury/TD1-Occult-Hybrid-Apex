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
struct Api {
    ImportFn import=nullptr;FieldsFn fields=nullptr;ConstructFn construct=nullptr;DestroyFn destroy=nullptr;
    SetFn available=nullptr,current=nullptr,availableData=nullptr;LookupFn lookup=nullptr;StoreFn store=nullptr;MetaFn metadata=nullptr;
    AllocateFn allocate=nullptr;FreeFn free=nullptr;TreeDestroyFn treeDestroy=nullptr;
    HistoryFn history=nullptr;ChangeFn change=nullptr;
    ProtoConstructFn protoConstruct=nullptr;DestroyFn protoDestroy=nullptr;ProtoParseFn protoParse=nullptr;
    AlternateFn alternate=nullptr;
    NormalizeFn normalize=nullptr;AssignDataFn assignData=nullptr;MetaFn copySim=nullptr;
    ServiceFn service=nullptr;HistoryFn controller=nullptr;AvatarFn avatar=nullptr;
    RebindFn rebind=nullptr;
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
struct Imported {
    std::map<std::uint32_t,std::unique_ptr<NativeOwner>> owners;
    std::unique_ptr<NativeOwner> active;
    std::unique_ptr<OwnerGraph<std::unique_ptr<NativeOwner>>> graph;
    bool initialImport=true;
    std::uint32_t mask=0,preferred=0;unsigned imports=0,switches=0,skippedPackets=0;bool seeded=false;std::string error;
};
struct State {
    std::recursive_mutex mutex;Api api;Scope scope;std::map<std::uint64_t,Imported> bank;
    std::uintptr_t image=0;bool installed=false,armed=false,selectionEnabled=false;unsigned intercepted=0,converted=0,alternateOverrides=0,normalizationsPrevented=0,initialOwnersImported=0,serviceSelections=0,rebindCorrections=0,blockedConversions=0;
};
// The DLL remains loaded for the entire process. Never run game destructors
// from CRT/DllMain teardown after the game's native services have gone away.
inline State& Runtime() {static auto* state=new State;return *state;}
struct Selection {std::uint64_t id=0;std::uint32_t target=0;void* controller=nullptr;};
inline thread_local Selection selected;

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
        const auto attributes=Read<const void*>(proto,0xc0);
        if(!attributes || !(Read<std::uint8_t>(attributes,0x13a)&1))
            throw std::runtime_error("Native import lacks occult tracker attributes.");
        const auto tracker=Read<const void*>(attributes,0x90);
        if(!tracker || (Read<std::uint32_t>(tracker,0x10)|1u)!=member->second.mask)
            throw std::runtime_error("Imported membership differs from the captured household scope: "+
                std::to_string(tracker?Read<std::uint32_t>(tracker,0x10):0));
        const auto count=Read<std::int32_t>(tracker,0x20);
        if(count<1 || count>7) throw std::runtime_error("Native import form count is out of bounds.");
        const auto records=Read<const void* const*>(tracker,0x18);Span(records,static_cast<std::size_t>(count)*8);
        std::map<std::uint32_t,const void*> byKind;std::vector<std::uint32_t> kinds;
        for(int i=0;i<count;++i) {
            const auto record=Read<const void*>(records,static_cast<std::size_t>(i)*8);
            if(!(Read<std::uint32_t>(record,0x84)&1)) throw std::runtime_error("Imported form has no native kind field.");
            const auto kind=Read<std::uint32_t>(record,0x18);kinds.push_back(kind);byKind.emplace(kind,record);
        }
        ValidateKinds(member->second.mask,kinds);
        Imported replacement;replacement.imports=bank.imports+1;replacement.seeded=sourceSeed;
        const auto current=Read<std::uint32_t>(tracker,0x14);
        replacement.preferred=Kind(current) && current!=1 && (member->second.mask&current)?current:0;
        for(const auto& row:byKind) {
            auto owner=std::make_unique<NativeOwner>(state.api,id);
            state.api.available(owner->value,member->second.mask);
            state.api.current(owner->value,row.first);
            state.api.fields(owner->value,proto,row.second);
            if(Read<std::uint64_t>(owner->value,0xb8)!=id || Read<std::uint32_t>(owner->data(),8)!=row.first ||
               Read<std::uint32_t>(owner->data(),12)!=member->second.mask)
                throw std::runtime_error("Native form deserializer changed owner identity or membership.");
            replacement.mask|=row.first;replacement.owners.emplace(row.first,std::move(owner));
            if(!replacement.preferred && row.first!=1) replacement.preferred=row.first;
        }
        if(sourceSeed) {
            replacement.active=std::make_unique<NativeOwner>(state.api,id);
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
                api.assignData(const_cast<void*>(clone->data()),from->data());
                api.current(clone->value,destination);
                if(Read<std::uint64_t>(clone->value,0xb8)!=id || Read<std::uint32_t>(clone->data(),8)!=destination)
                    throw std::runtime_error("Cloned appearance changed its exact Sim/form identity.");
                return clone;
            });
        if(replacement.active)
            replacement.graph->commit(replacement.graph->cursor(),replacement.active);
        bank=std::move(replacement);return true;
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
    if(state.selectionEnabled && IndependentHybridGenus(mask,current)) {
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
        if(std::isfinite(number) && number>=1 && number<=64 && std::floor(number)==number)
            target=static_cast<std::uint32_t>(number);
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
    // A request for an existing owner is NOT permission to convert it. The
    // separate owner-view adapter must bind that record on the native UI thread.
    std::lock_guard<std::recursive_mutex> lock(state.mutex);
    ++state.blockedConversions;return false;
}
inline void Rebind(void* controller,const void* metadata,std::uint32_t target) {
    auto& state=Runtime();
    {
        std::lock_guard<std::recursive_mutex> lock(state.mutex);
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
            for(const auto& owner:found->second.owners) {
                auto links=ui::Json::array();
                for(const auto& target:found->second.owners)
                    if(graph.linked(owner.first,target.first)) links.push_back(target.first);
                graphOwners.push_back({{"kind",owner.first},{"revision",graph.revision(owner.first)},
                    {"selected",graph.cursor().kind==owner.first},{"linked_targets",links}});
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
        {0x3e9120,"69cb8818733701549c0596bf8c90067de73203aa2c2b240df7d192a3dba4fbef"}
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
        {at(0x3e9120),reinterpret_cast<void*>(&Rebind),reinterpret_cast<void**>(&state.api.rebind)}
    };
    std::vector<void*> created;
    try {
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
        throw;
    }
}
inline ui::Json Control(const ui::Json& request) {
    auto& state=Runtime();std::lock_guard<std::recursive_mutex> lock(state.mutex);
    if(request.is_object() && request.size()==1 && request.value("operation","")=="status") return Status();
    if(request.is_object() && request.size()==3 && request.value("operation","")=="entry-ready" &&
       request.contains("scope_id") && request["scope_id"].is_string() && request.contains("sim_id")) {
        if(!state.selectionEnabled || request["scope_id"].get<std::string>()!=state.scope.id ||
           !state.scope.members.count(SimId(request["sim_id"])))
            throw std::runtime_error("Native CAS ready signal does not match its complete entry scope.");
        for(auto& row:state.bank) row.second.initialImport=false;
        return Status();
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
            if(found==state.bank.end() || found->second.mask!=row.second.mask)
                throw std::runtime_error("Every scoped Sim must have all native forms imported before selection.");
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
