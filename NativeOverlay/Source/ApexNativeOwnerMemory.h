#pragma once
#include <windows.h>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <new>
#include <stdexcept>

namespace td1::nativecas {
// Diagnostic allocation for Apex-owned native records only. Both outer pages
// are inaccessible, the object's last byte borders the trailing guard, and a
// destroyed record's payload stays inaccessible for the remaining process.
// Never install this allocator into EA's heaps or use it for game-owned slots.
class GuardedOwnerMemory {
    struct Counters {std::mutex mutex;std::size_t reserved=0,live=0,retired=0;};
    static Counters& Counts() {static auto* value=new Counters;return *value;}
    void* allocation_=nullptr;
    unsigned char* page_=nullptr;
    unsigned char* value_=nullptr;
    std::size_t committed_=0,prefix_=0;
public:
    struct Statistics {std::size_t reserved,live,retired;};
    static Statistics Status() {
        auto& c=Counts();std::lock_guard<std::mutex> lock(c.mutex);
        return {c.reserved,c.live,c.retired};
    }
    explicit GuardedOwnerMemory(std::size_t bytes) {
        SYSTEM_INFO info{};GetSystemInfo(&info);
        const auto page=static_cast<std::size_t>(info.dwPageSize);
        if(!bytes || bytes>0x100000 || bytes%16 || !page || page%16)
            throw std::invalid_argument("Invalid diagnostic native owner span.");
        committed_=(bytes+page-1)/page*page;
        const auto total=committed_+2*page;
        auto& c=Counts();std::lock_guard<std::mutex> lock(c.mutex);
        // Quarantine is bounded and fails before allocating another owner.
        // No old inaccessible region is recycled into a different object.
        if(total>128*1024*1024-c.reserved) throw std::bad_alloc();
        allocation_=VirtualAlloc(nullptr,total,MEM_RESERVE,PAGE_NOACCESS);
        if(!allocation_) throw std::bad_alloc();
        page_=static_cast<unsigned char*>(allocation_)+page;
        if(!VirtualAlloc(page_,committed_,MEM_COMMIT,PAGE_READWRITE)) {
            VirtualFree(allocation_,0,MEM_RELEASE);allocation_=nullptr;throw std::bad_alloc();
        }
        prefix_=committed_-bytes;value_=page_+prefix_;
        std::memset(page_,0xfd,prefix_);std::memset(value_,0,bytes);
        c.reserved+=total;++c.live;
    }
    GuardedOwnerMemory(const GuardedOwnerMemory&)=delete;
    GuardedOwnerMemory& operator=(const GuardedOwnerMemory&)=delete;
    void* get() const noexcept {return value_;}
    void Validate() const {
        if(!std::all_of(page_,page_+prefix_,[](unsigned char v){return v==0xfd;}))
            throw std::runtime_error("Native owner wrote before its inspected object span.");
    }
    ~GuardedOwnerMemory() noexcept {
        if(!allocation_) return;
        DWORD previous=0;
        if(!VirtualProtect(page_,committed_,PAGE_NOACCESS,&previous)) std::terminate();
        auto& c=Counts();std::lock_guard<std::mutex> lock(c.mutex);--c.live;++c.retired;
        // Intentionally retained until process exit: pointers into a retired
        // Apex record must fault at their first later access, not alias a new
        // allocation and silently damage an unrelated UI object.
    }
};
}
