// Microsoft WinHTTP runs solely inside search::Worker, never from Poll/Submit.
// https://learn.microsoft.com/windows/win32/winhttp/winhttp-sessions-overview
#pragma once
#include "ApexCasSearch.h"
#include <windows.h>
#include <winhttp.h>

namespace td1::search {
struct HttpHandle {
    HINTERNET value=nullptr;
    explicit HttpHandle(HINTERNET handle):value(handle) {
        if(!value)throw std::runtime_error("CAS metadata broker is unavailable.");
    }
    ~HttpHandle(){WinHttpCloseHandle(value);}
    HttpHandle(const HttpHandle&)=delete;
    HttpHandle& operator=(const HttpHandle&)=delete;
};
inline Json FetchMetadata(const Json& query) {
    HttpHandle session(WinHttpOpen(L"Apex CAS metadata/1",WINHTTP_ACCESS_TYPE_NO_PROXY,
                                   WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0));
    if(!WinHttpSetTimeouts(session.value,1500,1500,3000,3000))throw std::runtime_error("Metadata timeout setup failed.");
    HttpHandle connection(WinHttpConnect(session.value,L"127.0.0.1",8023,0));
    HttpHandle request(WinHttpOpenRequest(connection.value,L"POST",L"/v1/catalog/query",nullptr,
                                        WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,0));
    DWORD disabled=WINHTTP_DISABLE_REDIRECTS;
    if(!WinHttpSetOption(request.value,WINHTTP_OPTION_DISABLE_FEATURE,&disabled,sizeof(disabled)))
        throw std::runtime_error("Metadata redirect protection failed.");
    const auto body=query.dump();
    if(!WinHttpSendRequest(request.value,L"Content-Type: application/json\r\n",DWORD(-1),
                          const_cast<char*>(body.data()),static_cast<DWORD>(body.size()),static_cast<DWORD>(body.size()),0)||
       !WinHttpReceiveResponse(request.value,nullptr))throw std::runtime_error("CAS metadata broker did not respond.");
    DWORD status=0,bytes=sizeof(status);
    if(!WinHttpQueryHeaders(request.value,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,
                           WINHTTP_HEADER_NAME_BY_INDEX,&status,&bytes,WINHTTP_NO_HEADER_INDEX)||status!=200)
        throw std::runtime_error("CAS metadata query was refused.");
    std::string response;char buffer[8192];
    for(;;) {
        DWORD count=0;
        if(!WinHttpReadData(request.value,buffer,sizeof(buffer),&count))throw std::runtime_error("Incomplete metadata page.");
        if(!count)break;
        if(response.size()+count>120*1024)throw std::runtime_error("Metadata page exceeds its bound.");
        response.append(buffer,count);
    }
    return Json::parse(response);
}
inline Worker& MetadataWorker() {
    // This sidecar is process resident. Avoid a static thread destructor under
    // Windows loader lock; process teardown owns the worker's final lifetime.
    static auto* worker=new Worker(FetchMetadata);return *worker;
}
}
