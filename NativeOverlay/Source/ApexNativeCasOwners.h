// Fixed-layout metadata inspection for the SHA-pinned CAS implementation.
// Offsets come from its Sim-cache lookup and kind-cache assignment routines.
// Never used to call an interface, copy appearances, or mutate an owner.
#pragma once
#include <algorithm>
#include <cstdint>
#include <set>
#include <stdexcept>
#include <vector>
#include <utility>

namespace td1::nativecas {
struct KindCacheRow {
    std::uint64_t simId;
    std::vector<std::uint32_t> kinds;
    bool operator==(const KindCacheRow& other) const {return simId==other.simId && kinds==other.kinds;}
    bool operator!=(const KindCacheRow& other) const {return !(*this==other);}
};

template<class Read> std::vector<KindCacheRow> ReadKindCacheMetadata(std::uint64_t controller, Read read) {
    constexpr std::uint64_t limit=0x00007ffffffffff7ULL;
    auto address=[](std::uint64_t base,std::uint64_t offset) {
        if(base<0x10000 || base>limit || base%8 || offset>limit-base)
            throw std::runtime_error("Native owner metadata address is unaligned or out of bounds.");
        return base+offset;
    };
    std::vector<KindCacheRow> rows;
    std::vector<std::uint64_t> pending{read(address(controller,0x138))};
    std::set<std::uint64_t> nodes,ids,allKindNodes;
    while(!pending.empty()) {
        const auto node=pending.back();pending.pop_back();if(!node) continue;
        if(nodes.size()>=32 || !nodes.insert(node).second)
            throw std::runtime_error("Native Sim-cache tree is cyclic, shared or exceeds 32 nodes.");
        const auto id=read(address(node,0x20));
        if(!id || !ids.insert(id).second) throw std::runtime_error("Native Sim-cache identity is absent or duplicated.");
        KindCacheRow row{id,{}};
        // Outer value +28, metadata member +88, inner root +20.
        std::vector<std::uint64_t> kinds{read(address(node,0xd0))};
        std::set<std::uint64_t> kindNodes;std::set<std::uint32_t> keys;
        while(!kinds.empty()) {
            const auto entry=kinds.back();kinds.pop_back();if(!entry) continue;
            if(kindNodes.size()>=32 || !kindNodes.insert(entry).second || !allKindNodes.insert(entry).second)
                throw std::runtime_error("Native kind-cache tree is cyclic, shared or exceeds 32 nodes.");
            const auto kind=static_cast<std::uint32_t>(read(address(entry,0x20)));
            // The native value starts at +30, with its own kind at +8.
            const auto stored=static_cast<std::uint32_t>(read(address(entry,0x38)));
            if(!kind || kind>0x40000000u || (kind&(kind-1)) || !keys.insert(kind).second || kind!=stored)
                throw std::runtime_error("Native kind-cache key differs from its stored single-kind record.");
            row.kinds.push_back(kind);
            kinds.push_back(read(address(entry,0)));kinds.push_back(read(address(entry,8)));
        }
        std::sort(row.kinds.begin(),row.kinds.end());rows.push_back(std::move(row));
        pending.push_back(read(address(node,0)));pending.push_back(read(address(node,8)));
    }
    std::sort(rows.begin(),rows.end(),[](const auto& a,const auto& b){return a.simId<b.simId;});
    return rows;
}
}
