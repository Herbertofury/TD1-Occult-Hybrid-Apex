#include "ApexUiData.h"
#include <iostream>

int main() {
    using namespace td1::ui;
    int failed = 0;
    auto check = [&](bool ok, const char* name) {
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
    check(ParseObject(std::string(512 * 1024 + 1, ' ')).empty(), "bounded response bytes");
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
    numeric["color_editor"]["channels"]["hue"]["min"] = 1.0;
    check(!StudioDocument(numeric), "reversed slider bounds rejected");
    numeric["color_editor"]["channels"]["hue"]["min"] = -0.5;
    numeric["color_editor"]["channels"]["hue"]["value"] = "0.25";
    check(!StudioDocument(numeric), "wrong typed slider value rejected");
    auto cas = ParseObject(R"({"scope":"native-cas-client","sim":{"simId":"18446744073709551615","futurePackField":{"raw":true}},"menu_state":-2134376418,"panel_visible":true,"outfit":{"outfit_type":0,"outfit_index":1},"catalogs":[{"panel":"clothing_hair","menu_state":-2134376418,"supported":true,"items":[{"dataID":"18446744073709551615","unknownFutureField":"retained"}]},{"panel":"clothing_head_skin_details","menu_state":-2134375419,"supported":false,"items":null}]})");
    for (unsigned i = 2; i < 72; ++i) cas["catalogs"].push_back({{"panel", "mapped_panel_" + std::to_string(i)}, {"menu_state", i}, {"supported", true}, {"items", Json::array()}});
    for (auto& catalog : cas["catalogs"]) { catalog["preset_query"] = "returned-null"; catalog["preset"] = nullptr; }
    check(CasDocument(cas, "18446744073709551615"), "CAS exact Sim identity and future item fields retained");
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
    std::cout << "48 native transport/data checks; failures: " << failed << '\n';
    return failed ? 1 : 0;
}
