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
    std::cout << "21 native transport/data checks; failures: " << failed << '\n';
    return failed ? 1 : 0;
}
