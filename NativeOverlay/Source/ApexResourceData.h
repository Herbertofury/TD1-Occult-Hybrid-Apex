// Read-only pinned resource broker data. Native CAS catalog IDs are not TGIs.
#pragma once
#include "ApexUiData.h"
#include <cctype>
#include <set>

namespace td1::resource {
using Json = ui::Json;
inline bool Hex(const std::string& value, size_t length, bool upper = false) {
    if (value.size() != length) return false;
    return std::all_of(value.begin(), value.end(), [upper](char c) {
        return (c >= '0' && c <= '9') || (upper ? c >= 'A' && c <= 'F' : c >= 'a' && c <= 'f');
    });
}
inline bool Hash(const Json& object, const char* field) {
    const auto found = object.find(field);
    return found != object.end() && found->is_string() && Hex(found->get<std::string>(), 64);
}
inline bool Tgi(const std::string& value) {
    return value.size() == 34 && value.substr(0, 9) == "034AEECB:" && value[17] == ':' &&
        Hex(value.substr(9, 8), 8, true) && Hex(value.substr(18), 16, true);
}
inline bool NullableText(const Json& object, const char* field, size_t bound) {
    const auto found = object.find(field);
    return found != object.end() && (found->is_null() || (found->is_string() &&
        !found->get_ref<const std::string&>().empty() && found->get_ref<const std::string&>().size() <= bound));
}
enum class NameMode { Preferred, Package, Code };
struct ItemName { std::string text, source; };
inline ItemName Name(const Json& row, NameMode mode) {
    if (!row.is_object()) return {};
    if (mode == NameMode::Preferred) {
        return {ui::Scalar(row, row.contains("preferred_name") ? "preferred_name" : "display_name"),
                ui::Scalar(row, row.contains("preferred_name_status") ? "preferred_name_status" : "name_status")};
    }
    if (mode == NameMode::Package) {
        auto name = ui::Scalar(row, "package_name");
        if (!row.contains("package_name") && row.contains("provenance") && row["provenance"].is_object())
            name = ui::Scalar(row["provenance"], "package_filename");
        return {name, name.empty() ? "unresolved" : "containing-package-filename"};
    }
    auto name = ui::Scalar(row, "code_name");
    if (!row.contains("code_name")) {
        if (row.contains("metadata") && row["metadata"].is_object()) name = ui::Scalar(row["metadata"], "internal_name");
        if (name.empty() && ui::Scalar(row, "name_status") == "casp-internal-name") name = ui::Scalar(row, "display_name");
    }
    return {name, name.empty() ? "unresolved" : "casp-internal-name"};
}
inline bool NameFields(const Json& row) {
    const bool any = row.contains("preferred_name") || row.contains("preferred_name_status") ||
        row.contains("package_name") || row.contains("code_name");
    if (!any) return true; // Previously pinned catalogs retain their exact provenance.
    for (const auto* field : {"preferred_name", "package_name", "code_name"})
        if (!NullableText(row, field, 8192)) return false;
    if (!row.contains("preferred_name_status") || !row["preferred_name_status"].is_string() ||
        row["preferred_name"] != row["display_name"] || row["preferred_name_status"] != row["name_status"]) return false;
    if (ui::Scalar(row, "status") != "resolved")
        return row["preferred_name"].is_null() && row["package_name"].is_null() && row["code_name"].is_null();
    if (!row.contains("provenance") || !row["provenance"].is_object() ||
        !row.contains("metadata") || !row["metadata"].is_object()) return false;
    const auto package = ui::Scalar(row, "package_name"), code = ui::Scalar(row, "code_name");
    if (package.empty() || package != ui::Scalar(row["provenance"], "package_filename") ||
        package.find_first_of("/\\") != std::string::npos || code != ui::Scalar(row["metadata"], "internal_name")) return false;
    const auto state = ui::Scalar(row, "preferred_name_status"), preferred = ui::Scalar(row, "preferred_name");
    return (state == "localized-title" && !preferred.empty()) ||
        (state == "cc-package-filename" && ui::Scalar(row["provenance"], "origin") == "mod" && preferred == package) ||
        (state == "casp-internal-name" && !code.empty() && preferred == code) ||
        (state == "unresolved" && preferred.empty());
}
inline bool Catalog(const Json& value) {
    if (!value.is_object() || value.dump().size() > 512 * 1024 || !value.contains("schema") ||
        !value["schema"].is_number_integer() || value["schema"] != 1 || !value.contains("items") ||
        !value["items"].is_array() || value["items"].size() > 1024) return false;
    std::set<std::string> seen;
    for (const auto& row : value["items"]) {
        if (!row.is_object() || !Hash(row, "resource_id") || !Hash(row, "cache_proof") ||
            !Hash(row, "effective_resource_sha256") || !Tgi(ui::Scalar(row, "resource_tgi")) ||
            !seen.insert(ui::Scalar(row, "resource_id")).second ||
            !NullableText(row, "display_name", 8192)) return false;
        const auto state = ui::Scalar(row, "status"), nameState = ui::Scalar(row, "name_status");
        if ((state != "resolved" && state != "ambiguous" && state != "unresolved") ||
            (nameState != "localized-title" && nameState != "cc-package-filename" && nameState != "casp-internal-name" && nameState != "unresolved") ||
            ((nameState == "unresolved") != row["display_name"].is_null())) return false;
        if (!NameFields(row)) return false;
        if (!row.contains("body_type") || !(row["body_type"].is_null() || row["body_type"].is_number_integer()) ||
            !row.contains("provenance") || !row.contains("thumbnail") || !row["thumbnail"].is_object() ||
            !row.contains("studio_open") || !row["studio_open"].is_object()) return false;
        const auto& provenance = row["provenance"];
        if (state == "resolved") {
            if (!provenance.is_object() || !Hash(provenance, "package_sha256") || !Hash(provenance, "resource_sha256") ||
                ui::Scalar(provenance, "resource_sha256") != ui::Scalar(row, "effective_resource_sha256") ||
                (ui::Scalar(provenance, "origin") != "ea" && ui::Scalar(provenance, "origin") != "mod")) return false;
        } else if (!provenance.is_null()) return false;
        const auto& thumbnail = row["thumbnail"];
        const auto thumbState = ui::Scalar(thumbnail, "status");
        if (thumbState == "resolved") {
            if (!Hash(thumbnail, "sha256") || ui::Scalar(thumbnail, "url") !=
                "/v1/resources/" + ui::Scalar(row, "resource_id") + "/thumbnail" ||
                !thumbnail.contains("width") || !thumbnail["width"].is_number_integer() ||
                !thumbnail.contains("height") || !thumbnail["height"].is_number_integer() ||
                thumbnail["width"] <= 0 || thumbnail["width"] > 512 ||
                thumbnail["height"] <= 0 || thumbnail["height"] > 512 || state != "resolved") return false;
        } else if (thumbState != "unresolved" || !thumbnail.contains("url") || !thumbnail["url"].is_null() ||
            !thumbnail.contains("sha256") || !thumbnail["sha256"].is_null() ||
            !thumbnail.contains("width") || !thumbnail["width"].is_null() ||
            !thumbnail.contains("height") || !thumbnail["height"].is_null()) return false;
        if (!NullableText(thumbnail, "reason", 8192)) return false;
        const auto& studio = row["studio_open"];
        const auto studioState = ui::Scalar(studio, "status");
        if (ui::Scalar(studio, "selection") != "containing-package" ||
            !studio.contains("resource_selection_supported") || studio["resource_selection_supported"] != false ||
            (studioState != "ready" && studioState != "unavailable") ||
            (studioState == "ready" && state != "resolved") || !NullableText(studio, "reason", 8192)) return false;
    }
    return true;
}
inline Json EquippedFromValidatedCatalog(const Json& catalog, const Json& part, const Json& editor, const std::string& appearance) {
    // Effective game CASP bytes, exact instance and current appearance are all
    // required. A numeric CAS catalog dataID never enters this matching path.
    if (!part.is_object() || !editor.is_object() ||
        !Hex(ui::Scalar(part, "cas_part_hex"), 16, true) || !Hash(editor, "resource_sha256") ||
        !Tgi(ui::Scalar(editor, "resource_tgi")) ||
        ui::Scalar(editor, "resource_tgi").substr(18) != ui::Scalar(part, "cas_part_hex") ||
        !Hex(appearance, 64) || ui::Scalar(editor, "appearance_sha256") != appearance ||
        ui::Scalar(part, "target").empty() || ui::Scalar(editor, "target") != ui::Scalar(part, "target") ||
        ui::Scalar(part, "cas_part_id").empty() || ui::Scalar(editor, "cas_part_id") != ui::Scalar(part, "cas_part_id") ||
        !part.contains("body_type") || !part["body_type"].is_number_integer() ||
        !editor.contains("body_type") || editor["body_type"] != part["body_type"])
        return Json::object();
    Json result = Json::object();
    for (const auto& row : catalog["items"]) {
        if (ui::Scalar(row, "resource_tgi") != ui::Scalar(editor, "resource_tgi") ||
            ui::Scalar(row, "effective_resource_sha256") != ui::Scalar(editor, "resource_sha256") ||
            row["body_type"] != part["body_type"]) continue;
        // Duplicate exact effective bindings never select an arbitrary package.
        if (!result.empty()) return Json::object();
        result = row;
    }
    return !result.empty() && ui::Scalar(result, "status") == "resolved" ? result : Json::object();
}
inline Json Equipped(const Json& catalog, const Json& part, const Json& editor, const std::string& appearance) {
    if (!Catalog(catalog)) return Json::object();
    return EquippedFromValidatedCatalog(catalog, part, editor, appearance);
}
inline bool OpenReceipt(const Json& receipt, const std::string& id) {
    return Hex(id, 64) && receipt.is_object() && receipt.contains("ok") && receipt["ok"] == true &&
        ui::Scalar(receipt, "resource_id") == id && ui::Scalar(receipt, "selection") == "containing-package" &&
        receipt.contains("resource_selection_supported") && receipt["resource_selection_supported"] == false;
}
inline bool HttpBody(const std::string& raw, size_t bound, std::string& body) {
    body.clear();
    const auto split = raw.find("\r\n\r\n");
    if (split == std::string::npos || split > 16384 ||
        (raw.find("HTTP/1.1 200 ") != 0 && raw.find("HTTP/1.0 200 ") != 0)) return false;
    size_t length = 0; bool gotLength = false;
    size_t line = raw.find("\r\n") + 2;
    while (line < split) {
        const auto end = raw.find("\r\n", line);
        if (end == std::string::npos || end > split) return false;
        auto header = raw.substr(line, end - line);
        const auto colon = header.find(':');
        if (colon == std::string::npos) return false;
        auto key = header.substr(0, colon);
        std::transform(key.begin(), key.end(), key.begin(), [](unsigned char c) { return char(std::tolower(c)); });
        if (key == "transfer-encoding") return false;
        if (key == "content-length") {
            if (gotLength) return false;
            auto text = header.substr(colon + 1);
            const auto first = text.find_first_not_of(' '), last = text.find_last_not_of(' ');
            if (first == std::string::npos) return false;
            text = text.substr(first, last - first + 1);
            if (text.size() > 10) return false;
            for (char c : text) {
                if (c < '0' || c > '9') return false;
                length = length * 10 + static_cast<size_t>(c - '0');
                if (length > bound) return false;
            }
            gotLength = true;
        }
        line = end + 2;
    }
    if (!gotLength || raw.size() - split - 4 != length) return false;
    body.assign(raw.data() + split + 4, length);
    return true;
}
} // namespace td1::resource
