// The stock exporter regenerates Human genetics and chooses the paired child's
// pelt. Project the exact CAS output, keeping every native root intact.
namespace householdroots {
namespace w=td1::nativecas::wire;
std::map<const void*,std::string*> attrs;
unsigned parses=0,mode=0;
std::string Number(unsigned field,unsigned value) {return w::Var(std::uint64_t(field)<<3)+w::Var(value);}
void* ConstructPacket(void* p) {std::memset(p,0,0x400);return p;}
void DestroyPacket(void* p) {protoExports.erase(p);}
void Export(const void* root,void* packet) {
    const auto id=Read<std::uint64_t>(root,0xb8);Write(packet,0x10,id);
    const auto at=attrs.find(root);const auto attributes=at==attrs.end()?std::string():*at->second;
    auto raw=w::Var(9)+std::string(reinterpret_cast<const char*>(&id),8)+
        w::Bytes(12,std::string(static_cast<const char*>(root)+0xd0,0x300))+
        w::Bytes(28,"genome "+std::to_string(Read<unsigned>(root,0xe8)))+
        w::Bytes(30,attributes)+Number(8,777)+w::Bytes(501,"unknown root data");
    if(at==attrs.end() && Read<unsigned>(root,0xd8)==32)raw+=w::Bytes(63,"independent Werewolf pelt");
    protoExports[packet]=std::move(raw);
}
bool Parse(void* packet,const ByteView* input) {
    ++parses;
    if((mode==1 && parses==1) || (mode==2 && parses==2))return false;
    const std::string raw(static_cast<const char*>(input->data),static_cast<std::size_t>(input->length));
    Write(packet,0x10,w::Scalar(w::One(w::Fields(raw),1,1)));protoExports[packet]=raw;
    if(mode==3 && parses==2)protoExports[packet]+=Number(503,99);
    return true;
}
std::uint64_t Entity(void* p) {return Read<std::uint64_t>(p,0xa8);}
void* Clone(void* destination,const void* source) {
    std::memcpy(destination,source,0x830);
    const auto at=attrs.find(source);if(at!=attrs.end())attrs[destination]=at->second;else attrs.erase(destination);
    return destination;
}
void Release(void* value) {attrs.erase(value);std::memset(value,0,0x830);}
void* Next(const void* node) {return Read<void*>(node);}
void Exercise() {
    auto& state=Runtime();const auto api=state.api;const auto oldRoots=state.preparedRoots;
    const auto oldScope=state.preparedScope;auto* oldController=state.exportController;
    const auto acceptance=state.householdAcceptance;const bool accepting=state.acceptingHousehold;
    const auto oldCopies=state.householdCopies;const bool copiesEnabled=state.householdCopiesEnabled.load();
    const auto oldHousehold=state.preparedHouseholdId;const auto oldDispatch=state.householdDispatch;
    const auto firstView=state.bank.at(123).viewBound,secondView=state.bank.at(456).viewBound;
    auto firstActive=std::move(state.bank.at(123).active),secondActive=std::move(state.bank.at(456).active);
    state.api.protoConstruct=ConstructPacket;state.api.protoDestroy=DestroyPacket;
    state.api.protoParse=Parse;state.api.exportProto=Export;
    std::array<char,0x830> roots[2]{};std::string attributes[2],original[2];
    std::array<char,0x400> controller{};std::array<char,0x20> nodes[2]{};
    void* interfaces[]={reinterpret_cast<void*>(&Entity)};
    auto* sentinel=controller.data()+0x108;Write(sentinel,0,nodes[0].data());
    Write(nodes[0].data(),0,nodes[1].data());Write(nodes[1].data(),0,sentinel);
    std::map<std::pair<std::uint64_t,std::string>,std::string> graphBefore;
    for(unsigned n=0;n<2;++n) {
        const std::uint64_t id=n?456:123;auto& bank=state.bank.at(id);bank.viewBound=n==0;
        bank.active=std::make_unique<NativeOwner>(state.api,id);Current(bank.active->value,n?32:2);
        ::Construct(roots[n].data(),id);Current(roots[n].data(),n?32:2);Write(roots[n].data(),0xdc,127u);
        Write(roots[n].data(),0x10,interfaces);Write(nodes[n].data(),0x10,roots[n].data());
        std::string records;
        for(unsigned kind=1;kind<=64;kind<<=1)records+=w::Bytes(3,Number(1,kind)+w::Bytes(11,"wrong merged appearance")+
            w::Bytes(17,"wrong Human genome")+Number(18,kind+90));
        attributes[n]=w::Bytes(17,Number(1,126)+Number(2,n?32:2)+records)+w::Bytes(19,"gameplay and unknown attributes");
        attrs[roots[n].data()]=&attributes[n];
        NativePacket p(state.api);Export(roots[n].data(),p.data.data());original[n]=SerializeMessage(state.api,p.data.data());
        for(const auto& owner:bank.graph->owners())graphBefore[{id,owner.id}]=SerializeOwner(state.api,*bank.graph->appearance(owner.id),id);
    }
    const auto targets=EditorHouseholdRoots(state,controller.data());Require(targets.size()==2);
    Write(nodes[1].data(),0,nodes[0].data());Refuses([&]{EditorHouseholdRoots(state,controller.data());});Write(nodes[1].data(),0,sentinel);
    Write(nodes[1].data(),0x10,roots[0].data());Refuses([&]{EditorHouseholdRoots(state,controller.data());});Write(nodes[1].data(),0x10,roots[1].data());
    auto duplicate=targets;duplicate.push_back(targets[0]);Refuses([&]{CanonicalizeHouseholdRoots(state,duplicate);});
    auto foreign=targets;foreign[0].sim=999;Refuses([&]{CanonicalizeHouseholdRoots(state,foreign);});
    mode=1;parses=0;Refuses([&]{CanonicalizeHouseholdRoots(state,targets);});Require(state.preparedRoots.empty());
    for(unsigned testMode=0;testMode<4;++testMode) {
        mode=0;parses=0;CanonicalizeHouseholdRoots(state,targets);state.exportController=controller.data();
        state.acceptingHousehold=true;state.householdAcceptance={{"verified",false},{"native_accepted",false}};
        for(unsigned n=0;n<2;++n) {
            auto& bank=state.bank.at(n?456:123);NativePacket packet(state.api);Export(roots[n].data(),packet.data.data());
            mode=testMode;parses=0;ProjectHouseholdOutput(state,roots[n].data(),packet.data.data(),controller.data());
            const auto actual=SerializeMessage(state.api,packet.data.data());
            if(testMode)Require(w::Equivalent(original[n],actual) && bank.householdCanonical["original_output_restored"]==true);
            else {
                Require(bank.householdCanonical["verified"]==true && bank.householdCanonical["unselected_active_replaced"]==(n==1));
                std::map<std::uint32_t,std::string> owners;
                for(const auto& owner:bank.logicalOwners)owners.emplace(owner.first,SerializeOwner(state.api,*bank.graph->appearance(owner.second),n?456:123));
                Require(w::Equivalent(w::Household(original[n],n?456:123,127,owners,n?&owners.at(32):nullptr),actual));
                if(n)Require(w::One(w::Fields(actual),63,2).value=="independent Werewolf pelt");
            }
            mode=0;NativePacket rootAfter(state.api);Export(roots[n].data(),rootAfter.data.data());
            Require(w::Equivalent(original[n],SerializeMessage(state.api,rootAfter.data.data())));
        }
        for(const auto& member:state.bank)for(const auto& owner:member.second.graph->owners())
            Require(SerializeOwner(state.api,*member.second.graph->appearance(owner.id),member.first)==graphBefore.at({member.first,owner.id}));
    }
    mode=0;parses=0;CanonicalizeHouseholdRoots(state,targets);state.exportController=controller.data();
    NativePacket ordinary(state.api);Export(roots[0].data(),ordinary.data.data());
    state.acceptingHousehold=false;state.householdAcceptance={{"verified",false},{"native_accepted",false}};
    const auto parseCount=parses;
    ProjectHouseholdOutput(state,roots[0].data(),ordinary.data.data(),controller.data());Require(parses==parseCount && protoExports.at(ordinary.data.data())==original[0]);
    const auto beforeFault=state.householdOutputFaults;
    state.acceptingHousehold=true;ProjectHouseholdOutput(state,roots[0].data(),ordinary.data.data(),nullptr);
    Require(state.householdOutputFaults==beforeFault+1 && protoExports.at(ordinary.data.data())==original[0]);
    state.acceptingHousehold=false;state.householdAcceptance={{"verified",true},{"native_accepted",true}};
    ProjectHouseholdOutput(state,roots[0].data(),ordinary.data.data(),controller.data());Require(state.bank.at(123).householdCanonical["verified"]==true);
    Export(roots[0].data(),ordinary.data.data());state.preparedRoots.at(123).generation++;
    ProjectHouseholdOutput(state,roots[0].data(),ordinary.data.data(),controller.data());Require(protoExports.at(ordinary.data.data())==original[0]);
    state.preparedRoots.at(123).generation--;state.householdAcceptance={{"verified",true},{"native_accepted",true}};
    const auto unchangedFaults=state.householdOutputFaults;
    ProjectHouseholdOutput(state,state.bank.at(123).graph->appearance("native/1")->value,ordinary.data.data(),controller.data());
    Require(state.householdOutputFaults==unchangedFaults && protoExports.at(ordinary.data.data())==original[0]);
    // EA builds a separate outgoing household and deep-copies it through the
    // dispatch queue. Identity alone must never authorize one of those objects.
    CanonicalizeHouseholdRoots(state,targets);state.exportController=controller.data();
    state.householdCopiesEnabled.store(true);state.api.copySim=Clone;state.api.assignSim=Clone;state.api.destroy=Release;
    std::array<char,0x830> outgoing{},queued{},unrelated{};
    Clone(unrelated.data(),roots[0].data());state.acceptingHousehold=true;
    Export(unrelated.data(),ordinary.data.data());const auto untouched=protoExports.at(ordinary.data.data());
    ProjectHouseholdOutput(state,unrelated.data(),ordinary.data.data(),controller.data());
    Require(protoExports.at(ordinary.data.data())==untouched && state.householdCopies.empty());
    HouseholdCopyAssign(outgoing.data(),roots[0].data());Require(state.householdCopies.at(outgoing.data()).depth==1);
    state.acceptingHousehold=false;state.householdAcceptance={{"verified",true},{"native_accepted",true}};
    HouseholdCopyConstruct(queued.data(),outgoing.data());Require(state.householdCopies.at(queued.data()).depth==2);
    Export(queued.data(),ordinary.data.data());ProjectHouseholdOutput(state,queued.data(),ordinary.data.data(),controller.data());
    Require(state.bank.at(123).householdCanonical["verified"]==true && state.bank.at(123).householdCanonical["copy_depth"]==2);
    const auto projected=protoExports.at(ordinary.data.data());
    Require(!w::Equivalent(projected,untouched));
    HouseholdCopyAssign(queued.data(),unrelated.data());Require(!state.householdCopies.count(queued.data()));
    Export(queued.data(),ordinary.data.data());ProjectHouseholdOutput(state,queued.data(),ordinary.data.data(),controller.data());
    Require(w::Equivalent(protoExports.at(ordinary.data.data()),untouched));
    HouseholdCopyConstruct(queued.data(),outgoing.data());HouseholdCopyDestroy(queued.data());
    Require(!state.householdCopies.count(queued.data()));
    Clone(queued.data(),roots[0].data());Export(queued.data(),ordinary.data.data());
    ProjectHouseholdOutput(state,queued.data(),ordinary.data.data(),controller.data());Require(w::Equivalent(protoExports.at(ordinary.data.data()),untouched));
    state.householdAcceptance={{"verified",false},{"native_accepted",false}};
    HouseholdCopyConstruct(queued.data(),outgoing.data());Require(!state.householdCopies.count(queued.data()));
    state.acceptingHousehold=true;state.preparedRoots.at(123).generation++;
    HouseholdCopyConstruct(queued.data(),outgoing.data());Require(!state.householdCopies.count(queued.data()));
    state.preparedRoots.at(123).generation--;
    state.acceptingHousehold=false;state.householdAcceptance={{"verified",true},{"native_accepted",true}};
    HouseholdCopyConstruct(queued.data(),roots[0].data());Require(!state.householdCopies.count(queued.data()));
    // The accepted household is first copied from EA's stored household. Its
    // members can be unchanged/unselected and never copied from editor roots.
    // Seed only the complete, exact native CAS dispatch; identity alone fails.
    std::array<char,0x500> household{};std::array<char,0x860> treeNodes[2]{};
    Write(controller.data(),0xb0,std::uint64_t(777));state.preparedHouseholdId=777;state.api.treeNext=Next;
    Write(household.data(),0xc8,std::uint64_t(777));Write(household.data(),0xa8,2u);
    auto* treeSentinel=household.data()+0x88;Write(household.data(),0x90,treeNodes[0].data());
    Write(treeNodes[0].data(),0,treeNodes[1].data());Write(treeNodes[1].data(),0,treeSentinel);
    for(unsigned n=0;n<2;++n)Clone(treeNodes[n].data()+0x30,roots[n].data());
    state.householdCopies.clear();state.acceptingHousehold=true;
    SeedHouseholdDispatch(state,household.data(),controller.data());
    Require(state.householdDispatch["verified"]==true && state.householdDispatch["members"]==2 && state.householdCopies.size()==2);
    for(unsigned n=0;n<2;++n)Require(state.householdCopies.at(treeNodes[n].data()+0x30).dispatchOrigin);
    const auto seedCount=state.householdCopies.size();
    Write(household.data(),0xc8,std::uint64_t(778));Refuses([&]{SeedHouseholdDispatch(state,household.data(),controller.data());});Write(household.data(),0xc8,std::uint64_t(777));
    Write(treeNodes[1].data(),0,treeNodes[0].data());Refuses([&]{SeedHouseholdDispatch(state,household.data(),controller.data());});Write(treeNodes[1].data(),0,treeSentinel);
    Write(treeNodes[1].data()+0x30,0xb8,std::uint64_t(999));Refuses([&]{SeedHouseholdDispatch(state,household.data(),controller.data());});Write(treeNodes[1].data()+0x30,0xb8,std::uint64_t(456));
    Write(household.data(),0xa8,1u);Refuses([&]{SeedHouseholdDispatch(state,household.data(),controller.data());});Write(household.data(),0xa8,2u);
    Require(state.householdCopies.size()==seedCount); // Failed stages publish no partial authority.
    state.acceptingHousehold=false;state.householdAcceptance={{"verified",true},{"native_accepted",true}};
    Refuses([&]{SeedHouseholdDispatch(state,household.data(),controller.data());});
    HouseholdCopyConstruct(queued.data(),treeNodes[1].data()+0x30);
    Require(state.householdCopies.at(queued.data()).dispatchOrigin && state.householdCopies.at(queued.data()).depth==2);
    Export(queued.data(),ordinary.data.data());ProjectHouseholdOutput(state,queued.data(),ordinary.data.data(),controller.data());
    Require(state.bank.at(456).householdCanonical["verified"]==true && state.bank.at(456).householdCanonical["dispatch_origin"]==true);
    // Later successes cannot erase a prior native failure's diagnostic.
    const auto serial=state.householdOutputFaults;
    for(unsigned n=0;n<10;++n)HouseholdFault(state,"fixture","retained failure "+std::to_string(n),456);
    Require(state.householdFaults.size()==8 && state.householdFaults.front()["serial"]==serial+3 &&
        state.householdFaults.back()["serial"]==serial+10 && state.householdFaults.back()["sim_id"]=="456");
    state.householdAcceptance={{"verified",true},{"native_accepted",true}};
    state.acceptingHousehold=false;
    HouseholdCopyConstruct(queued.data(),treeNodes[0].data()+0x30);Require(state.householdCopies.at(queued.data()).dispatchOrigin);
    const auto faultsBeforeRetire=state.householdOutputFaults;
    ForgetHouseholdObject(state,roots[0].data());Release(roots[0].data());
    Require(state.preparedRoots.at(123).retired && state.householdCopies.count(queued.data())==1 &&
        state.householdOutputFaults==faultsBeforeRetire && state.householdDispatch["verified"]==true && state.householdAcceptance["verified"]==true);
    // The editor and its controller may disappear; the authenticated native
    // dispatch copy still owns its full data and final generation.
    Export(queued.data(),ordinary.data.data());ProjectHouseholdOutput(state,queued.data(),ordinary.data.data(),nullptr);
    Require(state.bank.at(123).householdCanonical["verified"]==true && state.bank.at(123).householdCanonical["dispatch_origin"]==true);
    HouseholdCopyConstruct(roots[0].data(),unrelated.data()); // Reused address, matching ID/entity, no provenance.
    Require(!state.householdCopies.count(roots[0].data()));
    Export(roots[0].data(),ordinary.data.data());const auto reused=protoExports.at(ordinary.data.data());
    ProjectHouseholdOutput(state,roots[0].data(),ordinary.data.data(),controller.data());Require(protoExports.at(ordinary.data.data())==reused);
    state.acceptingHousehold=true;HouseholdCopyConstruct(outgoing.data(),roots[0].data());
    Require(!state.householdCopies.count(outgoing.data()));state.acceptingHousehold=false;
    HouseholdCopyDestroy(treeNodes[0].data()+0x30);HouseholdCopyDestroy(treeNodes[1].data()+0x30);HouseholdCopyDestroy(queued.data());
    Require(state.householdCopies.empty() && !state.householdCopiesEnabled.load() && state.preparedRoots.at(456).retired &&
        state.householdAcceptance["verified"]==true && state.householdDispatch["verified"]==true);
    // Before an authenticated handoff, losing the source still blocks scope.
    Clone(treeNodes[1].data()+0x30,roots[1].data());CanonicalizeHouseholdRoots(state,targets);state.exportController=controller.data();
    ForgetHouseholdObject(state,roots[0].data());
    Require(state.preparedRoots.empty() && state.preparedScope.empty() && !state.exportController &&
        state.householdOutputFaults==faultsBeforeRetire+1 && state.householdAcceptance["verified"]==false);
    state.bank.at(123).active=std::move(firstActive);state.bank.at(456).active=std::move(secondActive);
    state.bank.at(123).viewBound=firstView;state.bank.at(456).viewBound=secondView;
    state.preparedRoots=oldRoots;state.preparedScope=oldScope;state.exportController=oldController;
    state.householdCopies=oldCopies;state.householdCopiesEnabled.store(copiesEnabled);
    state.preparedHouseholdId=oldHousehold;state.householdDispatch=oldDispatch;
    state.householdAcceptance=acceptance;state.acceptingHousehold=accepting;attrs.clear();state.api=api;
}
}
