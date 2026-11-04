// Per-draw category lookup for the equipped-items view. No retained state.
#pragma once
#include "ApexUiData.h"
#include <map>
#include <set>
#include <string>

namespace td1::ui {
class EquippedCategoryIndex {
    std::map<std::string, std::string> firstGroup_;
    std::set<std::string> equipped_;
public:
    EquippedCategoryIndex(const Json* categories, const Json& parts, bool includeEmpty) {
        if (!categories || parts.empty()) return;
        for (const auto& category : *categories)
            firstGroup_.emplace(Scalar(category, "body_type"), Scalar(category, "group"));
        if (includeEmpty)
            for (const auto& part : parts) equipped_.insert(Scalar(part, "body_type"));
    }
    const std::string* Group(const Json& part) const {
        if (firstGroup_.empty()) return nullptr;
        const auto found=firstGroup_.find(Scalar(part, "body_type"));
        return found==firstGroup_.end() ? nullptr : &found->second;
    }
    bool Equipped(const Json& category) const {
        return !equipped_.empty() && equipped_.find(Scalar(category, "body_type"))!=equipped_.end();
    }
};
}
