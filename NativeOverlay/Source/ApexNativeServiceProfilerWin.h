#pragma once
#include "ApexServiceTiming.h"
#include "ApexNativeCasProbeWin.h"
#include "MinHook.h"
#include <array>
#include <mutex>
#include <vector>

namespace td1::nativecas::performance {
// These optional observational detours are installed ONLY by an explicit
// scoped diagnostic request. Callback parameters and result pass unchanged.
// The inspected registration ABI supplies argument/provider pointers. The
// provider in RDX is required by catalog callbacks; never discard, inspect or
// retain either argument, or replace it with a selected test Sim.
using Callback=bool(*)(const void*,void*);
struct Definition {const char* name;std::uint32_t rva;const char* hash;};
inline constexpr std::array<Definition,8> Definitions{{
    {"GetCatalogBaseItems",0x426410,"2aeda6af8a71c34ab184c42ad6f3747d2354b6c1d6ef6c237c0e08878474b977"},
    {"GetCatalogColorFamilies.CAS",0x427070,"7bbd96272c0118897a471e86cb837a717173416ea4bc3c23e7f9b10dd036c366"},
    {"CasGetSwatchColorList",0x42c750,"93c9192fad1b54d255e12b871d7361b2f48e398a8a65c1840779679c4f729dd2"},
    {"CasGetSwatchColorSelected",0x42d3d0,"d2aa0e3b841a701181743469c6262f0e483f1b1bcd28806e899ff8231418138b"},
    {"GetCatalogItemsSelected",0x4277d0,"a09f1f612fc79fabdcfebbf6c0105cfd1c7123e8016956cd18dc581bd371b896"},
    {"GetLocalOriginId",0xdf9060,"089ac6e6f7043a4d010f57c92273a7b856c44c52dc5d2c1f026f80298a4ae291"},
    {"LoadUISettingsFromFile",0xc8a30,"c9b0c688b964699966b67222c299d8c73160adf3d19149af4e0f3cbd2006de6d"},
    {"GetCatalogColorFamilies.shared",0x1baf00,"929b32afa7221ea567b64b6d2e1ef5b36961347acede6d788708d8a2a4ee3d5f"}
}};
struct Runtime {
    td1::performance::ServiceTiming<Definitions.size()> timing;
    std::array<Callback,Definitions.size()> original{};
    bool installed=false,attempted=false;std::uint64_t frequency=0;double prepareMs=0;std::string scope,error;
};
inline Runtime& Shared() {static Runtime value;return value;}
inline std::uint64_t Clock() noexcept {LARGE_INTEGER value{};QueryPerformanceCounter(&value);return static_cast<std::uint64_t>(value.QuadPart);}
template<std::size_t Index> inline bool Dispatch(const void* a,void* b) {
    auto& runtime=Shared();auto ticket=runtime.timing.Begin(Index,Clock);
    struct Finish {
        Runtime& runtime;td1::performance::ServiceTiming<Definitions.size()>::Ticket ticket;
        ~Finish() noexcept {runtime.timing.End(ticket,Clock);}
    } finish{runtime,ticket};
    return runtime.original[Index](a,b);
}
inline const std::array<Callback,Definitions.size()> Detours{{Dispatch<0>,Dispatch<1>,Dispatch<2>,Dispatch<3>,Dispatch<4>,Dispatch<5>,Dispatch<6>,Dispatch<7>}};
inline void Install() {
    auto& runtime=Shared();if(runtime.installed)return;
    if(runtime.attempted)throw std::runtime_error("Native service profiling installation previously failed; use a fresh runtime.");
    runtime.attempted=true;const auto begin=Clock();std::vector<void*> created;
    try {
        auto image=OpenPinnedCasImage();
        for(const auto& definition:Definitions)
            if(resource::HashBytes(OwnImageRead(image.module,definition.rva,32))!=definition.hash)
                throw std::runtime_error("A profiled EA callback differs from its inspected original; no profiling window started.");
        const auto status=MH_Initialize();if(status!=MH_OK && status!=MH_ERROR_ALREADY_INITIALIZED)
            throw std::runtime_error("Native profiling hook registry unavailable.");
        for(std::size_t i=0;i<Definitions.size();++i) {
            void* target=reinterpret_cast<char*>(image.module)+Definitions[i].rva;
            if(MH_CreateHook(target,reinterpret_cast<void*>(Detours[i]),reinterpret_cast<void**>(&runtime.original[i]))!=MH_OK)
                throw std::runtime_error("A profiling callback is already modified or unavailable.");
            created.push_back(target);
        }
        for(auto* target:created)if(MH_QueueEnableHook(target)!=MH_OK)
            throw std::runtime_error("Native profiling detour activation could not be queued.");
        if(MH_ApplyQueued()!=MH_OK)throw std::runtime_error("Native profiling detour activation failed.");
        LARGE_INTEGER frequency{};if(!QueryPerformanceFrequency(&frequency) || frequency.QuadPart<=0)
            throw std::runtime_error("Native profiling clock unavailable.");
        runtime.frequency=static_cast<std::uint64_t>(frequency.QuadPart);runtime.installed=true;
        runtime.prepareMs=double(Clock()-begin)*1000.0/double(runtime.frequency);
    } catch(const std::exception& error) {
        runtime.timing.Stop();runtime.error=error.what();
        for(auto* target:created)MH_DisableHook(target);
        // Retain created trampolines until process exit. A callback that was
        // already dispatched during a failed activation must never call freed
        // trampoline memory. Do not touch any other mod's hooks.
        throw;
    }
}
inline void Configure(const std::string& scope,unsigned milliseconds) {
    auto& runtime=Shared();if(milliseconds==0) {runtime.timing.Stop();return;}
    if(milliseconds>30000)throw std::runtime_error("Use a bounded profiling window of at most thirty seconds.");
    Install();if(runtime.frequency>UINT64_MAX/milliseconds)throw std::runtime_error("Native profiling duration overflow.");
    const auto duration=runtime.frequency*milliseconds/1000;
    if(!runtime.timing.Start(Clock(),duration))throw std::runtime_error("A previous native profiling call is still in flight.");
    runtime.scope=scope;
}
inline ui::Json Snapshot() {
    auto& runtime=Shared();auto snapshot=runtime.timing.Read();
    if(snapshot.enabled && Clock()>=snapshot.deadline) {runtime.timing.Stop();snapshot=runtime.timing.Read();}
    ui::Json rows=ui::Json::array();
    for(std::size_t i=0;i<Definitions.size();++i) {
        const auto& row=snapshot.rows[i];const auto scale=runtime.frequency?1000.0/double(runtime.frequency):0;
        rows.push_back({{"service",Definitions[i].name},{"calls",row.calls},{"total_ms",double(row.total)*scale},
            {"max_ms",double(row.maximum)*scale},{"mean_ms",row.calls?double(row.total)*scale/double(row.calls):0.0}});
    }
    return {{"installed",runtime.installed},{"enabled",snapshot.enabled},{"generation",snapshot.generation},
        {"inflight",snapshot.inflight},{"skipped_calls",snapshot.skipped},{"scope_id",runtime.scope},{"services",std::move(rows)},
        {"preparation_ms",runtime.prepareMs},{"error",runtime.error},{"argument_bytes_read",0},
        {"background_service",false},{"appearance_written",false}};
}
}
