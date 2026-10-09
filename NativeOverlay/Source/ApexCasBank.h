#pragma once
#include "ApexUiData.h"
#include "ApexOwnerCommand.h"
#include <map>
#include <set>

namespace td1::ui {
inline bool BankHash(const Json& value) {
    if (!value.is_string()) return false;
    const auto text = value.get<std::string>();
    return text.size() == 64 && text.find_first_not_of("0123456789abcdef") == std::string::npos;
}
inline bool BankLane(const Json& value) {
    if (!value.is_string()) return false;
    const auto text = value.get<std::string>();
    if (text.empty() || text.size() > 10 || text[0] == '0' || text.find_first_not_of("0123456789") != std::string::npos) return false;
    try { const auto number = std::stoull(text); return number < (1ULL << 32) && (number & (number - 1)) == 0; }
    catch (...) { return false; }
}
inline bool BankFingerprint(const Json& row) {
    if (!row.is_object() || !row.contains("appearance_sha256") || !BankHash(row["appearance_sha256"]) ||
        !row.contains("field_sha256") || !row["field_sha256"].is_object() || row["field_sha256"].empty() || row["field_sha256"].size() > 128 ||
        !row.contains("readable_fields") || !row["readable_fields"].is_array() || row["readable_fields"].size() != row["field_sha256"].size()) return false;
    std::set<std::string> names;
    for (const auto& name : row["readable_fields"]) {
        if (!name.is_string() || name.get<std::string>().empty() || name.get<std::string>().size() > 128 ||
            !names.insert(name.get<std::string>()).second || !row["field_sha256"].contains(name.get<std::string>()) ||
            !BankHash(row["field_sha256"][name.get<std::string>()])) return false;
    }
    return true;
}
inline bool BankEvidence(const Json& reply) {
    if (!reply.is_object() || reply.value("lane_change_evidence_available", Json(false)) != true ||
        reply.value("evidence_establishes_edit_intent", Json(true)) != false || !reply.contains("changed_lanes") ||
        !reply["changed_lanes"].is_array() || !reply.contains("lane_change_evidence") ||
        !reply["lane_change_evidence"].is_array() || reply["lane_change_evidence"].empty() || reply["lane_change_evidence"].size() > 32) return false;
    std::set<std::string> declared, observed, all;
    for (const auto& lane : reply["changed_lanes"]) {
        if (!BankLane(lane) || !declared.insert(lane.get<std::string>()).second) return false;
    }
    for (const auto& row : reply["lane_change_evidence"]) {
        if (!row.is_object() || !row.contains("lane") || !BankLane(row["lane"]) || !all.insert(Scalar(row,"lane")).second ||
            !row.contains("changed") || !row["changed"].is_boolean() || !row.contains("changed_fields") ||
            !row["changed_fields"].is_array() || row["changed_fields"].size() > 128 ||
            !row.contains("before_fingerprint") || !BankFingerprint(row["before_fingerprint"]) ||
            !row.contains("returned_fingerprint") || !BankFingerprint(row["returned_fingerprint"])) return false;
        const auto& before = row["before_fingerprint"]; const auto& after = row["returned_fingerprint"];
        std::set<std::string> fields, actual;
        for (const auto& field : row["changed_fields"]) {
            if (!field.is_string() || !fields.insert(field.get<std::string>()).second) return false;
        }
        for (const auto& source : {before["field_sha256"], after["field_sha256"]}) for (auto it=source.begin(); it!=source.end(); ++it) {
            const auto& name=it.key();
            if (!before["field_sha256"].contains(name) || !after["field_sha256"].contains(name) ||
                before["field_sha256"][name] != after["field_sha256"][name]) actual.insert(name);
        }
        const bool changed = before["appearance_sha256"] != after["appearance_sha256"];
        if (fields != actual || row["changed"] != changed || changed != !actual.empty()) return false;
        if (changed) observed.insert(Scalar(row,"lane"));
    }
    return declared == observed;
}

struct CasBankView {
    std::string sim, pendingHash, rawHash, planHash, phase, action, ownerId, message, reviewNonce, reviewPhase;
    uint64_t generation = 0;
    bool busy = false, unresolved = false, failed = false, statusKnown = false, blocked = true,
         currentRuntime = false, hairEnabled = false, observeAttempted = false,
         prepareAttempted = false, commitAttempted = false, localPrepared = false, clockProof = false;
    Json evidence = Json::object(), lastReply = Json::object(), lastFailure = Json::object();
    std::map<std::string,std::string> choices;
};
inline bool BankCurrent(const CasBankView& state, const std::string& sim, uint64_t generation) {
    return state.sim == sim && state.generation == generation && ExactUint64Identity(Json(sim));
}
inline bool BankIdle(const CasBankView& state) { return !state.busy && !state.unresolved && !state.failed; }
inline bool BankCanBegin(const CasBankView& state) {
    return BankIdle(state) && state.statusKnown && !state.blocked && (state.phase.empty() || state.phase == "completed");
}
inline bool BankCanObserve(const CasBankView& state) {
    // Only the Source-certified observed branch may reopen a clock-only
    // review. It reuses durable raw owners and cannot repeat their capture.
    const bool reopen = state.phase=="observed" && !state.clockProof &&
        (state.reviewPhase=="idle" || state.reviewPhase=="observed" || state.reviewPhase=="completed") &&
        BankHash(Json(state.rawHash)) && CasRequestIdentity(Json(state.reviewNonce));
    return BankIdle(state) && state.currentRuntime && BankHash(Json(state.pendingHash)) &&
        ((state.phase=="captured" && !state.observeAttempted) || reopen);
}
inline bool BankCanPrepare(const CasBankView& state) {
    if (!BankIdle(state) || !state.currentRuntime || !state.clockProof || !CasRequestIdentity(Json(state.reviewNonce)) || state.phase != "observed" || state.prepareAttempted ||
        !BankHash(Json(state.pendingHash)) || !BankHash(Json(state.rawHash)) || !BankEvidence(state.evidence) ||
        state.choices.size() != state.evidence["changed_lanes"].size()) return false;
    for (const auto& lane : state.evidence["changed_lanes"]) {
        const auto found = state.choices.find(lane.get<std::string>());
        if (found == state.choices.end() || (found->second != "accept-returned" && found->second != "restore-original")) return false;
    }
    return true;
}
inline bool BankCanCommit(const CasBankView& state) {
    return BankIdle(state) && state.currentRuntime && state.clockProof && CasRequestIdentity(Json(state.reviewNonce)) && state.localPrepared && state.phase == "planned" &&
        !state.commitAttempted && BankHash(Json(state.pendingHash)) && BankHash(Json(state.planHash));
}
inline bool BankChoiceCurrent(const CasBankView& current, const CasBankView& rendered) {
    return BankCurrent(current,rendered.sim,rendered.generation) && BankIdle(current) &&
        current.phase=="observed" && rendered.phase=="observed" && !current.prepareAttempted && !current.localPrepared &&
        current.pendingHash==rendered.pendingHash && current.rawHash==rendered.rawHash && current.reviewNonce==rendered.reviewNonce &&
        BankHash(Json(current.pendingHash)) && BankHash(Json(current.rawHash));
}
inline const char* BankRoute(const std::string& action) {
    if (action=="cas_bank_status") return "cas_bank_ui_status";
    if (action=="cas_bank_observe") return "cas_bank_ui_review";
    if (action=="cas_bank_prepare") return "cas_bank_ui_prepare";
    if (action=="cas_bank_commit") return "cas_bank_ui_commit";
    return action=="cas_bank_begin" ? "cas_bank_begin" : "";
}
inline bool BankRequest(const CasBankView& state, const std::string& action, Json& argument) {
    argument = nullptr;
    if (state.busy || state.unresolved) return false;
    // A terminal refusal permits inspection, never automatic mutation replay.
    if (action == "cas_bank_status") return true;
    if (!BankIdle(state)) return false;
    if (action == "cas_bank_begin") return BankCanBegin(state);
    if (action == "cas_bank_observe" && BankCanObserve(state)) {
        argument = {{"expected_pending_sha256",state.pendingHash}}; return true;
    }
    if (action == "cas_bank_prepare" && BankCanPrepare(state)) {
        Json rows=Json::array();
        for (const auto& lane : state.evidence["changed_lanes"]) rows.push_back({{"lane",lane},{"action",state.choices.at(lane.get<std::string>())}});
        argument={{"expected_pending_sha256",state.pendingHash},{"expected_raw_return_sha256",state.rawHash},
            {"review_nonce",state.reviewNonce},{"dispositions",rows}}; return true;
    }
    if (action == "cas_bank_commit" && BankCanCommit(state)) {
        argument={{"expected_pending_sha256",state.pendingHash},{"expected_plan_sha256",state.planHash},{"review_nonce",state.reviewNonce}}; return true;
    }
    return false;
}
inline void BankSubmitted(CasBankView& state, const std::string& action) {
    state.busy=true; state.action=action; state.ownerId.clear(); state.message="One owner request queued; awaiting its exact result.";
    if (action=="cas_bank_observe") state.observeAttempted=true;
    if (action=="cas_bank_prepare") state.prepareAttempted=true;
    if (action=="cas_bank_commit") state.commitAttempted=true;
}
inline bool BankApply(CasBankView& state, const std::string& sim, uint64_t generation,
                      const std::string& action, const Json& reply) {
    if (!BankCurrent(state,sim,generation) || action != state.action) return false;
    const auto id=Scalar(reply,"request_id");
    if (!state.ownerId.empty() && state.ownerId != id) return false;
    state.lastReply=reply;
    if (Scalar(reply,"state")=="rejected" && reply.value("ok",Json(nullptr))==false &&
        !reply.contains("request_id") && !reply.contains("request_state") && !reply.contains("result")) {
        state.busy=false; state.lastFailure=reply; state.message=Scalar(reply,"message");
        // No owner was accepted. Permit a new explicit request, never an
        // automatic retry or a guessed rejection after transport failure.
        if (action=="cas_bank_observe") state.observeAttempted=false;
        if (action=="cas_bank_prepare") state.prepareAttempted=false;
        if (action=="cas_bank_commit") state.commitAttempted=false;
        return false;
    }
    if (CasRequestIdentity(Json(id))) state.ownerId=id;
    const auto requestState=Scalar(reply,"request_state");
    if (!CasRequestIdentity(Json(id)) || (requestState!="completed" && requestState!="failed" && requestState!="cancelled") ||
        !OwnerResultMatchesState(reply,requestState)) {
        state.busy=true; state.unresolved=true; state.message="Outcome unresolved. Check the retained owner UUID; do not submit this operation again."; return false;
    }
    state.busy=false; state.unresolved=false;
    if (reply["ok"] != true) { state.failed=true; state.lastFailure=reply; state.message=Scalar(reply,"message"); return false; }
    auto refuse=[&]() { state.failed=true; state.lastFailure=reply; state.message="Owner receipt lacks exact typed transaction evidence. No mutation is enabled."; return false; };
    const auto pending=Scalar(reply,"expected_pending_sha256");
    if (action=="cas_bank_status") {
        if (!reply.contains("blocked") || !reply["blocked"].is_boolean() ||
            !reply.contains("legacy_pending_not_converted") || !reply["legacy_pending_not_converted"].is_boolean() ||
            !reply.contains("clock_proof_validated") || !reply["clock_proof_validated"].is_boolean() ||
            !CasRequestIdentity(reply.value("review_nonce",Json(nullptr))) ||
            !reply.contains("review_state") || !reply["review_state"].is_string() ||
            Scalar(reply,"review_state").empty() || Scalar(reply,"review_state").size()>64) return refuse();
        const auto phase=Scalar(reply,"phase");
        if (!pending.empty() && !BankHash(Json(pending))) return refuse();
        const bool newEpoch = pending != state.pendingHash;
        const bool priorFailure = state.failed;
        if (newEpoch) {
            state.choices.clear(); state.localPrepared=false; state.clockProof=false;
            state.reviewNonce.clear(); state.reviewPhase.clear();
            state.lastFailure=Json::object();
            state.observeAttempted=false; state.prepareAttempted=false; state.commitAttempted=false;
        }
        state.statusKnown=true; state.blocked=reply["blocked"].get<bool>(); state.phase=phase; state.pendingHash=pending;
        if (!pending.empty() && (!reply.contains("current_runtime") || !reply["current_runtime"].is_boolean() ||
            !reply.contains("hair_policy_enabled") || !reply["hair_policy_enabled"].is_boolean())) return refuse();
        state.currentRuntime=reply.value("current_runtime",Json(false))==true;
        state.hairEnabled=reply.value("hair_policy_enabled",Json(false))==true;
        state.clockProof=reply["clock_proof_validated"].get<bool>();
        const auto nonce=Scalar(reply,"review_nonce");
        if (nonce != state.reviewNonce) { state.choices.clear(); state.localPrepared=false; }
        state.reviewNonce=nonce; state.reviewPhase=Scalar(reply,"review_state");
        if (!state.reviewNonce.empty() && !CasRequestIdentity(Json(state.reviewNonce))) return refuse();
        if (state.clockProof && !CasRequestIdentity(Json(state.reviewNonce))) return refuse();
        const auto plan=Scalar(reply,"plan_sha256");
        if (plan != state.planHash) state.localPrepared=false;
        state.planHash=plan; state.rawHash=Scalar(reply,"raw_return_sha256");
        if (BankEvidence(reply)) state.evidence=reply;
        else { state.evidence=Json::object(); state.choices.clear(); }
        if ((!phase.empty() && !BankHash(Json(pending))) || (!plan.empty() && !BankHash(Json(plan))) ||
            (!state.rawHash.empty() && !BankHash(Json(state.rawHash)))) return refuse();
        if (state.clockProof && (!state.currentRuntime || !BankHash(Json(state.rawHash)) ||
            (phase!="observed" && phase!="planned" && phase!="completed"))) return refuse();
        state.failed=(!newEpoch && priorFailure) || reply["legacy_pending_not_converted"]==true ||
            (phase!="" && phase!="captured" && phase!="observed" && phase!="planned" && phase!="completed");
    } else {
        if (!BankHash(Json(pending)) || (action!="cas_bank_begin" && pending != state.pendingHash)) return refuse();
        state.pendingHash=pending; state.currentRuntime=true; state.blocked=true;
        if (action=="cas_bank_begin") {
            if (reply.value("native_appearance_written",Json(nullptr))!=false ||
                reply.value("old_bank_restored",Json(nullptr))!=false ||
                !reply.contains("hair_policy_enabled") || !reply["hair_policy_enabled"].is_boolean() ||
                !reply.contains("native_owner_lanes") || !reply["native_owner_lanes"].is_array() ||
                reply["native_owner_lanes"].empty() || reply["native_owner_lanes"].size()>32) return refuse();
            std::set<std::string> owners;
            for (const auto& lane : reply["native_owner_lanes"])
                if (!BankLane(lane) || !owners.insert(lane.get<std::string>()).second) return refuse();
            if (!owners.count(Scalar(reply,"lane"))) return refuse();
            state.phase="captured"; state.evidence=Json::object(); state.choices.clear(); state.rawHash.clear(); state.planHash.clear();
            state.observeAttempted=false; state.prepareAttempted=false; state.commitAttempted=false; state.clockProof=false; state.localPrepared=false;
            state.reviewNonce.clear(); state.reviewPhase.clear();
            state.hairEnabled=reply.value("hair_policy_enabled",Json(false))==true;
        } else if (action=="cas_bank_observe") {
            // The canonical phone actor starts a bounded normal-speed/Pause
            // probe. Its submission ACK is not returned-owner evidence.
            if (!reply.contains("pending") || !reply["pending"].is_boolean() ||
                !CasRequestIdentity(reply.value("review_nonce",Json(nullptr))) ||
                (reply["pending"]==false && reply.value("clock_proof_validated",Json(nullptr))!=true)) return refuse();
            state.reviewNonce=Scalar(reply,"review_nonce"); state.reviewPhase=reply["pending"]==true ? "settling-live" : "ready-status";
            state.phase="settling-live"; state.clockProof=false;
        } else if (action=="cas_bank_prepare") {
            if (!BankHash(reply.value("plan_sha256",Json(nullptr))) || reply.value("all_changed_lanes_have_explicit_intent",Json(false))!=true ||
                reply.value("clock_proof_validated",Json(nullptr))!=true || Scalar(reply,"review_nonce")!=state.reviewNonce ||
                reply.value("native_write_attempted",Json(true))!=false || !reply.contains("changed_lanes") ||
                reply["changed_lanes"] != state.evidence["changed_lanes"]) return refuse();
            Json accepted=Json::array(); for (const auto& lane:state.evidence["changed_lanes"])
                if (state.choices.at(lane.get<std::string>())=="accept-returned") accepted.push_back(lane);
            if (reply.value("accepted_lanes",Json(nullptr)) != accepted) return refuse();
            state.planHash=Scalar(reply,"plan_sha256"); state.localPrepared=true; state.phase="planned";
            state.reviewPhase=Scalar(reply,"review_state");
        } else if (action=="cas_bank_commit") {
            if (Scalar(reply,"plan_sha256") != state.planHash || reply.value("bank_committed",Json(false))!=true ||
                reply.value("clock_proof_validated",Json(nullptr))!=true || Scalar(reply,"review_nonce")!=state.reviewNonce ||
                reply.value("all_native_owners_verified",Json(false))!=true || reply.value("save_reload_verified",Json(true))!=false) return refuse();
            state.phase="completed"; state.blocked=false; state.localPrepared=false; state.reviewPhase=Scalar(reply,"review_state");
        }
    }
    state.message=state.failed ? "Inspection completed; this transaction remains blocked. The earlier failure receipt is retained below." :
        "Exact owner result received. Appearance completion and durable game-save reload are separate evidence.";
    return true;
}
}
