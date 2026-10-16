// Explicit development diagnostic inside the authorized mod, never a frame hook.
#pragma once
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <algorithm>
#include <deque>
#include <set>
#include "ApexUiData.h"
#include "ApexResourceImage.h"
#include "ApexNativeCasProbe.h"
#include "ApexNativeCasOwners.h"

namespace td1::nativecas {
inline std::string OwnImageRead(HMODULE module,std::uint32_t rva,std::size_t count) {
    if(!module || !count || count>64u*1024u*1024u) throw std::runtime_error("Native probe span is unbounded.");
    std::string bytes(count,'\0');SIZE_T read=0;
    if(!ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const char*>(module)+rva,
        bytes.data(),count,&read) || read!=count) throw std::runtime_error("Exact own-image code span is unreadable.");
    return bytes;
}
inline std::uint64_t OwnControllerPointer(std::uintptr_t address) {
    // One typed pointer only. Never accept an address from the exported API,
    // invoke the interface, enumerate the heap or change memory protection.
    if(address<0x10000 || address>0x00007ffffffffff7ULL || address%8)
        throw std::runtime_error("Native controller pointer is not a readable aligned user pointer.");
    MEMORY_BASIC_INFORMATION region{};
    if(VirtualQuery(reinterpret_cast<const void*>(address),&region,sizeof(region))!=sizeof(region) ||
        region.State!=MEM_COMMIT || (region.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
        address<reinterpret_cast<std::uintptr_t>(region.BaseAddress) ||
        address-reinterpret_cast<std::uintptr_t>(region.BaseAddress)>region.RegionSize ||
        region.RegionSize-(address-reinterpret_cast<std::uintptr_t>(region.BaseAddress))<8)
        throw std::runtime_error("Native controller pointer is unavailable in committed memory.");
    std::uint64_t value=0;SIZE_T read=0;
    if(!ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),&value,sizeof(value),&read) || read!=sizeof(value))
        throw std::runtime_error("Native controller pointer changed or became unreadable.");
    return value;
}
inline ui::Json Inspect() {
    const auto module=GetModuleHandleW(nullptr);
    wchar_t filename[32768]={};
    const auto length=GetModuleFileNameW(module,filename,32768);
    if(!module || !length || length>=32768 || _wcsicmp(std::filesystem::path(filename).filename().c_str(),L"TS4_x64.exe"))
        throw std::runtime_error("Read-only CAS inspection requires the actual Sims executable.");
    std::ifstream stream(std::filesystem::path(filename),std::ios::binary|std::ios::ate);
    if(!stream) throw std::runtime_error("Cannot fingerprint the exact own executable.");
    const auto size=stream.tellg();
    if(size<4096 || size>128*1024*1024) throw std::runtime_error("Own executable exceeds its diagnostic bound.");
    std::string disk(static_cast<std::size_t>(size),'\0');stream.seekg(0);
    if(!stream.read(disk.data(),static_cast<std::streamsize>(disk.size()))) throw std::runtime_error("Own executable read failed.");
    const auto hash=resource::HashBytes(disk);
    if(hash!="916b852b187b9c41b9c2d77af55e0d5ed6aaf06909661397d7aa98f2e4db78ab")
        throw std::runtime_error("Native diagnostic does not support this game executable hash.");
    IMAGE_DOS_HEADER dos{};std::memcpy(&dos,disk.data(),sizeof(dos));
    if(dos.e_magic!=IMAGE_DOS_SIGNATURE || dos.e_lfanew<64 || static_cast<std::size_t>(dos.e_lfanew)>disk.size()-sizeof(IMAGE_NT_HEADERS64))
        throw std::runtime_error("Unsupported own PE header.");
    IMAGE_NT_HEADERS64 nt{};std::memcpy(&nt,disk.data()+dos.e_lfanew,sizeof(nt));
    if(nt.Signature!=IMAGE_NT_SIGNATURE || nt.FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64 ||
       nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC || !nt.FileHeader.NumberOfSections ||
       nt.FileHeader.NumberOfSections>32 || nt.OptionalHeader.SizeOfImage!=45785088 || nt.FileHeader.TimeDateStamp!=1788904532)
        throw std::runtime_error("Pinned own PE layout changed.");
    const auto nativeDos=OwnImageRead(module,0,sizeof(dos));IMAGE_DOS_HEADER loadedDos{};
    std::memcpy(&loadedDos,nativeDos.data(),sizeof(loadedDos));
    const auto nativeNt=OwnImageRead(module,static_cast<std::uint32_t>(dos.e_lfanew),sizeof(nt));IMAGE_NT_HEADERS64 loadedNt{};
    std::memcpy(&loadedNt,nativeNt.data(),sizeof(loadedNt));
    if(loadedDos.e_magic!=dos.e_magic || loadedDos.e_lfanew!=dos.e_lfanew || loadedNt.Signature!=nt.Signature ||
       loadedNt.FileHeader.Machine!=nt.FileHeader.Machine || loadedNt.FileHeader.TimeDateStamp!=nt.FileHeader.TimeDateStamp ||
       loadedNt.OptionalHeader.SizeOfImage!=nt.OptionalHeader.SizeOfImage)
        throw std::runtime_error("Loaded executable differs from its pinned file layout.");
    const auto table=static_cast<std::size_t>(dos.e_lfanew)+offsetof(IMAGE_NT_HEADERS64,OptionalHeader)+nt.FileHeader.SizeOfOptionalHeader;
    if(table>disk.size() || nt.FileHeader.NumberOfSections>(disk.size()-table)/sizeof(IMAGE_SECTION_HEADER))
        throw std::runtime_error("Own section table is truncated.");
    IMAGE_SECTION_HEADER text{},data{},writable{},unwind{};unsigned textCount=0,dataCount=0,writableCount=0,unwindCount=0;
    for(unsigned i=0;i<nt.FileHeader.NumberOfSections;++i) {
        IMAGE_SECTION_HEADER section{};std::memcpy(&section,disk.data()+table+i*sizeof(section),sizeof(section));
        const std::string name(reinterpret_cast<const char*>(section.Name),strnlen_s(reinterpret_cast<const char*>(section.Name),8));
        if(name==".text") {text=section;++textCount;}
        if(name==".rdata") {data=section;++dataCount;}
        if(name==".data") {writable=section;++writableCount;}
        if(name==".pdata") {unwind=section;++unwindCount;}
    }
    if(textCount!=1 || dataCount!=1 || !(text.Characteristics&IMAGE_SCN_MEM_EXECUTE) ||
       !(data.Characteristics&IMAGE_SCN_MEM_READ) || (data.Characteristics&(IMAGE_SCN_MEM_EXECUTE|IMAGE_SCN_MEM_WRITE)))
        throw std::runtime_error("Expected code/read-only sections are unavailable.");
    Bounds(text.VirtualAddress,text.Misc.VirtualSize,nt.OptionalHeader.SizeOfImage);
    Bounds(data.VirtualAddress,data.Misc.VirtualSize,nt.OptionalHeader.SizeOfImage);
    struct Function {std::uint32_t begin,end;};std::vector<Function> functions;
    if(unwindCount!=1 || !unwind.Misc.VirtualSize || unwind.Misc.VirtualSize%12 || unwind.Misc.VirtualSize>4u*1024u*1024u ||
       unwind.PointerToRawData>disk.size() || unwind.Misc.VirtualSize>disk.size()-unwind.PointerToRawData)
        throw std::runtime_error("Pinned native unwind boundaries are unavailable.");
    for(std::size_t offset=0;offset<unwind.Misc.VirtualSize;offset+=12) {
        std::uint32_t record[3]={};std::memcpy(record,disk.data()+unwind.PointerToRawData+offset,12);
        if(record[0]>=text.VirtualAddress && record[0]<record[1] && record[1]<=text.VirtualAddress+text.Misc.VirtualSize)
            functions.push_back({record[0],record[1]});
    }
    std::sort(functions.begin(),functions.end(),[](const Function& a,const Function& b){return a.begin<b.begin;});
    for(std::size_t i=1;i<functions.size();++i)
        if(functions[i-1].begin==functions[i].begin) throw std::runtime_error("Native unwind entry is ambiguous.");
    auto findFunction=[&](std::uint32_t address)->const Function* {
        const auto found=std::lower_bound(functions.begin(),functions.end(),address,
            [](const Function& item,std::uint32_t value){return item.begin<value;});
        return found!=functions.end() && found->begin==address?&*found:nullptr;
    };
    auto containingFunction=[&](std::uint32_t address)->const Function* {
        auto found=std::upper_bound(functions.begin(),functions.end(),address,
            [](std::uint32_t value,const Function& item){return value<item.begin;});
        if(found==functions.begin()) return nullptr;
        --found;return address<found->end?&*found:nullptr;
    };
    if(text.PointerToRawData>disk.size() || text.Misc.VirtualSize>disk.size()-text.PointerToRawData)
        throw std::runtime_error("Pinned on-disk code span is incomplete.");
    const auto diskCodeHash=resource::HashBytes(disk.substr(text.PointerToRawData,text.Misc.VirtualSize));
    if(diskCodeHash.size()!=64) throw std::runtime_error("Pinned code fingerprint is unavailable.");
    disk.clear();disk.shrink_to_fit();stream.close();
    const auto code=OwnImageRead(module,text.VirtualAddress,text.Misc.VirtualSize);
    const auto constants=OwnImageRead(module,data.VirtualAddress,data.Misc.VirtualSize);
    ui::Json controller={{"available",false},{"pointer_reads",0},{"interface_called",false},
        {"game_memory_written",false},{"methods",ui::Json::array()}};
    std::set<std::uint32_t> controllerMethods;
    try {
        constexpr std::uint32_t global=0x2948f00;
        // Two independently decoded registration callbacks reach this same
        // controller. Refuse drift before inspecting its typed vtable.
        if(RipLoadTarget(code,text.VirtualAddress,0x2096f8)!=global ||
           RipLoadTarget(code,text.VirtualAddress,0x208a42)!=global || writableCount!=1 ||
           !(writable.Characteristics&IMAGE_SCN_MEM_WRITE) || (writable.Characteristics&IMAGE_SCN_MEM_EXECUTE))
            throw std::runtime_error("Native CAS controller references differ from the inspected callbacks.");
        const auto base=reinterpret_cast<std::uintptr_t>(module);
        SectionPointer(base+global,base,writable.VirtualAddress,writable.Misc.VirtualSize,8);
        auto pointer=[&](std::uintptr_t address) {
            controller["pointer_reads"]=controller["pointer_reads"].get<unsigned>()+1;
            return OwnControllerPointer(address);
        };
        const auto object=pointer(base+global);
        if(!object) throw std::runtime_error("Native CAS controller is not initialized in this game state.");
        const auto vtable=pointer(object);
        const auto tableRva=SectionPointer(vtable,base,data.VirtualAddress,data.Misc.VirtualSize,0x428);
        ui::Json methods=ui::Json::array();
        for(const auto slot:{0x128u,0x1e0u,0x3f0u,0x410u,0x420u}) {
            std::uint64_t target=0;std::memcpy(&target,constants.data()+tableRva-data.VirtualAddress+slot,8);
            const auto rva=SectionPointer(target,base,text.VirtualAddress,text.Misc.VirtualSize,1);
            // A leaf vtable thunk need not have a PE unwind record. It is
            // still an exact, image-bound vtable target, not a function
            // boundary inferred from nearby bytes. Capture it separately.
            const char* name=slot==0x128?"set-occult-kind":slot==0x1e0?"select-primary-alternate":
                slot==0x3f0?"kind-conversion-controller-preflight":
                slot==0x410?"lookup-sim-cache":"build-current-sim-info";
            methods.push_back({{"name",name},
                {"slot",slot},{"target_rva",rva},{"unwind_entry_verified",findFunction(rva)!=nullptr}});
        }
        if(pointer(base+global)!=object || pointer(object)!=vtable ||
           OwnImageRead(module,tableRva,0x428)!=constants.substr(tableRva-data.VirtualAddress,0x428))
            throw std::runtime_error("Native CAS controller identity changed during inspection.");
        controller.update({{"available",true},{"global_rva",global},{"vtable_rva",tableRva},{"methods",methods}});
        for(const auto& method:methods) controllerMethods.insert(method.at("target_rva").get<std::uint32_t>());
        // The pinned kind setter delegates creation and UI rebinding to a
        // second interface. Follow only the four slots independently decoded
        // at 3f5c5d/3f5c76/3f5c97/3f0c62; never call or patch that interface.
        // This separates the actual native pair constructor from the public
        // setter and its old-pair cache, which are insufficient patch targets.
        ui::Json model={{"available",false},{"interface_called",false},{"game_memory_written",false}};
        try {
            const auto modelObject=pointer(object+0x1d0);
            if(!modelObject) throw std::runtime_error("Native conversion model is not initialized.");
            const auto modelTable=pointer(modelObject);
            const auto modelRva=SectionPointer(modelTable,base,data.VirtualAddress,data.Misc.VirtualSize,0x750);
            ui::Json modelMethods=ui::Json::array();
            for(const auto slot:{0x70u,0x348u,0x4b0u,0x748u}) {
                std::uint64_t target=0;std::memcpy(&target,constants.data()+modelRva-data.VirtualAddress+slot,8);
                const auto rva=SectionPointer(target,base,text.VirtualAddress,text.Misc.VirtualSize,1);
                const char* name=slot==0x70?"kind-conversion-model-stage-a":
                    slot==0x348?"kind-conversion-model-rebind":
                    slot==0x4b0?"kind-conversion-model-selection":"kind-conversion-pair-constructor";
                modelMethods.push_back({{"name",name},{"slot",slot},{"target_rva",rva},
                    {"unwind_entry_verified",findFunction(rva)!=nullptr}});
            }
            if(pointer(object+0x1d0)!=modelObject || pointer(modelObject)!=modelTable ||
                OwnImageRead(module,modelRva,0x750)!=constants.substr(modelRva-data.VirtualAddress,0x750))
                throw std::runtime_error("Native conversion model changed during inspection.");
            model.update({{"available",true},{"vtable_rva",modelRva},{"methods",modelMethods},
                {"scope","Callsite-derived native kind-conversion interface; method meanings require independent decoding"}});
            for(const auto& method:modelMethods) controllerMethods.insert(method.at("target_rva").get<std::uint32_t>());
        } catch(const std::exception& error) {model["reason"]=error.what();}
        controller["conversion_model"]=std::move(model);
        ui::Json inventory={{"available",false},{"appearance_data_read",false},
            {"scope","Pinned native cache keys only; no appearance equality or ownership-lifetime claim"}};
        try {
            const auto first=ReadKindCacheMetadata(object,pointer);
            const auto second=ReadKindCacheMetadata(object,pointer);
            if(first!=second || pointer(base+global)!=object || pointer(object)!=vtable)
                throw std::runtime_error("Native owner-cache metadata changed between bounded reads.");
            ui::Json owners=ui::Json::array();
            for(const auto& row:first) owners.push_back({{"sim_id",std::to_string(row.simId)},
                {"stored_kind_keys",row.kinds},{"key_matches_stored_record_kind",true}});
            inventory.update({{"available",true},{"double_read_verified",true},{"owners",owners}});
        } catch(const std::exception& error) {inventory["reason"]=error.what();}
        controller["kind_cache_inventory"]=std::move(inventory);
    } catch(const std::exception& error) {controller["reason"]=error.what();}
    ui::Json rows=ui::Json::array();std::set<std::uint32_t> callbacks,messageRegions,cacheHelpers;
    // Native helpers with leaf/no-unwind entries would otherwise be omitted
    // by the unwind-only graph. Verify the actual decoded callsites first.
    const auto conversionEdges=CodeEdges(code.substr(0x3f0af0-text.VirtualAddress,0x2bc),0x3f0af0);
    for(const auto expected:std::array<std::pair<std::uint32_t,std::uint32_t>,4>{{
            {0x3f0c06,0x442020},{0x3f0c18,0x1b1c70},{0x3f0c20,0x6a6e0},{0x3f0c2d,0x3405c0}}}) {
        if(std::none_of(conversionEdges.begin(),conversionEdges.end(),[&](const auto& edge){
                return edge.call && edge.instruction==expected.first && edge.target==expected.second;}))
            throw std::runtime_error("Native kind-cache helper callsite differs from the inspected layout.");
        cacheHelpers.insert(expected.second);
    }
    for(const auto* name:{"SetSimOccult","CasGetAvailableOccults","CasSelectOccultForm","CasCreateSimOccultForm",
            "CasRemoveSimOccultForm","CasSyncSimOccultForm","CasEnableAutoSyncOccultForm",
            "occult_sim_infos","current_occult_types","CasToClientIFace::SimInfoWithOutfitsResponse",
            "CasToClientIFace::SendProtocolBuffer"}) {
        ui::Json targets=ui::Json::array();
        for(const auto target:StringRvas(constants,data.VirtualAddress,nt.OptionalHeader.SizeOfImage,name)) {
            ui::Json refs=ui::Json::array();
            auto reference=[&](std::uint32_t destination,const char* kind) {
                for(const auto address:RipLeas(code,text.VirtualAddress,nt.OptionalHeader.SizeOfImage,destination)) {
                    if(refs.size()==64) throw std::runtime_error("Combined service references exceed their bound.");
                    auto row=ui::Json({{"kind",kind},{"target_rva",destination},{"instruction_rva",address},
                        {"window_rva",address-text.VirtualAddress<16?text.VirtualAddress:address-16},
                        {"code_hex",CodeWindow(code,text.VirtualAddress,address)}});
                    const auto callback=RegisteredCallback(code,text.VirtualAddress,nt.OptionalHeader.SizeOfImage,address,0xdad300);
                    if(callback && findFunction(callback)) {row["registered_callback_rva"]=callback;callbacks.insert(callback);}
                    if(std::string(name).rfind("CasToClientIFace::",0)==0) {
                        if(const auto* region=containingFunction(address)) {
                            row["containing_unwind_region_rva"]=region->begin;messageRegions.insert(region->begin);
                        }
                    }
                    refs.push_back(std::move(row));
                }
            };
            reference(target,"direct-service-string");
            const auto pointers=Pointers(constants,data.VirtualAddress,nt.OptionalHeader.SizeOfImage,
                reinterpret_cast<std::uintptr_t>(module),target);
            for(const auto pointer:pointers) reference(pointer,"read-only-service-pointer");
            targets.push_back({{"string_rva",target},{"pointer_rvas",pointers},{"references",refs}});
        }
        rows.push_back({{"service",name},{"targets",targets}});
    }
    const auto memoryHash=resource::HashBytes(code);
    if(memoryHash.size()!=64) throw std::runtime_error("Runtime code fingerprint is unavailable.");
    ui::Json snapshots=ui::Json::array(),contexts=ui::Json::array();std::deque<std::pair<std::uint32_t,unsigned>> pending;
    std::set<std::uint32_t> seen;std::size_t captured=0;
    std::vector<std::uint32_t> roots(cacheHelpers.begin(),cacheHelpers.end());
    roots.insert(roots.end(),controllerMethods.begin(),controllerMethods.end());
    roots.insert(roots.end(),messageRegions.begin(),messageRegions.end());
    for(const auto callback:callbacks) if(!controllerMethods.count(callback)) roots.push_back(callback);
    std::set<std::uint32_t> contextSeen;
    auto captureContext=[&](std::uint32_t callback,bool root) {
        if(captured>=49152 || !contextSeen.insert(callback).second) return;
        const auto offset=static_cast<std::size_t>(callback-text.VirtualAddress);
        const auto count=std::min<std::size_t>({root?4096u:2048u,code.size()-offset,49152-captured});
        const auto body=code.substr(offset,count);captured+=count;
        contexts.push_back({{"callback_rva",callback},{"captured_bytes",count},{"code_sha256",resource::HashBytes(body)},
            {"code_hex",HexBytes(body)},{"scope",controllerMethods.count(callback)?"bounded-controller-method-code-context":
                callbacks.count(callback)?"bounded-registered-callback-code-context":"bounded-decoded-callee-code-context"},
            {"semantic_function_complete",false},{"adjacent_code_may_be_included",true}});
    };
    for(const auto callback:roots) {
        pending.push_back({callback,0});
        captureContext(callback,true);
    }
    while(!pending.empty() && snapshots.size()<32 && captured<65536) {
        const auto item=pending.front();pending.pop_front();
        if(!seen.insert(item.first).second) continue;
        const auto* function=findFunction(item.first);if(!function) continue;
        if(item.second) captureContext(item.first,false);
        const auto count=std::min<std::size_t>({function->end-function->begin,4096,65536-captured});
        if(!count) break;
        const auto body=code.substr(function->begin-text.VirtualAddress,count);captured+=count;
        ui::Json branches=ui::Json::array();
        const auto graphBytes=std::min<std::size_t>(4096,code.size()-(function->begin-text.VirtualAddress));
        for(const auto& edge:CodeEdges(code.substr(function->begin-text.VirtualAddress,graphBytes),function->begin)) {
            const auto target=edge.target;
            if(!findFunction(target) || target==function->begin) continue;
            branches.push_back({{"instruction_rva",edge.instruction},{"target_rva",target},
                {"kind",edge.call?"decoded-direct-call":"decoded-direct-jump"},{"instruction_boundary_verified",true},
                {"decoder","hde64"},{"scope","bounded-control-flow-context"}});
            if(item.second<2 && pending.size()<128) pending.push_back({target,item.second+1});
        }
        snapshots.push_back({{"begin_rva",function->begin},{"end_rva",function->end},{"captured_bytes",count},
            {"complete",count==function->end-function->begin},{"unwind_boundary_verified",true},{"depth",item.second},
            {"scope","unwind-region"},{"semantic_function_complete",false},
            {"code_sha256",resource::HashBytes(body)},{"code_hex",HexBytes(body)},{"branch_candidates",branches}});
    }
    ui::Json faults=ui::Json::array();
    // Fixed sites from retained CAS crash reports only. These are bounded
    // diagnostic windows, never guessed function entries or hook targets.
    for(const auto fault:{0x105a1deu,0x112c645u,0x3f7ad2u}) {
        if(captured>=65536) break;
        const auto start=fault-256;
        Bounds(start,1024,nt.OptionalHeader.SizeOfImage);
        if(start<text.VirtualAddress || start-text.VirtualAddress>code.size() ||
           code.size()-(start-text.VirtualAddress)<1024)
            throw std::runtime_error("Pinned CAS crash site left its code section.");
        const auto count=std::min<std::size_t>(1024,65536-captured);
        const auto body=code.substr(start-text.VirtualAddress,count);captured+=count;
        faults.push_back({{"fault_rva",fault},{"window_rva",start},{"captured_bytes",count},
            {"code_sha256",resource::HashBytes(body)},{"code_hex",HexBytes(body)},
            {"scope","fixed-pinned-cas-crash-context"},{"function_entry_verified",false}});
    }
    return {{"schema",1},{"ok",true},{"pid",GetCurrentProcessId()},{"exe_sha256",hash},
        {"image_size",nt.OptionalHeader.SizeOfImage},{"text_rva",text.VirtualAddress},{"text_bytes",code.size()},
        {"disk_text_sha256",diskCodeHash},{"runtime_text_sha256",memoryHash},{"runtime_text_matches_disk",memoryHash==diskCodeHash},
        {"services",rows},{"controller",controller},{"function_snapshots",snapshots},{"callback_contexts",contexts},{"code_snapshot_bytes",captured},
        {"callback_roots",callbacks},{"pinned_fault_contexts",faults},{"own_process_only",true},{"read_only",true},{"game_memory_written",false},
        {"game_files_written",false},{"memory_dump_written",false},{"native_patch_qualified",false},
        {"sim_data_read",controller.contains("kind_cache_inventory")}};
}
}
