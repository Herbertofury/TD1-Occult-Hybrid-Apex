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

namespace td1::nativecas {
inline std::string OwnImageRead(HMODULE module,std::uint32_t rva,std::size_t count) {
    if(!module || !count || count>64u*1024u*1024u) throw std::runtime_error("Native probe span is unbounded.");
    std::string bytes(count,'\0');SIZE_T read=0;
    if(!ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const char*>(module)+rva,
        bytes.data(),count,&read) || read!=count) throw std::runtime_error("Exact own-image code span is unreadable.");
    return bytes;
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
    IMAGE_SECTION_HEADER text{},data{},unwind{};unsigned textCount=0,dataCount=0,unwindCount=0;
    for(unsigned i=0;i<nt.FileHeader.NumberOfSections;++i) {
        IMAGE_SECTION_HEADER section{};std::memcpy(&section,disk.data()+table+i*sizeof(section),sizeof(section));
        const std::string name(reinterpret_cast<const char*>(section.Name),strnlen_s(reinterpret_cast<const char*>(section.Name),8));
        if(name==".text") {text=section;++textCount;}
        if(name==".rdata") {data=section;++dataCount;}
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
    if(text.PointerToRawData>disk.size() || text.Misc.VirtualSize>disk.size()-text.PointerToRawData)
        throw std::runtime_error("Pinned on-disk code span is incomplete.");
    const auto diskCodeHash=resource::HashBytes(disk.substr(text.PointerToRawData,text.Misc.VirtualSize));
    if(diskCodeHash.size()!=64) throw std::runtime_error("Pinned code fingerprint is unavailable.");
    disk.clear();disk.shrink_to_fit();stream.close();
    const auto code=OwnImageRead(module,text.VirtualAddress,text.Misc.VirtualSize);
    const auto constants=OwnImageRead(module,data.VirtualAddress,data.Misc.VirtualSize);
    ui::Json rows=ui::Json::array();std::set<std::uint32_t> callbacks;
    for(const auto* name:{"SetSimOccult","CasGetAvailableOccults","CasSelectOccultForm","CasCreateSimOccultForm",
            "CasRemoveSimOccultForm","CasSyncSimOccultForm","CasEnableAutoSyncOccultForm",
            "occult_sim_infos","current_occult_types"}) {
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
    for(const auto callback:callbacks) {
        pending.push_back({callback,0});
        if(captured>=49152) continue;
        const auto offset=static_cast<std::size_t>(callback-text.VirtualAddress);
        const auto count=std::min<std::size_t>({4096,code.size()-offset,49152-captured});
        const auto body=code.substr(offset,count);captured+=count;
        contexts.push_back({{"callback_rva",callback},{"captured_bytes",count},{"code_sha256",resource::HashBytes(body)},
            {"code_hex",HexBytes(body)},{"scope","bounded-registered-callback-code-context"},
            {"semantic_function_complete",false},{"adjacent_code_may_be_included",true}});
    }
    while(!pending.empty() && snapshots.size()<32 && captured<65536) {
        const auto item=pending.front();pending.pop_front();
        if(!seen.insert(item.first).second) continue;
        const auto* function=findFunction(item.first);if(!function) continue;
        const auto count=std::min<std::size_t>({function->end-function->begin,4096,65536-captured});
        if(!count) break;
        const auto body=code.substr(function->begin-text.VirtualAddress,count);captured+=count;
        ui::Json branches=ui::Json::array();
        for(std::size_t offset=0;offset+5<=body.size() && branches.size()<16;++offset) {
            const auto opcode=static_cast<unsigned char>(body[offset]);if(opcode!=0xe8 && opcode!=0xe9) continue;
            std::int32_t displacement=0;std::memcpy(&displacement,body.data()+offset+1,4);
            const auto destination=static_cast<std::int64_t>(function->begin)+static_cast<std::int64_t>(offset)+5+displacement;
            if(destination<text.VirtualAddress || destination>=text.VirtualAddress+text.Misc.VirtualSize) continue;
            const auto target=static_cast<std::uint32_t>(destination);if(!findFunction(target) || target==function->begin) continue;
            branches.push_back({{"instruction_rva",function->begin+offset},{"target_rva",target},
                {"kind",opcode==0xe8?"direct-call-candidate":"direct-jump-candidate"},{"instruction_boundary_verified",false}});
            if(item.second<2 && pending.size()<128) pending.push_back({target,item.second+1});
        }
        snapshots.push_back({{"begin_rva",function->begin},{"end_rva",function->end},{"captured_bytes",count},
            {"complete",count==function->end-function->begin},{"unwind_boundary_verified",true},{"depth",item.second},
            {"scope","unwind-region"},{"semantic_function_complete",false},
            {"code_sha256",resource::HashBytes(body)},{"code_hex",HexBytes(body)},{"branch_candidates",branches}});
    }
    return {{"schema",1},{"ok",true},{"pid",GetCurrentProcessId()},{"exe_sha256",hash},
        {"image_size",nt.OptionalHeader.SizeOfImage},{"text_rva",text.VirtualAddress},{"text_bytes",code.size()},
        {"disk_text_sha256",diskCodeHash},{"runtime_text_sha256",memoryHash},{"runtime_text_matches_disk",memoryHash==diskCodeHash},
        {"services",rows},{"function_snapshots",snapshots},{"callback_contexts",contexts},{"code_snapshot_bytes",captured},
        {"callback_roots",callbacks},{"own_process_only",true},{"read_only",true},{"game_memory_written",false},
        {"game_files_written",false},{"memory_dump_written",false},{"native_patch_qualified",false}};
}
}
