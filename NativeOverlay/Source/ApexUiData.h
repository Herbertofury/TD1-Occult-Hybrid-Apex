// Typed transport data for the actual native overlay; no game/D3D dependencies.
#pragma once
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>
#include "nlohmann/json.hpp"

namespace td1::ui {
using Json = nlohmann::json;

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
    if (object.contains("outfit_inventory")) {
        if (!object["outfit_inventory"].is_array()) return false;
        for (const auto& outfit : object["outfit_inventory"]) {
            if (!outfit.is_object() || !outfit.contains("index") || !outfit["index"].is_number_unsigned() ||
                !outfit.contains("category") || !outfit["category"].is_number_unsigned() ||
                !outfit.contains("outfit_id") || !outfit["outfit_id"].is_string() ||
                !outfit.contains("parts") || !outfit["parts"].is_array()) return false;
            for (const auto& part : outfit["parts"]) {
                if (!part.is_object() || !part.contains("target") || !part["target"].is_string() ||
                    !part.contains("target_supported") || !part["target_supported"].is_boolean() ||
                    !part.contains("label") || !part["label"].is_string() ||
                    !part.contains("cas_part_hex") || !part["cas_part_hex"].is_string() ||
                    !part.contains("index") || !part["index"].is_number_unsigned() ||
                    !part.contains("color_hex") || !(part["color_hex"].is_null() || part["color_hex"].is_string())) return false;
            }
        }
    }
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
} // namespace td1::ui
