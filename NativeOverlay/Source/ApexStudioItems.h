// Bounded, read-only metadata pages for the exact displayed outfit owner.
#pragma once
#include "ApexResourceData.h"

namespace td1::ui {
inline bool StudioMetadataChanged(const Json& reply, const Json& current) {
    if (Scalar(reply, "history_lane") != Scalar(current, "history_lane")) return true;
    for (const auto* field : {"runtime_pid", "appearance_sha256", "inspected_form_flags"})
        if (reply.contains(field) && Scalar(reply, field) != Scalar(current, field)) return true;
    // Legacy editor responses omit the top-level PID/fingerprint. Their exact
    // appearance fingerprint still binds the editor to this inspected owner.
    for (const auto* field : {"part_editor", "color_editor"})
        if (reply.contains(field) && reply[field].is_object() &&
            Scalar(reply[field], "appearance_sha256") != Scalar(current, "appearance_sha256")) return true;
    return false;
}

inline bool StudioItemRequest(const Json& request) {
    if (!request.is_object() || request.size() != 6) return false;
    for (const auto* key : {"runtime_pid", "cursor", "limit", "outfit_index"})
        if (!request.contains(key) || !request[key].is_number_integer() || request[key].is_boolean()) return false;
    return !Scalar(request, "lane").empty() && resource::Hash(request, "appearance_sha256") &&
        request["runtime_pid"] > 0 && request["cursor"] >= 0 && request["cursor"] <= 16384 &&
        request["limit"] >= 1 && request["limit"] <= 8 && request["outfit_index"] >= 0 && request["outfit_index"] < 128;
}

inline bool StudioItemPage(const Json& page, const Json& request, const Json& outfit, int form) {
    if (!StudioItemRequest(request) || !page.is_object() || page.value("ok", Json(false)) != true ||
        !outfit.contains("parts") || !outfit["parts"].is_array() || outfit["parts"].size() > 1024) return false;
    for (const auto* key : {"runtime_pid", "cursor", "limit", "outfit_index"})
        if (!page.contains(key) || page[key] != request[key]) return false;
    if (Scalar(page, "history_lane") != Scalar(request, "lane") ||
        Scalar(page, "appearance_sha256") != Scalar(request, "appearance_sha256") ||
        !page.contains("inspected_form_flags") || page["inspected_form_flags"] != form ||
        !page.contains("owner") || !page["owner"].is_object()) return false;
    const auto& owner = page["owner"];
    if (!owner.contains("runtime_pid") || owner["runtime_pid"] != request["runtime_pid"] ||
        !owner.contains("form_flags") || owner["form_flags"] != form ||
        !owner.contains("slot_id") || !owner["slot_id"].is_number_integer() || owner["slot_id"] < 0 || owner["slot_id"] > 0xffffffffULL ||
        Scalar(owner, "save_guid").empty() || Scalar(owner, "sim_id").empty()) return false;
    const bool stableSlot = owner["slot_id"] > 0 && owner["slot_id"] < 0xffffffffULL;
    auto expectedLane = Scalar(owner, "save_guid") + ":" + Scalar(owner, "slot_id") + ":" + Scalar(owner, "sim_id") + ":" + std::to_string(form);
    if (!stableSlot) {
        if (page.value("stable_save_slot_verified", Json()) != false || page.value("history_runtime_only", Json()) != true) return false;
        expectedLane += ":runtime-" + Scalar(request, "runtime_pid");
    } else if ((page.contains("stable_save_slot_verified") && page["stable_save_slot_verified"] != true) ||
        (page.contains("history_runtime_only") && page["history_runtime_only"] != false)) return false;
    if (Scalar(request, "lane") != expectedLane + ":full-appearance-v1") return false;
    if (!page.contains("total") || page["total"] != outfit["parts"].size() ||
        !page.contains("items") || !page["items"].is_array() || page["items"].size() > 8 ||
        !page.contains("complete") || !page["complete"].is_boolean() || !page.contains("next_cursor") ||
        !page.contains("resource_inspection_count") || !page["resource_inspection_count"].is_number_integer() ||
        page["resource_inspection_count"] < 0 || page["resource_inspection_count"] > 8) return false;
    const auto cursor = request["cursor"].get<size_t>();
    const auto total = outfit["parts"].size();
    if (cursor > total || page["items"].size() != std::min(request["limit"].get<size_t>(), total - cursor)) return false;
    const auto next = cursor + page["items"].size();
    if ((next == total) != page["complete"].get<bool>() ||
        (next == total ? !page["next_cursor"].is_null() : page["next_cursor"] != next)) return false;
    for (size_t i = 0; i < page["items"].size(); ++i) {
        const auto& item = page["items"][i]; const auto& actual = outfit["parts"][cursor + i];
        if (!item.is_object() || !resource::Hash(item, "cache_key") ||
            !item.contains("outfit_index") || item["outfit_index"] != request["outfit_index"] ||
            Scalar(item, "outfit_id") != Scalar(outfit, "outfit_id")) return false;
        for (const auto* key : {"target", "body_type", "index", "cas_part_id"})
            if (Scalar(item, key).empty() || Scalar(item, key) != Scalar(actual, key)) return false;
        const auto status = Scalar(item, "status");
        if (status != "resolved" && status != "unresolved") return false;
        if (!item.contains("display_name") || !(item["display_name"].is_null() || item["display_name"].is_string()) ||
            Scalar(item, "display_name").size() > 4096 || !item.contains("part_editor")) return false;
        const auto& editor = item["part_editor"];
        if (!editor.is_null()) {
            if (!editor.is_object() || !resource::Hash(editor, "resource_sha256") ||
                Scalar(editor, "appearance_sha256") != Scalar(request, "appearance_sha256")) return false;
            for (const auto* key : {"target", "body_type", "cas_part_id"})
                if (Scalar(editor, key) != Scalar(actual, key)) return false;
            if (Scalar(item, "display_name") != Scalar(editor, "part_name")) return false;
        }
        if (status == "resolved" && (!editor.is_object() || !resource::Tgi(Scalar(editor, "resource_tgi")) ||
            Scalar(editor, "resource_key_query") != "native-key" ||
            Scalar(editor, "resource_tgi").substr(18) != Scalar(actual, "cas_part_hex"))) return false;
    }
    return true;
}
}
