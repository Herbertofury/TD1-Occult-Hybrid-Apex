#pragma once
#include "ApexUiData.h"
#include "ApexResourceImage.h"
#include <set>

namespace td1::tray {
inline std::string DestinationSim(const ui::Json& selection) {
    const auto lane=ui::Scalar(selection,"history_lane");size_t start=0;
    for(int i=0;i<2;++i){const auto colon=lane.find(':',start);if(colon==std::string::npos)return {};start=colon+1;}
    const auto end=lane.find(':',start);if(end==std::string::npos)return {};
    const auto sim=lane.substr(start,end-start);return ui::ExactUint64Identity(ui::Json(sim))?sim:std::string();
}
inline std::string FormName(unsigned form) {
    switch(form){case 1:return "Human";case 2:return "Alien";case 4:return "Vampire";
    case 8:return "Mermaid";case 16:return "Spellcaster";case 32:return "Werewolf";case 64:return "Fairy";default:return "Unknown";}
}
// Source identity remains separate from the existing destination selection.
// The broker independently validates the raw native payload and field hashes.
inline bool Forms(const ui::Json& rows, unsigned pid, const std::string& saveGuid) {
    try {
        if(!rows.is_array()||rows.empty()||rows.size()>7)return false;
        std::set<unsigned> seen;std::string sim,nativeHash,source;
        for(const auto& row:rows){
            if(!row.is_object()||row.size()!=3||!row.contains("name")||!row["name"].is_string()||row["name"].get<std::string>().size()>1024)return false;
            const auto& r=row.at("request");const auto& outfits=row.at("outfits");
            if(!r.is_object()||!r.value("ok",false)||!ui::ExactUint64Identity(r.at("sim_id"))||!ui::CasInt(r.at("form"),1,64)||
               !resource::Hash(r,"native_sha256")||!resource::Hash(r,"appearance_sha256")||!resource::Hash(r,"render_sha256")||
               r.at("runtime_pid")!=pid||r.at("save_guid")!=saveGuid||r.at("preview_id")!=nullptr||
               r.at("save_file_written")!=false||r.at("history_written")!=false||!r.at("fields").is_object()||!r.at("native_sim").is_string())return false;
            const auto form=r["form"].get<unsigned>();if((form&(form-1))||!seen.insert(form).second)return false;
            const auto origin=ui::Scalar(r,"appearance_source");if(origin.rfind("tray:",0)!=0||!resource::Hex(origin.substr(5),64))return false;
            const auto id=ui::Scalar(r,"sim_id"), hash=ui::Scalar(r,"native_sha256");
            if(sim.empty()){sim=id;nativeHash=hash;source=origin;}else if(sim!=id||nativeHash!=hash||source!=origin)return false;
            if(ui::Scalar(r,"lane")!=saveGuid+":0:"+id+":"+std::to_string(form)+":tray-"+origin.substr(5)+":runtime-"+std::to_string(pid))return false;
            if(!outfits.is_array()||outfits.empty()||outfits.size()>1024)return false;
            for(size_t i=0;i<outfits.size();++i){const auto& o=outfits[i];
                if(o.size()!=4||o.at("index")!=i||!ui::CasInt(o.at("category"),0,0xffffffffULL)||!ui::CasInt(o.at("number"),1,1024)||
                   !(o.at("outfit_id")=="0"||ui::ExactUint64Identity(o.at("outfit_id"))))return false;
            }
        }
        return true;
    }catch(...){return false;}
}
inline ui::Json Request(const ui::Json& rows,int formIndex,int outfitIndex) {
    if(formIndex<0||formIndex>=int(rows.size()))throw std::runtime_error("Select an existing Tray appearance owner.");
    const auto& row=rows[size_t(formIndex)];const auto& outfits=row.at("outfits");
    if(outfitIndex<0||outfitIndex>=int(outfits.size()))throw std::runtime_error("Select an existing Tray outfit.");
    auto r=row.at("request");r["outfit_index"]=outfits[size_t(outfitIndex)]["index"];r["outfit_id"]=outfits[size_t(outfitIndex)]["outfit_id"];return r;
}
inline std::string Base64(const std::string& raw) {
    static constexpr char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;out.reserve((raw.size()+2)/3*4);
    for(size_t i=0;i<raw.size();i+=3){const auto a=static_cast<unsigned char>(raw[i]);const bool b=i+1<raw.size(),c=i+2<raw.size();
        const unsigned v=(unsigned(a)<<16)|(b?unsigned(static_cast<unsigned char>(raw[i+1]))<<8:0)|(c?unsigned(static_cast<unsigned char>(raw[i+2])):0);
        out+=alphabet[(v>>18)&63];out+=alphabet[(v>>12)&63];out+=b?alphabet[(v>>6)&63]:'=';out+=c?alphabet[v&63]:'=';
    }return out;
}
}
