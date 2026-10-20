// Exercises the real root preparation against independent native data and a
// parser-backed packet fixture. Other engine tests supply the API lifetime stubs.
namespace householdroots {
namespace w=td1::nativecas::wire;
std::map<const void*,std::string*> attrs;
std::map<const void*,std::string*> inlineAttrs;
std::map<const void*,std::unique_ptr<std::string>> packetAttrs;
unsigned parses=0,copies=0,mode=0;
std::string Number(unsigned field,unsigned value) {return w::Var(std::uint64_t(field)<<3)+w::Var(value);}
void* ConstructPacket(void* p) {
    std::memset(p,0,0x400);packetAttrs[p]=std::make_unique<std::string>();Write(p,0xc0,packetAttrs[p].get());return p;
}
void DestroyPacket(void* p) {protoExports.erase(p);packetAttrs.erase(p);}
void Export(const void* root,void* packet) {
    const auto id=Read<std::uint64_t>(root,0xb8);Write(packet,0x10,id);
    const auto at=attrs.find(root);const auto attributes=at==attrs.end()?std::string():*at->second;
    *packetAttrs.at(packet)=attributes;
    protoExports[packet]=w::Var(9)+std::string(reinterpret_cast<const char*>(&id),8)+
        w::Bytes(12,std::string(static_cast<const char*>(root)+0xd0,0x300))+
        w::Bytes(30,attributes)+Number(8,777)+w::Bytes(501,"unknown root data");
}
bool Parse(void* packet,const ByteView* input) {
    if(++parses==2 && mode==1)return false;
    const std::string raw(static_cast<const char*>(input->data),static_cast<std::size_t>(input->length));
    const auto fields=w::Fields(raw);Write(packet,0x10,w::Scalar(w::One(fields,1,1)));
    *packetAttrs.at(packet)=w::One(fields,30,2).value;protoExports[packet]=raw;return true;
}
void Copy(void* destination,const void* source) {
    // Requires the embedded object address, never its shared vtable pointer.
    ++copies;*inlineAttrs.at(destination)=*static_cast<const std::string*>(source);
    if(copies==2 && mode==2)throw std::runtime_error("Injected second-member attribute copy failure.");
    if(copies==1 && mode==3)*inlineAttrs.at(destination)+=Number(502,99);
}
std::uint64_t Entity(void* p) {return Read<std::uint64_t>(p,0xa8);}
void Exercise() {
    auto& state=Runtime();const auto api=state.api;
    const auto firstView=state.bank.at(123).viewBound,secondView=state.bank.at(456).viewBound;
    auto firstActive=std::move(state.bank.at(123).active),secondActive=std::move(state.bank.at(456).active);
    state.api.protoConstruct=ConstructPacket;state.api.protoDestroy=DestroyPacket;
    state.api.protoParse=Parse;state.api.exportProto=Export;state.api.assignAttributes=Copy;
    std::array<char,0x830> roots[2]{};std::string attributes[2],original[2];
    std::array<char,0x400> controller{};std::array<char,0x20> nodes[2]{};
    void* interfaces[]={reinterpret_cast<void*>(&Entity)};
    auto* sentinel=controller.data()+0x108;Write(sentinel,0,nodes[0].data());
    Write(nodes[0].data(),0,nodes[1].data());Write(nodes[1].data(),0,sentinel);
    std::map<std::pair<std::uint64_t,std::string>,std::string> graphBefore;
    for(unsigned n=0;n<2;++n) {
        const std::uint64_t id=n?456:123;auto& bank=state.bank.at(id);bank.viewBound=false;
        bank.active=std::make_unique<NativeOwner>(state.api,id);Current(bank.active->value,2);
        ::Construct(roots[n].data(),id);Current(roots[n].data(),2);Write(roots[n].data(),0xdc,127u);
        Write(roots[n].data(),0x10,interfaces);Write(nodes[n].data(),0x10,roots[n].data());
        std::string records;
        for(unsigned kind=1;kind<=64;kind<<=1)records+=w::Bytes(3,Number(1,kind)+w::Bytes(11,"wrong merged appearance")+Number(18,kind+90));
        attributes[n]=w::Bytes(17,Number(1,126)+Number(2,2)+records)+w::Bytes(19,"gameplay and unknown attributes");
        attrs[roots[n].data()]=&attributes[n];inlineAttrs[roots[n].data()+0x4c8]=&attributes[n];
        Write(roots[n].data(),0x4c8,interfaces); // Same vtable; distinct embedded attributes objects.
        NativePacket p(state.api);Export(roots[n].data(),p.data.data());original[n]=SerializeMessage(state.api,p.data.data());
        for(const auto& owner:bank.graph->owners())graphBefore[{id,owner.id}]=SerializeOwner(state.api,*bank.graph->appearance(owner.id),id);
    }
    const auto targets=EditorHouseholdRoots(state,controller.data());Require(targets.size()==2);
    Write(nodes[1].data(),0,nodes[0].data());Refuses([&]{EditorHouseholdRoots(state,controller.data());});Write(nodes[1].data(),0,sentinel);
    Write(nodes[1].data(),0x10,roots[0].data());Refuses([&]{EditorHouseholdRoots(state,controller.data());});Write(nodes[1].data(),0x10,roots[1].data());
    Write(roots[1].data(),0xb8,std::uint64_t(999));Refuses([&]{EditorHouseholdRoots(state,controller.data());});Write(roots[1].data(),0xb8,std::uint64_t(456));
    Require(Read<void*>(roots[0].data(),0x4c8)==Read<void*>(roots[1].data(),0x4c8));
    Require(roots[0].data()+0x4c8!=roots[1].data()+0x4c8);
    auto duplicate=targets;duplicate.push_back(targets[0]);Refuses([&]{CanonicalizeHouseholdRoots(state,duplicate);});
    auto foreign=targets;foreign[0].sim=999;Refuses([&]{CanonicalizeHouseholdRoots(state,foreign);});
    std::array<char,0x300> initialData[2];const auto initialAttrs=std::array<std::string,2>{attributes[0],attributes[1]};
    for(unsigned n=0;n<2;++n)std::memcpy(initialData[n].data(),roots[n].data()+0xd0,0x300);
    for(mode=0;mode<5;++mode) {
        state.bank.at(123).viewBound=mode==4;
        parses=copies=0;
        for(unsigned n=0;n<2;++n) {std::memcpy(roots[n].data()+0xd0,initialData[n].data(),0x300);attributes[n]=initialAttrs[n];}
        if(mode>0 && mode<4)Refuses([&]{CanonicalizeHouseholdRoots(state,targets);});else CanonicalizeHouseholdRoots(state,targets);
        for(unsigned n=0;n<2;++n) {
            auto& bank=state.bank.at(n?456:123);NativePacket packet(state.api);Export(roots[n].data(),packet.data.data());
            const auto actual=SerializeMessage(state.api,packet.data.data());
            if(mode>0 && mode<4)Require(w::Equivalent(original[n],actual));
            else {
                const bool activeReplaced=!(mode==4 && n==0);
                Require(bank.householdCanonical["verified"]==true && bank.householdCanonical["unselected_active_replaced"]==activeReplaced);
                std::map<std::uint32_t,std::string> owners;
                for(const auto& owner:bank.logicalOwners)owners.emplace(owner.first,SerializeOwner(state.api,*bank.graph->appearance(owner.second),n?456:123));
                Require(w::Equivalent(w::Household(original[n],n?456:123,127,owners,activeReplaced?&owners.at(2):nullptr),actual));
            }
        }
        if(mode==1)Require(copies==0); // Every root stages before the first write.
        for(const auto& member:state.bank)for(const auto& owner:member.second.graph->owners())
            Require(SerializeOwner(state.api,*member.second.graph->appearance(owner.id),member.first)==graphBefore.at({member.first,owner.id}));
    }
    state.bank.at(123).active=std::move(firstActive);state.bank.at(456).active=std::move(secondActive);
    state.bank.at(123).viewBound=firstView;state.bank.at(456).viewBound=secondView;
    attrs.clear();inlineAttrs.clear();Require(packetAttrs.empty());state.api=api;
}
}
