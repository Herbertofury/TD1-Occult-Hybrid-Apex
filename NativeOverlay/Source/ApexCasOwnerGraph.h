// Separate editable appearances. Navigation never copies or links an owner.
#pragma once
#include "ApexNativeCasEngine.h"
#include <functional>
#include <set>
#include <type_traits>
#include <utility>

namespace td1::nativecas::engine {
template<class Appearance> class OwnerGraph {
public:
    // The native adapter deep-copies the complete CasData, including fields
    // unknown to Apex, and sets ONLY the destination's identity header.
    using Clone = std::function<Appearance(const Appearance&,std::uint32_t)>;
    struct Cursor {std::uint64_t sim;std::uint32_t kind;std::uint64_t generation;};
private:
    struct Entry {Appearance appearance;std::uint64_t revision=0;};
    std::uint64_t sim_;
    std::uint32_t mask_;
    Clone clone_;
    std::map<std::uint32_t,Entry> entries_;
    std::map<std::uint32_t,std::set<std::uint32_t>> links_;
    Cursor cursor_;
    void Owned(std::uint32_t kind) const {
        if(!Kind(kind) || !(mask_&kind) || !entries_.count(kind))
            throw std::runtime_error("This appearance is not an existing owner of this Sim.");
    }
    void Current(const Cursor& cursor) const {
        if(cursor.sim!=sim_ || cursor.kind!=cursor_.kind || cursor.generation!=cursor_.generation)
            throw std::runtime_error("The edit belongs to a different Sim, form or selection generation.");
        if(cursor_.generation==UINT64_MAX) throw std::runtime_error("Appearance generation is exhausted.");
    }
public:
    OwnerGraph(std::uint64_t sim,std::uint32_t mask,std::uint32_t initialKind,
               const std::map<std::uint32_t,Appearance>& captured,Clone clone)
        :sim_(sim),mask_(mask),clone_(std::move(clone)),cursor_{sim,initialKind,1} {
        if(!sim || !clone_ || (mask&~127u) || !(mask&1))
            throw std::runtime_error("A complete Sim and appearance roster is required.");
        std::vector<std::uint32_t> kinds;
        for(const auto& row:captured) kinds.push_back(row.first);
        ValidateKinds(mask,kinds);
        for(const auto& row:captured) entries_.emplace(row.first,Entry{clone_(row.second,row.first),0});
        Owned(initialKind);
    }
    Cursor cursor() const {return cursor_;}
    std::uint32_t mask() const {return mask_;}
    const Appearance& appearance(std::uint32_t kind) const {Owned(kind);return entries_.at(kind).appearance;}
    std::uint64_t revision(std::uint32_t kind) const {Owned(kind);return entries_.at(kind).revision;}
    bool linked(std::uint32_t source,std::uint32_t target) const {
        Owned(source);Owned(target);const auto at=links_.find(source);
        return at!=links_.end() && at->second.count(target)!=0;
    }
    Cursor select(const Cursor& expected,std::uint32_t target) {
        Current(expected);Owned(target);
        // A view selection cannot edit either the old or the new appearance.
        if(target!=cursor_.kind) {cursor_.kind=target;++cursor_.generation;}
        return cursor_;
    }
    Cursor commit(const Cursor& expected,const Appearance& edited) {
        Current(expected);
        // All forms start unlinked. Only an explicit Human/alternate link can
        // propagate an edit, and no appearance pointer is ever shared.
        std::set<std::uint32_t> destinations{cursor_.kind};
        // Reachability also covers links to lower-valued kinds and cycles.
        bool changed=true;
        while(changed) {
            const auto before=destinations.size();
            for(const auto kind:std::set<std::uint32_t>(destinations)) {
                const auto links=links_.find(kind);
                if(links!=links_.end()) destinations.insert(links->second.begin(),links->second.end());
            }
            changed=destinations.size()!=before;
        }
        std::map<std::uint32_t,Appearance> prepared;
        for(const auto kind:destinations) {
            if(entries_.at(kind).revision==UINT64_MAX) throw std::runtime_error("Appearance revision is exhausted.");
            prepared.emplace(kind,clone_(edited,kind));
        }
        // Clone failures leave every owner unchanged. Native Appearance uses
        // unique_ptr, whose swap is noexcept; never alias two live owners.
        static_assert(std::is_nothrow_swappable_v<Appearance>,"Appearance swap must be noexcept.");
        for(auto& row:prepared) {using std::swap;swap(entries_.at(row.first).appearance,row.second);++entries_.at(row.first).revision;}
        ++cursor_.generation;return cursor_;
    }
    Cursor copy(const Cursor& expected,std::uint32_t source,std::uint32_t target) {
        Current(expected);Owned(source);Owned(target);
        if(source==target) throw std::runtime_error("Copy requires two distinct form owners.");
        if(entries_.at(target).revision==UINT64_MAX) throw std::runtime_error("Appearance revision is exhausted.");
        auto prepared=clone_(entries_.at(source).appearance,target);
        using std::swap;swap(entries_.at(target).appearance,prepared);++entries_.at(target).revision;
        ++cursor_.generation;return cursor_;
    }
    Cursor link(const Cursor& expected,std::uint32_t source,std::uint32_t target,bool enabled) {
        Current(expected);Owned(source);Owned(target);
        if(source==target || (source!=1 && target!=1))
            throw std::runtime_error("A form link requires Human and one alternate; copy other forms explicitly.");
        // Enabling a link does not silently replace either existing appearance.
        if(enabled) links_[source].insert(target);
        else {const auto at=links_.find(source);if(at!=links_.end()) at->second.erase(target);}
        ++cursor_.generation;return cursor_;
    }
};
}
