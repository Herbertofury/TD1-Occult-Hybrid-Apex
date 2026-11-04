#pragma once
#include "ApexCasBank.h"

namespace td1::ui {
// This is the F11 drawer's model, not an independent appearance writer. An
// expected view binds unsent choices as well as the receiver-owned identities.
inline Json BankControlView(const CasBankView& state) {
    return {{"sim_id",state.sim},{"generation",state.generation},{"phase",state.phase},
        {"pending_sha256",state.pendingHash},{"raw_return_sha256",state.rawHash},{"plan_sha256",state.planHash},
        {"review_nonce",state.reviewNonce},{"review_phase",state.reviewPhase},{"owner_id",state.ownerId},
        {"busy",state.busy},{"unresolved",state.unresolved},{"failed",state.failed},{"status_known",state.statusKnown},
        {"current_runtime",state.currentRuntime},{"clock_proof",state.clockProof},{"hair_enabled",state.hairEnabled},
        {"hair_inventory_sha256",state.hairInventoryHash},{"hair_inventory",state.hairInventory},
        {"hair_targets",state.hairTargets},{"choices",state.choices},{"evidence",state.evidence},
        {"observe_attempted",state.observeAttempted},{"prepare_attempted",state.prepareAttempted},
        {"commit_attempted",state.commitAttempted},{"local_prepared",state.localPrepared},
        {"can_observe",BankCanObserve(state)},{"can_prepare",BankCanPrepare(state)},{"can_commit",BankCanCommit(state)}};
}
inline bool BankControlExpected(const CasBankView& state, const Json& expected) {
    return expected.is_object() && expected==BankControlView(state);
}
inline bool BankControlRoster(const Json& receipt, const std::string& sim) {
    if (!ExactUint64Identity(Json(sim)) || !receipt.is_object() || receipt.value("ok",Json(nullptr))!=true ||
        !CasRequestIdentity(receipt.value("request_id",Json(nullptr))) ||
        receipt.value("request_state",Json(nullptr))!="completed" ||
        !receipt.contains("sims") || !receipt["sims"].is_array() || receipt["sims"].empty() || receipt["sims"].size()>16384) return false;
    std::set<std::string> ids;
    for (const auto& row:receipt["sims"]) {
        if (!row.is_object() || !ExactUint64Identity(row.value("id",Json(nullptr))) ||
            !ids.insert(Scalar(row,"id")).second) return false;
    }
    return ids.count(sim)!=0;
}
// Returns the existing queue action, or changes only the same local choices
// used by ImGui. A refusal cannot partially update a choice or hair selection.
inline bool BankControlIntent(CasBankView& current, const Json& request, std::string& queueAction) {
    queueAction.clear();
    if (!request.is_object() || request.value("operation",Json(nullptr))!="cas-review" ||
        !request.contains("expected") || !BankControlExpected(current,request["expected"])) return false;
    const auto action=Scalar(request,"action");
    const size_t base=3;
    if (action=="refresh" || action=="observe" || action=="prepare" || action=="commit") {
        if (request.size()!=base) return false;
        const auto route=action=="refresh"?"cas_bank_status":action=="observe"?"cas_bank_observe":
            action=="prepare"?"cas_bank_prepare":"cas_bank_commit";
        Json argument; if (!BankRequest(current,route,argument)) return false;
        queueAction=route; return true;
    }
    if (!BankChoiceCurrent(current,current) || !current.currentRuntime || !current.clockProof ||
        !CasRequestIdentity(Json(current.reviewNonce)) || !BankEvidence(current.evidence)) return false;
    const auto lane=Scalar(request,"lane"); bool offered=false;
    for (const auto& changed:current.evidence["changed_lanes"]) if (changed==lane) offered=true;
    if (!offered) return false;
    if (action=="choice") {
        if (request.size()!=base+2) return false;
        const auto choice=Scalar(request,"choice");
        if (choice!="accept-returned" && choice!="restore-original" && choice!="clear") return false;
        if (choice=="clear") current.choices.erase(lane); else current.choices[lane]=choice;
        if (choice!="accept-returned") current.hairTargets.erase(lane);
        return true;
    }
    const auto rendered=current;
    if (action=="hair-none") return request.size()==base+1 && BankSetHairNone(current,rendered,lane);
    if (action=="hair") {
        if (request.size()!=base+3 || !request.contains("outfit") || !request.contains("selected") ||
            !request["selected"].is_boolean()) return false;
        return BankSetHairTarget(current,rendered,lane,request["outfit"],request["selected"].get<bool>());
    }
    return false;
}
}
