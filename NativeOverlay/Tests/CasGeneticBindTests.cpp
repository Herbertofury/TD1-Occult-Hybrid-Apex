#include "ApexCasGeneticBind.h"
#include <iostream>
#include <stdexcept>
#include <array>
using namespace td1::nativecas::engine;
void Check(bool value) {if(!value)throw std::runtime_error("Captured-genetics view-bind regression");}
int main() {
    GeneticViewBinding c;
    c.enabled=c.ownerPresent=true;c.image=0x140000000;c.controller=0x100000;
    c.model=0x200000;c.group=c.boundGroup=0x300000;c.sim=c.groupSim=123;
    c.capturedKind=c.modelKind=1;
    const auto genetics=reinterpret_cast<void*>(c.model+0x320);
    const auto outfit=reinterpret_cast<void*>(c.model+0xe8);
    const auto caller=c.image+0x457559;
    // Actual failure: merely binding Human replaced its inherited hair 277692
    // with the already equipped 306960. No user hair edit was performed.
    std::array<unsigned,3> inherited{{277692,0xdeadbeef,0x76543210}};
    unsigned calls=0;
    const auto native=[&]{++calls;inherited[0]=306960;};
    if(!RetainViewGenetics(c,caller,genetics,outfit))native();
    Check(calls==0&&inherited==std::array<unsigned,3>{{277692,0xdeadbeef,0x76543210}});
    // Every captured genus uses this rule; it does not give another form
    // Human/Vampire identity or replace the supplied inheritance bytes.
    for(unsigned kind:{1u,2u,4u,8u,16u,32u,64u}) {
        auto view=c;view.capturedKind=view.modelKind=kind;
        Check(RetainViewGenetics(view,caller,genetics,outfit));
    }
    // A real hair/outfit edit outside binding must still run EA exactly once.
    auto noView=c;noView.enabled=false;
    if(!RetainViewGenetics(noView,caller,genetics,outfit))native();
    Check(calls==1&&inherited[0]==306960&&inherited[1]==0xdeadbeef);
    Check(!RetainViewGenetics(c,caller+1,genetics,outfit));
    Check(!RetainViewGenetics(c,caller,reinterpret_cast<void*>(c.model+0x328),outfit));
    Check(!RetainViewGenetics(c,caller,genetics,reinterpret_cast<void*>(c.model+0xf0)));
    for(unsigned caseId=0;caseId<7;++caseId) {
        auto bad=c;
        if(caseId==0)bad.ownerPresent=false;
        if(caseId==1)bad.fault=true;
        if(caseId==2)bad.groupSim++;
        if(caseId==3)bad.boundGroup++;
        if(caseId==4)bad.modelKind=4;
        if(caseId==5)bad.capturedKind=bad.modelKind=3;
        if(caseId==6)bad.model=0;
        Check(!RetainViewGenetics(bad,caller,genetics,outfit));
    }
    std::cout<<"Captured view genetics retained; actual edits and foreign scopes stay native.\n";
}
