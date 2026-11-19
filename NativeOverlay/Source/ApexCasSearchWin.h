// Offline SQLite/FTS reads run exclusively on the existing metadata worker.
// The Rust library is built WITHOUT its CLI/network features for this DLL.
#pragma once
#include "ApexCasSearch.h"
#include <windows.h>
#include <filesystem>
#include <fstream>

extern "C" {
unsigned ApexCatalogVersion();
void* ApexCatalogOpen(const char* path,const char* sha256);
void* ApexCatalogOpenUsage(const char* path,const char* sha256,const char* usage,const char* usageSha256,const char* saveGuid);
char* ApexCatalogQuery(void* handle,const unsigned char* query,size_t bytes);
void ApexCatalogFree(char* value);
void ApexCatalogClose(void* handle);
}

namespace td1::search {
inline std::atomic<std::uint64_t>& IndexEpoch(){static auto* value=new std::atomic<std::uint64_t>(1);return *value;}
inline void ReloadOfflineMetadata(){IndexEpoch().fetch_add(1,std::memory_order_release);}

class OfflineMetadata {
    void* handle_=nullptr;
    std::mutex mutex_;
    std::uint64_t epoch_=0;
    std::string path_,digest_;
    std::string usage_,usageDigest_,saveGuid_;
    bool explicit_=false;
    void Open() {
        if(handle_){ApexCatalogClose(handle_);handle_=nullptr;}
        if(!explicit_){
            HMODULE module=nullptr;
            if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                reinterpret_cast<LPCWSTR>(&ApexCatalogVersion),&module))throw std::runtime_error("Cannot locate the catalogue owner module.");
            wchar_t buffer[32768];const auto size=GetModuleFileNameW(module,buffer,32768);
            if(!size||size>=32768)throw std::runtime_error("Catalogue owner path is unavailable.");
            const auto config=std::filesystem::path(buffer).parent_path()/L"apex-catalog.snapshot.json";
            std::ifstream file(config,std::ios::binary);
            if(!file)throw std::runtime_error("Run the explicit Apex metadata sync first; no offline snapshot is configured.");
            std::string bytes;char chunk[4097];file.read(chunk,sizeof(chunk));bytes.assign(chunk,static_cast<size_t>(file.gcount()));
            if(bytes.size()>4096)throw std::runtime_error("Offline snapshot configuration exceeds its bound.");
            const auto value=Json::parse(bytes);
            if(!value.is_object()||(value.size()!=4&&value.size()!=5)||value.value("schema",0)!=1||
                value.value("network_at_runtime",Json())!=false||!value.contains("index")||!value["index"].is_string()||
                !resource::Hash(value,"index_sha256"))throw std::runtime_error("Offline snapshot configuration differs.");
            path_=value["index"].get<std::string>();digest_=value["index_sha256"].get<std::string>();
            usage_.clear();usageDigest_.clear();saveGuid_.clear();
            if(value.contains("equipped")) {
                const auto& u=value["equipped"];
                if(!u.is_object()||u.size()!=3||!u.contains("index")||!u["index"].is_string()||
                    !resource::Hash(u,"index_sha256")||!u.contains("save_guid")||!u["save_guid"].is_string())
                    throw std::runtime_error("Equipped snapshot configuration differs.");
                usage_=u["index"].get<std::string>();usageDigest_=u["index_sha256"].get<std::string>();saveGuid_=u["save_guid"].get<std::string>();
                if(usage_.empty()||usage_.size()>32768||saveGuid_.empty()||saveGuid_.size()>20)
                    throw std::runtime_error("Equipped snapshot configuration exceeds its bound.");
            } else if(value.size()!=4)throw std::runtime_error("Unknown offline snapshot configuration field.");
        }
        if(path_.empty()||path_.size()>32768||ApexCatalogVersion()!=2)throw std::runtime_error("Offline catalogue ABI/configuration differs.");
        handle_=usage_.empty()?ApexCatalogOpen(path_.c_str(),digest_.c_str()):
            ApexCatalogOpenUsage(path_.c_str(),digest_.c_str(),usage_.c_str(),usageDigest_.c_str(),saveGuid_.c_str());
        if(!handle_)throw std::runtime_error("Offline catalogue could not open with its exact pinned digest.");
    }
public:
    OfflineMetadata()=default;
    OfflineMetadata(std::string path,std::string digest):path_(std::move(path)),digest_(std::move(digest)),explicit_(true){}
    OfflineMetadata(std::string path,std::string digest,std::string usage,std::string usageDigest,std::string save):
        path_(std::move(path)),digest_(std::move(digest)),usage_(std::move(usage)),usageDigest_(std::move(usageDigest)),saveGuid_(std::move(save)),explicit_(true){}
    ~OfflineMetadata(){if(handle_)ApexCatalogClose(handle_);}
    Json Read(const Json& query){
        std::lock_guard<std::mutex> lock(mutex_);
        const auto epoch=IndexEpoch().load(std::memory_order_acquire);
        if(!handle_||epoch_!=epoch){Open();epoch_=epoch;}
        const auto body=query.dump();
        char* raw=ApexCatalogQuery(handle_,reinterpret_cast<const unsigned char*>(body.data()),body.size());
        if(!raw)throw std::runtime_error("Offline catalogue did not return a bounded reply.");
        Json result;
        try{result=Json::parse(raw);}catch(...){ApexCatalogFree(raw);throw;}
        ApexCatalogFree(raw);
        if(result.value("ok",Json())!=true)throw std::runtime_error(result.value("message",std::string("Offline query failed.")).substr(0,512));
        return result;
    }
};

inline Json FetchMetadata(const Json& query){
    // Process-resident, like the metadata worker: no loader-lock destruction
    // of a live Rust/SQLite handle or a still-running worker during DLL detach.
    static auto* catalog=new OfflineMetadata();return catalog->Read(query);
}
inline Worker& MetadataWorker(){static auto* worker=new Worker(FetchMetadata);return *worker;}
}
