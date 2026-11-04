// A view bind must retain captured genetics; actual outfit/hair edits still
// use EA's regeneration path. This policy owns no appearance bytes.
#pragma once
#include "ApexNativeCasEngine.h"
#include <limits>

namespace td1::nativecas::engine {
struct GeneticViewBinding {
    bool enabled=false,ownerPresent=false,fault=false;
    std::uintptr_t image=0,controller=0,model=0,group=0,boundGroup=0;
    std::uint64_t sim=0,groupSim=0;
    std::uint32_t capturedKind=0,modelKind=0;
};
inline bool RetainViewGenetics(const GeneticViewBinding& c,std::uintptr_t caller,
                               const void* genetics,const void* outfit) {
    if(!c.enabled || !c.ownerPresent || c.fault || !c.image || !c.controller || !c.model ||
       !c.group || c.group!=c.boundGroup || !c.sim || c.sim!=c.groupSim ||
       !Kind(c.capturedKind) || c.modelKind!=c.capturedKind ||
       c.image>std::numeric_limits<std::uintptr_t>::max()-0x457559 ||
       c.model>std::numeric_limits<std::uintptr_t>::max()-0x320) return false;
    return caller==c.image+0x457559 &&
        reinterpret_cast<std::uintptr_t>(genetics)==c.model+0x320 &&
        reinterpret_cast<std::uintptr_t>(outfit)==c.model+0xe8;
}
inline bool RetainCatalogPreparationGenetics(const GeneticViewBinding& c,std::uintptr_t caller,
                                              const void* genetics) {
    // The inspected catalog handler asks the model for its embedded SimData
    // (+0x170), then regenerates that same model's genetics (+0x1b0) before
    // constructing the edit/history action. The later actual edit stays native.
    if(!c.enabled || !c.ownerPresent || c.fault || !c.image || !c.controller || !c.model ||
       !c.group || c.group!=c.boundGroup || !c.sim || c.sim!=c.groupSim ||
       !Kind(c.capturedKind) || c.modelKind!=c.capturedKind ||
       c.image>std::numeric_limits<std::uintptr_t>::max()-0x438b98 ||
       c.model>std::numeric_limits<std::uintptr_t>::max()-0x320) return false;
    return caller==c.image+0x438b98 &&
        reinterpret_cast<std::uintptr_t>(genetics)==c.model+0x320;
}
}
