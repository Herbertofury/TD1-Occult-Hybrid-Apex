namespace recordlookup {
unsigned nativeCalls=0;
void Legacy(void* context,std::uint32_t kind,const void*) {
    ++nativeCalls;
    auto* tracker=Read<void*>(Read<void*>(context));auto** rows=Read<void**>(tracker,0x18);
    for(int n=0;n<Read<int>(tracker,0x20);++n) {
        const auto old=Read<unsigned>(rows[n],0x18);
        if(kind&(old==1?1u:~1u)) {Write(rows[n],0x18,kind);Write(rows[n],0x30,kind+1000u);return;}
    }
    throw std::runtime_error("Fixture's stock bucket writer found no record.");
}
struct Fixture {
    std::array<char,0x400> packet{};std::array<char,0x140> attrs{};std::array<char,0x40> tracker{};
    std::array<std::array<char,0x90>,7> records{};std::array<void*,7> pointers{};
    void* trackerPointer=nullptr;void* contextPointer=nullptr;
    explicit Fixture(void* output,const std::vector<unsigned>& order) {
        Require(order.size()==7);for(unsigned n=0;n<7;++n) {
            Write(records[n].data(),0x18,order[n]);Write(records[n].data(),0x30,order[n]+900u);
            Write(records[n].data(),0x84,1u);pointers[n]=records[n].data();
        }
        Write(tracker.data(),0x10,126u);Write(tracker.data(),0x18,pointers.data());Write(tracker.data(),0x20,7);
        Write(attrs.data(),0x90,tracker.data());Write(output,0xc0,attrs.data());
        trackerPointer=tracker.data();contextPointer=&trackerPointer;
    }
};
void Visit(const void* root,void* output) {
    // The other root/output fixtures use a string serializer. Supply the exact
    // record-writer layout separately, without changing their wire oracle.
    if(!exactRecordLookup || exactRecordLookup->source!=root || exactRecordLookup->proto!=output)return;
    Fixture fixture(output,{1,32,2,4,8,64,16});
    ExportOccultRecord(&fixture.contextPointer,Read<unsigned>(root,0xd8),root);
    Write(output,0xc0,static_cast<void*>(nullptr));
}
void Exercise() {
    auto& api=Runtime().api;const auto old=api.occultRecord;api.occultRecord=Legacy;
    const std::vector<unsigned> kinds={1,2,4,8,16,32,64};
    std::array<char,0x830> root{};Write(root.data(),0xb8,std::uint64_t(123));Write(root.data(),0xdc,127u);
    for(unsigned rotate=0;rotate<kinds.size();++rotate)for(auto desired:kinds) {
        auto order=kinds;std::rotate(order.begin(),order.begin()+rotate,order.end());
        std::array<char,0x400> fresh{};Fixture f(fresh.data(),order);
        Write(root.data(),0xd8,desired);const auto rootBefore=root;const auto recordsBefore=f.records;
        const auto pointersBefore=f.pointers;const auto calls=nativeCalls;
        {ExactRecordLookupScope scope(root.data(),fresh.data(),123,127);
         ExportOccultRecord(&f.contextPointer,desired,root.data());
         Require(scope.error.empty() && scope.calls==1 && nativeCalls==calls+1);
         Require(scope.routed==unsigned(std::find(order.begin(),order.end(),desired)!=
             std::find_if(order.begin(),order.end(),[&](unsigned kind){return desired==1?kind==1:kind!=1;})));}
        Require(!exactRecordLookup && root==rootBefore && f.pointers==pointersBefore);
        for(unsigned n=0;n<7;++n) {
            Require(Read<unsigned>(f.pointers[n],0x18)==order[n]);
            if(order[n]==desired)Require(Read<unsigned>(f.pointers[n],0x30)==desired+1000);
            else Require(f.records[n]==recordsBefore[n]); // Complete unrelated records, including opaque metadata.
        }
    }
    { // Reproduce EA's real collision: the first non-Human is Werewolf.
        std::array<char,0x400> fresh{};Fixture f(fresh.data(),{1,32,2,4,8,64,16});
        Write(root.data(),0xd8,2u);ExportOccultRecord(&f.contextPointer,2,root.data());
        Require(Read<unsigned>(f.pointers[1],0x18)==2 && Read<unsigned>(f.pointers[2],0x18)==2);
    }
    for(unsigned bad=0;bad<9;++bad) {
        std::array<char,0x400> fresh{},otherProto{};Fixture f(fresh.data(),kinds);std::array<char,0x830> foreign=root;
        Write(root.data(),0xd8,2u);const auto calls=nativeCalls;
        ExactRecordLookupScope scope(root.data(),bad==0?otherProto.data():fresh.data(),bad==1?999:123,127);
        if(bad==2)Write(f.tracker.data(),0x20,8);
        if(bad==3)Write(f.tracker.data(),0x20,6);
        if(bad==4)Write(f.records[6].data(),0x18,32u);
        if(bad==5)Write(f.records[6].data(),0x84,0u);
        if(bad==6)Write(f.tracker.data(),0x10,2u);
        ExportOccultRecord(&f.contextPointer,bad==7?3u:2u,bad==8?foreign.data():root.data());
        Require(!scope.error.empty() && nativeCalls==calls);
        ExportOccultRecord(&f.contextPointer,2,root.data());Require(nativeCalls==calls); // Never replay a refusal.
    }
    { // Exceptions from an already attempted native writer also restore order.
        std::array<char,0x400> fresh{};Fixture f(fresh.data(),{1,32,2,4,8,64,16});const auto order=f.pointers;
        api.occultRecord=[](void*,std::uint32_t,const void*) {throw std::runtime_error("native writer fault");};
        ExactRecordLookupScope scope(root.data(),fresh.data(),123,127);
        ExportOccultRecord(&f.contextPointer,2,root.data());
        Require(!scope.error.empty() && scope.calls==1 && f.pointers==order);
    }
    api.occultRecord=old;
}
}
