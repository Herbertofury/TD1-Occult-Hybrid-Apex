#pragma once
#include "ApexOwnerMailbox.h"
#include "ApexOwnerCommand.h"
#include <set>

namespace td1::ownerbridge {
using Json=ui::Json;
inline Json Strict(const std::string& raw,std::size_t limit=MaxBytes) {
    if(raw.empty()||raw.size()>limit)throw std::runtime_error("Bounded mailbox JSON required.");
    std::vector<std::set<std::string>> keys;
    auto value=Json::parse(raw,[&](int depth,Json::parse_event_t event,Json& item) {
        if(depth>32)throw std::runtime_error("Mailbox JSON exceeds nesting bound.");
        if(event==Json::parse_event_t::object_start)keys.emplace_back();
        else if(event==Json::parse_event_t::key){if(keys.empty()||!keys.back().insert(item.get<std::string>()).second)throw std::runtime_error("Mailbox JSON repeats an intent field.");}
        else if(event==Json::parse_event_t::object_end)keys.pop_back();
        return true;
    });
    if(!value.is_object())throw std::runtime_error("Mailbox JSON object required.");return value;
}
inline bool Keys(const Json& object,const std::set<std::string>& expected) {
    if(!object.is_object()||object.size()!=expected.size())return false;
    for(auto it=object.begin();it!=object.end();++it)if(!expected.count(it.key()))return false;
    return true;
}
inline bool Uint(const Json& value,bool zero=false) {
    if(value.is_number_unsigned())return zero||value.get<std::uint64_t>()!=0;
    if(!value.is_number_integer()||value.get<std::int64_t>()<0)return false;
    return zero||value.get<std::int64_t>()!=0;
}
inline Json RuntimeJson(const Runtime& value){return {{"nonce",value.nonce},{"epoch",value.epoch},{"pid",value.pid},{"owner",value.owner}};}
inline Runtime RuntimeFrom(const Json& value) {
    if(!Keys(value,{"nonce","epoch","pid","owner"})||!value["nonce"].is_string()||!Identity(value["nonce"].get<std::string>())||
       !Uint(value["epoch"])||!Uint(value["pid"])||value["pid"].get<std::uint64_t>()>UINT32_MAX||
       !Uint(value["owner"])||value["owner"].get<std::uint64_t>()>UINT32_MAX)throw std::runtime_error("Exact mailbox runtime required.");
    return {value["nonce"].get<std::string>(),value["epoch"].get<std::uint64_t>(),value["pid"].get<std::uint32_t>(),value["owner"].get<std::uint32_t>()};
}
template<class Selection>
inline Json ControlWithSelection(Mailbox& mailbox,const std::string& raw,std::uint32_t pid,std::uint32_t caller,Selection selection,std::uint64_t now) {
    try {
        const auto request=Strict(raw,MaxBytes*2+4096);
        if(!request.contains("operation")||!request["operation"].is_string())throw std::runtime_error("Typed mailbox operation required.");
        const auto operation=request["operation"].get<std::string>();
        if(operation=="status") {
            if(!Keys(request,{"operation"}))throw std::runtime_error("Mailbox status accepts no authority or options.");
            const auto m=mailbox.Status();
            return {{"ok",true},{"transport","in-process-immutable-owner-mailbox"},{"ready",m.ready},{"runtime_epoch",m.epoch},
                {"accepted",m.accepted},{"claimed",m.claimed},{"completed",m.completed},{"pending",m.pending},
                {"unresolved",m.unresolved},{"retained",m.retained},{"bytes",m.bytes},
                {"appearance_read",false},{"mutation_authority",false}};
        }
        if(operation=="bind") {
            if(!Keys(request,{"operation","nonce","pid"})||!request["nonce"].is_string()||!Uint(request["pid"])||
                    request["pid"].get<std::uint64_t>()!=pid)throw std::runtime_error("Mailbox binding requires the actual process.");
            const auto runtime=mailbox.Bind(request["nonce"].get<std::string>(),pid,caller);
            return {{"ok",runtime.epoch!=0},{"runtime",RuntimeJson(runtime)}};
        }
        if(!request.contains("runtime"))throw std::runtime_error("Mailbox runtime is absent.");
        const auto runtime=RuntimeFrom(request["runtime"]);
        if(runtime.pid!=pid||runtime.owner!=caller)throw std::runtime_error("Foreign mailbox runtime/thread refused.");
        if(runtime!=mailbox.Context())throw std::runtime_error("Mailbox runtime epoch/nonce is no longer current.");
        if(operation=="take") {
            if(!Keys(request,{"operation","runtime"}))throw std::runtime_error("Mailbox claim options differ.");
            const auto job=mailbox.Take(runtime,caller);
            return {{"ok",true},{"job",job.ticket?Json{{"ticket",job.ticket},{"request_id",job.id},{"selection",job.selection},{"request",*job.request}}:Json(nullptr)}};
        }
        if(operation=="retire") {
            if(!Keys(request,{"operation","runtime"}))throw std::runtime_error("Mailbox retirement options differ.");
            return {{"ok",mailbox.Retire(runtime,caller)}};
        }
        if(!request.contains("ticket")||!Uint(request["ticket"])||!request.contains("request_id")||
                !request["request_id"].is_string()||!Identity(request["request_id"].get<std::string>()))throw std::runtime_error("Mailbox job identity is absent.");
        const auto ticket=request["ticket"].get<std::uint64_t>();const auto id=request["request_id"].get<std::string>();
        if(operation=="authorize") {
            if(!Keys(request,{"operation","runtime","ticket","request_id"}))throw std::runtime_error("Mailbox authorization options differ.");
            return {{"ok",mailbox.Authorize(runtime,caller,ticket,id,selection(),now)}};
        }
        if(operation=="publish") {
            if(!Keys(request,{"operation","runtime","ticket","request_id","phase","receipt"})||
                    !request["phase"].is_string()||!request["receipt"].is_string())throw std::runtime_error("Mailbox publication options differ.");
            const auto bytes=request["receipt"].get<std::string>();const auto receipt=Strict(bytes);
            if(!ui::OwnerIdentityMatches(receipt,id)||!receipt.contains("state")||!receipt["state"].is_string()||
                    !receipt.contains("ok")||!receipt["ok"].is_boolean())throw std::runtime_error("Canonical receipt lost its UUID/state.");
            const auto state=receipt["state"].get<std::string>();const auto phase=request["phase"].get<std::string>();Phase nativePhase;
            if(state=="pending"&&phase=="submitted"&&receipt["ok"]==true)nativePhase=Phase::Submitted;
            else if(state=="running"&&phase=="running"&&receipt["ok"]==true)nativePhase=Phase::Running;
            else if(state=="unknown"&&phase=="uncertain"&&receipt["ok"]==false)nativePhase=Phase::Uncertain;
            else if((state=="completed"||state=="failed"||state=="cancelled")&&phase=="terminal"&&
                    receipt.contains("result")&&ui::OwnerResultMatchesState(receipt["result"],state)&&receipt["ok"]==(state=="completed"))nativePhase=Phase::Terminal;
            else throw std::runtime_error("Canonical receipt state/phase/result disagree.");
            return {{"ok",mailbox.Publish(runtime,caller,ticket,id,bytes,nativePhase)}};
        }
        throw std::runtime_error("Unsupported mailbox operation.");
    }catch(const std::exception& error){return {{"ok",false},{"message",error.what()}};}
}
inline Json Control(Mailbox& mailbox,const std::string& raw,std::uint32_t pid,std::uint32_t caller,std::uint64_t selection,std::uint64_t now) {
    return ControlWithSelection(mailbox,raw,pid,caller,[selection]{return selection;},now);
}
}
