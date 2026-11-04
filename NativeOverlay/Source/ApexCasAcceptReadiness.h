// Same-request editor preparation and read-only readiness. No game/file APIs.
#pragma once
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>

namespace td1::nativecas::acceptance {
struct Intent {
    std::string id,nonce;
    std::uint64_t sim=0,household=0,channel=0;
    std::string layer,viewKind,modelKind,viewMask,owner,generation;
    bool operator==(const Intent& b) const {return id==b.id && nonce==b.nonce && sim==b.sim && household==b.household && channel==b.channel && layer==b.layer && viewKind==b.viewKind && modelKind==b.modelKind && viewMask==b.viewMask && owner==b.owner && generation==b.generation;}
};
struct Observation {
    // identity excludes only changes this explicit preparation may perform:
    // current model appearance and the selected graph's new edit generation.
    std::string identity,complete;
    std::string publicContext;
    bool busy=false,previewSettled=false;
    std::uint32_t phase=0;
    std::string scalar; // Complete cheap identity/generation/roster stamp, no appearance bytes.
};
struct Record {Intent intent;Observation prepared;std::string state,error;bool authoritativeHarvest=false;};
class Ledger {
    std::map<std::string,Record> records;
    static bool hex(const std::string& value,std::size_t length) {
        return value.size()==length && value.find_first_not_of("0123456789abcdef")==std::string::npos;
    }
    static void valid(const Intent& intent) {
        if(!hex(intent.id,32)||!hex(intent.nonce,64)||!intent.sim||!intent.household)
            throw std::runtime_error("Acceptance preparation requires its exact original request and editor identity.");
    }
public:
    template<class Capture,class Prepare> const Record& Begin(const Intent& intent,Capture&& capture,Prepare&& prepare) {
        valid(intent);
        const auto prior=records.find(intent.id);
        if(prior!=records.end()) {
            if(!(prior->second.intent==intent))throw std::runtime_error("Acceptance UUID cannot adopt a replacement context.");
            return prior->second; // Never execute preparation a second time.
        }
        if(records.size()>=4096)throw std::runtime_error("Acceptance request evidence capacity is retained.");
        auto [where,inserted]=records.emplace(intent.id,Record{intent,{},"preparing",{}});
        auto& record=where->second;
        try {
            const auto before=capture();
            record.authoritativeHarvest=prepare(); // Explicit once-only owner harvest, or plain-room preview cleanup.
            const auto after=capture();
            if(before.identity.empty() || before.scalar.empty() || after.scalar.empty() || after.complete.empty() || before.identity!=after.identity || !after.previewSettled)
                throw std::runtime_error("Acceptance preparation changed its editor/other-owner identity or left a preview open.");
            record.prepared=after;record.state="prepared";
        } catch(const std::exception& error) {record.state="refused";record.error=error.what();}
        return record;
    }
    template<class Capture,class Probe> Observation Poll(const Intent& intent,Capture&& capture,Probe&& probe) {
        valid(intent);
        const auto where=records.find(intent.id);
        if(where==records.end() || !(where->second.intent==intent))
            throw std::runtime_error("Readiness requires its exact original prepared request.");
        auto& record=where->second;
        if(record.state!="prepared")throw std::runtime_error("Acceptance preparation retained a refusal; it cannot replay.");
        try {
            auto current=probe();
            if(current.scalar!=record.prepared.scalar || current.identity!=record.prepared.identity || !current.previewSettled)
                throw std::runtime_error("Acceptance editor/owner/roster changed during readiness wait.");
            // Busy frames never clone or serialize the current appearance. A
            // genuine-ready transition must prove every complete byte before
            // it can authorize Save, including same-generation opaque edits.
            if(current.busy || current.phase!=0)return current;
            current=capture();
            if(current.scalar!=record.prepared.scalar || current.complete!=record.prepared.complete || !current.previewSettled)
                throw std::runtime_error("Acceptance editor/appearance changed before readiness authorization.");
            return current;
        } catch(const std::exception& error) {record.state="refused";record.error=error.what();throw;}
    }
    void Cancel(const Intent& intent) {
        valid(intent);const auto found=records.find(intent.id);
        if(found==records.end() || !(found->second.intent==intent))throw std::runtime_error("Cancellation lacks its exact original prepared request.");
        if(found->second.state=="consumed")return;
        found->second.state="refused";found->second.error="Prepared acceptance was cancelled before native save; never replayed.";
    }
    const Intent& IntentForSave(const std::string& id,const std::string& nonce) const {
        const auto found=records.find(id);
        if(found==records.end() || found->second.intent.nonce!=nonce)
            throw std::runtime_error("Native save lacks its exact prepared request/nonce.");
        return found->second.intent;
    }
    template<class Capture,class Probe> const Record& Consume(const Intent& intent,Capture&& capture,Probe&& probe) {
        const auto current=Poll(intent,capture,probe);
        if(!current.previewSettled || current.busy || current.phase!=0) {
            auto& refused=records.at(intent.id);refused.state="refused";refused.error="Native save is still genuinely busy; no attempt authorized.";
            throw std::runtime_error(refused.error);
        }
        auto& record=records.at(intent.id);
        record.state="consumed"; // Before the first native save; never reusable.
        return record;
    }
};
inline bool Ready(const Observation& value) noexcept {return value.previewSettled && !value.busy && value.phase==0;}
}
