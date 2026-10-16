// Every editable form is a separate owner. Native genus is not its identity.
#pragma once
#include "ApexNativeCasEngine.h"
#include <functional>
#include <set>
#include <type_traits>
#include <utility>

namespace td1::nativecas::engine {
inline bool FormOwnerId(const std::string& value) {
    if(value.empty() || value.size()>129) return false;
    const auto slash=value.find('/');
    if(slash==std::string::npos || slash==0 || slash>64 || value.size()-slash-1==0 ||
       value.size()-slash-1>64 || value.find('/',slash+1)!=std::string::npos) return false;
    for(const auto c:value)
        if(!((c>='a' && c<='z') || (c>='0' && c<='9') || c=='_' || c=='-' || c=='/')) return false;
    return value[0]!='-' && value[slash+1]!='-';
}
inline std::string NativeOwnerId(std::uint32_t kind) {
    if(!Kind(kind)) throw std::runtime_error("Unknown native rendering genus.");
    return "native/"+std::to_string(kind);
}
template<class Appearance> class OwnerGraph {
public:
    using Clone=std::function<Appearance(const Appearance&,std::uint32_t)>;
    struct Capture {std::uint32_t nativeKind;const Appearance* appearance;};
    using Captures=std::map<std::string,Capture>;
    struct Cursor {std::uint64_t sim;std::uint32_t kind;std::uint64_t generation;std::string owner;};
    struct Owner {std::string id;std::uint32_t nativeKind;std::uint64_t revision;bool selected;};
private:
    static_assert(std::is_nothrow_swappable_v<Appearance>,"Appearance swap must be noexcept.");
    struct Entry {std::uint32_t nativeKind;Appearance appearance;std::uint64_t revision=0;};
    std::uint64_t sim_;
    std::uint32_t mask_;
    Clone clone_;
    std::map<std::string,Entry> entries_;
    std::map<std::string,std::set<std::string>> links_;
    Cursor cursor_;
    const Entry& Owned(const std::string& id) const {
        const auto at=entries_.find(id);
        if(at==entries_.end()) throw std::runtime_error("This exact form owner does not belong to this Sim.");
        return at->second;
    }
    void Current(const Cursor& cursor) const {
        if(cursor.sim!=sim_ || cursor.owner!=cursor_.owner || cursor.kind!=cursor_.kind || cursor.generation!=cursor_.generation)
            throw std::runtime_error("The edit belongs to a different Sim, form or selection generation.");
        if(cursor_.generation==UINT64_MAX) throw std::runtime_error("Appearance generation is exhausted.");
    }
    static Captures NativeCaptures(const std::map<std::uint32_t,Appearance>& captured) {
        Captures result;
        for(const auto& row:captured) result.emplace(NativeOwnerId(row.first),Capture{row.first,&row.second});
        return result;
    }
public:
    OwnerGraph(std::uint64_t sim,std::uint32_t mask,const std::string& initialOwner,const Captures& captured,Clone clone)
        :sim_(sim),mask_(mask),clone_(std::move(clone)),cursor_{sim,0,1,initialOwner} {
        if(!sim || !clone_ || (mask&~127u) || !(mask&1) || captured.empty())
            throw std::runtime_error("A complete Sim and appearance roster is required.");
        std::uint32_t observed=0;
        for(const auto& row:captured) {
            const auto kind=row.second.nativeKind;
            if(!FormOwnerId(row.first) || !Kind(kind) || !(mask&kind) || !row.second.appearance)
                throw std::runtime_error("Invalid form identity, rendering genus or captured appearance.");
            observed|=kind;
            entries_.emplace(row.first,Entry{kind,clone_(*row.second.appearance,kind),0});
        }
        if(observed!=mask) throw std::runtime_error("Captured appearances omit an existing native owner.");
        cursor_.kind=Owned(initialOwner).nativeKind;
    }
    OwnerGraph(std::uint64_t sim,std::uint32_t mask,std::uint32_t initialKind,
               const std::map<std::uint32_t,Appearance>& captured,Clone clone)
        :OwnerGraph(sim,mask,NativeOwnerId(initialKind),NativeCaptures(captured),std::move(clone)) {}
    Cursor cursor() const {return cursor_;}
    std::uint32_t mask() const {return mask_;}
    const Appearance& appearance(const std::string& id) const {return Owned(id).appearance;}
    const Appearance& appearance(std::uint32_t kind) const {return appearance(NativeOwnerId(kind));}
    std::uint64_t revision(const std::string& id) const {return Owned(id).revision;}
    std::uint64_t revision(std::uint32_t kind) const {return revision(NativeOwnerId(kind));}
    std::vector<Owner> owners() const {
        std::vector<Owner> result;
        for(const auto& row:entries_) result.push_back({row.first,row.second.nativeKind,row.second.revision,row.first==cursor_.owner});
        return result;
    }
    bool linked(const std::string& source,const std::string& target) const {
        Owned(source);Owned(target);const auto at=links_.find(source);
        return at!=links_.end() && at->second.count(target)!=0;
    }
    bool linked(std::uint32_t source,std::uint32_t target) const {return linked(NativeOwnerId(source),NativeOwnerId(target));}
    Cursor capture(const Cursor& expected,const std::string& id,std::uint32_t kind,const Appearance& appearance) {
        Current(expected);
        if(!FormOwnerId(id) || !Kind(kind) || !(mask_&kind) || entries_.count(id))
            throw std::runtime_error("A new form must have its own unused identity and existing rendering genus.");
        auto copy=clone_(appearance,kind);
        entries_.emplace(id,Entry{kind,std::move(copy),0});++cursor_.generation;return cursor_;
    }
    Cursor select(const Cursor& expected,const std::string& target) {
        Current(expected);const auto kind=Owned(target).nativeKind;
        // Even two forms rendered with the same EA kind have distinct IDs.
        if(target!=cursor_.owner) {cursor_.owner=target;cursor_.kind=kind;++cursor_.generation;}
        return cursor_;
    }
    Cursor select(const Cursor& expected,std::uint32_t target) {return select(expected,NativeOwnerId(target));}
    Cursor commit(const Cursor& expected,const Appearance& edited) {
        Current(expected);
        std::set<std::string> destinations{cursor_.owner};
        bool changed=true;
        while(changed) {
            const auto before=destinations.size();
            for(const auto& id:std::set<std::string>(destinations)) {
                const auto links=links_.find(id);
                if(links!=links_.end()) destinations.insert(links->second.begin(),links->second.end());
            }
            changed=destinations.size()!=before;
        }
        // Prepare all complete clones before writing any owner. A failed native
        // allocation cannot leave half a linked group updated.
        std::map<std::string,Appearance> prepared;
        for(const auto& id:destinations) {
            const auto& entry=entries_.at(id);
            if(entry.revision==UINT64_MAX) throw std::runtime_error("Appearance revision is exhausted.");
            prepared.emplace(id,clone_(edited,entry.nativeKind));
        }
        for(auto& row:prepared) {using std::swap;swap(entries_.at(row.first).appearance,row.second);++entries_.at(row.first).revision;}
        ++cursor_.generation;return cursor_;
    }
    Cursor copy(const Cursor& expected,const std::string& source,const std::string& target) {
        Current(expected);const auto& from=Owned(source);const auto& to=Owned(target);
        if(source==target) throw std::runtime_error("Copy requires two distinct form owners.");
        if(to.revision==UINT64_MAX) throw std::runtime_error("Appearance revision is exhausted.");
        auto prepared=clone_(from.appearance,to.nativeKind);
        using std::swap;swap(entries_.at(target).appearance,prepared);++entries_.at(target).revision;
        ++cursor_.generation;return cursor_;
    }
    Cursor copy(const Cursor& expected,std::uint32_t source,std::uint32_t target) {return copy(expected,NativeOwnerId(source),NativeOwnerId(target));}
    Cursor link(const Cursor& expected,const std::string& source,const std::string& target,bool enabled) {
        Current(expected);Owned(source);Owned(target);
        if(source==target) throw std::runtime_error("A form cannot link to itself.");
        // Any two independently owned forms may be linked explicitly. No
        // Human-only restriction, implicit linking or automatic appearance copy.
        if(enabled) links_[source].insert(target);
        else {const auto at=links_.find(source);if(at!=links_.end()) at->second.erase(target);}
        ++cursor_.generation;return cursor_;
    }
    Cursor link(const Cursor& expected,std::uint32_t source,std::uint32_t target,bool enabled) {
        return link(expected,NativeOwnerId(source),NativeOwnerId(target),enabled);
    }
};
}
