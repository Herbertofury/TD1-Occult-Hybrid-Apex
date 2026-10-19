#pragma once
#include "ApexCasOwnerGraph.h"

namespace td1::nativecas::engine {
struct PairAction {
    std::uint64_t sim,generation;
    std::string request,source,target;
    bool copy,enabled;
};
inline PairAction ParsePairAction(const std::string& text) {
    if(text.size()>512)throw std::runtime_error("Pair action exceeds its bound.");
    std::vector<std::string> parts;std::size_t start=0;
    for(;;) {
        const auto end=text.find('|',start);parts.push_back(text.substr(start,end-start));
        if(end==std::string::npos)break;start=end+1;
    }
    if(parts.size()!=7 || parts[0].size()!=32 ||
       parts[0].find_first_not_of("0123456789abcdef")!=std::string::npos ||
       !FormOwnerId(parts[3]) || !FormOwnerId(parts[4]) || parts[3]==parts[4] ||
       (parts[5]!="copy"&&parts[5]!="link") || (parts[6]!="0"&&parts[6]!="1") ||
       (parts[5]=="copy"&&parts[6]!="0"))throw std::runtime_error("Untyped pair action.");
    return {SimId(ui::Json(parts[1])),SimId(ui::Json(parts[2])),parts[0],parts[3],parts[4],parts[5]=="copy",parts[6]=="1"};
}
}
