// Bounded, read-only instruction/reference analysis. No process handles or writes.
#pragma once
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace td1::nativecas {
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
