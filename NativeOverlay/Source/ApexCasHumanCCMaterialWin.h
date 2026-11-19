// Keep Human geometry and the player's canine parts. Only EA's temporary
// texture-composition genus uses Werewolf when this exact preview has a pelt.
inline std::atomic<const void*> humanCCMaterialGenus{nullptr},humanCCMaterialRenderer{nullptr};
inline std::atomic<std::uint64_t> humanCCMaterialCompositions{0},humanCCMaterialShaderQueries{0};
inline void* humanCCMaterialRelay=nullptr;
inline void* humanCCMaterialTrampoline=nullptr;
inline void ClearHumanCCMaterial() noexcept {
    humanCCMaterialGenus.store(nullptr,std::memory_order_release);
    humanCCMaterialRenderer.store(nullptr,std::memory_order_release);
}
inline void BindHumanCCMaterial(void* model,const std::string& owner) {
    ClearHumanCCMaterial();
    if(owner!="werewolf/werewolf_human_cc" || !model)return;
    const auto renderer=Read<const void*>(model,0x520);
    // EA's pinned 19EEE90 genus setter writes renderer+10 -> +120.
    // renderer+18 is a different object (its genus is at +1F8).
    const auto assembly=renderer?Read<const void*>(renderer,0x10):nullptr;
    if(!assembly)return;
    const auto genus=static_cast<const char*>(assembly)+0x120;
    if(Read<std::uint32_t>(genus,8)!=1 || Read<std::uint32_t>(genus,0x10)!=1)return;
    humanCCMaterialRenderer.store(renderer,std::memory_order_release);
    humanCCMaterialGenus.store(genus,std::memory_order_release);
}
inline bool HumanCCPeltContext(const void* genus) noexcept {
    if(!genus || genus!=humanCCMaterialGenus.load(std::memory_order_acquire))return false;
    try {
        const auto renderer=humanCCMaterialRenderer.load(std::memory_order_acquire);
        if(!renderer || Read<std::uint32_t>(genus,8)!=1 || Read<std::uint32_t>(genus,0x10)!=1)return false;
        const auto begin=Read<std::uintptr_t>(renderer,0xc0),end=Read<std::uintptr_t>(renderer,0xc8);
        // An empty pelt keeps normal Human skin. Never manufacture fur or
        // replace an existing skin tone, sculpt, part, outfit or pelt layer.
        return begin && end>begin && (end-begin)%24==0 && (end-begin)/24<=1024 &&
               genus==humanCCMaterialGenus.load(std::memory_order_acquire);
    } catch(...) {return false;}
}
inline bool PeltGenus(const void* genus) {
    if(HumanCCPeltContext(genus)) {
        humanCCMaterialShaderQueries.fetch_add(1,std::memory_order_relaxed);return true;
    }
    return Runtime().api.peltGenus(genus);
}
inline bool ComposeHumanCCPelt(void* temporary,const void* original) {
    if(temporary!=original && HumanCCPeltContext(original)) {
        try {
            // The pinned caller just copied these exact twenty bytes. Modify
            // its stack copy only, leaving the stored/render geometry intact.
            Span(temporary,20);Span(original,20);
            if(std::memcmp(temporary,original,20)==0) {
                const std::uint32_t materialKind=32;
                std::memcpy(static_cast<char*>(temporary)+8,&materialKind,4);
                humanCCMaterialCompositions.fetch_add(1,std::memory_order_relaxed);
            }
        } catch(...) {}
    }
    return Runtime().api.peltGenus(temporary);
}
inline void* MakeHumanCCMaterialRelay(const void* helper,const void* continuation) {
    // R9 retains the original genus; RCX is the temporary copy. The native
    // caller already supplies aligned shadow space and consumes AL.
    std::array<unsigned char,29> code{{0x4c,0x89,0xca,0x48,0xb8}};
    const auto callback=reinterpret_cast<std::uintptr_t>(helper),resume=reinterpret_cast<std::uintptr_t>(continuation);
    std::memcpy(code.data()+5,&callback,8);code[13]=0xff;code[14]=0xd0;code[15]=0xff;code[16]=0x25;
    std::memcpy(code.data()+21,&resume,8);
    auto* memory=VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if(!memory)throw std::bad_alloc();std::memcpy(memory,code.data(),code.size());DWORD previous=0;
    if(!VirtualProtect(memory,4096,PAGE_EXECUTE_READ,&previous)) {
        VirtualFree(memory,0,MEM_RELEASE);throw std::runtime_error("Cannot seal the Human/CC material relay.");
    }
    FlushInstructionCache(GetCurrentProcess(),memory,code.size());return memory;
}
