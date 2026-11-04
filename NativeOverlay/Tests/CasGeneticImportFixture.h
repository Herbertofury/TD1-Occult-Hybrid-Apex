namespace geneticimport {
using Filter=bool(*)(std::uint32_t,const void*,const void*);
Filter filter=GeneticBodyAtInsert;unsigned legacyCalls=0;
bool Legacy(std::uint32_t body,const void*) {++legacyCalls;return body==4;}
bool NativeImport(const void*,const void* genus,void* destination) {
    auto& result=*static_cast<std::set<unsigned>*>(destination);
    for(auto body:{3u,4u,8u,62u,73u,74u,191u,192u})if(filter(body,genus,destination))result.insert(body);
    return true;
}
struct Input {
    std::array<char,0x90> record{};std::array<char,0x40> genetics{},list{};
    std::array<std::array<char,0x38>,7> parts{};std::array<const void*,7> pointers{};
    Input() {
        unsigned n=0;for(auto type:{3u,8u,62u,73u,74u,191u,192u}) {
            Write(parts[n].data(),0x20,type);Write(parts[n].data(),0x30,2u);pointers[n]=parts[n].data();++n;
        }
        Write(list.data(),0x10,pointers.data());Write(list.data(),0x18,int(n));Write(genetics.data(),0x28,list.data());
        Write(record.data(),0x40,genetics.data());Write(record.data(),0x84,1u<<7);
    }
};
void Exercise() {
    auto& state=Runtime();const auto oldImport=state.api.geneticImport;const auto oldAllowed=state.api.geneticBodyAllowed;
    state.api.geneticImport=NativeImport;state.api.geneticBodyAllowed=Legacy;
    Input input;int genus=0,foreignGenus=0;std::set<unsigned> result,foreign;
    ImportCapturedGenetics(input.genetics.data(),&genus,&result);Require(result==std::set<unsigned>{4});
    result.clear();
    {GeneticImportRequest request(input.record.data());Require(request.bodyTypes.size()==7);
     Require(ImportCapturedGenetics(input.genetics.data(),&genus,&result));
     Require(result.size()==8 && request.admitted==7 && !geneticImportBinding);
     result.clear();ImportCapturedGenetics(input.list.data(),&genus,&result);Require(result==std::set<unsigned>{4});
     {GeneticImportBinding binding(request,&genus,&result);
      Require(!GeneticBodyAtInsert(3,&foreignGenus,&result));Require(!GeneticBodyAtInsert(3,&genus,&foreign));
      Require(GeneticBodyAtInsert(4,&genus,&result));
      bool leaked=true;std::thread worker([&]{leaked=GeneticBodyAtInsert(3,&genus,&result);});worker.join();Require(!leaked);}
     const auto imported=state.api.geneticImport;
     state.api.geneticImport=[](const void*,const void*,void*)->bool {throw std::runtime_error("native import failed");};
     Refuses([&]{ImportCapturedGenetics(input.genetics.data(),&genus,&result);});Require(!geneticImportBinding);
     state.api.geneticImport=imported;}
    Require(!geneticImportRequest && !geneticImportBinding);
    for(unsigned mode=0;mode<3;++mode) {
        Input bad;if(mode==0)Write(bad.list.data(),0x18,-1);
        if(mode==1)Write(bad.list.data(),0x18,1025);
        if(mode==2)Write(bad.parts[2].data(),0x30,0u);
        Refuses([&]{GeneticImportRequest request(bad.record.data());});Require(!geneticImportRequest);
    }
    // Execute the actual relay ABI: native RBX destination becomes helper R8,
    // then AL reaches the original continuation without stack/register damage.
    auto* memory=static_cast<unsigned char*>(VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Require(memory);
    const unsigned char prefix[]={0x53,0x48,0x83,0xec,0x20,0x4c,0x89,0xc3,0x48,0xb8};
    std::memcpy(memory,prefix,sizeof(prefix));void* relay=MakeGeneticInsertRelay(reinterpret_cast<const void*>(&GeneticBodyAtInsert),memory+20);
    std::memcpy(memory+10,&relay,8);memory[18]=0xff;memory[19]=0xe0;
    const unsigned char suffix[]={0x48,0x83,0xc4,0x20,0x5b,0xc3};std::memcpy(memory+20,suffix,sizeof(suffix));
    DWORD previous=0;Require(VirtualProtect(memory,4096,PAGE_EXECUTE_READ,&previous)!=0);FlushInstructionCache(GetCurrentProcess(),memory,26);
    const auto invoke=reinterpret_cast<Filter>(memory);Require(!invoke(3,&genus,&result) && invoke(4,&genus,&result));
    {GeneticImportRequest request(input.record.data());GeneticImportBinding binding(request,&genus,&result);
     Require(invoke(3,&genus,&result) && !invoke(3,&genus,&foreign));}
    Require(VirtualFree(relay,0,MEM_RELEASE)!=0 && VirtualFree(memory,0,MEM_RELEASE)!=0);
    state.api.geneticImport=oldImport;state.api.geneticBodyAllowed=oldAllowed;
}
}
