#include "ApexHttpResponseFrame.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using td1::http::ResponseFrame;
using td1::http::ResponseProgress;
static void Check(bool ok,const char* message) {if(!ok)throw std::runtime_error(message);}
static std::string Wire(const std::string& body) {
    return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "+std::to_string(body.size())+"\r\nConnection: close\r\n\r\n"+body;
}
static void Reject(const std::string& wire,std::size_t limit=4096) {
    ResponseFrame frame(limit); Check(frame.Observe(wire)==ResponseProgress::Rejected,"Invalid response framing accepted");
}

int main() {
    try {
        const std::string payload="{\"request_id\":\"0123456789abcdef0123456789abcdef\",\"ok\":true}";
        const auto wire=Wire(payload);
        {
            ResponseFrame frame(4096); std::string received;
            for(std::size_t i=0;i<wire.size();++i) {
                received.push_back(wire[i]);
                const auto progress=frame.Observe(received);
                Check(progress==(i+1==wire.size()?ResponseProgress::Complete:ResponseProgress::NeedMore),"Fragmented response extent differs");
            }
            Check(received.substr(frame.BodyOffset(),frame.BodySize())==payload,"Body extent changed bytes");
            Check(frame.Observe(received)==ResponseProgress::Complete,"Complete response required EOF");
        }
        {
            // This peer supplies a complete body and stays open. Asking for
            // another read, instead of accepting Content-Length, is a fault.
            ResponseFrame frame(4096); std::string received;unsigned reads=0;
            auto recv=[&] {if(++reads>1)throw std::runtime_error("Client waited for peer close after complete body");return wire;};
            for(;;) {received+=recv();const auto progress=frame.Observe(received);
                Check(progress!=ResponseProgress::Rejected,"Valid complete response rejected");
                if(progress==ResponseProgress::Complete)break;}
            Check(reads==1,"Complete response performed an extra socket read");
        }
        {
            for(std::size_t size=0;size<wire.size();++size) {
                ResponseFrame frame(4096);const auto prefix=wire.substr(0,size);
                Check(frame.EndOfStream(prefix)==ResponseProgress::Rejected,"Early EOF accepted a truncated response");
            }
            ResponseFrame frame(4096);Check(frame.EndOfStream(wire)==ResponseProgress::Complete,"Exact complete EOF rejected");
        }
        {
            Reject(wire+"extra");
            ResponseFrame frame(4096);Check(frame.Observe(wire)==ResponseProgress::Complete,"Valid response rejected");
            Check(frame.Observe(wire+"x")==ResponseProgress::Rejected,"Later supplied surplus bytes accepted");
            ResponseFrame exact(payload.size());Check(exact.Observe(wire)==ResponseProgress::Complete,"Exact body limit rejected");
            Reject(wire,payload.size()-1);
        }
        for(const auto& length:std::vector<std::string>{"", "-2", "+2", "2, 2", "2x", "2 0", "18446744073709551616", "99999999999999999999999999999999999999"})
            Reject("HTTP/1.1 200 OK\r\nContent-Length: "+length+"\r\n\r\n{}");
        for(const auto& headers:std::vector<std::string>{
                "Content-Length: 2\r\nContent-Length: 2", "Content-Length: 2\r\ncontent-length: 3",
                "Content-Length: 2\r\nTransfer-Encoding: chunked", "Transfer-Encoding: chunked", "Other: value",
                "Content-Length: 2\r\n Content-Length: 2", "Content-Length : 2", "Content-Length 2"})
            Reject("HTTP/1.1 200 OK\r\n"+headers+"\r\n\r\n{}");
        for(const auto& status:std::vector<std::string>{"HTTP/1.0 200 OK", "HTTP/1.1 201 Created", "HTTP/1.1 500 Error", "HTTP/1.1 200", "HTTP/1.1 200\tOK", "HTTP/1.1 200 O\nK"})
            Reject(status+"\r\nContent-Length: 2\r\n\r\n{}");
        {
            ResponseFrame frame(4096);Check(frame.Observe("HTTP/1.1 200 OK\r\ncOnTeNt-LeNgTh:\t2 \t\r\n\r\n{}")==ResponseProgress::Complete,"Valid case-insensitive field/OWS rejected");
            ResponseFrame shortHeader(4096,24);Check(shortHeader.Observe("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")==ResponseProgress::Rejected,"Header extent exceeded its bound");
            ResponseFrame unfinished(4096,24);Check(unfinished.Observe(std::string(25,'x'))==ResponseProgress::Rejected,"Unterminated header exceeded bound");
            Reject("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nOther: "+std::string(1,'\0')+"\r\n\r\n{}");
        }
        std::cout<<"PASS owner HTTP response framing: fragmented/complete-without-EOF, truncation, bounds and ambiguous framing\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
