#pragma once
#include <cstddef>
#include <string_view>

namespace td1::http {
enum class ResponseProgress { NeedMore, Complete, Rejected };

// Strict framing for the existing one-response, HTTP/1.1 200 owner client.
// The caller owns the append-only byte buffer. Completion is determined by the
// declared body extent, never by when the peer's Python thread closes TCP.
class ResponseFrame {
    std::size_t bodyLimit_, headerLimit_, searchStart_=0, observedSize_=0;
    std::size_t bodyOffset_=0, bodySize_=0;
    bool headerParsed_=false, rejected_=false;

    static bool EqualAscii(std::string_view left, std::string_view right) noexcept {
        if(left.size()!=right.size()) return false;
        for(std::size_t i=0;i<left.size();++i) {
            const auto lower=[](char value) { return value>='A'&&value<='Z' ? char(value+'a'-'A') : value; };
            if(lower(left[i])!=lower(right[i])) return false;
        }
        return true;
    }
    static bool Token(char value) noexcept {
        return (value>='a'&&value<='z') || (value>='A'&&value<='Z') ||
            (value>='0'&&value<='9') || std::string_view("!#$%&'*+-.^_`|~").find(value)!=std::string_view::npos;
    }
    ResponseProgress Reject() noexcept { rejected_=true; return ResponseProgress::Rejected; }
public:
    explicit ResponseFrame(std::size_t bodyLimit, std::size_t headerLimit=16384) noexcept
        : bodyLimit_(bodyLimit), headerLimit_(headerLimit) {}

    ResponseProgress Observe(std::string_view bytes) noexcept {
        if(rejected_ || bytes.size()<observedSize_) return Reject();
        observedSize_=bytes.size();
        // Subtraction also avoids overflow when validating an external limit.
        if(bytes.size()>headerLimit_ && bytes.size()-headerLimit_>bodyLimit_) return Reject();
        if(!headerParsed_) {
            const auto end=bytes.find("\r\n\r\n",searchStart_);
            if(end==std::string_view::npos) {
                searchStart_=bytes.size()>3 ? bytes.size()-3 : 0;
                return bytes.size()>headerLimit_ ? Reject() : ResponseProgress::NeedMore;
            }
            if(end>headerLimit_ || headerLimit_-end<4) return Reject();
            const auto statusEnd=bytes.find("\r\n");
            if(statusEnd==std::string_view::npos || statusEnd>end) return Reject();
            const auto status=bytes.substr(0,statusEnd);
            if(status.size()<13 || status.substr(0,13)!="HTTP/1.1 200 ") return Reject();
            for(const unsigned char value:status) if(value<32 || value==127) return Reject();
            bool lengthSeen=false;
            std::size_t position=statusEnd+2;
            while(position<end) {
                auto lineEnd=bytes.find("\r\n",position);
                if(lineEnd==std::string_view::npos || lineEnd>end) lineEnd=end;
                const auto line=bytes.substr(position,lineEnd-position);
                const auto colon=line.find(':');
                if(colon==std::string_view::npos || colon==0) return Reject();
                const auto name=line.substr(0,colon);
                for(const auto value:name) if(!Token(value)) return Reject();
                auto value=line.substr(colon+1);
                for(const unsigned char byte:value) if((byte<32 && byte!='\t') || byte==127) return Reject();
                if(EqualAscii(name,"transfer-encoding")) return Reject();
                if(EqualAscii(name,"content-length")) {
                    if(lengthSeen) return Reject();
                    lengthSeen=true;
                    while(!value.empty() && (value.front()==' ' || value.front()=='\t')) value.remove_prefix(1);
                    while(!value.empty() && (value.back()==' ' || value.back()=='\t')) value.remove_suffix(1);
                    if(value.empty()) return Reject();
                    for(const auto digit:value) {
                        if(digit<'0' || digit>'9') return Reject();
                        const auto number=static_cast<std::size_t>(digit-'0');
                        if(number>bodyLimit_ || bodySize_>(bodyLimit_-number)/10) return Reject();
                        bodySize_=bodySize_*10+number;
                    }
                }
                position=lineEnd+2;
            }
            // The previous client required Content-Length after EOF as well.
            if(!lengthSeen) return Reject();
            bodyOffset_=end+4; headerParsed_=true;
        }
        const auto bodyBytes=bytes.size()-bodyOffset_;
        if(bodyBytes>bodySize_) return Reject();
        return bodyBytes==bodySize_ ? ResponseProgress::Complete : ResponseProgress::NeedMore;
    }
    ResponseProgress EndOfStream(std::string_view bytes) noexcept {
        const auto state=Observe(bytes);
        return state==ResponseProgress::Complete ? state : Reject();
    }
    std::size_t BodyOffset() const noexcept { return bodyOffset_; }
    std::size_t BodySize() const noexcept { return bodySize_; }
};
}
