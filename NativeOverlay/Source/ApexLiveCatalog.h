#pragma once
#include "ApexResourceData.h"
namespace td1::library {
using Json = ui::Json;
inline bool ImagesRequest(const Json& q) {
    if (!q.is_object() || q.size()!=3 || !resource::Hash(q,"index_sha256") ||
        !q.contains("gender") || !(q["gender"]=="male" || q["gender"]=="female") ||
        !q.contains("part_ids") || !q["part_ids"].is_array() || q["part_ids"].empty() || q["part_ids"].size()>24) return false;
    std::set<std::string> seen;
    for (const auto& id:q["part_ids"]) if (!id.is_string() || !resource::Hex(id.get<std::string>(),64) || !seen.insert(id.get<std::string>()).second) return false;
    return true;
}
inline bool ImagesPage(const Json& p,const Json& request,const Json& page) {
    if (!ImagesRequest(request) || !p.is_object() || p.value("ok",Json())!=true ||
        p.value("index_sha256",Json())!=request["index_sha256"] || p.value("gender",Json())!=request["gender"] ||
        p.value("part_ids",Json())!=request["part_ids"] || !p.contains("items") || !p["items"].is_array() ||
        p["items"].size()!=request["part_ids"].size() || !page.contains("items")) return false;
    for(size_t i=0;i<p["items"].size();++i) {
        const auto& item=p["items"][i];if(!item.is_object() || item.value("part_id",Json())!=request["part_ids"][i] ||
            !item.contains("resource") || !resource::CatalogIdentities({{"schema",1},{"items",Json::array({item["resource"]})}})) return false;
        const auto& row=item["resource"];bool bound=false;
        for(const auto& original:page["items"]) if(original["part_id"]==item["part_id"]) {
            bound=row.value("broker_port",Json())==8023 && row.value("resource_tgi",Json())==original["resource_tgi"] &&
                row.value("effective_resource_sha256",Json())==original["resource_sha256"] && row.value("body_type",Json())==original["body_type"];
            if(row.value("status",Json())=="resolved")bound=bound&&row["provenance"].value("package_sha256",Json())==original["package_sha256"];
            break;
        }
        if(!bound)return false;
    }
    return p.dump().size()<=512*1024;
}
inline bool Query(const Json& q) {
    if(q.is_object()&&q.contains("folder")) {
        if(!q["folder"].is_string()||q["folder"].get<std::string>().size()>2048)return false;
        auto legacy=q;legacy.erase("folder");return Query(legacy);
    }
    if(q.is_object()&&q.contains("added_days")) {
        if(!q["added_days"].is_null()&&!ui::CasInt(q["added_days"],1,36500))return false;
        auto legacy=q;legacy.erase("added_days");return Query(legacy);
    }
    if(q.is_object()&&q.contains("fuzzy")) {
        if(!q["fuzzy"].is_boolean())return false;
        auto legacy=q;legacy.erase("fuzzy");return Query(legacy);
    }
    if(q.is_object()&&q.contains("grouped")) {
        if(!q["grouped"].is_boolean())return false;
        auto legacy=q;legacy.erase("grouped");return Query(legacy);
    }
    if (!q.is_object() || !(q.size() == 7 || q.size() == 9 && q.contains("author") && q["author"].is_string() && q["author"].get<std::string>().size() <= 320 && q.contains("sort") && (q["sort"]=="name"||q["sort"]=="package"||q["sort"]=="creator"||q["sort"]=="id"||q["sort"]=="newest"||q["sort"]=="modified")) || !q.contains("text") || !q["text"].is_string() ||
        q["text"].get<std::string>().size() > 800 || !q.contains("body_type") ||
        !(q["body_type"].is_null() || q["body_type"].is_number_integer() && q["body_type"] >= 0 && q["body_type"] <= 0xffffffffULL) ||
        !q.contains("origin") || !(q["origin"].is_null() || q["origin"] == "mod" || q["origin"] == "ea") ||
        !q.contains("name_mode") || !(q["name_mode"] == "preferred" || q["name_mode"] == "package" || q["name_mode"] == "code") ||
        !q.contains("offset") || !q["offset"].is_number_integer() || q["offset"] < 0 || q["offset"] > 2000000 ||
        !q.contains("limit") || !q["limit"].is_number_integer() || q["limit"] < 1 || q["limit"] > 240 ||
        !q.contains("view") || !(q["view"] == "all" || q["view"] == "favorites" || q["view"] == "recent")) return false;
    return true;
}
inline bool Selection(const Json& q, bool favorite = false) {
    if(!favorite&&q.is_object()&&q.contains("swatch_offset")) {
        if(!ui::CasInt(q["swatch_offset"],0,2000000))return false;
        auto legacy=q;legacy.erase("swatch_offset");return Selection(legacy);
    }
    return q.is_object() && q.size() == (favorite ? 3 : 2) && resource::Hash(q, "part_id") &&
        resource::Hash(q, "index_sha256") && (!favorite || q.contains("enabled") && q["enabled"].is_boolean());
}
inline bool Swatches(const Json& p,const Json& item) {
    if(!p.is_object()||p.value("available",Json())!=true||!resource::Hash(p,"family_id")||
       p.value("family_id",Json())!=item.value("family_id",Json())||!p.contains("items")||!p["items"].is_array()||p["items"].size()>240||
       !p.contains("total")||!ui::CasInt(p["total"],1,2000000)||!p.contains("offset")||!ui::CasInt(p["offset"],0,2000000)||
       !p.contains("next_offset")||!(p["next_offset"].is_null()||p["next_offset"]==p["offset"].get<size_t>()+p["items"].size()&&p["next_offset"]<p["total"]))return false;
    std::set<std::string> seen;
    for(const auto& v:p["items"]) {
        if(!v.is_object()||!resource::Hash(v,"part_id")||!resource::Hash(v,"resource_sha256")||!resource::Hash(v,"package_sha256")||
           !resource::Hash(v,"variant_key")||!seen.insert(ui::Scalar(v,"variant_key")).second||
           v.value("family_id",Json())!=p["family_id"]||v.value("body_type",Json())!=item.value("body_type",Json())||
           !resource::Tgi(ui::Scalar(v,"resource_tgi"))||v.contains("package_path")||!v.contains("metadata")||!v["metadata"].is_object())return false;
        const auto& meta=v["metadata"];
        if(!meta.contains("swatch_colors_argb")||!meta["swatch_colors_argb"].is_array()||meta["swatch_colors_argb"].size()>255||
           !meta.contains("swatch_order")||!ui::CasInt(meta["swatch_order"],0,65535))return false;
        for(const auto& c:meta["swatch_colors_argb"])if(!ui::CasInt(c,0,0xffffffffLL))return false;
    }
    return true;
}
inline bool VisibleSelection(const Json& page,const Json& inspection,const Json& request) {
    if(!Selection(request)||page.value("index_sha256",Json())!=request["index_sha256"]||!page.contains("items")||!page["items"].is_array())return false;
    for(const auto& row:page["items"])if(row.value("part_id",Json())==request["part_id"])return true;
    if(inspection.value("index_sha256",Json())!=request["index_sha256"]||!inspection.contains("item")||!inspection.contains("swatches")||!Swatches(inspection["swatches"],inspection["item"]))return false;
    bool family=false;for(const auto& row:page["items"])if(row.value("family_id",Json())==inspection["item"].value("family_id",Json()))family=true;
    if(!family)return false;
    for(const auto& row:inspection["swatches"]["items"])if(row["part_id"]==request["part_id"])return true;
    return false;
}
inline bool Workspace(const Json& values) {
    if(!values.is_object()||values.empty()||values.size()>10)return false;
    for(const auto& item:values.items()) {
        const auto& v=item.value();const auto& k=item.key();
        if(k=="layout") {if(!(v=="balanced"||v=="character"||v=="catalog"||v=="custom"))return false;}
        else if(k=="preview_share") {if(!v.is_number()||!std::isfinite(v.get<double>())||v<.25||v>.65)return false;}
        else if(k=="columns") {if(!ui::CasInt(v,2,8))return false;}
        else if(k=="sidebar"||k=="thumbnails"||k=="generate_thumbnails") {if(!v.is_boolean())return false;}
        else if(k=="gender") {if(!(v=="male"||v=="female"))return false;}
        else if(k=="tab") {if(!(v=="equipped"||v=="library"||v=="sliders"||v=="tray"))return false;}
        else if(k=="query") {if(!Query(v)||v["limit"]!=60)return false;}
        else return false;
    }
    return true;
}
inline bool Page(const Json& p, const Json& request) {
    if(request.is_object()&&request.contains("grouped")&&p.value("grouped",Json())!=request["grouped"])return false;
    if (!Query(request) || !p.is_object() || p.value("ok", Json(false)) != true || !resource::Hash(p, "index_sha256") ||
        !p.contains("query") || p["query"] != request || !p.contains("items") || !p["items"].is_array() ||
        p["items"].size() > request["limit"].get<size_t>() || !p.contains("categories") || !p["categories"].is_array() ||
        p["categories"].size() > 4096 || !p.contains("total") || !p["total"].is_number_integer() ||
        p["total"] < 0 || p["total"] > 2000000 || !p.contains("offset") || p["offset"] != request["offset"] ||
        !p.contains("next_offset") || !(p["next_offset"].is_null() || p["next_offset"].is_number_integer() &&
        p["next_offset"] == p["offset"].get<size_t>() + p["items"].size() && p["next_offset"] < p["total"]) ||
        !p.contains("snapshot") || !p["snapshot"].is_object() || !p["snapshot"].contains("parts") ||
        !p["snapshot"]["parts"].is_number_integer() || !p["snapshot"].contains("complete") ||
        !p["snapshot"]["complete"].is_boolean() || p.dump().size() > 512 * 1024) return false;
    std::set<std::string> seen;
    for (const auto& row : p["items"]) {
        if (!row.is_object() || !resource::Hash(row, "part_id") || !resource::Hash(row, "resource_sha256") ||
            !resource::Hash(row, "package_sha256") || !resource::Tgi(ui::Scalar(row, "resource_tgi")) ||
            !seen.insert(ui::Scalar(row, "part_id")).second || row.contains("package_path") ||
            !row.contains("body_type") || !(row["body_type"].is_null() || row["body_type"].is_number_integer() && row["body_type"] >= 0) ||
            !row.contains("favorite") || !row["favorite"].is_boolean() || !resource::NullableText(row, "name", 8192) ||
            !row.contains("package_name") || !row["package_name"].is_string() ||
            ui::Scalar(row, "package_name").find_first_of("/\\") != std::string::npos ||
            !(row.value("status", Json()) == "indexed" || row.value("status", Json()) == "unclassified") ||
            !(row.value("origin", Json()) == "ea" || row.value("origin", Json()) == "mod")) return false;
    }
    for (const auto& category : p["categories"]) {
        if (!category.is_object() || !category.contains("body_type") ||
            !(category["body_type"].is_null() || category["body_type"].is_number_integer() && category["body_type"] >= 0) ||
            !category.contains("count") || !category["count"].is_number_integer() || category["count"] <= 0) return false;
    }
    return true;
}
inline bool Inspection(const Json& p, const Json& request) {
    if (!Selection(request) || !p.is_object() || p.value("ok", Json(false)) != true ||
        !p.contains("index_sha256") || p["index_sha256"] != request["index_sha256"] ||
        !p.contains("item") || !p["item"].is_object() || !p["item"].contains("part_id") ||
        p["item"]["part_id"] != request["part_id"] || !p.contains("resource") ||
        !resource::CatalogIdentities({{"schema", 1}, {"items", Json::array({p["resource"]})}})) return false;
    const auto& row = p["resource"]; const auto& item = p["item"];
    return row.value("broker_port", Json()) == 8023 && row.value("status", Json()) == "resolved" &&
        row.value("resource_tgi", Json()) == item.value("resource_tgi", Json()) &&
        row.value("effective_resource_sha256", Json()) == item.value("resource_sha256", Json()) &&
        row.value("body_type", Json()) == item.value("body_type", Json()) &&
        row["provenance"].value("package_sha256", Json()) == item.value("package_sha256", Json());
}
}
