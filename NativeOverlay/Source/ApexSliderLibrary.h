#pragma once
#include "ApexResourceData.h"
namespace td1::sliders {
inline bool Tgi(const std::string& value) {
    return value.size()==34 && value[8]==':' && value[17]==':' &&
        (value.substr(0,8)=="C5F6763E"||value.substr(0,8)=="8B18FF6E"||value.substr(0,8)=="9D1AB874"||value.substr(0,8)=="EAA32ADD") &&
        resource::Hex(value.substr(9,8),8,true) && resource::Hex(value.substr(18),16,true);
}
inline bool Query(const ui::Json& q) {
    return q.is_object() && q.size()==5 && q.contains("search") && q["search"].is_string() &&
        q["search"].get<std::string>().size()<=200 && q.contains("offset") && q["offset"].is_number_integer() && q["offset"]>=0 &&
        q.contains("limit") && q["limit"].is_number_integer() && q["limit"]>=1 && q["limit"]<=100 &&
        q.contains("kind") && (q["kind"]=="modifier"||q["kind"]=="hotspot"||q["kind"]=="preset"||q["kind"]=="sculpt"||q["kind"]=="all") &&
        q.contains("conflicts_only") && q["conflicts_only"].is_boolean();
}
inline bool Page(const ui::Json& p,const ui::Json& q) {
    if(!Query(q)||!p.is_object()||p.value("ok",ui::Json())!=true||!resource::Hash(p,"catalog_sha256")||
       p.value("offset",ui::Json())!=q["offset"]||p.value("limit",ui::Json())!=q["limit"]||
       p.value("game_contacted",ui::Json())!=false||p.value("source_files_written",ui::Json())!=false||
       p.value("effective_load_source_verified",ui::Json())!=false||!p.contains("total")||!p["total"].is_number_integer()||p["total"]<0||
       !p.contains("items")||!p["items"].is_array()||p["items"].size()>q["limit"].get<size_t>())return false;
    std::set<std::string> seen;
    for(const auto& row:p["items"]){
        if(!row.is_object()||!row.contains("providers")||!row["providers"].is_array()||row["providers"].empty()||row["providers"].size()>512||
           !row.contains("resource_tgi")||!row["resource_tgi"].is_string()||!Tgi(row["resource_tgi"].get<std::string>())||
           !seen.insert(row["resource_tgi"].get<std::string>()).second||!row.contains("instance")||!(row["instance"]=="0"||ui::ExactUint64Identity(row["instance"]))||
           row.value("effective_load_source_verified",ui::Json())!=false)return false;
        const auto tgi=row["resource_tgi"].get<std::string>();
        if(std::to_string(std::stoull(tgi.substr(18),nullptr,16))!=row["instance"].get<std::string>())return false;
        const auto kind=ui::Scalar(row,"kind");
        if((kind=="modifier"?"C5F6763E":kind=="hotspot"?"8B18FF6E":kind=="sculpt"?"9D1AB874":kind=="preset"?"EAA32ADD":"")!=tgi.substr(0,8) ||
           (q["kind"]!="all"&&row["kind"]!=q["kind"]))return false;
        for(const auto& provider:row["providers"])
            if(!provider.is_object()||!resource::Hash(provider,"resource_sha256")||!resource::Hash(provider,"package_sha256")||
               !provider.contains("package_name")||!provider["package_name"].is_string()||provider["package_name"].get<std::string>().size()>1024)return false;
    }
    return true;
}
}
