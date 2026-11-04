#pragma once
#include <cstdint>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace td1::nativecas::menu {
struct Owner {std::uint32_t kind=0,token=0;};
struct Prepared {std::vector<std::string> pages;std::map<std::uint32_t,std::string> byOffset;std::size_t count=0;};
inline std::vector<std::string> Split(const std::string& value,char delimiter) {
    std::vector<std::string> result;std::size_t at=0;
    for(;;){const auto end=value.find(delimiter,at);result.push_back(value.substr(at,end-at));if(end==std::string::npos)break;at=end+1;}
    return result;
}
inline std::uint32_t Number(const std::string& text) {
    if(text.empty()||text.size()>10||(text.size()>1&&text[0]=='0'))throw std::runtime_error("Noncanonical menu number.");
    std::uint64_t value=0;
    for(const auto c:text){if(c<'0'||c>'9')throw std::runtime_error("Untyped menu number.");value=value*10+static_cast<unsigned>(c-'0');if(value>UINT32_MAX)throw std::runtime_error("Menu number overflow.");}
    return static_cast<std::uint32_t>(value);
}
inline bool Id(const std::string& value,bool slash) {
    if(value.empty()||value.size()>(slash?129u:64u))return false;
    unsigned separators=0;std::size_t segment=0;
    for(const auto c:value){if(c=='/'&&slash){if(!segment||segment>64)return false;segment=0;++separators;continue;}
        if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||(c=='-'&&segment)))return false;++segment;}
    return segment&&segment<=64&&separators==(slash?1u:0u);
}
inline bool Icon(const std::string& text) {
    if(text.empty())return true;
    if(text.size()>20||text[0]=='0')return false;std::uint64_t value=0;
    for(const auto c:text){if(c<'0'||c>'9')return false;const auto digit=static_cast<unsigned>(c-'0');
        if(value>(UINT64_MAX-digit)/10)return false;value=value*10+digit;}
    return value!=0;
}
inline bool Escaped(const std::string& text) {
    auto hex=[](char c){return(c>='0'&&c<='9')||(c>='A'&&c<='F')||(c>='a'&&c<='f');};
    for(std::size_t n=0;n<text.size();++n)if(text[n]=='%'){
        if(n+2>=text.size()||!hex(text[n+1])||!hex(text[n+2]))return false;n+=2;
    }
    return true;
}
inline Prepared Validate(const std::vector<std::string>& pages,const std::map<std::string,Owner>& owners,
                         const std::map<std::uint32_t,std::string>& logical,const std::string& human) {
    if(pages.empty()||pages.size()>64||owners.empty()||!owners.count(human)||!logical.count(1)||logical.at(1)!=human)
        throw std::runtime_error("Prepared menu lacks its exact owner scope.");
    Prepared result;std::set<std::string> seen;std::uint32_t total=0;std::size_t bytes=0;unsigned humans=0;
    const std::map<std::uint32_t,std::string> primary={{1,"human/shared"},{2,"alien/alien"},{4,"vampire/dark"},
        {8,"mermaid/mermaid"},{16,"witch/primary"},{32,"werewolf/beast"},{64,"fairy/primary"}};
    for(const auto& page:pages) {
        bytes+=page.size();if(page.empty()||page.size()>131072||bytes>2u*1024u*1024u)throw std::runtime_error("Prepared menu exceeds its bounds.");
        for(const auto c:page)if(static_cast<unsigned char>(c)<32||static_cast<unsigned char>(c)>126)throw std::runtime_error("Prepared menu must be escaped ASCII.");
        const auto header=Split(page,'|');
        if(header.size()!=4||header[0]!="OWNERS"||Number(header[1])!=seen.size())throw std::runtime_error("Prepared menu page order differs.");
        result.byOffset.emplace(Number(header[1]),page);
        const auto count=Number(header[2]);if(!count||count>2048||(total&&total!=count))throw std::runtime_error("Prepared menu total differs.");total=count;
        const auto rows=Split(header[3],';');if(rows.empty()||rows.size()>32||seen.size()+rows.size()>total)throw std::runtime_error("Prepared menu page is incomplete.");
        for(const auto& row:rows) {
            const auto fields=Split(row,',');
            if(fields.size()!=10||!Id(fields[0],true)||!Id(fields[3],true)||!Id(fields[5],false)||fields[4].empty()||fields[4].size()>1024||
               fields[8].empty()||fields[8].size()>4096||fields[9].empty()||fields[9].size()>1024||!Icon(fields[6])||!Icon(fields[7])||
               !Escaped(fields[4])||!Escaped(fields[8])||!Escaped(fields[9]))
                throw std::runtime_error("Prepared menu descriptor differs.");
            const auto found=owners.find(fields[0]);const auto kind=Number(fields[1]),token=Number(fields[2]);
            if(found==owners.end()||kind!=found->second.kind||token!=found->second.token||!seen.insert(fields[0]).second)
                throw std::runtime_error("Prepared menu contains a foreign, duplicate or retagged owner.");
            if(fields[3].substr(0,fields[3].find('/'))!=fields[5])throw std::runtime_error("Prepared menu family differs.");
            if(fields[0]==human){if(fields[3]!="human/shared"||kind!=1)throw std::runtime_error("Shared Human display differs.");++humans;}
            else if(fields[5]=="human"||fields[0].rfind("human/",0)==0)throw std::runtime_error("Prepared menu duplicates Human.");
            if(fields[0].rfind("native/",0)==0||fields[0].rfind("active/",0)==0) {
                if(!logical.count(kind)||logical.at(kind)!=fields[0]||!primary.count(kind)||primary.at(kind)!=fields[3])
                    throw std::runtime_error("Prepared menu exposes a backup native alias.");
            }
            else if(logical.count(kind)&&logical.at(kind)==fields[0]) {
                if(!primary.count(kind)||primary.at(kind)!=fields[3])throw std::runtime_error("Logical form presentation differs.");
            }
            else if(fields[3]!=fields[0])throw std::runtime_error("Named form identity differs.");
        }
    }
    if(seen.size()!=total||humans!=1)throw std::runtime_error("Prepared menu omits owners or duplicates Human.");
    for(const auto& row:logical)if(!seen.count(row.second))throw std::runtime_error("Prepared menu omits a logical native form.");
    result.pages=pages;result.count=seen.size();return result;
}
}
