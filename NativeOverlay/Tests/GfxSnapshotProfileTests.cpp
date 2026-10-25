#pragma warning(push)
#pragma warning(disable:4018) // Existing shared probe header, outside this subtask.
#include "ApexNativeCasProbeWin.h"
#pragma warning(pop)
#include "ApexGfxSnapshotProfileWin.h"
#include <algorithm>
#include <atomic>
#include <future>
#include <iostream>
#include <stdexcept>
#include <vector>

using namespace td1::nativecas::gfxprofile;
namespace profile=td1::nativecas::gfxprofile::win;
#define CHECK(x) do {if(!(x))throw std::runtime_error(#x);}while(false)

void atomic_window_and_clock_gates() {
    SnapshotTiming timing;std::uint64_t now=100,clocks=0;auto clock=[&]() noexcept {++clocks;return now;};
    CHECK(!timing.Begin(Boundary::PointerAllocate,true,clock).active&&clocks==0);
    CHECK(timing.Start(now,1000,false));
    auto ticket=timing.Begin(Boundary::PointerAllocate,false,clock);CHECK(ticket.active&&clocks==0);
    timing.Stop();CHECK(!timing.Start(now,1000,false));
    timing.End(ticket,false,true,true,clock);CHECK(clocks==0);
    auto data=timing.Read();CHECK(data.inflight==0&&data.rows[2].returned==1&&data.rows[2].null_returns==1&&data.rows[2].qualified==1);
    CHECK(timing.Start(now,1000,true));ticket=timing.Begin(Boundary::PointerFree,true,clock);now+=23;
    timing.End(ticket,true,false,false,clock);data=timing.Read();CHECK(data.rows[3].unwound==1&&data.rows[3].ticks==23&&data.rows[3].maximum_ticks==23);
    timing.Stop();CHECK(!timing.Start(UINT64_MAX-2,3,false));
}
void exact_deadline_and_record_bounds() {
    SnapshotTiming timing;std::uint64_t now=50;auto clock=[&]() noexcept{return now;};CHECK(timing.Start(now,10,true));
    now=60;CHECK(!timing.Begin(Boundary::Capture,true,clock).active);CHECK(!timing.Active()&&timing.Read().inflight==0);
    CHECK(timing.Start(now,1000,true));auto scope=timing.Begin(Boundary::Capture,true,clock);
    for(std::uint64_t i=0;i<100;++i){CaptureRecord r;r.generation=scope.generation;r.serial=i+1;timing.Record(r);}
    CHECK(timing.Read().record_count==64);timing.End(scope,false,false,true,clock);timing.Stop();
    CHECK(timing.Start(now,1000,false));CaptureRecord old;old.generation=scope.generation;timing.Record(old);CHECK(timing.Read().record_count==0);timing.Stop();
}
void concurrent_counting() {
    SnapshotTiming timing;CHECK(timing.Start(0,UINT64_C(1000000000),false));auto clock=[]() noexcept{return std::uint64_t{1};};
    std::vector<std::thread> threads;
    for(unsigned i=0;i<16;++i)threads.emplace_back([&]{for(unsigned j=0;j<2000;++j){auto ticket=timing.Begin(Boundary::PointerAllocate,false,clock);timing.End(ticket,false,false,true,clock);}});
    for(auto& thread:threads)thread.join();timing.Stop();auto result=timing.Read();CHECK(result.inflight==0&&result.rows[2].started==32000&&result.rows[2].returned==32000);
}

struct ExecutableFixture {
    unsigned char* memory{};
    static constexpr std::size_t Bytes=0x2970000;
    std::array<RUNTIME_FUNCTION,6> entries{};
    std::array<bool,6> registered{};
    ExecutableFixture(){memory=static_cast<unsigned char*>(VirtualAlloc(nullptr,Bytes,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));CHECK(memory);}
    ~ExecutableFixture(){for(std::size_t i=0;i<entries.size();++i)if(registered[i])RtlDeleteFunctionTable(&entries[i]);if(memory)VirtualFree(memory,0,MEM_RELEASE);}
    std::uintptr_t base() const noexcept{return reinterpret_cast<std::uintptr_t>(memory);}
    void jump(std::size_t offset,std::uintptr_t target){const unsigned char op[]{0xff,0x25,0,0,0,0};std::memcpy(memory+offset,op,6);std::memcpy(memory+offset+6,&target,8);}
    void call_stub(std::size_t index,std::uintptr_t return_rva,void* function) {
        const auto start=return_rva-16;unsigned char code[]{0x48,0x83,0xec,0x28,0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xd0,0x48,0x83,0xc4,0x28,0xc3};
        const auto ptr=reinterpret_cast<std::uintptr_t>(function);std::memcpy(code+6,&ptr,8);std::memcpy(memory+start,code,sizeof(code));
        const unsigned char unwind[]{1,4,1,0,4,0x42,0,0};std::memcpy(memory+start+56,unwind,8);
        entries[index]={0,static_cast<DWORD>(sizeof(code)),56};CHECK(RtlAddFunctionTable(&entries[index],1,base()+start));registered[index]=true;
        FlushInstructionCache(GetCurrentProcess(),memory+start,64);
    }
    profile::TrampolineUnwind* make_trampoline(std::size_t kind,profile::TrampolineUnwind& receipt,bool corrupt_tail=false,profile::TrampolineUnwind::AddFn add=RtlAddFunctionTable) {
        const auto at=0x1000+kind*0x100;const auto native=base()+0x3000+kind*0x100;const auto detour=base()+0x8000+kind*0x100;
        std::size_t body=0;
        if(kind==0){const unsigned char b[]{0x40,0x55,0x48,0x83,0xec,0x40};std::memcpy(memory+at,b,6);jump(at+6,native+6);body=20;}
        if(kind==1){const unsigned char b[]{0x48,0x89,0x5c,0x24,8};std::memcpy(memory+at,b,5);jump(at+5,native+5);body=19;}
        if(kind==2){const unsigned char b[]{0x48,0x89,0x6c,0x24,0x10};std::memcpy(memory+at,b,5);jump(at+5,native+5);body=19;}
        if(kind==3){const unsigned char b[]{0x48,0x85,0xd2,0x75,0x0e};std::memcpy(memory+at,b,5);jump(at+5,native+0x170);jump(at+19,native+9);body=33;}
        jump(at+body,detour);if(corrupt_tail)memory[at+56]=0xcc;
        CHECK(receipt.Prepare(kind,memory+at,reinterpret_cast<void*>(native),reinterpret_cast<void*>(detour),add)==(!corrupt_tail&&add==RtlAddFunctionTable));
        return &receipt;
    }
};

void unwind_all_relocated_boundaries_and_exclude_relay() {
    ExecutableFixture image;std::array<profile::TrampolineUnwind,4> receipts{};
    for(std::size_t kind=0;kind<4;++kind) {
        auto& r=*image.make_trampoline(kind,receipts[kind]);CHECK(r.registered);
        const std::vector<unsigned> points=kind==0?std::vector<unsigned>{0,2,6,16}:kind==3?std::vector<unsigned>{0,3,5,19,29}:std::vector<unsigned>{0,5,15};
        for(const auto offset:points) {
            alignas(16) std::array<std::uint64_t,64> stack{};
            const auto entry_rsp=reinterpret_cast<std::uintptr_t>(&stack[24]);const auto caller=UINT64_C(0x1234567812345678),old_rbp=UINT64_C(0x5555666677778888),old_rbx=UINT64_C(0x3333444455556666);
            stack[24]=caller;CONTEXT context{};context.ContextFlags=CONTEXT_FULL;context.Rip=r.base+offset;context.Rsp=entry_rsp;context.Rbp=old_rbp;context.Rbx=old_rbx;
            if(kind==0&&offset>=2){stack[23]=old_rbp;context.Rsp=entry_rsp-8;context.Rbp=0x91;}
            if(kind==0&&offset>=6)context.Rsp-=0x40;
            if(kind==1&&offset>=5){stack[25]=old_rbx;context.Rbx=0x92;}
            if(kind==2&&offset>=5){stack[26]=old_rbp;context.Rbp=0x93;}
            DWORD64 lookup_base=0;auto* found=RtlLookupFunctionEntry(context.Rip,&lookup_base,nullptr);CHECK(found&&lookup_base==r.base&&found->EndAddress==r.entry.EndAddress);
            PVOID handler_data=nullptr;DWORD64 establisher=0;RtlVirtualUnwind(UNW_FLAG_NHANDLER,r.base,context.Rip,found,&context,&handler_data,&establisher,nullptr);
            if(context.Rip!=caller||context.Rsp!=entry_rsp+8||context.Rbp!=old_rbp||context.Rbx!=old_rbx)
                std::cerr<<"unwind kind="<<kind<<" offset="<<offset<<" RIP="<<std::hex<<context.Rip<<" RSP="<<context.Rsp<<" expected RSP="<<entry_rsp+8<<" RBP="<<context.Rbp<<" RBX="<<context.Rbx<<std::dec<<'\n';
            CHECK(context.Rip==caller&&context.Rsp==entry_rsp+8&&context.Rbp==old_rbp&&context.Rbx==old_rbx);
        }
        DWORD64 relay_base=0;CHECK(RtlLookupFunctionEntry(r.base+r.entry.EndAddress,&relay_base,nullptr)==nullptr);
    }
    for(auto& receipt:receipts)CHECK(receipt.RollbackNeverActivated());
}
BOOLEAN WINAPI RejectRegistration(PRUNTIME_FUNCTION,DWORD,DWORD64){return FALSE;}
void unwind_registration_failure_and_conflicting_tail() {
    ExecutableFixture image;profile::TrampolineUnwind rejected,conflict;
    image.make_trampoline(0,rejected,false,RejectRegistration);CHECK(!rejected.registered&&rejected.tail_written);CHECK(rejected.RollbackNeverActivated());
    const std::array<unsigned char,8> empty{};CHECK(profile::TrampolineUnwind::Bytes(rejected.base+56,empty.data(),8));
    image.make_trampoline(1,conflict,true);CHECK(!conflict.registered&&!conflict.tail_written&&image.memory[0x1100+56]==0xcc);
}
void DummyDetour(){}
void actual_minhook_layout_acceptance_before_activation() {
    const auto initialized=MH_Initialize();CHECK(initialized==MH_OK||initialized==MH_ERROR_ALREADY_INITIALIZED);
    ExecutableFixture image;std::array<profile::TrampolineUnwind,4> receipts{};std::array<void*,4> targets{};
    for(std::size_t kind=0;kind<4;++kind) {
        auto* target=image.memory+0x10000+kind*0x1000;targets[kind]=target;
        std::memset(target,0xcc,512);
        const std::array<std::vector<unsigned char>,4> prefixes{{{0x40,0x55,0x48,0x83,0xec,0x40},{0x48,0x89,0x5c,0x24,8},{0x48,0x89,0x6c,0x24,0x10},{0x48,0x85,0xd2,0x0f,0x84,0x67,1,0,0}}};
        std::memcpy(target,prefixes[kind].data(),prefixes[kind].size());void* original=nullptr;
        CHECK(MH_CreateHook(target,reinterpret_cast<void*>(DummyDetour),&original)==MH_OK);
        CHECK(receipts[kind].Prepare(kind,original,target,reinterpret_cast<void*>(DummyDetour)));
        DWORD64 base=0;CHECK(RtlLookupFunctionEntry(reinterpret_cast<DWORD64>(original),&base,nullptr)!=nullptr);
    }
    // These fixture hooks have NEVER been activated; no native callback can
    // hold their trampolines, so this private test can remove them safely.
    for(std::size_t i=0;i<4;++i){CHECK(receipts[i].RollbackNeverActivated());CHECK(MH_RemoveHook(targets[i])==MH_OK);}
}

#pragma warning(push)
#pragma warning(disable:4324) // Deliberately16-byte-aligned native page fixture.
struct NativeScenario {
    ExecutableFixture code;
    alignas(16) std::array<unsigned char,0x100> context{};
    std::array<unsigned char,0x20> snapshot{};
    std::array<std::uintptr_t,2> heap{};
    alignas(16) std::array<unsigned char,0x268> page{};
    profile::AllocateFn allocate{};profile::FreeFn free{};profile::CaptureFn capture{};profile::SnapshotDestructorFn destructor{};
    unsigned allocations{},frees{},captures{},dtors{},seen_flags{};bool capture_result=true,allocation_null{},throw_cpp{},throw_seh{};
    DWORD entry_error{},native_error=0x771;
    NativeScenario();~NativeScenario();
};
#pragma warning(pop)
inline NativeScenario* Scenario{};
void* MockAllocate(void* heap,std::size_t bytes,std::size_t alignment,const void* info) {
    auto& s=*Scenario;CHECK(heap==s.heap.data()&&bytes==0x268&&alignment==16&&info==nullptr);++s.allocations;
    SetLastError(s.native_error);return s.allocation_null?nullptr:s.page.data();
}
void MockFree(void* heap,void* page){auto& s=*Scenario;CHECK(heap==s.heap.data()&&page==s.page.data());++s.frees;SetLastError(s.native_error);}
void* MockDestructor(void* snapshot,unsigned flags) {
    auto& s=*Scenario;CHECK(snapshot==s.snapshot.data());++s.dtors;s.seen_flags=flags;
    if(s.throw_cpp)throw std::runtime_error("native-cpp-sentinel");
    if(s.throw_seh){SetLastError(s.native_error);RaiseException(0xe0434377,0,0,nullptr);}
    s.free(s.heap.data(),s.page.data());SetLastError(s.native_error);return snapshot;
}
bool MockCapture(void* context) {
    auto& s=*Scenario;CHECK(context==s.context.data());++s.captures;s.entry_error=GetLastError();
    void* page=s.allocate(s.heap.data(),0x268,16,nullptr);CHECK(page==(s.allocation_null?nullptr:s.page.data()));
    CHECK(s.destructor(s.snapshot.data(),0x1234)==s.snapshot.data());SetLastError(s.native_error);return s.capture_result;
}
NativeScenario::NativeScenario() {
    auto& r=profile::Shared();r.timing.Stop();Scenario=this;r.image=code.base();
    heap[0]=r.image+profile::RootHeapVtableRva;const auto heap_ptr=reinterpret_cast<std::uintptr_t>(heap.data());
    std::memcpy(code.memory+profile::RootHeapRva,&heap_ptr,8);std::memcpy(context.data(),&heap_ptr,8);std::memcpy(context.data()+0x18,&heap_ptr,8);
    const std::uint64_t frame=42;std::memcpy(context.data()+0xe8,&frame,8);const auto owner=reinterpret_cast<std::uintptr_t>(context.data());std::memcpy(snapshot.data()+0x10,&owner,8);
    r.original[0]=reinterpret_cast<void*>(MockCapture);r.original[1]=reinterpret_cast<void*>(MockDestructor);r.original[2]=reinterpret_cast<void*>(MockAllocate);r.original[3]=reinterpret_cast<void*>(MockFree);
    code.call_stub(0,profile::AllocateReturnRva,reinterpret_cast<void*>(profile::Allocate));allocate=reinterpret_cast<profile::AllocateFn>(r.image+profile::AllocateReturnRva-16);
    code.call_stub(1,profile::FreeReturnRva,reinterpret_cast<void*>(profile::Free));free=reinterpret_cast<profile::FreeFn>(r.image+profile::FreeReturnRva-16);
    code.call_stub(2,0xff7e88,reinterpret_cast<void*>(profile::Capture));capture=reinterpret_cast<profile::CaptureFn>(r.image+0xff7e88-16);
    code.call_stub(3,0x10087ee,reinterpret_cast<void*>(profile::SnapshotDestructor));destructor=reinterpret_cast<profile::SnapshotDestructorFn>(r.image+0x10087ee-16);
    CHECK(r.timing.Start(profile::Clock(),UINT64_C(1000000000),true));
}
NativeScenario::~NativeScenario(){profile::Shared().timing.Stop();Scenario=nullptr;}

void actual_wrappers_preserve_arguments_returns_last_error_and_native_pages() {
    NativeScenario s;SetLastError(0xabc);CHECK(s.capture(s.context.data()));CHECK(GetLastError()==s.native_error&&s.entry_error==0xabc);
    CHECK(s.allocations==1&&s.frees==1&&s.captures==1&&s.dtors==1&&s.seen_flags==0x1234);
    auto data=profile::Shared().timing.Read();CHECK(data.inflight==0&&data.rows[0].returned==1&&data.rows[1].returned==1&&data.rows[2].qualified==1&&data.rows[3].qualified==1);
    CHECK(data.record_count==1&&data.records[0].heap_verified&&data.records[0].native_frame_id==42&&data.records[0].allocations==1&&data.records[0].retired_frees==1);
    CHECK(profile::CurrentContext==nullptr&&profile::CurrentSnapshot==nullptr&&profile::ObservationDepth==0);
    s.capture_result=false;CHECK(!s.capture(s.context.data()));s.allocation_null=true;CHECK(!s.capture(s.context.data()));
    data=profile::Shared().timing.Read();CHECK(data.rows[2].null_returns==1&&data.rows[0].returned==3);
    // Direct calls have a different return PC: native forwarding, no record.
    const auto prior=data.rows[2].started;CHECK(profile::Allocate(s.heap.data(),0x268,16,nullptr)==nullptr);CHECK(profile::Shared().timing.Read().rows[2].started==prior);
}
void actual_cpp_exception_unwinds_observer_scopes() {
    NativeScenario s;s.throw_cpp=true;bool caught=false;
    try{s.capture(s.context.data());}catch(const std::runtime_error& e){caught=std::strcmp(e.what(),"native-cpp-sentinel")==0;}
    CHECK(caught);const auto data=profile::Shared().timing.Read();CHECK(data.inflight==0&&data.rows[0].unwound==1&&data.rows[1].unwound==1&&data.rows[3].started==0);
    CHECK(profile::CurrentContext==nullptr&&profile::CurrentSnapshot==nullptr&&profile::ObservationDepth==0);
}
DWORD InvokeSeh(profile::CaptureFn capture,void* context) {
    DWORD code=0;__try {capture(context);}__except(EXCEPTION_EXECUTE_HANDLER){code=GetExceptionCode();}return code;
}
void actual_seh_exception_unwinds_observer_scopes() {
    NativeScenario s;s.throw_seh=true;CHECK(InvokeSeh(s.capture,s.context.data())==0xe0434377);
    const auto data=profile::Shared().timing.Read();CHECK(data.inflight==0&&data.rows[0].unwound==1&&data.rows[1].unwound==1);
    CHECK(profile::CurrentContext==nullptr&&profile::CurrentSnapshot==nullptr&&profile::ObservationDepth==0);
}

struct ActivationFixture {
    profile::Runtime runtime;
    std::array<std::string,4> bytes{};
    std::array<unsigned,4> enabled{},disabled{};
    int fail=-1;
    static inline ActivationFixture* active{};
    static std::string Read(profile::Runtime&,std::size_t i){return active->bytes[i];}
    static MH_STATUS WINAPI Enable(LPVOID target) {
        auto& self=*active;const auto index=static_cast<std::size_t>(reinterpret_cast<std::uintptr_t>(target)-1);
        if(static_cast<int>(index)==self.fail)return MH_ERROR_MEMORY_PROTECT;
        ++self.enabled[index];self.bytes[index]=self.runtime.owned_prefix[index];return MH_OK;
    }
    static MH_STATUS WINAPI Disable(LPVOID target) {
        auto& self=*active;const auto index=static_cast<std::size_t>(reinterpret_cast<std::uintptr_t>(target)-1);
        ++self.disabled[index];self.bytes[index]=self.runtime.original_prefix[index];return MH_OK;
    }
    ActivationFixture() {
        active=this;runtime.image=0x140000000;runtime.read_prefix=Read;runtime.enable_hook=Enable;runtime.disable_hook=Disable;runtime.created=true;
        for(std::size_t i=0;i<4;++i) {
            runtime.targets[i]=reinterpret_cast<void*>(i+1);runtime.original[i]=reinterpret_cast<void*>(i+0x100);
            runtime.original_prefix[i]=std::string(32,static_cast<char>(0x40+i));bytes[i]=runtime.original_prefix[i];
            runtime.unwind[i].base=runtime.image+profile::Definitions[i].rva+0x1000;runtime.unwind[i].entry.EndAddress=i==0?20:i==3?33:19;
        }
    }
    ~ActivationFixture(){active=nullptr;}
};
void owned_activation_stop_and_partial_rollback() {
    {ActivationFixture f;profile::ActivatePreparedLocked(f.runtime);CHECK(f.runtime.active_hooks);
     for(std::size_t i=0;i<4;++i)CHECK(f.enabled[i]==1&&f.bytes[i]==f.runtime.owned_prefix[i]);
     profile::DisableOwnedLocked(f.runtime);CHECK(!f.runtime.active_hooks);
     for(std::size_t i=0;i<4;++i)CHECK(f.disabled[i]==1&&f.bytes[i]==f.runtime.original_prefix[i]);}
    for(int failure=0;failure<4;++failure) {
        ActivationFixture f;f.fail=failure;bool failed=false;try{profile::ActivatePreparedLocked(f.runtime);}catch(const std::runtime_error&){failed=true;}
        CHECK(failed&&!f.runtime.active_hooks);
        for(std::size_t i=0;i<4;++i){CHECK(f.bytes[i]==f.runtime.original_prefix[i]);CHECK(f.disabled[i]==(static_cast<int>(i)<failure?1u:0u));}
    }
}
void foreign_activation_and_stop_bytes_never_overwritten() {
    {ActivationFixture f;f.bytes[2]=std::string(32,'X');bool failed=false;
     try{profile::ActivatePreparedLocked(f.runtime);}catch(const std::runtime_error&){failed=true;}
     CHECK(failed&&f.runtime.conflict&&f.bytes[2]==std::string(32,'X')&&f.disabled[2]==0&&f.enabled[2]==0);
     CHECK(f.bytes[0]==f.runtime.original_prefix[0]&&f.bytes[1]==f.runtime.original_prefix[1]);}
    {ActivationFixture f;profile::ActivatePreparedLocked(f.runtime);f.bytes[0]=std::string(32,'Y');bool failed=false;
     try{profile::DisableOwnedLocked(f.runtime);}catch(const std::runtime_error&){failed=true;}
     CHECK(failed&&f.runtime.conflict&&f.runtime.active_hooks&&f.bytes[0]==std::string(32,'Y')&&f.disabled[0]==0);
     for(std::size_t i=1;i<4;++i)CHECK(f.bytes[i]==f.runtime.original_prefix[i]);}
}
void timeout_restores_only_owned_entries_without_persistent_work() {
    ActivationFixture f;profile::ActivatePreparedLocked(f.runtime);CHECK(f.runtime.timing.Start(profile::Clock(),1000000000,false));
    profile::StartTimeoutWorkerLocked(f.runtime,15);CHECK(f.runtime.worker.joinable());f.runtime.worker.join();
    CHECK(!f.runtime.active_hooks&&!f.runtime.timing.Active());
    for(std::size_t i=0;i<4;++i)CHECK(f.disabled[i]==1&&f.bytes[i]==f.runtime.original_prefix[i]);
}
void standalone_image_cannot_arm_game_profiler() {
    auto& runtime=profile::Shared();runtime.timing.Stop();bool refused=false;
    try{profile::Configure("standalone-must-not-arm",1,false);}catch(const std::runtime_error&){refused=true;}
    CHECK(refused&&!runtime.active_hooks&&!runtime.created&&!runtime.timing.Active());
}

int main() {
    const std::pair<const char*,void(*)()> tests[]{
        {"atomic window and clocks",atomic_window_and_clock_gates},{"deadline and record bounds",exact_deadline_and_record_bounds},
        {"concurrent counts",concurrent_counting},{"registered trampoline boundary unwind",unwind_all_relocated_boundaries_and_exclude_relay},
        {"registration failure and foreign tail",unwind_registration_failure_and_conflicting_tail},
        {"actual MinHook layouts before activation",actual_minhook_layout_acceptance_before_activation},
        {"actual ABI wrappers and LastError",actual_wrappers_preserve_arguments_returns_last_error_and_native_pages},
        {"actual C++ exception propagation",actual_cpp_exception_unwinds_observer_scopes},{"actual SEH propagation",actual_seh_exception_unwinds_observer_scopes},
        {"owned activation and every partial rollback",owned_activation_stop_and_partial_rollback},{"foreign activation/stop patches preserved",foreign_activation_and_stop_bytes_never_overwritten},
        {"one-off timeout restores owned entries",timeout_restores_only_owned_entries_without_persistent_work},{"standalone image cannot arm game hooks",standalone_image_cannot_arm_game_profiler}
    };
    try{for(const auto& test:tests){test.second();std::cout<<"PASS "<<test.first<<'\n';}}
    catch(const std::exception& error){std::cerr<<"FAIL "<<error.what()<<'\n';return 1;}
    std::cout<<"13 isolated native profiler scenarios passed; no Sims process or measured gain.\n";
}
