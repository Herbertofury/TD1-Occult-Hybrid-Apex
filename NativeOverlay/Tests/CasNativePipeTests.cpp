#include "ApexCasNativePipeWin.h"
#include <iostream>
#include <functional>
using namespace td1::nativecas::pipe;
void Check(bool value){if(!value)throw std::runtime_error("Native CAS pipe contract failed.");}
void Refuses(const std::function<void()>& action){bool refused=false;try{action();}catch(const std::exception&){refused=true;}Check(refused);}
int main(){try {
    Check(FrameSize("00131072")==Limit);
    for(const auto header:{"00000000","00131073","-0000001","0000000x","0000001"})Refuses([&]{FrameSize(header);});
    ValidateFrame("00000004WAIT");
    for(const auto frame:{"00000004WAITextra","00000005WAIT","0000000xWAIT"})Refuses([&]{ValidateFrame(frame);});
    Refuses([]{ValidateFrame(std::string("00000001\0",9));});
    Mailbox box;box.generation=7;box.scope="captured-scope";box.stop=false;
    Check(box.Poll(7,box.scope)=="WAIT");box.connected=true;
    Check(box.Poll(7,box.scope)=="CONNECTED");Check(box.Poll(7,box.scope)=="WAIT");
    Check(box.Send(6,box.scope,"00000004WAIT")=="STALE");Check(box.outgoing.empty());
    Check(box.Send(7,"foreign-scope","00000004WAIT")=="STALE");Check(box.outgoing.empty());
    Check(box.Send(7,box.scope,"00000004WAIT")=="QUEUED");
    Check(box.Send(7,box.scope,"00000004WAIT")=="BUSY");
    // The worker moving bytes out does not release the one-frame lease.
    box.outgoing.clear();Check(box.Send(7,box.scope,"00000004WAIT")=="BUSY");
    box.incoming="00000004WAIT";
    Check(box.Poll(6,box.scope)=="STALE"&&!box.incoming.empty());
    Check(box.Poll(7,"foreign-scope")=="STALE"&&!box.incoming.empty());
    Check(box.Poll(7,box.scope)=="DATA|00000004WAIT");
    Check(box.incoming.empty()&&!box.inFlight);
    Check(box.Send(7,box.scope,"00000004WAIT")=="QUEUED");
    Check(box.Close(6,box.scope)=="STALE"&&!box.stop);
    Check(box.Close(7,box.scope)=="CLOSED"&&box.stop);
    Check(box.Poll(7,box.scope)=="CLOSED");Check(box.Send(7,box.scope,"00000004WAIT")=="CLOSED");
    std::cout<<"Native CAS pipe framing, ownership and one-frame leases passed\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
