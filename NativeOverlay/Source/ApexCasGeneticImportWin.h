// Existing, explicitly captured genetic entries must survive a detached form
// import even when today's automatic-inheritance whitelist excludes a type.
// Scope the exception to the exact input message, native temporary and callsite.
struct GeneticImportRequest;
struct GeneticImportBinding;
inline thread_local GeneticImportRequest* geneticImportRequest=nullptr;
inline thread_local GeneticImportBinding* geneticImportBinding=nullptr;
struct GeneticImportRequest {
    GeneticImportRequest* previous;const void* input=nullptr;
    std::set<std::uint32_t> bodyTypes;unsigned admitted=0;
    explicit GeneticImportRequest(const void* record):previous(geneticImportRequest) {
        if(Read<std::uint32_t>(record,0x84)&(1u<<7))input=Read<const void*>(record,0x40);
        if(input) {
            const auto parts=Read<const void*>(input,0x28);
            if(parts) {
                const auto count=Read<int>(parts,0x18);
                if(count<0 || count>1024)throw std::runtime_error("Captured genetic part inventory exceeds its bound.");
                const auto rows=Read<const void* const*>(parts,0x10);
                if(count)Span(rows,std::size_t(count)*8);
                for(int n=0;n<count;++n) {
                    const auto part=Read<const void*>(rows,std::size_t(n)*8);
                    if(!(Read<std::uint32_t>(part,0x30)&2u))throw std::runtime_error("Captured genetic part lacks its exact body type.");
                    bodyTypes.insert(Read<std::uint32_t>(part,0x20));
                }
            }
        }
        geneticImportRequest=this;
    }
    ~GeneticImportRequest() {geneticImportRequest=previous;}
    GeneticImportRequest(const GeneticImportRequest&)=delete;
};
struct GeneticImportBinding {
    GeneticImportBinding* previous;GeneticImportRequest& request;const void* genus;void* target;
    GeneticImportBinding(GeneticImportRequest& captured,const void* context,void* destination):
        previous(geneticImportBinding),request(captured),genus(context),target(destination) {geneticImportBinding=this;}
    ~GeneticImportBinding() {geneticImportBinding=previous;}
};
inline bool ImportCapturedGenetics(const void* input,const void* genus,void* target) {
    auto* request=geneticImportRequest;
    if(!request || !request->input || request->input!=input || !genus || !target)
        return Runtime().api.geneticImport(input,genus,target);
    GeneticImportBinding binding(*request,genus,target);
    return Runtime().api.geneticImport(input,genus,target);
}
inline bool GeneticBodyAtInsert(std::uint32_t body,const void* genus,const void* target) {
    const auto* binding=geneticImportBinding;
    if(binding && binding->target==target && binding->genus==genus && binding->request.bodyTypes.count(body)) {
        ++binding->request.admitted;return true;
    }
    return Runtime().api.geneticBodyAllowed(body,genus);
}
inline void* MakeGeneticInsertRelay(const void* helper,const void* continuation) {
    // At the pinned CALL, RBX is the exact destination GeneticData. Supply it
    // as R8; RCX/RDX retain the native body type and genus. The original caller
    // already supplies aligned shadow space. Preserve the helper's AL result.
    std::array<unsigned char,29> code{{0x49,0x89,0xd8,0x48,0xb8}};
    const auto callback=reinterpret_cast<std::uintptr_t>(helper),resume=reinterpret_cast<std::uintptr_t>(continuation);
    std::memcpy(code.data()+5,&callback,8);code[13]=0xff;code[14]=0xd0;code[15]=0xff;code[16]=0x25;
    std::memcpy(code.data()+21,&resume,8);
    auto* memory=VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if(!memory)throw std::bad_alloc();std::memcpy(memory,code.data(),code.size());DWORD previous=0;
    if(!VirtualProtect(memory,4096,PAGE_EXECUTE_READ,&previous)) {
        VirtualFree(memory,0,MEM_RELEASE);throw std::runtime_error("Cannot seal the genetic import callsite relay.");
    }
    FlushInstructionCache(GetCurrentProcess(),memory,code.size());return memory;
}
