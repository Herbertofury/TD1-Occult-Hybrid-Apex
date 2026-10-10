#include "ApexUiData.h"
#include "ApexStudioItems.h"
#include "ApexPartColorControls.h"
#include "ApexOwnerCommand.h"
#include "ApexCasRoom.h"
#include <iostream>

int main() {
    using namespace td1::ui;
    int failed = 0, checks = 0;
    auto check = [&](bool ok, const char* name) {
        ++checks;
        if (!ok) { std::cerr << name << '\n'; ++failed; }
    };
    const auto data = ParseObject(R"({"nested":{"sim_id":"wrong"},"sim_id":"18446744073709551615","label":"Fairy \u03bb \ud83e\uddda","logs":["literal ] and \" quote", "line\nnext"],"pending_preview":null,"ok":false,"uint64":18446744073709551615})");
    check(Scalar(data, "sim_id") == "18446744073709551615", "top-level Sim identity");
    check(Scalar(data, "label") == "Fairy \xCE\xBB \xF0\x9F\xA7\x9A", "Unicode and surrogate decoding");
    check(Scalar(data, "uint64") == "18446744073709551615", "exact uint64 metadata");
    check(Scalar(data, "pending_preview").empty(), "null preview clears selection");
    check(Scalar(data, "ok") == "false", "boolean result");
    const auto logs = Logs(data);
    check(logs.size() == 2 && logs[0] == "literal ] and \" quote" && logs[1] == "line\nnext", "quoted log delimiters");
    check(ParseObject("{\"ok\":true}").at("ok") == true, "valid object");
    check(ParseObject("{\"ok\":true} garbage").empty(), "trailing malformed response");
    check(ParseObject("{\"ok\":true").empty(), "truncated response");
    check(ParseObject("[]").empty(), "non-object response");
    std::string nested(40, '['); nested += "0"; nested += std::string(40, ']');
    check(ParseObject("{\"value\":" + nested + "}").empty(), "bounded nesting");
    check(ParseObject(std::string(kMaxOwnerJsonBytes + 1, ' ')).empty(), "bounded response bytes");
    check(ParseObject("{\"native_appearance\":\""+std::string(773174,'a')+"\"}").contains("native_appearance"), "real full-owner Studio response fits bounded transport");
    const auto boundedOwner = std::string("{\"value\":\"") + std::string(kMaxOwnerJsonBytes - 12, 'a') + "\"}";
    check(ParseObject(boundedOwner).contains("value"), "valid owner response at exact byte bound is accepted");
    check(ParseObject(boundedOwner.substr(0, boundedOwner.size() - 2) + "a\"}").empty(), "valid owner response over byte bound is rejected");
    const std::string ownerId(32,'a'); Json completed;
    check(ReadOwnerSubmission(Json{{"request_id",ownerId},{"request_state","running"}},ownerId)==OwnerReply::Pending,"owner pending receipt is not completion");
    check(ReadOwnerSubmission(Json{{"request_id",std::string(32,'b')},{"request_state","completed"}},ownerId)==OwnerReply::Invalid,"different owner submission refused");
    check(ReadOwnerCompletion(Json{{"request_id",ownerId},{"state","unknown"}},ownerId,completed)==OwnerReply::Pending,"unknown owner remains unresolved without replay");
    check(ReadOwnerCompletion(Json{{"request_id",ownerId},{"state","completed"},{"result",Json{{"ok",true},{"history_lane","exact"}}}},ownerId,completed)==OwnerReply::Terminal && completed["history_lane"]=="exact" && completed["request_id"]==ownerId && completed["request_state"]=="completed","matching owner result unwrapped with identity");
    check(ReadOwnerCompletion(Json{{"request_id",ownerId},{"state","completed"},{"result",nullptr}},ownerId,completed)==OwnerReply::Invalid,"completed owner without result refused");
    check(ReadOwnerCompletion(Json{{"request_id",std::string(32,'b')},{"state","completed"},{"result",Json::object()}},ownerId,completed)==OwnerReply::Invalid,"different owner completion refused");
    check(ReadOwnerCompletion(Json{{"request_id",ownerId},{"state","failed"},{"result",Json{{"ok",false},{"message","native refusal"}}}},ownerId,completed)==OwnerReply::Terminal && completed["ok"]==false,"native failure stays a failure");
    const Json rejected{{"ok",false},{"state","rejected"},{"message","Queue is full; no accepted command was dropped."}};
    check(ReadOwnerSubmission(rejected, ownerId)==OwnerReply::Rejected, "explicit rejection before owner acceptance is distinguished from uncertain execution");
    auto ambiguousRejection = rejected;
    ambiguousRejection["request_id"] = ownerId;
    check(ReadOwnerSubmission(ambiguousRejection, ownerId)==OwnerReply::Invalid, "rejection carrying an accepted identity is not a safe pre-submission refusal");
    ambiguousRejection = rejected; ambiguousRejection["request_state"] = "running";
    check(ReadOwnerSubmission(ambiguousRejection, ownerId)==OwnerReply::Invalid, "rejection carrying execution state remains uncertain");
    ambiguousRejection = rejected; ambiguousRejection["result"] = nullptr;
    check(ReadOwnerSubmission(ambiguousRejection, ownerId)==OwnerReply::Invalid, "rejection carrying a completion field remains uncertain");
    ambiguousRejection = rejected; ambiguousRejection["ok"] = 0;
    check(ReadOwnerSubmission(ambiguousRejection, ownerId)==OwnerReply::Invalid, "pre-submission refusal requires a typed false result");
    check(ReadOwnerSubmission(rejected, "invalid")==OwnerReply::Invalid, "invalid local owner identity cannot authorize even a rejection");
    for (const auto& state : {"completed", "failed", "cancelled"}) {
        const bool success = std::string(state) == "completed";
        const Json terminal{{"request_id",ownerId},{"request_state",state},{"ok",success}};
        check(ReadOwnerSubmission(terminal,ownerId)==OwnerReply::Terminal, "terminal submission preserves a verified boolean outcome");
        auto inconsistent = terminal; inconsistent["ok"] = !success;
        check(ReadOwnerSubmission(inconsistent,ownerId)==OwnerReply::Invalid, "terminal submission cannot contradict its execution state");
        inconsistent = terminal; inconsistent.erase("ok");
        check(ReadOwnerSubmission(inconsistent,ownerId)==OwnerReply::Invalid, "terminal submission without a verification outcome is refused");
        inconsistent = terminal; inconsistent["ok"] = success ? 1 : 0;
        check(ReadOwnerSubmission(inconsistent,ownerId)==OwnerReply::Invalid, "terminal submission outcome must be boolean");
        const Json status{{"request_id",ownerId},{"state",state},{"result",Json{{"ok",success}}}};
        check(ReadOwnerCompletion(status,ownerId,completed)==OwnerReply::Terminal && completed["ok"]==success,
            "matching terminal owner completion preserves its success or failure");
        inconsistent = status; inconsistent["result"]["ok"] = !success;
        check(ReadOwnerCompletion(inconsistent,ownerId,completed)==OwnerReply::Invalid,
            "owner completion cannot report success for a failed or cancelled action");
        inconsistent = status; inconsistent["result"] = Json::object();
        check(ReadOwnerCompletion(inconsistent,ownerId,completed)==OwnerReply::Invalid,
            "owner completion requires an explicit result verification");
    }
    check(ReadOwnerCompletion(Json{{"request_id",ownerId},{"state","cancelled"},{"ok",false},{"result",nullptr},{"message","Cancelled before execution."}},
        ownerId,completed)==OwnerReply::Terminal && completed["ok"]==false && completed["message"]=="Cancelled before execution.",
        "verified cancellation without a domain result retains its refusal reason");
    check(ReadOwnerCompletion(Json{{"request_id",ownerId},{"state","cancelled"},{"result",nullptr}},ownerId,completed)==OwnerReply::Invalid,
        "cancellation without a result needs an explicit false receipt");
    for (const auto& state : {"pending", "running", "unknown"})
        check(OwnerCommandUnresolved(Json{{"request_id",ownerId},{"request_state",state},{"ok",false},{"outcome","unresolved"}}),
            "uncertain execution retains its typed owner identity for observation and blocks new mutations");
    check(!OwnerCommandUnresolved(Json{{"request_id",ownerId},{"request_state","completed"},{"ok",true}}) &&
        !OwnerCommandUnresolved(Json{{"request_id",std::string(32,'x')},{"request_state","unknown"}}) &&
        !OwnerCommandUnresolved(Json{{"request_id",12},{"request_state","unknown"}}) && !OwnerCommandUnresolved(rejected),
        "only unresolved replies with an exact typed owner UUID reserve owner execution");
    OwnerObservation observation;
    const std::string nativeOwnerId(32, 'b');
    const Json uncertainOwner{{"request_id",ownerId},{"request_state","unknown"},{"ok",false},{"outcome","unresolved"}};
    check(RetainOwnerObservation(observation, uncertainOwner, 7, "11", nativeOwnerId, 1000) &&
        observation.requestId==ownerId && observation.nativeRequestId==nativeOwnerId && observation.sim=="11" && observation.generation==7,
        "retained owner observation preserves separate owner/native identities and original selection");
    check(OwnerObservationPath(observation)=="/api/requests/status?request_id="+ownerId,
        "owner recovery observes the exact owner identity without constructing another command submission");
    check(!OwnerObservationDue(observation,1999,true,true) && OwnerObservationDue(observation,2000,true,true) &&
        !OwnerObservationDue(observation,5999,true) && OwnerObservationDue(observation,6000,true),
        "explicit checks are throttled to one second and automatic checks to five seconds");
    check(!OwnerObservationDue(observation,6000,false) && !OwnerObservationDue(observation,999,true,true),
        "hidden views and backward clocks cannot schedule owner observation");
    observation.checking = true;
    check(!OwnerObservationDue(observation,6000,true,true), "an in-flight owner observation cannot stack more status checks");
    observation.checking = false;
    check(!RetainOwnerObservation(observation,uncertainOwner,8,"22",nativeOwnerId,2000) && observation.generation==7 && observation.sim=="11",
        "reusing a retained owner identity cannot silently change its selection ownership");
    auto otherOwner = uncertainOwner; otherOwner["request_id"] = std::string(32, 'c');
    check(!RetainOwnerObservation(observation,otherOwner,7,"11",nativeOwnerId,2000) && observation.requestId==ownerId,
        "a second uncertain owner cannot overwrite the first retained identity");
    check(!RetainOwnerObservation(observation,Json{{"request_id",ownerId},{"request_state","completed"},{"ok",true}},7,"11",nativeOwnerId,2000),
        "a terminal result is not converted back into uncertain owner execution");
    observation.requestId.clear();
    check(RetainOwnerObservation(observation,otherOwner,8,"22","",3000) && observation.nativeRequestId.empty() && observation.retainedAtMs==3000,
        "the next owner reservation does not inherit the previous native UUID or receipt age");
    const auto& first = ReadObject("{\"sim_id\":\"first\"}");
    const auto& second = ReadObject("{\"sim_id\":\"second\"}");
    check(Scalar(first, "sim_id") == "first" && Scalar(second, "sim_id") == "second", "independent status/result caches");
    const auto studio = ParseObject(R"({"history_lane":"save:sim:form","history_nodes":[{"id":"0123456789abcdef0123456789abcdef","label":"Checkpoint","time":1,"parent":null}],"outfit_inventory":[{"index":0,"category":0,"outfit_id":"18446744073709551615","parts":[{"index":0,"target":"0:7:0","label":"Hair","cas_part_hex":"FFFFFFFFFFFFFFFF","target_supported":true,"color_hex":null}]}]})");
    check(StudioDocument(studio), "actual structured Studio response");
    auto corrupt = studio;
    corrupt["history_nodes"][0]["id"] = "invalid node";
    check(!StudioDocument(corrupt), "ambiguous history identity rejected");
    corrupt = studio;
    corrupt["outfit_inventory"][0]["parts"][0]["target_supported"] = "true";
    check(!StudioDocument(corrupt), "wrong typed part eligibility rejected");
    auto stored = studio;
    stored["inspected_form_flags"] = 4u;
    stored["form_inventory"] = Json::array({{{"flags", 4u}, {"name", "Vampire"}, {"current", false},
        {"outfit_inventory", studio["outfit_inventory"]}, {"appearance_fields", Json::array({{{"name", "skin_tone"}, {"kind", "value"}, {"value", 99u}}})}}});
    stored["category_catalog"] = Json::array({{{"body_type", 21u}, {"label", "Ring"}, {"group", "Jewelry"}, {"supported", true}}});
    check(StudioDocument(stored), "inactive form and empty jewelry category transport");
    corrupt = stored; corrupt["form_inventory"][0]["current"] = "false";
    check(!StudioDocument(corrupt), "invalid inactive form owner rejected");
    corrupt = stored; corrupt["form_inventory"][0]["outfit_inventory"] = "untyped outfits";
    check(!StudioDocument(corrupt), "invalid stored outfit inventory rejected");
    corrupt = stored; corrupt["category_catalog"][0]["body_type"] = "21";
    check(!StudioDocument(corrupt), "invalid category identity rejected");
    const auto envelope = ParseObject(R"({"mccc":{"sim_id":"wrong"},"status":{"sim_id":"selected","drift_warning_count":2}})");
    check(StatusScalar(envelope, "sim_id") == "selected", "documented compact status envelope");
    check(StatusScalar(ParseObject(R"({"data":{"sim_id":"selected","drift_warning_count":2}})"), "drift_warning_count") == "2", "documented command status envelope");
    auto numeric = studio;
    numeric["color_editor"] = {{"target", "0:7:0"}, {"cas_part_id", "999"}, {"color_hex", "4000000000000000"},
        {"appearance_sha256", std::string(64, 'a')}, {"resource_sha256", std::string(64, 'b')}, {"part_name", "Part"}};
    for (const auto* name : {"hue", "saturation", "brightness", "opacity"})
        numeric["color_editor"]["channels"][name] = {{"value", 0.0}, {"min", -0.5}, {"max", 0.5}, {"step", 0.05}, {"enabled", true}};
    check(StudioDocument(numeric), "numeric color editor protocol");
    auto shiftEditor = numeric["color_editor"];
    shiftEditor["channels"]["opacity"] = {{"value", 1.0}, {"min", 0.2}, {"max", 1.0}, {"step", 0.05}, {"enabled", true}};
    td1::color::Bounds hue;
    check(td1::color::ReadBounds(shiftEditor, 0, hue), "wheel reads effective CASP hue metadata");
    double wheelValue = 0;
    check(td1::color::WheelValue(hue, 0.75, wheelValue) && wheelValue == 0.25 &&
        td1::color::WheelPosition(hue, 0.25) == 0.75f, "wheel maps only the inspected shift range");
    check(!td1::color::WheelValue(hue, -0.01, wheelValue) &&
        !td1::color::WheelValue(hue, 1.01, wheelValue), "wheel refuses out-of-range gestures");
    double quantized; int32_t signedLane;
    check(td1::color::Quantize(hue, 0.5 / 16384, quantized, signedLane) && signedLane == 1 &&
        td1::color::Quantize(hue, -0.5 / 16384, quantized, signedLane) && signedLane == -1,
        "positive and negative Q14 halves agree with native rounding");
    float shiftValues[]{0.1f, 0.0f, 0.0f, 1.0f}; bool shiftChanged[]{true, false, false, false};
    Json shiftEdits; std::string shiftRaw;
    check(td1::color::Prepare(shiftEditor, shiftValues, shiftChanged, shiftEdits, shiftRaw) &&
        shiftRaw == "4000066600000000" && shiftEdits.size() == 1 && shiftEdits.contains("hue") &&
        shiftEdits["hue"] == 1638.0 / 16384, "hue draft quantizes while preserving other exact packed lanes");
    shiftEditor["color_hex"] = "4567123456789ABC";
    check(td1::color::Prepare(shiftEditor, shiftValues, shiftChanged, shiftEdits, shiftRaw) &&
        shiftRaw == "4567066656789ABC", "unedited raw lanes retain every bit even outside current editing ranges");
    shiftValues[0] = 0.6f;
    check(!td1::color::Prepare(shiftEditor, shiftValues, shiftChanged, shiftEdits, shiftRaw), "draft refuses values outside effective CASP range");
    shiftValues[0] = 0.1f; shiftEditor["channels"]["hue"]["enabled"] = false;
    check(!td1::color::Prepare(shiftEditor, shiftValues, shiftChanged, shiftEdits, shiftRaw), "disabled hue cannot change through wheel or numeric draft");
    shiftEditor["channels"]["hue"]["enabled"] = true;
    shiftEditor["channels"]["hue"]["min"] = -3.0; shiftEditor["channels"]["hue"]["max"] = 3.0;
    td1::color::ReadBounds(shiftEditor, 0, hue); double editLow, editHigh;
    check(td1::color::EditRange(hue, editLow, editHigh) && editLow == -2.0 && editHigh == 32767.0 / 16384,
        "wheel editing intersection respects signed Q14 capacity without altering inspected bounds");
    check(!td1::color::Quantize(hue, 2.0, quantized, signedLane), "Q14 overflow cannot enter a preview");
    hue.enabled = false;
    check(!td1::color::WheelValue(hue, 0.5, wheelValue), "disabled effective channel has no wheel edit");
    shiftEditor["color_hex"] = "lowercase-invalid";
    check(!td1::color::Prepare(shiftEditor, shiftValues, shiftChanged, shiftEdits, shiftRaw), "raw preview requires exact packed hexadecimal state");
    numeric["color_editor"]["channels"]["hue"]["min"] = 1.0;
    check(!StudioDocument(numeric), "reversed slider bounds rejected");
    numeric["color_editor"]["channels"]["hue"]["min"] = -0.5;
    numeric["color_editor"]["channels"]["hue"]["value"] = "0.25";
    check(!StudioDocument(numeric), "wrong typed slider value rejected");
    auto cas = ParseObject(R"({"scope":"native-cas-client","sim":{"simId":"18446744073709551615","futurePackField":{"raw":true}},"menu_state":-2134376418,"panel_visible":true,"outfit":{"outfit_type":0,"outfit_index":1},"catalogs":[{"panel":"clothing_hair","menu_state":-2134376418,"supported":true,"items":[{"dataID":"18446744073709551615","unknownFutureField":"retained"}]},{"panel":"clothing_head_skin_details","menu_state":-2134375419,"supported":false,"items":null}]})");
    for (unsigned i = 2; i < 72; ++i) cas["catalogs"].push_back({{"panel", "mapped_panel_" + std::to_string(i)}, {"menu_state", i}, {"supported", true}, {"items", Json::array()}});
    for (auto& catalog : cas["catalogs"]) { catalog["preset_query"] = "returned-null"; catalog["preset"] = nullptr; }
    check(CasDocument(cas, "18446744073709551615"), "CAS exact Sim identity and future item fields retained");
    auto roomClient=cas;
    const std::string roomSim="18446744073709551615";
    roomClient["sim"].update(Json{{"householdId","9223372036854775817"},{"occultType",64},{"occultLayer",1}});
    roomClient["owner_pair_observation"]={{"session",3}};
    Json room={{"schema",1},{"scope","captured-cas-room-inventory"},{"sim_id",roomSim},
        {"household_id","9223372036854775817"},{"save_guid","9223372036854775823"},
        {"native_session",3},{"selected_form",64},{"selected_layer",1},{"all_captured_forms_visible",true},
        {"all_forms_editable_this_visit",false},{"membership_modified",false},{"mapping_verified",false},
        {"alternate_accept_authorized",false},{"appearance_persistence_verified",false},{"rows",Json::array()}};
    for(const auto form:{1,2,4,8,16,32,64,128}) {
        const bool paired=form==1 || form==64;
        room["rows"].push_back({{"form_flags",form},{"captured_owner_id",std::to_string(1000+form)},
            {"label","Retained form"},{"visible",true},{"selected",form==64},
            {"navigation_supported",paired},{"native_layer",paired ? Json(form==1 ? 0 : 1) : Json(nullptr)}});
    }
    check(CasRoomDocument(room,roomClient,roomSim),"CAS workspace retains all seven and future forms");
    auto invalidRoom=room;invalidRoom["native_session"]=4;
    check(!CasRoomDocument(invalidRoom,roomClient,roomSim),"CAS workspace stale native session refused");
    invalidRoom=room;invalidRoom["rows"][2]["navigation_supported"]=true;
    check(!CasRoomDocument(invalidRoom,roomClient,roomSim),"hidden native form cannot authorize navigation");
    invalidRoom=room;invalidRoom["rows"][0]["captured_owner_id"]=roomSim;
    check(!CasRoomDocument(invalidRoom,roomClient,roomSim),"CAS workspace refuses original/stored owner alias");
    invalidRoom=room;invalidRoom["rows"][0]["selected"]=true;
    check(!CasRoomDocument(invalidRoom,roomClient,roomSim),"CAS workspace selection cannot select two forms");
    invalidRoom=room;invalidRoom["rows"][2]["visible"]=false;
    check(!CasRoomDocument(invalidRoom,roomClient,roomSim),"CAS workspace cannot silently hide retained forms");
    auto vampireRoom=room, vampireClient=roomClient;
    vampireClient["sim"].update(Json{{"occultType",4},{"occultLayer",1}});
    vampireRoom.update(Json{{"selected_form",4},{"selected_layer",1},{"native_layer_selection_only",true}});
    vampireRoom["native_layers"]=Json::array();
    for(int layer=0;layer<2;++layer) vampireRoom["native_layers"].push_back({{"layer",layer},{"form_flags",4},
        {"sim_id",roomSim},{"label",layer==0 ? "Primary layer" : "Dark form"},
        {"selected",layer==1},{"navigation_supported",true}});
    for(auto& row:vampireRoom["rows"]) {
        row["selected"]=row["form_flags"]==4;row["navigation_supported"]=false;row["native_layer"]=nullptr;
    }
    check(CasRoomDocument(vampireRoom,vampireClient,roomSim),"Native Vampire kind on both layers stays distinct without Human mapping");
    auto invalidVampire=vampireRoom;invalidVampire["native_layers"][0]["sim_id"]="13";
    check(!CasRoomDocument(invalidVampire,vampireClient,roomSim),"Native layer cannot select a foreign Sim");
    invalidVampire=vampireRoom;invalidVampire["native_layers"][0]["selected"]=true;
    check(!CasRoomDocument(invalidVampire,vampireClient,roomSim),"Native layer cannot select both layers");
    auto namedCas = cas;
    namedCas["catalog_metadata_complete"] = true;
    namedCas["catalog_metadata_scope"] = "native-catalog-identities-only";
    namedCas["catalog_metadata"] = Json::array({{{"data_id", "18446744073709551615"}, {"query", "returned-value"},
        {"source", "native:GetCatalogItem"}, {"name", "Localized skin detail"}, {"name_query", "localized-title"},
        {"name_source", "native:LocKey"}, {"native_image_uri", "thumbs/cas/c_414264_l_f"},
        {"image_query", "native-uri"}, {"image_source", "native:GetCatalogItem.image"},
        {"raw_json", "{\"title\":{\"hash\":123},\"future_field\":true}"}}});
    check(CasDocument(namedCas, "18446744073709551615") &&
        Scalar(CasItemMetadata(namedCas, cas["catalogs"][0]["items"][0]), "name") == "Localized skin detail",
        "native catalog names are resolved metadata bound to exact equipped identity");
    check(namedCas["catalogs"] == cas["catalogs"], "catalog metadata never replaces raw equipped or modifier records");
    auto badNamed = namedCas; badNamed["catalog_metadata"][0]["data_id"] = "12";
    check(!CasDocument(badNamed, "18446744073709551615") && CasItemMetadata(badNamed, cas["catalogs"][0]["items"][0]).empty(),
        "another catalog identity cannot provide an equipped name");
    badNamed = namedCas; badNamed["catalog_metadata"].push_back(badNamed["catalog_metadata"][0]);
    check(!CasDocument(badNamed, "18446744073709551615"), "duplicate native annotation rejected");
    badNamed = namedCas; badNamed["catalog_metadata"][0]["name_query"] = "unavailable";
    check(!CasDocument(badNamed, "18446744073709551615"), "unresolved native names cannot substitute ID text");
    badNamed = namedCas; badNamed["catalog_metadata"][0]["image_query"] = "decoded-pixels";
    check(!CasDocument(badNamed, "18446744073709551615"), "virtual image URI cannot masquerade as extracted pixels");
    badNamed = namedCas; badNamed["catalog_metadata"][0]["raw_json"] = "{";
    check(!CasDocument(badNamed, "18446744073709551615"), "malformed raw native product refused");
    badNamed = namedCas; badNamed["catalog_metadata"][0]["raw_json"] = "{}";
    check(CasDocument(badNamed, "18446744073709551615"), "native empty raw product remains a complete record");
    check(!CasDocument(cas, "12"), "CAS selected Sim mismatch rejected");
    corrupt = cas; corrupt["catalogs"][1]["items"] = Json::array();
    check(!CasDocument(corrupt, "18446744073709551615"), "CAS unknown panel must not masquerade as empty");
    corrupt = cas; corrupt["catalogs"].push_back(corrupt["catalogs"][0]);
    check(!CasDocument(corrupt, "18446744073709551615"), "CAS duplicate category rejected");
    check(cas["sim"]["futurePackField"]["raw"] == true && cas["catalogs"][0]["items"][0]["unknownFutureField"] == "retained", "CAS validation does not project away unknown metadata");
    corrupt = cas; corrupt["sim"]["simId"] = 18446744073709551615ULL;
    check(!CasDocument(corrupt, "18446744073709551615"), "numeric Sim ID rejected instead of losing precision in CAS");
    corrupt = cas; corrupt["catalogs"].erase(corrupt["catalogs"].begin());
    check(!CasDocument(corrupt, "18446744073709551615"), "missing mapped CAS category rejected");
    corrupt = cas; corrupt["catalogs"][2]["menu_state"] = corrupt["catalogs"][0]["menu_state"];
    check(!CasDocument(corrupt, "18446744073709551615"), "duplicate CAS native menu state rejected");
    corrupt = cas; corrupt["outfit"]["outfit_index"] = -1;
    check(!CasDocument(corrupt, "18446744073709551615"), "negative CAS outfit index rejected");
    corrupt = cas; corrupt["outfit"]["outfit_index"] = 5;
    check(!CasDocument(corrupt, "18446744073709551615"), "out of range CAS outfit index rejected");
    corrupt = cas; corrupt["outfit"]["outfit_type"] = "0";
    check(!CasDocument(corrupt, "18446744073709551615"), "untyped CAS outfit category rejected");
    corrupt = cas; corrupt["menu_state"] = 18446744073709551615ULL;
    check(!CasDocument(corrupt, "18446744073709551615"), "overflow CAS menu state rejected");
    check(ExactUint64Identity(Json("18446744073709551615")) && !ExactUint64Identity(Json("18446744073709551616")) && !ExactUint64Identity(Json("012")), "exact native identity range and canonical decimal text");
    auto nextCas = cas;
    nextCas["catalogs"][0]["items"][0]["unknownFutureField"] = "updated by CAS";
    const auto refreshed = RefreshCasSelection(nextCas, "clothing_hair", cas["catalogs"][0]["items"][0]);
    check(refreshed["unknownFutureField"] == "updated by CAS", "CAS inspected item refresh uses new acknowledged raw metadata");
    nextCas["catalogs"][0]["items"] = Json::array();
    check(RefreshCasSelection(nextCas, "clothing_hair", cas["catalogs"][0]["items"][0]).empty(), "CAS removed item clears inspected selection");
    nextCas = cas; nextCas["catalogs"][0]["items"].push_back(nextCas["catalogs"][0]["items"][0]);
    check(RefreshCasSelection(nextCas, "clothing_hair", cas["catalogs"][0]["items"][0]).empty(), "CAS ambiguous duplicate identity clears inspected selection");
    nextCas = cas; nextCas["catalogs"][2]["preset_query"] = "returned-value";
    nextCas["catalogs"][2]["preset"] = {{"futurePresetField", {{"unknown", true}}}};
    check(CasDocument(nextCas, "18446744073709551615"), "CAS preset keeps unknown raw fields without requiring invented identity");
    const auto preset = RefreshCasSelection(nextCas, "mapped_panel_2", nextCas["catalogs"][2]["preset"], true);
    check(preset["futurePresetField"]["unknown"] == true, "CAS preset selection resolves complete acknowledged raw record");
    nextCas["catalogs"][2]["preset_query"] = "returned-null";
    check(!CasDocument(nextCas, "18446744073709551615"), "CAS preset query/value mismatch rejected");
    nextCas["catalogs"][2]["preset_query"] = "failed"; nextCas["catalogs"][2]["preset"] = nullptr;
    check(CasDocument(nextCas, "18446744073709551615") && RefreshCasSelection(nextCas, "mapped_panel_2", preset, true).empty(), "CAS failed preset query retained as unresolved and clears old inspected preset");
    check(StudioOverlayTab(11) == 11 && StudioOverlayTab(12) == 12, "sidecar legacy Live/bank history and equipped tabs preserved");
    check(StudioOverlayTab(13) == 11 && StudioOverlayTab(14) == 12, "sidecar native CAS view requests map to existing rendered history/equipped tabs");
    check(StudioOverlayTab(2) == -1 && StudioOverlayTab(3) == -1 && StudioOverlayTab(15) == -1, "sidecar rejects undocumented tab identities");
    check(static_cast<uint32_t>(MetricHandleBits(0xF1234567ULL)) == 0xF1234567U, "native HWND diagnostic preserves high-bit int32 identity");
    check(static_cast<uint32_t>(MetricHandleBits(0xFFFFFFFFF1234567ULL)) == 0xF1234567U && MetricHandleBits(0) == 0, "native HWND diagnostic normalizes sign-extended handles and null");
    auto boundedCas = cas; boundedCas["futureRawField"] = "";
    const auto baseBytes = boundedCas.dump().size();
    boundedCas["futureRawField"] = std::string(131072 - baseBytes, 'x');
    check(boundedCas.dump().size() == 131072 && CasDocument(boundedCas, "18446744073709551615"), "native CAS retains complete raw document at UTF8 byte boundary");
    boundedCas["futureRawField"].get_ref<std::string&>().push_back('x');
    check(!CasDocument(boundedCas, "18446744073709551615"), "native CAS refuses oversized entire document without partial inventory");
    auto emptyPresetCatalog = cas["catalogs"][2];
    emptyPresetCatalog["preset_query"] = "returned-value";
    emptyPresetCatalog["preset"] = {{"index", -1}, {"presetId", "0"}, {"futureSentinelField", {{"retained", true}}}};
    check(CasPresetAbsent(emptyPresetCatalog["preset"]) && !CasHasPreset(emptyPresetCatalog) && CasCatalogEmpty(emptyPresetCatalog), "actual no-preset sentinel is not equipped and does not keep an empty category visible");
    check(RefreshCasSelection(Json({{"catalogs", Json::array({emptyPresetCatalog})}}), "mapped_panel_2", emptyPresetCatalog["preset"], true)["futureSentinelField"]["retained"] == true, "no-selection sentinel still retains every unknown raw field");
    auto mistypedSentinel = emptyPresetCatalog["preset"]; mistypedSentinel["index"] = "-1";
    check(!CasPresetAbsent(mistypedSentinel), "string preset index must not be coerced into known absence");
    mistypedSentinel = emptyPresetCatalog["preset"]; mistypedSentinel["presetId"] = 0;
    check(!CasPresetAbsent(mistypedSentinel), "numeric preset ID must not be coerced into known absence");
    auto chosenPreset = emptyPresetCatalog; chosenPreset["preset"] = {{"index", 4}, {"presetId", "25818"}};
    check(CasPresetSelected(chosenPreset["preset"]) && CasHasPreset(chosenPreset) && !CasCatalogEmpty(chosenPreset), "observed body preset remains equipped even when modifier items are empty");
    chosenPreset["preset"] = {{"index", 12}, {"presetId", "58488"}};
    check(CasPresetSelected(chosenPreset["preset"]), "observed chin preset is selected");
    chosenPreset["preset"] = {{"futurePackField", {{"raw", true}}}};
    check(!CasPresetAbsent(chosenPreset["preset"]) && !CasPresetSelected(chosenPreset["preset"]) && !CasCatalogEmpty(chosenPreset), "unknown future preset schema is retained without a selected or absent claim");
    check(CasPanelLabel("clothing_head_skin_details") == "Head Skin Details" && CasPanelLabel("clothing_body_skin_details") == "Body Skin Details", "native head and body skin detail categories have distinct friendly labels");
    check(CasPanelLabel("clothing_accessories_rings") == "Jewelry / Rings" && CasPanelLabel("clothing_accessories_earrings") == "Jewelry / Earrings", "verified jewelry categories have readable labels");
    check(CasPanelLabel("profile_body_skincolor") == "Body Skin Color" && CasPanelLabel("clothing_body_bodyhair_torsofront") == "Body Hair Torso Front", "verified compound category words remain readable");
    const std::string refreshSim = "18446744073709551615";
    CasRefreshClock refresh;
    auto due = [&](uint64_t now = 5000, bool visible = true, bool enabled = true, bool busy = false, bool retained = false) {
        return CasRefreshDue(refresh, now, 1000, refreshSim, visible, enabled, busy, retained);
    };
    check(CasNativePaneVisible(true, true, 11) && CasNativePaneVisible(true, true, 12) &&
        !CasNativePaneVisible(false, true, 12) && !CasNativePaneVisible(true, false, 12) &&
        !CasNativePaneVisible(true, true, 10), "auto refresh only belongs to visible native CAS history/equipped panes");
    check(due(), "stale inventory permits one automatic freshness cycle");
    check(!CasRefreshDue(refresh, 2999, 1000, refreshSim, true, true, false, false) &&
        CasRefreshDue(refresh, 3000, 1000, refreshSim, true, true, false, false), "fresh acknowledgement defers polling until the two-second boundary");
    check(!due(5000, false) && !due(5000, true, false), "hidden and opted-out native CAS views never poll");
    check(!due(5000, true, true, true) && !due(5000, true, true, false, true), "busy work and retained native UUID prohibit another read");
    check(!CasRefreshDue(refresh, 5000, 0, "012", true, true, false, false) &&
        !CasRefreshDue(refresh, 5000, 0, "", true, true, false, false), "automatic refresh cannot infer or coerce a selected Sim identity");
    refresh.lastAttemptMs = 4000;
    check(!due(5999) && due(6000) && !due(3999), "attempt interval is bounded and rejects a reversed clock");
    CasRefreshFailed(refresh, 6000);
    check(refresh.backoffUntilMs == 11000 && !due(10999) && due(11000), "explicit refresh failure backs off for five seconds");
    CasRefreshFailed(refresh, 11000); CasRefreshFailed(refresh, 21000); CasRefreshFailed(refresh, 41000);
    check(refresh.backoffUntilMs == 71000 && refresh.failures == 4, "repeated failures have a bounded thirty-second backoff");
    CasRefreshFailed(refresh, 71000, true);
    check(refresh.unresolved && !due(200000), "unresolved submission remains paused after backoff and cannot replay a read");
    auto diagnostic = Json{{"ok", true}, {"socket_transport", {{"bound", true}, {"host", "127.0.0.1"}, {"port", 8021}}},
        {"native_peers", Json::array({{{"sim_id", refreshSim}, {"age_seconds", 0.25}}})}, {"requests", Json::array()}};
    check(CasFreshNativePeer(diagnostic, refreshSim, 5000, 5000) && CasTransportIdle(diagnostic), "fresh exact native peer and idle transport authorize a status read");
    check(!CasFreshNativePeer(diagnostic, "12", 5000, 5000), "another Sim's heartbeat cannot authorize refresh");
    check(CasFreshNativePeer(diagnostic, refreshSim, 5000, 7750) &&
        !CasFreshNativePeer(diagnostic, refreshSim, 5000, 7751) &&
        !CasFreshNativePeer(diagnostic, refreshSim, 5000, 4999), "heartbeat freshness includes local elapsed time and rejects reversed receipt time");
    auto badDiagnostic = diagnostic; badDiagnostic["native_peers"][0]["sim_id"] = 18446744073709551615ULL;
    check(!CasFreshNativePeer(badDiagnostic, refreshSim, 5000, 5000), "numeric peer Sim identity is not rounded into a match");
    badDiagnostic = diagnostic; badDiagnostic["native_peers"][0]["age_seconds"] = -0.1;
    check(!CasFreshNativePeer(badDiagnostic, refreshSim, 5000, 5000), "negative heartbeat age cannot count as fresh");
    badDiagnostic["native_peers"][0]["age_seconds"] = "0.1";
    check(!CasFreshNativePeer(badDiagnostic, refreshSim, 5000, 5000), "untyped heartbeat age cannot count as fresh");
    badDiagnostic = diagnostic; badDiagnostic["socket_transport"]["bound"] = "true";
    check(!CasFreshNativePeer(badDiagnostic, refreshSim, 5000, 5000), "automatic refresh requires a typed verified socket binding");
    badDiagnostic = diagnostic; badDiagnostic["socket_transport"]["host"] = "0.0.0.0";
    check(!CasFreshNativePeer(badDiagnostic, refreshSim, 5000, 5000), "native refresh requires the established loopback peer transport");
    diagnostic["requests"].push_back({{"state", "pending"}, {"operation", "swatch"}, {"cas_request_id", std::string(32, 'a')}});
    check(!CasTransportIdle(diagnostic), "pending external mutation prevents automatic status read");
    diagnostic["requests"][0]["state"] = "future-unresolved-state";
    check(!CasTransportIdle(diagnostic), "unknown request state remains unresolved");
    diagnostic["requests"][0]["state"] = "completed";
    check(CasTransportIdle(diagnostic), "completed native request releases freshness work");
    diagnostic["requests"][0]["state"] = "accept-intent";
    check(!CasTransportIdle(diagnostic), "native precommit intent cannot release automatic freshness work");
    diagnostic["requests"][0]["state"] = "accept-unresolved";
    check(!CasTransportIdle(diagnostic), "unresolved native acceptance cannot release automatic freshness work");
    diagnostic["requests"][0]["state"] = "completed"; diagnostic["requests"][0]["outcome"] = "unresolved";
    check(!CasTransportIdle(diagnostic), "a nominal completed state cannot hide an unresolved native outcome");
    diagnostic["requests"][0].erase("outcome"); diagnostic["requests"][0]["state"] = "superseded-read";
    check(!CasTransportIdle(diagnostic), "a superseded mutation must remain unresolved");
    diagnostic["requests"][0]["operation"] = "status";
    check(CasTransportIdle(diagnostic), "only historical status reads may expire without blocking every later CLI probe");
    diagnostic["requests"][0]["outcome"] = "accept-intent";
    check(!CasTransportIdle(diagnostic), "historical status expiry cannot hide a current acceptance intent");
    diagnostic.erase("requests");
    check(!CasTransportIdle(diagnostic), "missing request inventory cannot be treated as idle");
    check(CasRequestIdentity(Json(std::string(32, 'a'))) && !CasRequestIdentity(Json(std::string(32, 'x'))) &&
        !CasRequestIdentity(Json(12)), "retained UUID must remain a typed exact native request identity");
    check(CasExplicitFailure(Json{{"ok", false}, {"cas_request_state", "failed"}}) &&
        !CasExplicitFailure(Json{{"ok", false}, {"outcome", "unknown"}}) &&
        !CasExplicitFailure(Json{{"ok", false}, {"outcome", "superseded-read"}}), "only an acknowledged explicit native failure releases its retained UUID");
    const auto readId = std::string(32, 'a');
    CasRefreshClock reconciliation;
    check(CasReadReconcileDue(reconciliation, 5000, refreshSim, true, true, false, readId, readId), "visible automatic status ownership may check only its retained result ID");
    check(!CasReadReconcileDue(reconciliation, 5000, refreshSim, false, true, false, readId, readId) &&
        !CasReadReconcileDue(reconciliation, 5000, refreshSim, true, true, true, readId, readId), "hidden and busy retained reads do not poll");
    check(!CasReadReconcileDue(reconciliation, 5000, refreshSim, true, true, false, readId, std::string(32, 'b')) &&
        !CasReadReconcileDue(reconciliation, 5000, refreshSim, true, true, false, "", readId), "mutation or foreign UUID ownership cannot trigger automatic read reconciliation");
    reconciliation.lastAttemptMs = 4000;
    check(!CasReadReconcileDue(reconciliation, 5999, refreshSim, true, true, false, readId, readId) &&
        CasReadReconcileDue(reconciliation, 6000, refreshSim, true, true, false, readId, readId), "retained result checks have the same bounded two-second cadence");
    CasRefreshFailed(reconciliation, 6000);
    check(!CasReadReconcileDue(reconciliation, 10999, refreshSim, true, true, false, readId, readId), "retained result failures respect backoff");
    auto readReply = Json{{"ok", true}, {"cas_request_id", readId}, {"cas_request_state", "completed"}, {"operation", "status"}, {"client", cas}};
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Completed, "exact terminal automatic status inventory can release old read ownership");
    check(ResolveCasRead(readReply, std::string(32, 'b'), refreshSim) == CasReadResolution::Blocked &&
        ResolveCasRead(readReply, readId, "12") == CasReadResolution::Blocked, "wrong UUID or wrong selected Sim cannot release retained status ownership");
    readReply["operation"] = "hair-swatch";
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Blocked, "native mutation receipt cannot be reconciled as an automatic status read");
    readReply["operation"] = "status"; readReply["outcome"] = "accept-intent";
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Blocked, "completed-looking acceptance intent cannot release automatic ownership");
    readReply["outcome"] = "unresolved";
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Blocked, "unresolved native outcome keeps the same read UUID");
    readReply = {{"ok", false}, {"cas_request_id", readId}, {"outcome", "pending-client"}};
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Pending, "pending fixed-ID result does not authorize another native read");
    readReply["outcome"] = "unknown";
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Blocked, "unknown result identity remains blocked");
    readReply["outcome"] = "superseded-read";
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Expired, "a canonical expired owned status read can release without presenting its historical inventory");
    readReply = {{"ok", false}, {"cas_request_id", readId}, {"cas_request_state", "failed"}, {"operation", "status"}};
    check(ResolveCasRead(readReply, readId, refreshSim) == CasReadResolution::Failed, "an explicit failed owned status read can release without an invented snapshot");
    const std::string itemHash(64, 'a');
    Json itemRequest = {{"lane", "123:2:18446744073709551615:1:full-appearance-v1"},
        {"appearance_sha256", itemHash}, {"runtime_pid", 456}, {"cursor", 0}, {"limit", 8}, {"outfit_index", 0}};
    Json equippedPart = {{"target", "0:900:0"}, {"body_type", 900}, {"index", 0},
        {"cas_part_id", "414264"}, {"cas_part_hex", "0000000000065238"}};
    Json itemEditor = equippedPart;
    itemEditor.update({{"part_name", "Real CASP skin detail"}, {"appearance_sha256", itemHash},
        {"resource_sha256", itemHash}, {"resource_tgi", "034AEECB:00000000:0000000000065238"}, {"resource_key_query", "native-key"}});
    Json equippedItem = equippedPart;
    equippedItem.update({{"outfit_index", 0}, {"outfit_id", "999"}, {"cache_key", itemHash},
        {"status", "resolved"}, {"display_name", "Real CASP skin detail"}, {"part_editor", itemEditor}});
    Json itemOutfit = {{"outfit_id", "999"}, {"parts", Json::array({equippedPart})}};
    Json itemPage = {{"ok", true}, {"runtime_pid", 456}, {"history_lane", itemRequest["lane"]},
        {"appearance_sha256", itemHash}, {"inspected_form_flags", 1}, {"cursor", 0}, {"limit", 8}, {"outfit_index", 0},
        {"owner", {{"runtime_pid", 456}, {"form_flags", 1}, {"save_guid", "123"}, {"slot_id", 2}, {"sim_id", refreshSim}}},
        {"total", 1}, {"resource_inspection_count", 1}, {"items", Json::array({equippedItem})}, {"next_cursor", nullptr}, {"complete", true}};
    check(StudioItemPage(itemPage, itemRequest, itemOutfit, 1), "exact equipped metadata page supports unknown future body categories");
    for (const auto slot : {0ULL, 0xffffffffULL}) {
        auto transientRequest = itemRequest; auto transientPage = itemPage;
        transientRequest["lane"] = "123:" + std::to_string(slot) + ":" + refreshSim + ":1:runtime-456:full-appearance-v1";
        transientPage["history_lane"] = transientRequest["lane"];
        transientPage["owner"]["slot_id"] = slot;
        transientPage["stable_save_slot_verified"] = false; transientPage["history_runtime_only"] = true;
        check(StudioItemPage(transientPage, transientRequest, itemOutfit, 1), "transient native slot retains an exact process-bound equipped page");
        auto changed = transientPage; changed["history_runtime_only"] = false;
        check(!StudioItemPage(changed, transientRequest, itemOutfit, 1), "transient equipped page cannot claim saved-slot history");
        changed = transientPage; changed["history_lane"] = "123:" + std::to_string(slot) + ":" + refreshSim + ":1:runtime-457:full-appearance-v1";
        check(!StudioItemPage(changed, transientRequest, itemOutfit, 1), "prior runtime lane cannot name transient equipped parts");
    }
    auto badPage = itemPage; badPage["runtime_pid"] = 457;
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "prior process metadata cannot name this outfit");
    badPage = itemPage; badPage["owner"]["sim_id"] = "12";
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "another Sim owner cannot share a metadata lane");
    badPage = itemPage; badPage["appearance_sha256"] = std::string(64, 'b');
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "appearance changes invalidate the whole metadata page");
    badPage = itemPage; badPage["items"][0]["body_type"] = 2;
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "hair metadata cannot name an unknown skin detail row");
    badPage = itemPage; badPage["items"][0]["part_editor"]["resource_tgi"] = "034AEECB:00000000:0000000000065239";
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "exact CASP instance is checked before resource cache admission");
    badPage = itemPage; badPage["items"][0]["display_name"] = "Invented name";
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "display name must equal the inspected native resource name");
    badPage = itemPage; badPage["items"] = Json::array();
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "missing rows cannot complete a metadata page");
    badPage = itemPage; badPage["next_cursor"] = 1;
    check(!StudioItemPage(badPage, itemRequest, itemOutfit, 1), "terminal page cannot request another cursor");
    badPage = itemPage; badPage["items"][0]["status"] = "unresolved";
    badPage["items"][0]["display_name"] = nullptr; badPage["items"][0]["part_editor"] = nullptr;
    check(StudioItemPage(badPage, itemRequest, itemOutfit, 1), "unresolved rows are retained without fictional names or CASP bindings");
    auto badRequest = itemRequest; badRequest["cursor"] = true;
    check(!StudioItemRequest(badRequest), "boolean paging coordinates are refused");
    badRequest = itemRequest; badRequest["limit"] = 9;
    check(!StudioItemRequest(badRequest), "automatic pages cannot exceed eight resource inspections");
    badRequest = itemRequest; badRequest["outfit_index"] = 128;
    check(!StudioItemRequest(badRequest), "absent outfit indices cannot start metadata traversal");
    Json inspected = {{"history_lane", itemRequest["lane"]}, {"runtime_pid", 456},
        {"appearance_sha256", itemHash}, {"inspected_form_flags", 1}};
    Json colorReply = {{"history_lane", itemRequest["lane"]},
        {"color_editor", {{"appearance_sha256", itemHash}}}};
    check(!StudioMetadataChanged(colorReply, inspected), "legacy color inspection keeps exact owner-bound item names and thumbnail metadata");
    auto changedReply = colorReply; changedReply["runtime_pid"] = 457;
    check(StudioMetadataChanged(changedReply, inspected), "another explicit runtime invalidates metadata");
    changedReply = colorReply; changedReply["color_editor"]["appearance_sha256"] = std::string(64, 'b');
    check(StudioMetadataChanged(changedReply, inspected), "nested color appearance change invalidates metadata");
    changedReply = colorReply; changedReply["history_lane"] = "different";
    check(StudioMetadataChanged(changedReply, inspected), "another history owner cannot retain names");
    changedReply = inspected; changedReply["inspected_form_flags"] = 64;
    check(StudioMetadataChanged(changedReply, inspected), "another explicit form invalidates metadata");
    std::cout << checks << " native transport/data checks; failures: " << failed << '\n';
    return failed ? 1 : 0;
}
