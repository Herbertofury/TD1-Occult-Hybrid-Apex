#include "ApexCasBank.h"
#include <iostream>

using namespace td1::ui;
static const std::string pending(64,'a'), raw(64,'b'), plan(64,'c'), nonce(32,'e');
static Json Owner(Json reply, char id='d') {
    reply["request_id"]=std::string(32,id); reply["request_state"]="completed"; reply["ok"]=true; return reply;
}
static Json Finger(char appearance, char physique, char future='f') {
    return {{"appearance_sha256",std::string(64,appearance)},
        {"field_sha256",{{"physique",std::string(64,physique)},{"future_owner_field",std::string(64,future)}}},
        {"readable_fields",Json::array({"physique","future_owner_field"})}};
}
static Json Evidence() {
    return {{"lane_change_evidence_available",true},{"evidence_establishes_edit_intent",false},
        {"changed_lanes",Json::array({"1","32"})},
        {"lane_change_evidence",Json::array({
            Json{{"lane","1"},{"changed",true},{"changed_fields",Json::array({"physique"})},
                {"before_fingerprint",Finger('1','2')},{"returned_fingerprint",Finger('3','4')}},
            Json{{"lane","4"},{"changed",false},{"changed_fields",Json::array()},
                {"before_fingerprint",Finger('5','6')},{"returned_fingerprint",Finger('5','6')}},
            Json{{"lane","32"},{"changed",true},{"changed_fields",Json::array({"future_owner_field"})},
                {"before_fingerprint",Finger('7','8')},{"returned_fingerprint",Finger('9','8','e')}}})}};
}
static CasBankView Observed() {
    CasBankView state; state.sim="18446744073709551615"; state.generation=4; state.phase="observed";
    state.statusKnown=true; state.currentRuntime=true; state.clockProof=true; state.reviewNonce=nonce;
    state.reviewPhase="observed";
    state.pendingHash=pending; state.rawHash=raw; state.evidence=Evidence();
    return state;
}
int main() {
    int checks=0,failed=0;
    auto check=[&](bool ok,const char* name) { ++checks; if(!ok) { ++failed; std::cerr<<name<<'\n'; } };
    Json argument;
    auto state=Observed();
    check(BankEvidence(state.evidence),"all returned owner fields including future field are retained as evidence");
    check(!BankRequest(state,"cas_bank_prepare",argument),"missing choices cannot infer accept-all");
    state.choices["1"]="accept-returned";
    check(!BankCanPrepare(state),"one choice cannot authorize multiple changed owners");
    state.choices["32"]="restore-original";
    check(BankRequest(state,"cas_bank_prepare",argument) && argument==Json{{"expected_pending_sha256",pending},
        {"expected_raw_return_sha256",raw},{"review_nonce",nonce},{"dispositions",Json::array({Json{{"lane","1"},{"action","accept-returned"}},
            Json{{"lane","32"},{"action","restore-original"}}})}},"exact complete per-owner dispositions only");
    state.choices["4"]="accept-returned"; check(!BankCanPrepare(state),"unchanged owner cannot receive injected intent"); state.choices.erase("4");
    auto invalid=Evidence(); invalid["lane_change_evidence"][2]["changed_fields"]=Json::array();
    check(!BankEvidence(invalid),"changed field summaries must match native fingerprints");
    invalid=Evidence(); invalid["lane_change_evidence"].push_back(invalid["lane_change_evidence"][0]);
    check(!BankEvidence(invalid),"duplicate owner rejected");
    invalid=Evidence(); invalid["evidence_establishes_edit_intent"]=true;
    check(!BankEvidence(invalid),"fingerprint changes alone do not establish edit intent");
    state.phase="captured"; state.evidence=Json::object(); state.clockProof=false;
    check(BankCanObserve(state),"captured checkpoint permits one Source-owned clock review, not immediate observation");
    check(BankRequest(state,"cas_bank_observe",argument) && argument==Json{{"expected_pending_sha256",pending}},"observe supplies only pinned transaction hash");
    BankSubmitted(state,"cas_bank_observe");
    check(!BankRequest(state,"cas_bank_observe",argument),"observe cannot be queued twice");
    auto unknown=Json{{"ok",false},{"request_id",std::string(32,'d')},{"request_state","unknown"}};
    check(!BankApply(state,state.sim,4,"cas_bank_observe",unknown) && state.unresolved && state.ownerId==std::string(32,'d'),"lost receipt retains exact UUID and blocks mutations");
    auto started=Json{{"expected_pending_sha256",pending},{"pending",true},{"review_nonce",nonce},{"clock_proof_validated",false}};
    const auto prior=state.lastReply;
    check(!BankApply(state,state.sim,4,"cas_bank_observe",Owner(started,'e')) && state.lastReply==prior,"different owner completion cannot overwrite retained evidence");
    check(!BankApply(state,"22",4,"cas_bank_observe",Owner(started)),"wrong Sim rejected");
    check(!BankApply(state,state.sim,5,"cas_bank_observe",Owner(started)),"wrong selection generation rejected");
    check(BankApply(state,state.sim,4,"cas_bank_observe",Owner(started)) && !state.busy && state.phase=="settling-live" &&
        !state.clockProof && !BankCanPrepare(state),"same UUID resolves async start without claiming returned owners or clock proof");
    auto observed=Evidence(); observed.update(Json{{"expected_pending_sha256",pending},{"raw_return_sha256",raw},{"phase","observed"},
        {"current_runtime",true},{"hair_policy_enabled",false},{"blocked",true},{"legacy_pending_not_converted",false},
        {"clock_proof_validated",true},{"review_nonce",nonce},{"review_state","observed"}});
    BankSubmitted(state,"cas_bank_status");
    check(BankApply(state,state.sim,4,"cas_bank_status",Owner(observed,'e')) && state.phase=="observed" && state.clockProof,
        "canonical status supplies actual observation and positive normal/Pause proof");
    check(!BankCanObserve(state),"completed observe cannot be repeated");
    state.choices={{"1","accept-returned"},{"32","restore-original"}};
    BankSubmitted(state,"cas_bank_prepare");
    check(state.ownerId.empty(),"new operation must receive a new owner UUID");
    Json prepared={{"expected_pending_sha256",pending},{"plan_sha256",plan},{"all_changed_lanes_have_explicit_intent",true},
        {"native_write_attempted",false},{"clock_proof_validated",true},{"review_nonce",nonce},{"review_state","planned"},
        {"changed_lanes",Json::array({"1","32"})},{"accepted_lanes",Json::array({"1"})}};
    check(BankApply(state,state.sim,4,"cas_bank_prepare",Owner(prepared,'e')) && BankCanCommit(state),"prepared receipt binds explicit user choices");
    check(BankRequest(state,"cas_bank_commit",argument) && argument==Json{{"expected_pending_sha256",pending},{"expected_plan_sha256",plan},{"review_nonce",nonce}},"commit uses exact prepared plan and actor nonce only");
    BankSubmitted(state,"cas_bank_commit");
    check(!BankCanCommit(state),"commit is one-shot before delivery");
    Json committed={{"expected_pending_sha256",pending},{"plan_sha256",plan},{"bank_committed",true},
        {"all_native_owners_verified",true},{"save_reload_verified",false},{"clock_proof_validated",true},{"review_nonce",nonce},{"review_state","completed"}};
    check(BankApply(state,state.sim,4,"cas_bank_commit",Owner(committed,'f')) && state.phase=="completed" && !BankCanCommit(state),"native completion remains distinct from durable save/reload");
    auto external=Observed(); external.phase="planned"; external.planHash=plan;
    check(!BankCanCommit(external),"status from external prepared plan cannot manufacture local commit authority");
    auto mismatch=Observed(); mismatch.choices={{"1","accept-returned"},{"32","restore-original"}}; BankSubmitted(mismatch,"cas_bank_prepare");
    auto bad=prepared; bad["accepted_lanes"]=Json::array({"32"});
    check(!BankApply(mismatch,mismatch.sim,4,"cas_bank_prepare",Owner(bad)) && mismatch.failed && !BankCanCommit(mismatch),"prepared acceptance mismatch fails closed");
    check(BankRequest(mismatch,"cas_bank_status",argument) && argument.is_null(),"terminal failure can be inspected without mutation replay");
    BankSubmitted(mismatch,"cas_bank_status");
    Json status={{"blocked",true},{"legacy_pending_not_converted",false},{"phase","observed"},
        {"expected_pending_sha256",pending},{"raw_return_sha256",raw},{"plan_sha256",nullptr},
        {"current_runtime",true},{"hair_policy_enabled",false},{"clock_proof_validated",true},{"review_nonce",nonce},{"review_state","observed"}};
    status.update(Evidence());
    check(BankApply(mismatch,mismatch.sim,4,"cas_bank_status",Owner(status,'e')) && mismatch.failed && !BankCanPrepare(mismatch),"inspection does not clear failed same-epoch preparation");
    auto begin=CasBankView{}; begin.sim="11"; begin.generation=2; BankSubmitted(begin,"cas_bank_status");
    check(BankApply(begin,"11",2,"cas_bank_status",Owner(Json{{"blocked",false},{"legacy_pending_not_converted",false},
        {"clock_proof_validated",false},{"review_nonce",nonce},{"review_state","idle"}})) &&
        BankRequest(begin,"cas_bank_begin",argument) && argument.is_null(),"fresh status enables no-payload checkpoint");
    BankSubmitted(begin,"cas_bank_begin");
    auto begun=Json{{"expected_pending_sha256",pending},{"native_appearance_written",false},{"old_bank_restored",false},
        {"hair_policy_enabled",false},{"native_owner_lanes",Json::array({"1","4","32"})},{"lane","1"}};
    check(BankApply(begin,"11",2,"cas_bank_begin",Owner(begun,'e')) && begin.phase=="captured","begin requires native-original retention receipt");
    auto old=begin; BankSubmitted(old,"cas_bank_status"); status["phase"]="captured"; status["current_runtime"]=false; status["clock_proof_validated"]=false;
    check(BankApply(old,"11",2,"cas_bank_status",Owner(status,'f')) && !BankCanObserve(old),"prior-runtime checkpoint cannot observe current owners");
    auto legacy=CasBankView{}; legacy.sim="11"; legacy.generation=2; BankSubmitted(legacy,"cas_bank_status");
    check(BankApply(legacy,"11",2,"cas_bank_status",Owner(Json{{"blocked",true},{"legacy_pending_not_converted",true},
        {"clock_proof_validated",false},{"review_nonce",nonce},{"review_state","idle"}})) &&
        legacy.failed && !BankCanBegin(legacy),"legacy pending originals require explicit recovery");
    auto typed=CasBankView{}; typed.sim="11"; typed.generation=2; BankSubmitted(typed,"cas_bank_status");
    auto wrongType=status; wrongType["current_runtime"]=1;
    check(!BankApply(typed,"11",2,"cas_bank_status",Owner(wrongType)) && typed.failed,"boolean runtime authority cannot be numeric");
    auto stale=Observed(); const auto rendered=stale;
    check(BankChoiceCurrent(stale,rendered),"rendered choice belongs to exact observed epoch");
    stale.pendingHash=std::string(64,'d'); check(!BankChoiceCurrent(stale,rendered),"new same-Sim pending epoch rejects old rendered choice");
    stale=rendered; stale.rawHash=std::string(64,'d'); check(!BankChoiceCurrent(stale,rendered),"new raw observation rejects old rendered choice");
    stale=rendered; stale.reviewNonce=std::string(32,'f'); check(!BankChoiceCurrent(stale,rendered),"new actor nonce rejects old rendered intent");
    auto unverified=Observed(); unverified.clockProof=false; unverified.choices={{"1","accept-returned"},{"32","restore-original"}};
    check(BankRequest(unverified,"cas_bank_observe",argument) && argument==Json{{"expected_pending_sha256",pending}},
        "CLI-observed return without phone proof can reopen clock review without replaying observation");
    unverified.observeAttempted=true;
    check(BankCanObserve(unverified),"durable observed return can explicitly reverify clock after an earlier review");
    for (const auto* blockedPhase:{"blocked","settling-live","observing","preparing","committing","unknown"}) {
        unverified.reviewPhase=blockedPhase;
        check(!BankCanObserve(unverified),"blocked or in-flight Source review cannot be reopened");
    }
    unverified.reviewPhase="observed";
    check(!BankCanPrepare(unverified),"complete decisions without canonical clock proof cannot prepare");
    unverified.phase="planned"; unverified.localPrepared=true; unverified.planHash=plan;
    check(!BankCanCommit(unverified),"prepared plan without current clock proof cannot commit");
    auto rejected=Observed(); rejected.choices={{"1","accept-returned"},{"32","restore-original"}};
    BankSubmitted(rejected,"cas_bank_prepare");
    check(!BankApply(rejected,rejected.sim,4,"cas_bank_prepare",Json{{"ok",false},{"state","rejected"},{"message","No HTTP submitted"}}) &&
        !rejected.busy && !rejected.unresolved && !rejected.prepareAttempted && BankCanPrepare(rejected),
        "proven rejection before owner acceptance permits new explicit request without automatic replay");
    check(std::string(BankRoute("cas_bank_status"))=="cas_bank_ui_status" &&
        std::string(BankRoute("cas_bank_observe"))=="cas_bank_ui_review" &&
        std::string(BankRoute("cas_bank_prepare"))=="cas_bank_ui_prepare" &&
        std::string(BankRoute("cas_bank_commit"))=="cas_bank_ui_commit" &&
        std::string(BankRoute("cas_bank_begin"))=="cas_bank_begin","F11 mutations use Source clock-gated adapters");
    auto nonceStatus=Observed(); nonceStatus.choices={{"1","accept-returned"},{"32","restore-original"}};
    nonceStatus.localPrepared=true; BankSubmitted(nonceStatus,"cas_bank_status");
    auto replacement=observed; replacement["review_nonce"]=std::string(32,'f');
    check(BankApply(nonceStatus,nonceStatus.sim,4,"cas_bank_status",Owner(replacement)) && nonceStatus.choices.empty() &&
        !nonceStatus.localPrepared,"new Source review nonce invalidates all older UI intent");
    std::cout<<checks<<" checks, "<<failed<<" failures\n"; return failed?1:0;
}
