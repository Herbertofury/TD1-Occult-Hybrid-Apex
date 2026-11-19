// Bounded, read-only instruction/reference analysis. No process handles or writes.
#pragma once
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include <set>
#include <deque>
#include <algorithm>
extern "C" {
#include "../third_party/minhook/src/hde/hde64.h"
}

namespace td1::nativecas {
struct DirectEdge {std::uint32_t instruction,target;bool call;};
inline std::vector<DirectEdge> CodeEdges(const std::string& bytes,std::uint32_t rva) {
    if(bytes.empty() || bytes.size()>4096 || bytes.size()>UINT32_MAX-rva)
        throw std::runtime_error("Native instruction graph exceeds its bounded context.");
    std::deque<std::uint32_t> pending{rva};std::set<std::uint32_t> seen;
    std::vector<DirectEdge> result;
    while(!pending.empty() && seen.size()<2048) {
        auto at=pending.front();pending.pop_front();
        while(at>=rva && at-rva<bytes.size() && seen.insert(at).second && seen.size()<=2048) {
            const auto offset=at-rva;
            const auto remaining=bytes.size()-offset;
            unsigned char padded[32]={};std::memcpy(padded,bytes.data()+offset,std::min<std::size_t>(remaining,sizeof(padded)));
            hde64s op{};hde64_disasm(padded,&op);
            if(!op.len || op.len>remaining || (op.flags&F_ERROR)) break;
            const bool call=op.opcode==0xe8;
            const bool jump=op.opcode==0xe9 || op.opcode==0xeb;
            const bool conditional=(op.opcode>=0x70 && op.opcode<=0x7f) ||
                (op.opcode==0x0f && op.opcode2>=0x80 && op.opcode2<=0x8f) ||
                (op.opcode>=0xe0 && op.opcode<=0xe3);
            if(call || jump || conditional) {
                const auto delta=(op.flags&F_IMM8)?static_cast<std::int64_t>(static_cast<std::int8_t>(op.imm.imm8)):
                    static_cast<std::int64_t>(static_cast<std::int32_t>(op.imm.imm32));
                const auto dest=static_cast<std::int64_t>(at)+op.len+delta;
                if(dest>=0 && dest<=UINT32_MAX) {
                    const auto target=static_cast<std::uint32_t>(dest);
                    if((call || jump) && result.size()<32) result.push_back({at,target,call});
                    if(!call && target>=rva && target-rva<bytes.size()) pending.push_back(target);
                }
            }
            // An indirect dispatch has no statically verified destination.
            if(jump || op.opcode==0xc3 || op.opcode==0xc2 || op.opcode==0xcb || op.opcode==0xca ||
                op.opcode==0xcc || (op.opcode==0xff && (op.modrm_reg==4 || op.modrm_reg==5))) break;
            at+=op.len;
        }
    }
    return result;
}
inline std::uint32_t SectionPointer(std::uint64_t pointer, std::uint64_t base,
        std::uint32_t sectionRva, std::size_t sectionSize, std::size_t count) {
    if (!sectionSize || !count || count>sectionSize || base>UINT64_MAX-sectionRva ||
        sectionSize>UINT64_MAX-(base+sectionRva) || pointer<base+sectionRva ||
        pointer-(base+sectionRva)>sectionSize-count)
        throw std::runtime_error("Native controller pointer left its pinned section.");
    const auto offset=pointer-base;
    if(offset>UINT32_MAX) throw std::runtime_error("Native controller RVA exceeds the pinned image.");
    return static_cast<std::uint32_t>(offset);
}
inline std::uint32_t RipLoadTarget(const std::string& code, std::uint32_t codeRva,
        std::uint32_t instructionRva) {
    if(instructionRva<codeRva || instructionRva-codeRva>code.size() ||
        code.size()-(instructionRva-codeRva)<7)
        throw std::runtime_error("Native controller reference is truncated.");
    const auto* p=reinterpret_cast<const unsigned char*>(code.data()+instructionRva-codeRva);
    if(p[0]!=0x48 || p[1]!=0x8b || (p[2]&0xc7)!=5)
        throw std::runtime_error("Native controller reference is not the inspected RIP load.");
    std::int32_t delta=0;std::memcpy(&delta,p+3,4);
    const auto target=static_cast<std::int64_t>(instructionRva)+7+delta;
    if(target<0 || target>UINT32_MAX) throw std::runtime_error("Native controller reference overflows its image.");
    return static_cast<std::uint32_t>(target);
}
inline void Bounds(std::uint32_t rva, std::size_t size, std::uint32_t imageSize) {
    if (!imageSize || imageSize > 128u*1024u*1024u || !size || size > 64u*1024u*1024u ||
        rva >= imageSize || size > imageSize-rva) throw std::runtime_error("Unsupported bounded image span.");
}
inline std::vector<std::uint32_t> StringRvas(const std::string& bytes, std::uint32_t rva,
        std::uint32_t imageSize, const std::string& name) {
    Bounds(rva,bytes.size(),imageSize);
    if (name.empty() || name.size()>64 || name.find('\0')!=std::string::npos)
        throw std::runtime_error("Unsupported fixed service name.");
    std::vector<std::uint32_t> result;
    const auto needle=name+std::string(1,'\0');
    for(std::size_t offset=0;(offset=bytes.find(needle,offset))!=std::string::npos;++offset) {
        if(result.size()==16) throw std::runtime_error("Ambiguous native service string inventory.");
        result.push_back(rva+static_cast<std::uint32_t>(offset));
    }
    return result;
}
inline std::vector<std::uint32_t> RipLeas(const std::string& bytes, std::uint32_t rva,
        std::uint32_t imageSize, std::uint32_t target) {
    Bounds(rva,bytes.size(),imageSize);
    if(target>=imageSize) throw std::runtime_error("Reference target is outside the exact image.");
    std::vector<std::uint32_t> result;
    for(std::size_t i=0;i+7<=bytes.size();++i) {
        const auto* p=reinterpret_cast<const unsigned char*>(bytes.data()+i);
        if((p[0]!=0x48 && p[0]!=0x4c) || p[1]!=0x8d || (p[2]&0xc7)!=5) continue;
        std::int32_t displacement=0;std::memcpy(&displacement,p+3,sizeof(displacement));
        const auto destination=static_cast<std::int64_t>(rva)+static_cast<std::int64_t>(i)+7+displacement;
        if(destination==target) {
            if(result.size()==64) throw std::runtime_error("Native reference inventory exceeds its bound.");
            result.push_back(rva+static_cast<std::uint32_t>(i));
        }
    }
    return result;
}
inline std::vector<std::uint32_t> Pointers(const std::string& bytes,std::uint32_t rva,
        std::uint32_t imageSize,std::uint64_t base,std::uint32_t target) {
    Bounds(rva,bytes.size(),imageSize);
    if(target>=imageSize || base>UINT64_MAX-imageSize) throw std::runtime_error("Invalid exact image pointer.");
    std::vector<std::uint32_t> result;
    const auto expected=base+target;
    for(std::size_t i=0;i+8<=bytes.size();++i) {
        std::uint64_t observed=0;std::memcpy(&observed,bytes.data()+i,sizeof(observed));
        if(observed==expected) {
            if(result.size()==32) throw std::runtime_error("Native pointer inventory exceeds its bound.");
            result.push_back(rva+static_cast<std::uint32_t>(i));
        }
    }
    return result;
}
inline std::string CodeWindow(const std::string& code,std::uint32_t codeRva,std::uint32_t address) {
    if(address<codeRva || address-codeRva>=code.size()) throw std::runtime_error("Code reference left its section.");
    const auto center=static_cast<std::size_t>(address-codeRva);
    const auto start=center<16?0:center-16;
    const auto end=(center+48<code.size()?center+48:code.size());
    static const char hex[]="0123456789abcdef";std::string result;
    for(std::size_t i=start;i<end;++i) {
        const auto value=static_cast<unsigned char>(code[i]);result.push_back(hex[value>>4]);result.push_back(hex[value&15]);
    }
    return result;
}
inline std::uint32_t RegisteredCallback(const std::string& code,std::uint32_t codeRva,
        std::uint32_t imageSize,std::uint32_t reference,std::uint32_t registration) {
    Bounds(codeRva,code.size(),imageSize);
    if(reference<codeRva || reference-codeRva<10 || reference-codeRva>code.size() ||
       code.size()-(reference-codeRva)<16) return 0;
    const auto at=static_cast<std::size_t>(reference-codeRva);
    const auto* p=reinterpret_cast<const unsigned char*>(code.data()+at);
    // Observed Win64 service registration: zero R9, callback in R8, literal
    // service name in RDX, registry in RCX, then the pinned registration call.
    static const unsigned char prefix[]={0x45,0x33,0xc9,0x4c,0x8d,0x05};
    if(std::memcmp(p-10,prefix,sizeof(prefix)) || p[0]!=0x48 || p[1]!=0x8d || p[2]!=0x15 ||
       (p[7]!=0x48 && p[7]!=0x49) || p[8]!=0x8d || p[9]!=0x4f || p[11]!=0xe8) return 0;
    std::int32_t callbackDelta=0,callDelta=0;
    std::memcpy(&callbackDelta,p-4,4);std::memcpy(&callDelta,p+12,4);
    if(static_cast<std::int64_t>(reference)+16+callDelta!=registration) return 0;
    const auto callback=static_cast<std::int64_t>(reference)+callbackDelta;
    if(callback<codeRva || callback>=static_cast<std::int64_t>(codeRva)+code.size()) return 0;
    return static_cast<std::uint32_t>(callback);
}
inline std::string HexBytes(const std::string& bytes) {
    static const char hex[]="0123456789abcdef";std::string result;result.reserve(bytes.size()*2);
    for(const auto raw:bytes) {const auto c=static_cast<unsigned char>(raw);result.push_back(hex[c>>4]);result.push_back(hex[c&15]);}
    return result;
}
}
