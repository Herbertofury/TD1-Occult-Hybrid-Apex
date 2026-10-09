#pragma once
#include "ApexUiData.h"

namespace td1::ui {
enum class OwnerReply { Invalid, Pending, Terminal, Rejected };

inline bool OwnerIdentityMatches(const Json& reply, const std::string& id) {
    return CasRequestIdentity(Json(id)) && reply.is_object() && reply.contains("request_id") &&
        CasRequestIdentity(reply["request_id"]) && Scalar(reply, "request_id") == id;
}

inline bool OwnerResultMatchesState(const Json& result, const std::string& state) {
    return result.is_object() && result.contains("ok") && result["ok"].is_boolean() &&
        result["ok"] == (state == "completed");
}

inline bool OwnerCommandUnresolved(const Json& reply) {
    if (!reply.is_object() || !reply.contains("request_id") || !CasRequestIdentity(reply["request_id"])) return false;
    const auto state = Scalar(reply, "request_state");
    return state == "pending" || state == "running" || state == "unknown";
}

inline OwnerReply ReadOwnerSubmission(const Json& reply, const std::string& id) {
    if (!CasRequestIdentity(Json(id)) || !reply.is_object()) return OwnerReply::Invalid;
    // The backend rejects before accepting an owner identity. An accepted
    // receipt or completion must never be mistaken for that safe rejection.
    if (Scalar(reply, "state") == "rejected" && reply.contains("ok") && reply["ok"] == false &&
        !reply.contains("request_id") && !reply.contains("request_state") && !reply.contains("result"))
        return OwnerReply::Rejected;
    if (!OwnerIdentityMatches(reply, id))
        return OwnerReply::Invalid;
    const auto state=Scalar(reply, "request_state");
    if (state=="pending" || state=="running" || state=="unknown") return OwnerReply::Pending;
    if ((state=="completed" || state=="failed" || state=="cancelled") && OwnerResultMatchesState(reply, state))
        return OwnerReply::Terminal;
    return OwnerReply::Invalid;
}

inline OwnerReply ReadOwnerCompletion(const Json& reply, const std::string& id, Json& result) {
    if (!OwnerIdentityMatches(reply, id))
        return OwnerReply::Invalid;
    const auto state=Scalar(reply,"state");
    if (state=="pending" || state=="running" || state=="unknown") return OwnerReply::Pending;
    if (state!="completed" && state!="failed" && state!="cancelled") return OwnerReply::Invalid;
    if (reply.contains("result") && reply["result"].is_object()) {
        if (!OwnerResultMatchesState(reply["result"], state)) return OwnerReply::Invalid;
        result=reply["result"];
    }
    else if (state=="cancelled" && reply.contains("ok") && reply["ok"] == false)
        result={{"ok",false},{"message",Scalar(reply,"message")}};
    else return OwnerReply::Invalid;
    result["request_id"]=id; result["request_state"]=state;
    return OwnerReply::Terminal;
}

struct OwnerObservation {
    std::string requestId, nativeRequestId, sim;
    uint64_t generation = 0, lastCheckMs = 0, retainedAtMs = 0;
    bool checking = false;
    Json lastReply = Json::object();
};

inline bool RetainOwnerObservation(OwnerObservation& retained, const Json& reply, uint64_t generation,
                                   const std::string& sim, const std::string& nativeId, uint64_t now) {
    if (!OwnerCommandUnresolved(reply) || (!retained.requestId.empty() &&
        (retained.requestId != Scalar(reply, "request_id") || retained.generation != generation || retained.sim != sim))) return false;
    if (retained.requestId.empty()) { retained = {}; retained.retainedAtMs = now; }
    retained.requestId = Scalar(reply, "request_id"); retained.generation = generation; retained.sim = sim;
    if (CasRequestIdentity(Json(nativeId))) retained.nativeRequestId = nativeId;
    retained.lastCheckMs = now; retained.checking = false; retained.lastReply = reply;
    return true;
}

inline bool OwnerObservationDue(const OwnerObservation& retained, uint64_t now, bool visible, bool explicitCheck = false) {
    const uint64_t interval = explicitCheck ? 1000 : 5000;
    return visible && CasRequestIdentity(Json(retained.requestId)) && !retained.checking &&
        now >= retained.lastCheckMs && now - retained.lastCheckMs >= interval;
}

inline std::string OwnerObservationPath(const OwnerObservation& retained) {
    return CasRequestIdentity(Json(retained.requestId)) ? "/api/requests/status?request_id=" + retained.requestId : "";
}
}
