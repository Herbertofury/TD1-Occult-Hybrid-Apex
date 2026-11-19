#pragma once
#include "ApexCasOwnerGraph.h"
#include "ApexCasSelectiveAppearance.h"

namespace td1::nativecas::engine {
struct PairAction {
    std::uint64_t sim,generation;
    std::string request,source,target;
    bool copy,enabled;
    std::uint32_t flags=UINT32_MAX;
};
enum class HumanCCFurMode { None, Remove, CopyWerewolf };
inline HumanCCFurMode HumanCCFurAction(const PairAction& action,const std::string& selected,const std::string& human) {
    if(action.flags==UINT32_MAX)return HumanCCFurMode::None;
    const bool target=action.copy && selected=="werewolf/werewolf_human_cc" && action.target==selected;
    if(target && action.source==human && action.flags==(selective::ClearFur|16u))return HumanCCFurMode::Remove;
    if(action.flags&selective::ClearFur)throw std::runtime_error("Fur removal requires the selected Human/CC Werewolf and its own shared Human skin.");
    if(target && action.source=="native/32" && action.flags==(selective::Fur|16u))return HumanCCFurMode::CopyWerewolf;
    return HumanCCFurMode::None;
}
template<class Graph,class Flush> void ApplyPairLink(Graph& graph,const PairAction& action,Flush flush) {
    const auto before=graph.cursor();
    if(action.copy || before.sim!=action.sim || before.generation!=action.generation)
        throw std::runtime_error("Link change lacks its exact current model generation.");
    // Finish pending edits through the OLD scope before changing that scope.
    // In particular unlink must not strand an edit that was made while linked.
    // Enabling a link also must not retroactively copy earlier unlinked edits.
    flush();
    const auto after=graph.cursor();
    if(after.sim!=before.sim || after.owner!=before.owner || after.kind!=before.kind)
        throw std::runtime_error("The selected owner changed during link synchronization.");
    graph.linkPairSelected(after,action.source,action.target,action.enabled,action.flags);
}
inline PairAction ParsePairAction(const std::string& text) {
    if(text.size()>512)throw std::runtime_error("Pair action exceeds its bound.");
    std::vector<std::string> parts;std::size_t start=0;
    for(;;) {
        const auto end=text.find('|',start);parts.push_back(text.substr(start,end-start));
        if(end==std::string::npos)break;start=end+1;
    }
    if((parts.size()!=7 && parts.size()!=8) || parts[0].size()!=32 ||
       parts[0].find_first_not_of("0123456789abcdef")!=std::string::npos ||
       !FormOwnerId(parts[3]) || !FormOwnerId(parts[4]) || parts[3]==parts[4] ||
       (parts[5]!="copy"&&parts[5]!="link") || (parts[6]!="0"&&parts[6]!="1") ||
       (parts[5]=="copy"&&parts[6]!="0"))throw std::runtime_error("Untyped pair action.");
    std::uint32_t flags=UINT32_MAX;
    if(parts.size()==8) {
        if(parts[7].empty() || parts[7].size()>10 || parts[7].find_first_not_of("0123456789")!=std::string::npos ||
           (parts[7].size()>1 && parts[7][0]=='0'))throw std::runtime_error("Untyped pair category flags.");
        const auto value=std::stoull(parts[7]);if(value>UINT32_MAX)throw std::runtime_error("Pair category flags overflow.");
        flags=static_cast<std::uint32_t>(value);
        if(!flags && (parts[5]=="copy" || parts[6]=="1"))throw std::runtime_error("Empty pair operation scope.");
    }
    return {SimId(ui::Json(parts[1])),SimId(ui::Json(parts[2])),parts[0],parts[3],parts[4],parts[5]=="copy",parts[6]=="1",flags};
}
}
