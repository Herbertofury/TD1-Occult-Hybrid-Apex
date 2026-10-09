#include <iostream>
#include "ApexResourceImage.h"

int main() {
    using namespace td1; using resource::Json;
    unsigned checks = 0, failed = 0;
    auto check = [&](bool pass, const char* label) { ++checks; if (!pass) { ++failed; std::cerr << label << '\n'; } };
    const unsigned char png[] = {137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,0,0,0,13,73,68,65,84,120,156,99,16,84,50,254,15,0,2,20,1,102,4,224,222,127,0,0,0,0,73,69,78,68,174,66,96,130};
    const std::string bytes(reinterpret_cast<const char*>(png), sizeof(png));
    const std::string tgi = "034AEECB:00000002:00000000000003E7", effective(64, 'b'), appearance(64, 'a');
    Json row = {{"resource_tgi", tgi}, {"resource_id", resource::HashBytes(tgi + "\n" + effective)},
        {"cache_proof", std::string(64, 'c')}, {"effective_resource_sha256", effective}, {"status", "resolved"},
        {"display_name", "Actual CASP internal name"}, {"name_status", "casp-internal-name"}, {"body_type", 7},
        {"provenance", {{"origin", "ea"}, {"package_sha256", std::string(64, 'd')}, {"resource_sha256", effective}}},
        {"thumbnail", {{"status", "resolved"}, {"url", ""}, {"sha256", resource::HashBytes(bytes)}, {"width", 1}, {"height", 1}, {"reason", nullptr}}},
        {"studio_open", {{"status", "ready"}, {"selection", "containing-package"}, {"resource_selection_supported", false}, {"reason", nullptr}}}};
    row["thumbnail"]["url"] = "/v1/resources/" + ui::Scalar(row, "resource_id") + "/thumbnail";
    Json catalog = {{"schema", 1}, {"items", Json::array({row})}};
    Json part = {{"cas_part_hex", "00000000000003E7"}, {"cas_part_id", "999"}, {"target", "0:7:0"}, {"body_type", 7}};
    Json editor = {{"target", "0:7:0"}, {"cas_part_id", "999"}, {"body_type", 7},
        {"appearance_sha256", appearance}, {"resource_sha256", effective}, {"resource_tgi", tgi}};
    check(resource::HashBytes("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "actual CNG SHA256 known vector");
    check(resource::CatalogIdentities(catalog) && !resource::Equipped(catalog, part, editor, appearance).empty(), "exact typed TGI/hash/body/appearance equips pinned resource");
    check(resource::Name(row, resource::NameMode::Preferred).text == "Actual CASP internal name" &&
        resource::Name(row, resource::NameMode::Code).text == "Actual CASP internal name" &&
        resource::Name(row, resource::NameMode::Package).text.empty(), "legacy pinned naming never invents a package filename");
    auto named = row;
    named["provenance"]["origin"] = "mod";
    named["provenance"]["package_filename"] = "J\xC3\xA9welry_[Author].PACKAGE";
    named["metadata"] = {{"internal_name", "yfAcc_Long_Internal_Code_01"}};
    named["preferred_name"] = "Verified localized title"; named["preferred_name_status"] = "localized-title";
    named["display_name"] = named["preferred_name"]; named["name_status"] = named["preferred_name_status"];
    named["package_name"] = named["provenance"]["package_filename"];
    named["code_name"] = named["metadata"]["internal_name"];
    Json namedCatalog = {{"schema", 1}, {"items", Json::array({named})}};
    check(resource::Catalog(namedCatalog) && resource::Name(named, resource::NameMode::Preferred).text == "Verified localized title" &&
        resource::Name(named, resource::NameMode::Package).text == "J\xC3\xA9welry_[Author].PACKAGE" &&
        resource::Name(named, resource::NameMode::Code).text == "yfAcc_Long_Internal_Code_01",
        "name modes retain actual localized title, Unicode containing filename and genuine internal code separately");
    named["preferred_name"] = named["package_name"]; named["preferred_name_status"] = "cc-package-filename";
    named["display_name"] = named["preferred_name"]; named["name_status"] = named["preferred_name_status"];
    namedCatalog["items"][0] = named;
    check(resource::Catalog(namedCatalog) && resource::Name(named, resource::NameMode::Preferred).text ==
        "J\xC3\xA9welry_[Author].PACKAGE", "preferred CC fallback is the exact original containing filename");
    auto forgedName = namedCatalog; forgedName["items"][0]["preferred_name"] = "Invented friendly label";
    check(!resource::Catalog(forgedName), "name aliases cannot substitute invented friendly labels");
    forgedName = namedCatalog; forgedName["items"][0]["code_name"] = "Pretty humanized code";
    check(!resource::Catalog(forgedName), "code display must match actual CASP metadata");
    forgedName = namedCatalog; forgedName["items"][0]["package_name"] = "renamed-copy.package";
    check(!resource::Catalog(forgedName), "package display must match the original provenance filename");
    forgedName = namedCatalog; forgedName["items"][0].erase("code_name");
    check(!resource::Catalog(forgedName), "partial new naming contracts cannot mix fallbacks");
    named["metadata"]["internal_name"] = ""; named["code_name"] = nullptr; namedCatalog["items"][0] = named;
    check(resource::Catalog(namedCatalog) && resource::Name(named, resource::NameMode::Code).text.empty(),
        "absent genuine internal code remains unavailable in code mode");
    auto changed = catalog; changed["items"][0]["resource_id"] = std::string(64, 'a');
    check(!resource::CatalogIdentities(changed), "forged resource ID derivation is rejected");
    changed = catalog; changed["items"][0]["resource_tgi"] = "034AEECB:00000003:00000000000003E7";
    check(resource::Equipped(changed, part, editor, appearance).empty(), "same instance and bytes under wrong group cannot claim effective source");
    auto changedEditor = editor; changedEditor.erase("resource_tgi");
    check(resource::Equipped(catalog, part, changedEditor, appearance).empty(), "unavailable native group cannot be guessed");
    changedEditor = editor; changedEditor["resource_sha256"] = std::string(64, 'e');
    check(resource::Equipped(catalog, part, changedEditor, appearance).empty(), "stale effective hash cannot select resource");
    check(resource::Equipped(catalog, part, editor, std::string(64, 'f')).empty(), "stale appearance cannot select resource");
    changedEditor = editor; changedEditor["cas_part_id"] = "998";
    check(resource::Equipped(catalog, part, changedEditor, appearance).empty(), "different exact outfit resource cannot select cache");
    changedEditor = editor; changedEditor["body_type"] = 2;
    check(resource::Equipped(catalog, part, changedEditor, appearance).empty(), "different equipped body category cannot select cache");
    changed = catalog; changed["items"].push_back(row);
    check(!resource::Catalog(changed), "duplicate pinned IDs cannot choose a package arbitrarily");
    changed = catalog; changed["items"][0]["name_status"] = "unresolved";
    check(!resource::Catalog(changed), "unresolved metadata cannot carry substituted name");
    changed = catalog; changed["items"][0]["thumbnail"]["url"] = "https://example.com/image.png";
    check(!resource::Catalog(changed), "thumbnail URL cannot select an arbitrary network origin");
    changed = catalog; changed["items"][0]["provenance"]["resource_sha256"] = std::string(64, 'e');
    check(!resource::Catalog(changed), "provenance must match actual effective bytes");
    changed = catalog; changed["items"][0]["studio_open"]["resource_selection_supported"] = true;
    check(!resource::Catalog(changed), "containing package open cannot claim selected CASP editor parity");
    const auto id = ui::Scalar(row, "resource_id");
    Json receipt = {{"ok", true}, {"resource_id", id}, {"selection", "containing-package"}, {"resource_selection_supported", false}};
    check(resource::OpenReceipt(receipt, id), "same exact resource receipt proves containing package delivery");
    receipt["resource_id"] = std::string(64, 'e');
    check(!resource::OpenReceipt(receipt, id), "foreign resource cannot acknowledge requested Studio delivery");
    std::string body;
    const auto http = "HTTP/1.0 200 OK\r\nContent-Length: " + std::to_string(bytes.size()) + "\r\nContent-Type: image/png\r\n\r\n" + bytes;
    check(resource::HttpBody(http, bytes.size(), body) && body == bytes, "HTTP1.0 broker retains exact binary PNG body");
    check(!resource::HttpBody(http.substr(0, http.size() - 1), bytes.size(), body) && body.empty(), "truncated response cannot retain partial pixels");
    check(!resource::HttpBody(http + "x", bytes.size(), body), "extra bytes cannot hide ContentLength mismatch");
    check(!resource::HttpBody(http, bytes.size() - 1, body), "entire image response respects byte bound");
    check(!resource::HttpBody("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n", 100, body), "non200 broker response is not success");
    check(!resource::HttpBody("HTTP/1.1 200 OK\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n", 100, body), "duplicate length headers rejected");
    check(!resource::HttpBody("HTTP/1.1 200 OK\r\nContent-Length: 0\r\nTransfer-Encoding: chunked\r\n\r\n", 100, body), "unsupported chunked response rejected");
    check(!resource::HttpBody("HTTP/1.1 200 OK\r\nContent-Length: +1\r\n\r\nx", 100, body), "signed malformed length rejected");
    resource::Pixels pixels; std::string reason;
    check(resource::DecodeThumbnail(bytes, row, pixels, reason) && pixels.width == 1 && pixels.height == 1 &&
        pixels.rgba == std::vector<unsigned char>({17,34,51,255}), "actual WIC decode yields exact owned RGBA pixels");
    auto badRow = row; badRow["thumbnail"]["sha256"] = std::string(64, 'e');
    check(!resource::DecodeThumbnail(bytes, badRow, pixels, reason) && pixels.rgba.empty(), "wrong PNG hash clears pixels");
    badRow = row; badRow["thumbnail"]["width"] = 2;
    check(!resource::DecodeThumbnail(bytes, badRow, pixels, reason) && pixels.rgba.empty(), "actual dimensions must equal pinned receipt");
    std::string broken = bytes; broken.resize(40); badRow = row; badRow["thumbnail"]["sha256"] = resource::HashBytes(broken);
    check(!resource::DecodeThumbnail(broken, badRow, pixels, reason), "hash matching malformed PNG fails actual decoder");
    badRow = row; badRow["thumbnail"]["width"] = 513;
    check(!resource::DecodeThumbnail(bytes, badRow, pixels, reason), "oversized pinned dimensions are refused before image allocation");
    std::cout << checks << " native resource schema/hash/HTTP/WIC checks; failures: " << failed << '\n';
    return failed ? 1 : 0;
}
