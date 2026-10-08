// Typed transport data for the actual native overlay; no game/D3D dependencies.
#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include "nlohmann/json.hpp"

namespace td1::ui {
using Json = nlohmann::json;

inline int32_t MetricHandleBits(uint64_t value) {
    // The C sidecar ABI returns signed int32 values. Windows HWND identity
    // uses the low 32 bits; preserve their exact pattern for Python's & mask.
    const auto bits = static_cast<uint32_t>(value);
    int32_t result = 0;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}

inline int StudioOverlayTab(int request) {
    // Public sidecar API: 11/12 remain the accepted Live/bank views; 13/14
    // explicitly request native CAS client history/equipped views.
    if (request == 11 || request == 13) return 11;
    if (request == 12 || request == 14) return 12;
    return -1;
}

inline Json ParseObject(const std::string& raw) {
    if (raw.size() > 512 * 1024) return Json::object();
    try {
        auto result = Json::parse(raw, [](int depth, Json::parse_event_t, Json&) {
            if (depth > 32) throw std::runtime_error("Overlay JSON nesting exceeds its bound");
            return true;
        });
        return result.is_object() ? result : Json::object();
    } catch (const std::exception&) { return Json::object(); }
}

inline const Json& ReadObject(const std::string& raw) {
    // Worker and render threads have separate caches. Two entries cover the
    // current status and retained command result without parsing every frame.
    struct Entry { std::string raw; Json data = Json::object(); };
    static thread_local std::array<Entry, 2> cache;
    static thread_local size_t next = 0;
    for (const auto& entry : cache) if (entry.raw == raw) return entry.data;
    auto& entry = cache[next];
    next = (next + 1) % cache.size();
    entry.raw = raw;
    entry.data = ParseObject(raw);
    return entry.data;
}

inline std::string Scalar(const Json& object, const char* key) {
    const auto found = object.find(key);
    if (found == object.end() || found->is_null()) return {};
    if (found->is_string()) return found->get<std::string>();
    if (found->is_boolean() || found->is_number()) return found->dump();
    return {};
}

inline std::string StatusScalar(const Json& object, const char* key) {
    // These are the backend's two documented status envelopes, not a search
    // through arbitrary nested objects (MCCC/cache records can have other Sims).
    for (const auto* envelope : {"status", "data"}) {
        const auto found = object.find(envelope);
        if (found != object.end() && found->is_object()) return Scalar(*found, key);
    }
    return Scalar(object, key);
}

inline std::vector<std::string> Logs(const Json& object) {
    auto found = object.find("logs");
    if (found == object.end()) found = object.find("history");
    if (found == object.end() || !found->is_array()) return {};
    std::vector<std::string> result;
    const auto start = found->size() > 260 ? found->size() - 260 : 0;
    for (size_t i = start; i < found->size(); ++i) {
        const auto& value = (*found)[i];
        if (value.is_string()) result.push_back(value.get<std::string>());
    }
    return result;
}

inline bool StudioDocument(const Json& object) {
    if (!object.contains("history_nodes") || !object["history_nodes"].is_array() ||
        !object.contains("history_lane") || !object["history_lane"].is_string()) return false;
    auto identity = [](const Json& value) {
        if (!value.is_string()) return false;
        const auto text = value.get<std::string>();
        if (text.size() != 32) return false;
        for (const char c : text) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        return true;
    };
    for (const auto& node : object["history_nodes"]) {
        if (!node.is_object() || !node.contains("id") || !identity(node["id"]) ||
            !node.contains("label") || !node["label"].is_string() ||
            !node.contains("time") || !node["time"].is_number() ||
            !node.contains("parent") || !(node["parent"].is_null() || identity(node["parent"]))) return false;
    }
    auto inventory = [](const Json& outfits) {
        if (!outfits.is_array() || outfits.size() > 1024) return false;
        for (const auto& outfit : outfits) {
            if (!outfit.is_object() || !outfit.contains("index") || !outfit["index"].is_number_unsigned() ||
                !outfit.contains("category") || !outfit["category"].is_number_unsigned() ||
                !outfit.contains("outfit_id") || !outfit["outfit_id"].is_string() ||
                !outfit.contains("parts") || !outfit["parts"].is_array() || outfit["parts"].size() > 1024) return false;
            for (const auto& part : outfit["parts"]) {
                if (!part.is_object() || !part.contains("target") || !part["target"].is_string() ||
                    !part.contains("target_supported") || !part["target_supported"].is_boolean() ||
                    !part.contains("label") || !part["label"].is_string() ||
                    !part.contains("cas_part_hex") || !part["cas_part_hex"].is_string() ||
                    !part.contains("index") || !part["index"].is_number_unsigned() ||
                    !part.contains("color_hex") || !(part["color_hex"].is_null() || part["color_hex"].is_string())) return false;
            }
        }
        return true;
    };
    if (object.contains("outfit_inventory") && !inventory(object["outfit_inventory"])) return false;
    if (object.contains("form_inventory")) {
        const auto& forms = object["form_inventory"];
        if (!forms.is_array() || forms.size() > 128) return false;
        if (!object.contains("inspected_form_flags") || !object["inspected_form_flags"].is_number_unsigned()) return false;
        for (const auto& form : forms) {
            if (!form.is_object() || !form.contains("flags") || !form["flags"].is_number_unsigned() ||
                !form.contains("current") || !form["current"].is_boolean() || !form.contains("name") || !form["name"].is_string() ||
                !form.contains("outfit_inventory") || !inventory(form["outfit_inventory"]) ||
                !form.contains("appearance_fields") || !form["appearance_fields"].is_array()) return false;
            for (const auto& field : form["appearance_fields"])
                if (!field.is_object() || !field.contains("name") || !field["name"].is_string() ||
                    !field.contains("kind") || !field["kind"].is_string() || !field.contains("value")) return false;
        }
    }
    if (object.contains("category_catalog")) {
        const auto& categories = object["category_catalog"];
        if (!categories.is_array() || categories.size() > 1024) return false;
        for (const auto& category : categories)
            if (!category.is_object() || !category.contains("body_type") || !category["body_type"].is_number_unsigned() ||
                !category.contains("label") || !category["label"].is_string() || !category.contains("group") ||
                !category["group"].is_string() || !category.contains("supported") || !category["supported"].is_boolean()) return false;
    }
    if (object.contains("hair_policy") && (!object["hair_policy"].is_object() ||
        !object["hair_policy"].contains("enabled") || !object["hair_policy"]["enabled"].is_boolean())) return false;
    if (object.contains("part_editor")) {
        const auto& editor = object["part_editor"];
        if (!editor.is_object()) return false;
        for (const auto* key : {"target", "part_name", "appearance_sha256"})
            if (!editor.contains(key) || !editor[key].is_string()) return false;
        if (!editor.contains("candidates") || !editor["candidates"].is_array() || editor["candidates"].size() > 256) return false;
        for (const auto& source : editor["candidates"])
            for (const auto* key : {"target", "cas_part_hex"})
                if (!source.contains(key) || !source[key].is_string()) return false;
    }
    if (object.contains("preview_delta") && (!object["preview_delta"].is_object() ||
        !object["preview_delta"].contains("summary") || !object["preview_delta"]["summary"].is_string())) return false;
    if (object.contains("color_editor")) {
        const auto& editor = object["color_editor"];
        if (!editor.is_object()) return false;
        for (const auto* key : {"target", "cas_part_id", "color_hex", "appearance_sha256", "resource_sha256", "part_name"})
            if (!editor.contains(key) || !editor[key].is_string()) return false;
        if (!editor.contains("channels") || !editor["channels"].is_object()) return false;
        for (const auto* name : {"hue", "saturation", "brightness", "opacity"}) {
            if (!editor["channels"].contains(name) || !editor["channels"][name].is_object()) return false;
            const auto& channel = editor["channels"][name];
            if (!channel.contains("enabled") || !channel["enabled"].is_boolean()) return false;
            for (const auto* key : {"value", "min", "max", "step"})
                if (!channel.contains(key) || !channel[key].is_number() || !std::isfinite(channel[key].get<double>())) return false;
            if (channel["min"].get<double>() > channel["max"].get<double>() || channel["step"].get<double>() < 0) return false;
        }
    }
    return true;
}

inline bool ExactUint64Identity(const Json& value) {
    if (!value.is_string()) return false;
    const auto text = value.get<std::string>();
    if (text.empty() || text.size() > 20 || text[0] == '0') return false;
    for (const char c : text) if (c < '0' || c > '9') return false;
    return text.size() < 20 || text <= "18446744073709551615";
}

inline bool CasInt(const Json& value, int64_t minimum, int64_t maximum) {
    if (!value.is_number_integer()) return false;
    if (value.is_number_unsigned()) {
        const auto number = value.get<uint64_t>();
        return maximum >= 0 && number <= static_cast<uint64_t>(maximum) &&
            (minimum <= 0 || number >= static_cast<uint64_t>(minimum));
    }
    const auto number = value.get<int64_t>();
    return number >= minimum && number <= maximum;
}

inline bool CasDocument(const Json& object, const std::string& sim) {
    // Protocol 1 queries all 72 panels mapped by the pinned game build. An
    // omitted category is not an empty category. Unknown item fields survive
    // validation unchanged; this is validation, never a projected DTO.
    if (!object.is_object() || object.dump().size() > 131072 ||
        Scalar(object, "scope") != "native-cas-client" || !object.contains("sim") || !object["sim"].is_object() ||
        !object["sim"].contains("simId") || !ExactUint64Identity(object["sim"]["simId"]) ||
        Scalar(object["sim"], "simId") != sim || !object.contains("menu_state") ||
        !CasInt(object["menu_state"], -2147483648LL, 2147483647LL) ||
        !object.contains("panel_visible") || !object["panel_visible"].is_boolean() ||
        !object.contains("catalogs") || !object["catalogs"].is_array() || object["catalogs"].size() != 72 ||
        !object.contains("outfit") || !object["outfit"].is_object() ||
        !object["outfit"].contains("outfit_type") || !CasInt(object["outfit"]["outfit_type"], 0, 255) ||
        !object["outfit"].contains("outfit_index") || !CasInt(object["outfit"]["outfit_index"], 0, 4)) return false;
    std::vector<std::string> names;
    std::vector<int64_t> states;
    for (const auto& catalog : object["catalogs"]) {
        const auto name = Scalar(catalog, "panel");
        if (!catalog.is_object() || !catalog.contains("panel") || !catalog["panel"].is_string() ||
            name.empty() || name.size() > 128 || std::find(names.begin(), names.end(), name) != names.end() ||
            !catalog.contains("menu_state") || !CasInt(catalog["menu_state"], -2147483648LL, 2147483647LL) ||
            !catalog.contains("supported") || !catalog["supported"].is_boolean() || !catalog.contains("items")) return false;
        names.push_back(name);
        const auto state = catalog["menu_state"].get<int64_t>();
        if (std::find(states.begin(), states.end(), state) != states.end()) return false;
        states.push_back(state);
        const auto& items = catalog["items"];
        if (!catalog["supported"].get<bool>()) { if (!items.is_null()) return false; }
        else {
            if (!items.is_array() || items.size() > 1024) return false;
            for (const auto& item : items) if (!item.is_object()) return false;
        }
        if (!catalog.contains("preset") || !catalog.contains("preset_query") || !catalog["preset_query"].is_string()) return false;
        const auto presetQuery = Scalar(catalog, "preset_query");
        if (presetQuery == "returned-value") { if (!catalog["preset"].is_object()) return false; }
        else if ((presetQuery != "returned-null" && presetQuery != "failed") || !catalog["preset"].is_null()) return false;
    }
    return true;
}

inline bool CasPresetAbsent(const Json& preset) {
    // Observed native no-selection sentinel. Do not coerce strings/numbers or
    // discard future fields in the same raw record.
    return preset.is_object() && preset.contains("index") && CasInt(preset["index"], -1, -1) &&
        preset.contains("presetId") && preset["presetId"].is_string() && preset["presetId"] == "0";
}

inline bool CasPresetSelected(const Json& preset) {
    return preset.is_object() && preset.contains("index") && CasInt(preset["index"], 0, 2147483647LL) &&
        preset.contains("presetId") && ExactUint64Identity(preset["presetId"]);
}

inline bool CasHasPreset(const Json& catalog) {
    return Scalar(catalog, "preset_query") == "returned-value" && catalog.contains("preset") &&
        catalog["preset"].is_object() && !CasPresetAbsent(catalog["preset"]);
}

inline bool CasCatalogEmpty(const Json& catalog) {
    if (!catalog.contains("supported") || !catalog["supported"].is_boolean() || !catalog["supported"].get<bool>() ||
        !catalog.contains("items") || !catalog["items"].is_array() || !catalog["items"].empty()) return false;
    const auto query = Scalar(catalog, "preset_query");
    return query == "returned-null" || (query == "returned-value" && catalog.contains("preset") && CasPresetAbsent(catalog["preset"]));
}

inline std::string CasPanelLabel(std::string name) {
    for (const auto& entry : std::array<std::pair<const char*, const char*>, 5>{{
        {"clothing_accessories_earrings", "Jewelry / Earrings"}, {"clothing_accessories_necklaces", "Jewelry / Necklaces"},
        {"clothing_accessories_rings", "Jewelry / Rings"}, {"clothing_accessories_piercings", "Jewelry / Piercings"},
        {"clothing_accessories_bracelets", "Jewelry / Bracelets"}}})
        if (name == entry.first) return entry.second;
    for (const auto* prefix : {"clothing_", "profile_"})
        if (name.find(prefix) == 0) { name.erase(0, std::strlen(prefix)); break; }
    std::replace(name.begin(), name.end(), '_', ' ');
    for (const auto& entry : std::array<std::pair<const char*, const char*>, 12>{{
        {"bodyhair", "body hair"}, {"skincolor", "skin color"}, {"skinspecularity", "skin specularity"},
        {"fullbody", "full body"}, {"bodydetails", "body details"}, {"bodyscar", "body scars"},
        {"headdeco", "head decoration"}, {"fingernail", "fingernails"}, {"toenail", "toenails"},
        {"hoofcolor", "hoof color"}, {"torsoback", "torso back"}, {"torsofront", "torso front"}}}) {
        const auto at = name.find(entry.first);
        if (at != std::string::npos) name.replace(at, std::strlen(entry.first), entry.second);
    }
    if (name.find("body body hair ") == 0) name.erase(0, 5);
    bool beginning = true;
    for (char& c : name) {
        if (beginning && c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
        beginning = c == ' ';
    }
    return name;
}

inline Json RefreshCasSelection(const Json& document, const std::string& panel, const Json& selected, bool preset = false) {
    // Keep an inspected item only when the newly acknowledged catalog still
    // identifies it uniquely. Use the new record so modified/unknown fields
    // are never displayed from a previous outfit or refresh.
    if (!selected.is_object() || selected.empty() || !document.contains("catalogs") || !document["catalogs"].is_array()) return Json::object();
    const auto identity = Scalar(selected, "dataID");
    Json found = Json::object();
    for (const auto& catalog : document["catalogs"]) {
        if (Scalar(catalog, "panel") != panel) continue;
        if (preset) return Scalar(catalog, "preset_query") == "returned-value" && catalog.contains("preset") && catalog["preset"].is_object()
            ? catalog["preset"] : Json::object();
        if (!catalog.contains("items") || !catalog["items"].is_array()) continue;
        for (const auto& item : catalog["items"]) {
            if ((!identity.empty() && Scalar(item, "dataID") == identity) || (identity.empty() && item == selected)) {
                if (!found.empty()) return Json::object();
                found = item;
            }
        }
    }
    return found;
}
} // namespace td1::ui
