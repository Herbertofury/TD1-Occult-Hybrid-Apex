#pragma once
#include "ApexTrayView.h"
namespace td1::tray {
inline bool Text(const ui::Json& row,const char* name,size_t bound) {
    const auto it=row.find(name);return it!=row.end()&&it->is_string()&&it->get_ref<const std::string&>().size()<=bound;
}
inline bool Query(const ui::Json& q) {
    return q.is_object()&&q.size()==4&&q.contains("text")&&q["text"].is_string()&&q["text"].get<std::string>().size()<=800&&
        q.contains("kind")&&(q["kind"]=="all"||q["kind"]=="household"||q["kind"]=="lot"||q["kind"]=="room")&&
        q.contains("offset")&&ui::CasInt(q["offset"],0,100000)&&q.contains("limit")&&ui::CasInt(q["limit"],1,60);
}
inline bool Selection(const ui::Json& q,bool image=false) {
    if(!q.is_object()||!resource::Hash(q,"item_id")||!resource::Hash(q,"library_sha256"))return false;
    if(image)return q.size()==3&&q.contains("image_index")&&ui::CasInt(q["image_index"],0,255);
    if(q.size()==2)return true;
    if(q.size()!=3||!q.contains("context")||!q["context"].is_object()||q["context"].size()!=2)return false;
    const auto& c=q["context"];return c.contains("runtime_pid")&&ui::CasInt(c["runtime_pid"],1,0xffffffffLL)&&
        c.contains("history_lane")&&c["history_lane"].is_string()&&c["history_lane"].get<std::string>().size()<=256;
}
inline bool Page(const ui::Json& p,const ui::Json& q) {
    if(!Query(q)||!p.is_object()||!p.value("ok",false)||!resource::Hash(p,"library_sha256")||p.value("query",ui::Json())!=q||
        p.value("game_contacted",ui::Json())!=false||p.value("source_files_written",ui::Json())!=false||
        !p.contains("items")||!p["items"].is_array()||p["items"].size()>q["limit"].get<size_t>()||
        !p.contains("total")||!ui::CasInt(p["total"],0,100000)||p.value("offset",ui::Json())!=q["offset"]||
        !p.contains("next_offset")||!(p["next_offset"].is_null()||p["next_offset"]==q["offset"].get<size_t>()+p["items"].size()&&p["next_offset"]<p["total"]))return false;
    std::set<std::string> seen;
    for(const auto& row:p["items"])if(!row.is_object()||!resource::Hash(row,"item_id")||!seen.insert(ui::Scalar(row,"item_id")).second||
        !Text(row,"name",1024)||!Text(row,"creator",1024)||!Text(row,"description",32768)||
        !row.contains("sim_count")||!ui::CasInt(row["sim_count"],0,128)||!row.contains("image_count")||!ui::CasInt(row["image_count"],0,256)||
        !(row.value("kind",ui::Json())=="household"||row.value("kind",ui::Json())=="lot"||row.value("kind",ui::Json())=="room"||row.value("kind",ui::Json())=="unknown"))return false;
    return p.dump().size()<=512*1024;
}
inline std::string Decode64(const std::string& input) {
    if(input.empty()||input.size()>8*1024*1024||input.size()%4)throw std::runtime_error("Bounded base64 image required.");
    static const std::string chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string result;unsigned value=0,bits=0;
    for(char c:input){if(c=='=')break;const auto n=chars.find(c);if(n==std::string::npos)throw std::runtime_error("Invalid image encoding.");value=(value<<6)|unsigned(n);bits+=6;if(bits>=8){bits-=8;result.push_back(char((value>>bits)&255));}}
    if(Base64(result)!=input)throw std::runtime_error("Noncanonical image encoding.");return result;
}
}
