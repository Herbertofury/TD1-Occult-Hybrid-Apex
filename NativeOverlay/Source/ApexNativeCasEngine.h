// Apex's existing-form selection policy. The Windows adapter supplies native
// constructors; this layer never confuses adding an occult with selecting one.
#pragma once
#include "ApexUiData.h"
#include <map>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace td1::nativecas::engine {
struct Member {std::uint64_t id;std::uint32_t mask;};
struct Scope {std::string id;std::map<std::uint64_t,Member> members;};
inline bool Kind(std::uint32_t value) {return value && value<=64 && !(value&(value-1));}
inline bool IndependentHybridGenus(std::uint32_t mask,std::uint32_t current) {
    const auto other=mask&~1u;
    return !(mask&~127u) && other && (other&(other-1)) && Kind(current) && ((mask|1u)&current);
}
inline std::uint64_t SimId(const ui::Json& value) {
    if(!value.is_string()) throw std::runtime_error("An exact decimal Sim ID is required.");
    const auto text=value.get<std::string>();
    if(text.empty() || text.size()>20 || text[0]=='0') throw std::runtime_error("Invalid native Sim ID.");
    std::uint64_t result=0;
    for(const auto c:text) {
        if(c<'0' || c>'9' || result>(UINT64_MAX-static_cast<unsigned>(c-'0'))/10)
            throw std::runtime_error("Native Sim ID exceeds its integer bound.");
        result=result*10+static_cast<unsigned>(c-'0');
    }
    return result;
}
inline Scope ParseScope(const ui::Json& request) {
    if(!request.is_object() || request.size()!=3 || request.value("operation","")!="arm" ||
       !request.contains("scope_id") || !request["scope_id"].is_string() ||
       !request.contains("members") || !request["members"].is_array())
        throw std::runtime_error("Native form selection requires a complete captured household scope.");
    Scope result{request["scope_id"].get<std::string>(),{}};
    if(result.id.size()!=32 || result.id.find_first_not_of("0123456789abcdef")!=std::string::npos ||
       request["members"].empty() || request["members"].size()>8)
        throw std::runtime_error("Native form scope identity or roster is invalid.");
    for(const auto& row:request["members"]) {
        if(!row.is_object() || row.size()!=2 || !row.contains("sim_id") || !row.contains("owned_mask") ||
           !row["owned_mask"].is_number_unsigned()) throw std::runtime_error("Untyped native form scope member.");
        const auto id=SimId(row["sim_id"]);const auto mask=row["owned_mask"].get<std::uint64_t>();
        if(mask>127 || !(mask&1) || !(mask&~1ULL) || !result.members.emplace(id,Member{id,static_cast<std::uint32_t>(mask)}).second)
            throw std::runtime_error("Native form ownership is absent, duplicated or outside supported kinds.");
    }
    return result;
}
inline void ValidateKinds(std::uint32_t expected,const std::vector<std::uint32_t>& kinds) {
    std::uint32_t observed=0;
    if(kinds.empty() || kinds.size()>7) throw std::runtime_error("Native import lacks a bounded owner roster.");
    for(const auto kind:kinds) {
        if(!Kind(kind) || (observed&kind) || !(expected&kind))
            throw std::runtime_error("Native import contains an unknown, foreign or duplicate owner.");
        observed|=kind;
    }
    if(observed!=expected) throw std::runtime_error("Native import does not contain every captured form owner.");
}
inline bool OwnedTarget(const Member& member,std::uint32_t imported,std::uint32_t target) {
    return Kind(target) && (member.mask&target) && imported==member.mask;
}
}
