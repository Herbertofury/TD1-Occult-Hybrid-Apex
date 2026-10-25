#pragma once
#include "ApexGfxSnapshotProfile.h"
#include "ApexNativeCasProbeWin.h"
#include "MinHook.h"
#include <array>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <intrin.h>
#include <mutex>
#include <thread>
#include <type_traits>

namespace td1::nativecas::gfxprofile::win {
using CaptureFn=bool(*)(void*);
using SnapshotDestructorFn=void*(*)(void*,unsigned);
using AllocateFn=void*(*)(void*,std::size_t,std::size_t,const void*);
using FreeFn=void(*)(void*,void*);
struct Definition {const char* name;std::uint32_t rva,end;const char* hash;std::uint32_t unwind_rva,unwind_end;const char* unwind_hex;};
// Hashes are filled from the authenticated runtime text, not encrypted disk
// .text. Full functions, original .pdata entries and their unwind codes gate
// installation. The disk executable identity is checked by OpenPinnedCasImage.
inline constexpr std::array<Definition,4> Definitions{{
    {"ContextCapture",0x1006a20,0x1006da5,"6d6c8e09cdf728bcd63a0db85218bdd08378c87d5fb589a959a7be47841f3484",0x267fd88,0x1006a54,"0134080034740c002f640b0026340a0006720250"},
    {"SnapshotDestructor",0x10063d0,0x1006509,"f3f3068ef310ee21440890c8c34662c8043df0f3125aa9387982bc8421e1c9d4",0x24adb98,0x1006509,"0114080014640800145407001434060014321070"},
    {"PointerAllocate",0x10026e0,0x100277c,"5b4d8359d405b2294f20c2701423a74aceeda29ec6fdfa6630ba5c7b36133a7e",0x267f8b8,0x1002701,"010f06000f640e000f540d000f920b70"},
    {"PointerFree",0x1002da0,0x1002f11,"fb7a49402348eb8b9965a3a2e42d54b3ce2fd6cca42301367b3a9c474c8644ff",0x24ec560,0x1002db8,"010e02000e320a50"}
}};
inline constexpr std::uintptr_t AllocateReturnRva=0x1006b8a,FreeReturnRva=0x10064b7;
inline constexpr std::uint32_t RootHeapRva=0x29640d0,RootHeapVtableRva=0x201ede0;
inline std::uint64_t Clock() noexcept {LARGE_INTEGER value{};return QueryPerformanceCounter(&value)?static_cast<std::uint64_t>(value.QuadPart):0;}
inline bool ReadValue(std::uintptr_t address,void* output,std::size_t size) noexcept {
    SIZE_T read=0;return address>=0x10000&&address<=0x00007fffffffffffULL-size&&
        ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),output,size,&read)&&read==size;
}
inline std::uint64_t Fingerprint(std::uintptr_t address,std::uint64_t generation) noexcept {
    auto value=static_cast<std::uint64_t>(address)^(generation*0x9e3779b97f4a7c15ull);
    value=(value^(value>>30))*0xbf58476d1ce4e5b9ull;value=(value^(value>>27))*0x94d049bb133111ebull;
    return (value^(value>>31))|1;
}

// This metadata covers ONLY the relocated body and jump-back. The separate
// entry relay runs before any copied prologue and must remain outside the range.
struct TrampolineUnwind {
    RUNTIME_FUNCTION entry{};
    std::uintptr_t base{};
    std::array<unsigned char,8> metadata{};
    std::array<unsigned char,14> original_jump{};
    std::size_t jump_offset{};
    bool registered{},tail_written{},jump_written{};
    static constexpr std::size_t SlotBytes=64,TailOffset=56;
    using AddFn=BOOLEAN(WINAPI*)(PRUNTIME_FUNCTION,DWORD,DWORD64);
    using DeleteFn=BOOLEAN(WINAPI*)(PRUNTIME_FUNCTION);
    static bool Bytes(std::uintptr_t at,const void* expected,std::size_t size) noexcept {
        std::array<unsigned char,64> value{};return size<=value.size()&&ReadValue(at,value.data(),size)&&std::memcmp(value.data(),expected,size)==0;
    }
    static bool Jump(std::uintptr_t at,std::uintptr_t destination) noexcept {
        std::array<unsigned char,14> expected{{0xff,0x25,0,0,0,0}};std::memcpy(expected.data()+6,&destination,8);return Bytes(at,expected.data(),expected.size());
    }
    bool Prepare(std::size_t kind,void* trampoline,void* target,void* detour,AddFn add=RtlAddFunctionTable) noexcept {
        if(kind>=4||registered||tail_written||jump_written||!trampoline||!target||!detour||!add)return false;
        base=reinterpret_cast<std::uintptr_t>(trampoline);const auto native=reinterpret_cast<std::uintptr_t>(target),hook=reinterpret_cast<std::uintptr_t>(detour);
        std::size_t body=0;
        if(kind==0) {const unsigned char code[]{0x40,0x55,0x48,0x83,0xec,0x40};if(!Bytes(base,code,sizeof(code))||!Jump(base+6,native+6))return false;body=20;metadata={1,6,2,0,6,0x72,2,0x50};}
        if(kind==1) {const unsigned char code[]{0x48,0x89,0x5c,0x24,8};if(!Bytes(base,code,sizeof(code))||!Jump(base+5,native+5))return false;body=19;metadata={1,5,2,0,5,0x34,1,0};}
        if(kind==2) {const unsigned char code[]{0x48,0x89,0x6c,0x24,0x10};if(!Bytes(base,code,sizeof(code))||!Jump(base+5,native+5))return false;body=19;metadata={1,5,2,0,5,0x54,2,0};}
        if(kind==3) {const unsigned char code[]{0x48,0x85,0xd2,0x75,0x0e};if(!Bytes(base,code,sizeof(code))||!Jump(base+5,native+0x170)||!Jump(base+19,native+9))return false;body=33;metadata={1,0,0,0,0,0,0,0};}
        if(!body||body+14>TailOffset||!Jump(base+body,hook))return false;
        const std::array<unsigned char,8> empty{};if(!Bytes(base+TailOffset,empty.data(),empty.size()))return false;
        MEMORY_BASIC_INFORMATION region{};
        if(VirtualQuery(trampoline,&region,sizeof(region))!=sizeof(region)||region.State!=MEM_COMMIT||
           (region.Protect&(PAGE_GUARD|PAGE_NOACCESS))||base<reinterpret_cast<std::uintptr_t>(region.BaseAddress)||
           base-reinterpret_cast<std::uintptr_t>(region.BaseAddress)>region.RegionSize||
           region.RegionSize-(base-reinterpret_cast<std::uintptr_t>(region.BaseAddress))<SlotBytes)return false;
        jump_offset=kind==3?19:kind==0?6:5;
        if(!ReadValue(base+jump_offset,original_jump.data(),original_jump.size()))return false;
        std::array<unsigned char,14> jump{{0x49,0xbb,0,0,0,0,0,0,0,0,0x41,0xff,0xe3,0x90}};
        const auto destination=native+(kind==3?9:kind==0?6:5);std::memcpy(jump.data()+2,&destination,8);
        DWORD old=0;if(!VirtualProtect(reinterpret_cast<void*>(base),SlotBytes,PAGE_EXECUTE_READWRITE,&old))return false;
        // RtlVirtualUnwind mistakes MinHook's FF25 jump-back for a tail
        // epilogue and skips the copied prologue. These exact4 native bodies
        // never read incoming R11. The same-length MOVABS R11/JMP R11 keeps
        // every argument/nonvolatile/stack location and is not an epilogue.
        std::memcpy(reinterpret_cast<void*>(base+jump_offset),jump.data(),jump.size());jump_written=true;
        std::memcpy(reinterpret_cast<void*>(base+TailOffset),metadata.data(),metadata.size());
        FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(base+jump_offset),jump.size());
        DWORD ignored=0;const bool restored=VirtualProtect(reinterpret_cast<void*>(base),SlotBytes,old,&ignored)!=FALSE;
        tail_written=true;entry={0,static_cast<DWORD>(body),static_cast<DWORD>(TailOffset)};
        if(!restored||!add(&entry,1,base))return false;
        registered=true;return true;
    }
    // Allowed ONLY before any activation attempt. After callbacks might have
    // dispatched, both metadata and disabled trampolines live until process exit.
    bool RollbackNeverActivated(DeleteFn remove=RtlDeleteFunctionTable) noexcept {
        if(registered&&(!remove||!remove(&entry)))return false;
        registered=false;
        if(tail_written) {
            if(!Bytes(base+TailOffset,metadata.data(),metadata.size()))return false;
            DWORD old=0;if(!VirtualProtect(reinterpret_cast<void*>(base+TailOffset),metadata.size(),PAGE_EXECUTE_READWRITE,&old))return false;
            std::memset(reinterpret_cast<void*>(base+TailOffset),0,metadata.size());DWORD ignored=0;
            if(!VirtualProtect(reinterpret_cast<void*>(base+TailOffset),metadata.size(),old,&ignored))return false;
            tail_written=false;
        }
        if(jump_written){DWORD old=0;if(!VirtualProtect(reinterpret_cast<void*>(base+jump_offset),original_jump.size(),PAGE_EXECUTE_READWRITE,&old))return false;
            std::memcpy(reinterpret_cast<void*>(base+jump_offset),original_jump.data(),original_jump.size());FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(base+jump_offset),original_jump.size());DWORD ignored=0;
            if(!VirtualProtect(reinterpret_cast<void*>(base+jump_offset),original_jump.size(),old,&ignored))return false;jump_written=false;}
        return true;
    }
};

struct ContextFrame {ContextFrame* previous{};TimingTicket ticket{};CaptureRecord record{};std::uintptr_t context{},heap{};};
struct SnapshotFrame {SnapshotFrame* previous{};std::uintptr_t context{};std::uintptr_t caller{};bool owner_read{};};
inline thread_local ContextFrame* CurrentContext{};
inline thread_local SnapshotFrame* CurrentSnapshot{};
inline thread_local unsigned ObservationDepth{};
struct Runtime {
    SnapshotTiming timing;
    std::array<std::atomic<void*>,4> original{};
    std::array<void*,4> targets{};
    std::array<TrampolineUnwind,4> unwind{};
    std::array<std::string,4> original_prefix{},owned_prefix{};
    std::mutex requests,control,worker_mutex;
    std::condition_variable worker_condition;
    std::thread worker;
    std::atomic<bool> worker_running{};
    bool worker_cancel{},attempted{},created{},active_hooks{},activation_attempted{},conflict{};
    std::uintptr_t image{};
    std::uint64_t frequency{};
    std::string scope,error;
    double prepare_ms{};
    // Controller-only seams also let the exact activation/restoration code run
    // against an isolated fixture. Native callbacks never use these functions.
    std::string (*read_prefix)(Runtime&,std::size_t){};
    MH_STATUS (WINAPI* enable_hook)(LPVOID)=MH_EnableHook;
    MH_STATUS (WINAPI* disable_hook)(LPVOID)=MH_DisableHook;
};
// Process lifetime storage matches the disabled trampoline/unwind lifetime.
// Constructed by control/fixture setup before a native hook can dispatch.
inline Runtime& Shared(){static Runtime* value=new Runtime;return *value;}

inline bool Observing() noexcept {return ObservationDepth!=0;}
inline bool QualifiedAllocate(Runtime& runtime,void* heap,std::size_t bytes,std::size_t alignment,const void* info) noexcept {
    return CurrentContext&&CurrentContext->ticket.active&&CurrentContext->record.heap_verified&&
        reinterpret_cast<std::uintptr_t>(heap)==CurrentContext->heap&&bytes==0x268&&alignment==16&&info==nullptr&&runtime.timing.Active();
}
inline bool QualifiedFree(Runtime& runtime,void* heap) noexcept {
    return CurrentContext&&CurrentContext->ticket.active&&CurrentContext->record.heap_verified&&CurrentSnapshot&&CurrentSnapshot->owner_read&&
        CurrentSnapshot->context==CurrentContext->context&&reinterpret_cast<std::uintptr_t>(heap)==CurrentContext->heap&&runtime.timing.Active();
}
inline void BeginContext(Runtime& runtime,void* context,ContextFrame& frame) noexcept {
    ++ObservationDepth;frame.previous=CurrentContext;frame.context=reinterpret_cast<std::uintptr_t>(context);
    frame.ticket=runtime.timing.Begin(Boundary::Capture,true,Clock);frame.record.generation=frame.ticket.generation;
    if(frame.ticket.active) {
        frame.record.serial=runtime.timing.NextRecordSerial();frame.record.context_fingerprint=Fingerprint(frame.context,frame.ticket.generation);
        frame.record.thread=GetCurrentThreadId();frame.record.started_ticks=frame.ticket.started;
        std::uintptr_t context_heap=0,root=0,vtable=0;
        frame.record.heap_verified=ReadValue(frame.context,&context_heap,8)&&ReadValue(frame.context+0x18,&frame.heap,8)&&
            ReadValue(runtime.image+RootHeapRva,&root,8)&&root&&context_heap==root&&frame.heap==root&&
            ReadValue(root,&vtable,8)&&vtable==runtime.image+RootHeapVtableRva;
        if(!ReadValue(frame.context+0xe8,&frame.record.native_frame_id,8))frame.record.heap_verified=false;
    }
    CurrentContext=&frame;--ObservationDepth;
}
inline void EndContext(Runtime& runtime,ContextFrame& frame,bool abnormal,bool result) noexcept {
    ++ObservationDepth;CurrentContext=frame.previous;
    if(frame.ticket.active) {
        const auto now=Clock();frame.record.elapsed_ticks=now>=frame.ticket.started?now-frame.ticket.started:0;
        frame.record.unwound=abnormal;frame.record.native_return=result;
        runtime.timing.Record(frame.record);runtime.timing.End(frame.ticket,abnormal,false,frame.record.heap_verified,[now]() noexcept{return now;});
    }
    --ObservationDepth;
}

// Direct _ReturnAddress is captured in each noinline detour BEFORE helpers.
// No unrelated heap call reads an argument, clock, counter or game object.
__declspec(noinline) inline void* Allocate(void* heap,std::size_t bytes,std::size_t alignment,const void* info) {
    auto& runtime=Shared();const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    const auto native=reinterpret_cast<AllocateFn>(runtime.original[2].load(std::memory_order_acquire));
    if(caller!=runtime.image+AllocateReturnRva||Observing()||!runtime.timing.Active())return native(heap,bytes,alignment,info);
    const auto incoming=GetLastError();++ObservationDepth;
    const bool qualified=QualifiedAllocate(runtime,heap,bytes,alignment,info);
    const auto ticket=runtime.timing.Begin(Boundary::PointerAllocate,runtime.timing.Detail(),Clock);--ObservationDepth;
    void* result=nullptr;SetLastError(incoming);
    __try {result=native(heap,bytes,alignment,info);}
    __finally {
        const auto outgoing=GetLastError();++ObservationDepth;const auto now=ticket.timed?Clock():0;
        if(ticket.active&&qualified&&CurrentContext) {
            ++CurrentContext->record.allocations;if(result==nullptr&&!AbnormalTermination())++CurrentContext->record.allocation_nulls;
            if(ticket.timed&&now>=ticket.started)CurrentContext->record.allocation_ticks+=now-ticket.started;
        }
        runtime.timing.End(ticket,AbnormalTermination()!=FALSE,result==nullptr,qualified,[now]() noexcept{return now;});
        --ObservationDepth;SetLastError(outgoing);
    }
    return result;
}
__declspec(noinline) inline void Free(void* heap,void* page) {
    auto& runtime=Shared();const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    const auto native=reinterpret_cast<FreeFn>(runtime.original[3].load(std::memory_order_acquire));
    if(caller!=runtime.image+FreeReturnRva||Observing()||!runtime.timing.Active()){native(heap,page);return;}
    const auto incoming=GetLastError();++ObservationDepth;const bool qualified=QualifiedFree(runtime,heap);
    const auto ticket=runtime.timing.Begin(Boundary::PointerFree,runtime.timing.Detail(),Clock);--ObservationDepth;SetLastError(incoming);
    __try {native(heap,page);}
    __finally {
        const auto outgoing=GetLastError();++ObservationDepth;const auto now=ticket.timed?Clock():0;
        if(ticket.active&&qualified&&CurrentContext) {
            ++CurrentContext->record.frees;
            if(CurrentSnapshot->caller==runtime.image+0x10087ee)++CurrentContext->record.retired_frees;
            if(CurrentSnapshot->caller==runtime.image+0x1006adb)++CurrentContext->record.merged_frees;
            if(ticket.timed&&now>=ticket.started)CurrentContext->record.free_ticks+=now-ticket.started;
        }
        runtime.timing.End(ticket,AbnormalTermination()!=FALSE,false,qualified,[now]() noexcept{return now;});--ObservationDepth;SetLastError(outgoing);
    }
}
__declspec(noinline) inline bool Capture(void* context) {
    auto& runtime=Shared();const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    const auto native=reinterpret_cast<CaptureFn>(runtime.original[0].load(std::memory_order_acquire));
    if((caller!=runtime.image+0xff7e88&&caller!=runtime.image+0xff7929)||Observing()||!runtime.timing.Active())return native(context);
    const auto incoming=GetLastError();ContextFrame frame{};BeginContext(runtime,context,frame);bool result=false;SetLastError(incoming);
    __try {result=native(context);}
    __finally {const auto outgoing=GetLastError();EndContext(runtime,frame,AbnormalTermination()!=FALSE,result);SetLastError(outgoing);}
    return result;
}
__declspec(noinline) inline void* SnapshotDestructor(void* snapshot,unsigned flags) {
    auto& runtime=Shared();const auto native=reinterpret_cast<SnapshotDestructorFn>(runtime.original[1].load(std::memory_order_acquire));
    if(Observing()||!runtime.timing.Active()||!CurrentContext)return native(snapshot,flags);
    const auto incoming=GetLastError();SnapshotFrame frame{};frame.previous=CurrentSnapshot;
    frame.caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());++ObservationDepth;
    frame.owner_read=ReadValue(reinterpret_cast<std::uintptr_t>(snapshot)+0x10,&frame.context,8);
    const auto ticket=runtime.timing.Begin(Boundary::SnapshotDestructor,true,Clock);CurrentSnapshot=&frame;--ObservationDepth;
    void* result=nullptr;SetLastError(incoming);
    __try {result=native(snapshot,flags);}
    __finally {
        const auto outgoing=GetLastError();++ObservationDepth;CurrentSnapshot=frame.previous;
        runtime.timing.End(ticket,AbnormalTermination()!=FALSE,false,frame.owner_read&&CurrentContext&&frame.context==CurrentContext->context,Clock);
        --ObservationDepth;SetLastError(outgoing);
    }
    return result;
}
inline const std::array<void*,4> Detours{{reinterpret_cast<void*>(Capture),reinterpret_cast<void*>(SnapshotDestructor),reinterpret_cast<void*>(Allocate),reinterpret_cast<void*>(Free)}};

inline std::string HexBytes(const char* text) {
    std::string result;for(std::size_t i=0;text[i];i+=2){if(!text[i+1])throw std::runtime_error("Unwind pin hex is incomplete.");auto digit=[](char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;};const int a=digit(text[i]),b=digit(text[i+1]);if(a<0||b<0)throw std::runtime_error("Unwind pin hex differs.");result.push_back(static_cast<char>((a<<4)|b));}return result;
}
inline void VerifyNative(Runtime& runtime) {
    auto image=OpenPinnedCasImage();runtime.image=reinterpret_cast<std::uintptr_t>(image.module);
    for(std::size_t i=0;i<Definitions.size();++i) {
        const auto& d=Definitions[i];
        if(resource::HashBytes(OwnImageRead(image.module,d.rva,d.end-d.rva))!=d.hash)throw std::runtime_error("Renderer profiler native function differs from its authenticated complete body.");
        DWORD64 base=0;auto* entry=RtlLookupFunctionEntry(runtime.image+d.rva,&base,nullptr);
        if(!entry||base!=runtime.image||entry->BeginAddress!=d.rva||entry->EndAddress!=d.unwind_end||entry->UnwindData!=d.unwind_rva||
           OwnImageRead(image.module,d.unwind_rva,HexBytes(d.unwind_hex).size())!=HexBytes(d.unwind_hex))throw std::runtime_error("Renderer profiler native unwind entry differs.");
        runtime.targets[i]=reinterpret_cast<void*>(runtime.image+d.rva);runtime.original_prefix[i]=OwnImageRead(image.module,d.rva,32);
    }
    const auto alloc=OwnImageRead(image.module,0x1006b80,10),release=OwnImageRead(image.module,0x10064b1,6);
    if(alloc!=HexBytes("488b01458d4110ff5048")||release!=HexBytes("488b01ff5060"))throw std::runtime_error("Exact renderer pointer-page caller differs.");
    std::uint64_t targets[2]{};
    const auto valloc=OwnImageRead(image.module,RootHeapVtableRva+0x48,8),vfree=OwnImageRead(image.module,RootHeapVtableRva+0x60,8);
    std::memcpy(&targets[0],valloc.data(),8);std::memcpy(&targets[1],vfree.data(),8);
    if(targets[0]!=runtime.image+Definitions[2].rva||targets[1]!=runtime.image+Definitions[3].rva)throw std::runtime_error("Root native heap vtable ABI differs.");
}
inline std::string EntryPrefix(Runtime& runtime,std::size_t index) {
    return runtime.read_prefix?runtime.read_prefix(runtime,index):OwnImageRead(reinterpret_cast<HMODULE>(runtime.image),Definitions[index].rva,32);
}
inline void DisableOwnedLocked(Runtime& runtime) {
    runtime.timing.Stop();bool ok=true;
    for(std::size_t i=0;i<Definitions.size();++i)if(runtime.targets[i]&&runtime.original[i].load()) {
        const auto bytes=EntryPrefix(runtime,i);
        if(bytes==runtime.original_prefix[i])continue;
        if(runtime.owned_prefix[i].empty()||bytes!=runtime.owned_prefix[i]){runtime.conflict=true;ok=false;continue;}
        const auto status=runtime.disable_hook(runtime.targets[i]);if(status!=MH_OK&&status!=MH_ERROR_DISABLED)ok=false;
    }
    if(ok)for(std::size_t i=0;i<Definitions.size();++i)if(runtime.targets[i]&&EntryPrefix(runtime,i)!=runtime.original_prefix[i])ok=false;
    runtime.active_hooks=!ok;
    if(!ok)throw std::runtime_error("Renderer profiler could not verify restoration of every owned native entry; foreign changes were not overwritten.");
}
inline void ActivatePreparedLocked(Runtime& runtime) {
    try {
        runtime.activation_attempted=true;
        // Derive every exact owned entry before activation. Use individual
        // owned EnableHook operations, leaving no partially queued intents
        // for another component's later ApplyQueued to activate unexpectedly.
        for(std::size_t i=0;i<Definitions.size();++i) {
            auto bytes=runtime.original_prefix[i];bytes[0]=static_cast<char>(0xe9);
            const auto relay=runtime.unwind[i].base+runtime.unwind[i].entry.EndAddress;
            const auto delta=static_cast<std::int64_t>(relay)-static_cast<std::int64_t>(runtime.image+Definitions[i].rva+5);
            if(delta<INT32_MIN||delta>INT32_MAX)throw std::runtime_error("Renderer profiler relay exceeds native branch range.");
            const auto relative=static_cast<std::int32_t>(delta);std::memcpy(bytes.data()+1,&relative,4);runtime.owned_prefix[i]=std::move(bytes);
        }
        for(std::size_t i=0;i<Definitions.size();++i) {
            if(EntryPrefix(runtime,i)!=runtime.original_prefix[i])throw std::runtime_error("Renderer profiler entry changed before its owned activation.");
            if(runtime.enable_hook(runtime.targets[i])!=MH_OK)throw std::runtime_error("Renderer profiler activation failed.");
            runtime.active_hooks=true;
            if(EntryPrefix(runtime,i)!=runtime.owned_prefix[i])throw std::runtime_error("Renderer profiler activated entry differs from its owned patch.");
        }
    } catch(...) {DisableOwnedLocked(runtime);throw;}
}
inline void InstallLocked(Runtime& runtime) {
    if(runtime.conflict)throw std::runtime_error("Renderer profiler observed a conflicting patch; use a fresh runtime.");
    const auto started=Clock();VerifyNative(runtime);
    LARGE_INTEGER frequency{};if(!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0)throw std::runtime_error("Renderer profiler QPC clock unavailable.");
    runtime.frequency=static_cast<std::uint64_t>(frequency.QuadPart);
    if(!runtime.created) {
        if(runtime.attempted)throw std::runtime_error("Renderer profiler preparation previously failed; use a fresh runtime.");
        runtime.attempted=true;
        const auto status=MH_Initialize();if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED)throw std::runtime_error("Renderer profiler hook registry unavailable.");
        HMODULE retained=nullptr;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&Shared),&retained))throw std::runtime_error("Renderer profiler module lifetime cannot be pinned.");
        try {
            for(std::size_t i=0;i<Definitions.size();++i) {
                void* original=nullptr;if(MH_CreateHook(runtime.targets[i],Detours[i],&original)!=MH_OK)throw std::runtime_error("Renderer profiler target is already owned or unavailable.");
                runtime.original[i].store(original,std::memory_order_release);
                if(!runtime.unwind[i].Prepare(i,original,runtime.targets[i],Detours[i]))throw std::runtime_error("Renderer profiler trampoline layout/unwind registration differs.");
            }
            runtime.created=true;
        } catch(...) {
            for(auto& value:runtime.unwind)if(value.registered||value.tail_written||value.jump_written)value.RollbackNeverActivated();
            throw;
        }
    } else for(std::size_t i=0;i<Definitions.size();++i)if(!runtime.unwind[i].registered||
        !TrampolineUnwind::Bytes(runtime.unwind[i].base+TrampolineUnwind::TailOffset,runtime.unwind[i].metadata.data(),8))throw std::runtime_error("Renderer profiler retained unwind lifetime changed.");
    ActivatePreparedLocked(runtime);runtime.prepare_ms=double(Clock()-started)*1000.0/double(runtime.frequency);
}

inline void CancelWorker(Runtime& runtime) {
    {std::lock_guard<std::mutex> guard(runtime.worker_mutex);runtime.worker_cancel=true;runtime.worker_condition.notify_all();}
    if(runtime.worker.joinable()&&runtime.worker.get_id()!=std::this_thread::get_id())runtime.worker.join();
}
inline void Stop() {
    auto& runtime=Shared();if(Observing()||CurrentContext)throw std::runtime_error("Stop renderer profiling outside a native observation callback.");
    std::lock_guard<std::mutex> request(runtime.requests);CancelWorker(runtime);std::lock_guard<std::mutex> guard(runtime.control);
    if(runtime.created||runtime.active_hooks)DisableOwnedLocked(runtime);else runtime.timing.Stop();
}
inline void StartTimeoutWorkerLocked(Runtime& runtime,unsigned milliseconds) {
    {std::lock_guard<std::mutex> worker_guard(runtime.worker_mutex);runtime.worker_cancel=false;}
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(milliseconds);
    // One explicitly requested diagnostic timeout, with no polling loop or
    // persistent service. It restores native entries at the end of the window.
    runtime.worker_running=true;
    try {runtime.worker=std::thread([&runtime,deadline] {
        std::unique_lock<std::mutex> wait(runtime.worker_mutex);
        if(runtime.worker_condition.wait_until(wait,deadline,[&runtime]{return runtime.worker_cancel;})){runtime.worker_running=false;return;}
        wait.unlock();std::lock_guard<std::mutex> control(runtime.control);
        try {DisableOwnedLocked(runtime);}catch(const std::exception& error){runtime.error=error.what();}
        runtime.worker_running=false;
    });}catch(...){runtime.worker_running=false;throw;}
}
inline void Configure(const std::string& scope,unsigned milliseconds,bool detail_timing=false) {
    auto& runtime=Shared();if(Observing()||CurrentContext)throw std::runtime_error("Configure renderer profiling outside native observation callbacks.");
    if(!milliseconds){Stop();return;}
    if(milliseconds>30000||scope.empty()||scope.size()>128||scope.find('\0')!=std::string::npos)throw std::runtime_error("Use an explicit scope and renderer profiling window of1to30000milliseconds.");
    std::lock_guard<std::mutex> request(runtime.requests);CancelWorker(runtime);std::lock_guard<std::mutex> guard(runtime.control);
    if(runtime.active_hooks)DisableOwnedLocked(runtime);
    try {
        InstallLocked(runtime);
        if(runtime.frequency>UINT64_MAX/milliseconds||!runtime.timing.Start(Clock(),runtime.frequency*milliseconds/1000,detail_timing))throw std::runtime_error("Prior renderer profiling calls remain in flight or duration overflowed.");
        runtime.scope=scope;runtime.error.clear();
        StartTimeoutWorkerLocked(runtime,milliseconds);
    } catch(const std::exception& error) {
        runtime.error=error.what();runtime.timing.Stop();
        if(runtime.active_hooks)try{DisableOwnedLocked(runtime);}catch(const std::exception& cleanup){runtime.error+="; ";runtime.error+=cleanup.what();}
        throw;
    }
}
inline ui::Json Snapshot() {
    auto& runtime=Shared();std::lock_guard<std::mutex> guard(runtime.control);const auto data=runtime.timing.Read();
    ui::Json rows=ui::Json::array(),records=ui::Json::array();const double scale=runtime.frequency?1000.0/double(runtime.frequency):0;
    for(std::size_t i=0;i<Definitions.size();++i){const auto& row=data.rows[i];const bool timed=i<2||data.detail_timing;rows.push_back({{"boundary",Definitions[i].name},{"started",row.started},{"returned",row.returned},{"unwound",row.unwound},{"null_returns",row.null_returns},{"qualified_calls",row.qualified},{"timed",timed},{"total_ms",timed?ui::Json(double(row.ticks)*scale):ui::Json(nullptr)},{"max_ms",timed?ui::Json(double(row.maximum_ticks)*scale):ui::Json(nullptr)}});}
    if(!data.records_contended)for(std::size_t i=0;i<data.record_count;++i){const auto& row=data.records[i];records.push_back({{"scope_serial",row.serial},{"context_fingerprint",row.context_fingerprint},{"native_frame_id",row.native_frame_id},{"thread_id",row.thread},{"heap_verified",row.heap_verified},{"native_return",row.native_return},{"unwound",row.unwound},{"started_qpc",row.started_ticks},{"total_ms",double(row.elapsed_ticks)*scale},{"allocations",row.allocations},{"allocation_nulls",row.allocation_nulls},{"frees",row.frees},{"retired_frees",row.retired_frees},{"merged_frees",row.merged_frees},{"allocation_ms",double(row.allocation_ticks)*scale},{"free_ms",double(row.free_ticks)*scale}});}
    return {{"available",true},{"enabled",data.enabled},{"active_heap_hooks",runtime.active_hooks},{"prepared",runtime.created},{"generation",data.generation},{"scope_id",runtime.scope},{"inflight",data.inflight},{"detail_timing",data.detail_timing},{"boundaries",std::move(rows)},{"captures",std::move(records)},{"records_contended",data.records_contended},{"skipped_calls",data.skipped},{"dropped_records",data.dropped_records},{"preparation_ms",runtime.prepare_ms},{"error",runtime.error},{"conflicting_patch",runtime.conflict},{"native_entries_restored",runtime.created&&!runtime.active_hooks&&!runtime.conflict},{"disabled_trampolines_retained",runtime.created},{"diagnostic_timeout_thread",runtime.worker_running.load()},{"background_service",false},{"appearance_written",false},{"page_substitution",false},{"page_retention",false},{"timing","QPC wall time including hook/observer overhead and scheduling; not exclusive CPU time"},{"counter_semantics","calls accepted while enabled; accepted calls may finish after stop"},{"context_fingerprint_semantics","window address hash; not a persistent Sim, form or lifetime identity"}};
}
static_assert(std::is_trivially_destructible_v<ContextFrame>&&std::is_trivially_destructible_v<SnapshotFrame>&&std::is_trivially_destructible_v<TimingTicket>,"SEH wrappers require POD observation frames");
} // namespace td1::nativecas::gfxprofile::win
