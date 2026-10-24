#include "ApexNativeOwnerMemory.h"
#include <iostream>
using td1::nativecas::GuardedOwnerMemory;
void Check(bool value) {if(!value) throw std::runtime_error("Native diagnostic memory contract failed.");}
int main() {
    try {
        unsigned char* retired=nullptr;
        const auto start=GuardedOwnerMemory::Status();
        {
            GuardedOwnerMemory memory(0x830);
            auto* value=static_cast<unsigned char*>(memory.get());retired=value;
            Check(reinterpret_cast<std::uintptr_t>(value)%16==0);
            MEMORY_BASIC_INFORMATION body{},end{};
            Check(VirtualQuery(value,&body,sizeof(body))==sizeof(body));
            Check(body.State==MEM_COMMIT && body.Protect==PAGE_READWRITE);
            Check(VirtualQuery(value+0x830,&end,sizeof(end))==sizeof(end));
            Check(end.State==MEM_RESERVE || end.Protect==PAGE_NOACCESS);
            // Every valid byte is usable; an underwrite is reported before
            // a later unrelated allocation can reuse or conceal that damage.
            std::memset(value,0x31,0x830);memory.Validate();
            value[-1]=0;bool rejected=false;
            try {memory.Validate();}catch(const std::runtime_error&) {rejected=true;}
            Check(rejected);value[-1]=0xfd;memory.Validate();
            const auto live=GuardedOwnerMemory::Status();
            Check(live.live==start.live+1 && live.retired==start.retired && live.reserved>start.reserved);
        }
        MEMORY_BASIC_INFORMATION gone{};
        Check(VirtualQuery(retired,&gone,sizeof(gone))==sizeof(gone));
        Check(gone.State==MEM_COMMIT && gone.Protect==PAGE_NOACCESS);
        const auto after=GuardedOwnerMemory::Status();
        Check(after.live==start.live && after.retired==start.retired+1);
        GuardedOwnerMemory next(0x830);Check(next.get()!=retired);
        for(const auto size:{std::size_t(0),std::size_t(1),std::size_t(0x100010)}) {
            bool refused=false;try {GuardedOwnerMemory invalid(size);}catch(const std::invalid_argument&) {refused=true;}
            Check(refused);
        }
        std::cout<<"Native owner guard boundaries, underwrite detection and retirement passed\n";return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
