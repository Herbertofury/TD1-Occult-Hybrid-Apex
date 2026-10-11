#include <iostream>
#include <fstream>
#include "ApexResourceImage.h"
#include "ApexLiveCatalog.h"
#include "ApexPointerGate.h"
#include "ApexGameWindow.h"
#include "ApexTrayView.h"
#include "ApexTrayGallery.h"

int main(int argc, char** argv) {
    using namespace td1; using resource::Json;
    unsigned checks = 0, failed = 0;
    auto check = [&](bool pass, const char* label) { ++checks; if (!pass) { ++failed; std::cerr << label << '\n'; } };
    check(tray::Base64("f")=="Zg=="&&tray::Base64("fo")=="Zm8="&&tray::Base64("foo")=="Zm9v"&&tray::Base64(std::string("\xff\x00",2))=="/wA=","bounded clipboard chunks preserve all raw bytes");
    check(tray::DestinationSim({{"history_lane","123:2:285159751289798669:8:runtime-77"}})=="285159751289798669","Tray viewer retains destination Sim independently of source");
    Json trayRequest={{"ok",true},{"sim_id","42"},{"form",2},{"native_sha256",std::string(64,'a')},{"appearance_sha256",std::string(64,'b')},{"render_sha256",std::string(64,'b')},
        {"runtime_pid",77},{"save_guid","123"},{"preview_id",nullptr},{"save_file_written",false},{"history_written",false},{"fields",Json::object()},{"native_sim","AQ=="},
        {"appearance_source","tray:"+std::string(64,'c')},{"lane","123:0:42:2:tray-"+std::string(64,'c')+":runtime-77"}};
    Json trayRows=Json::array({{{"name","Alien source"},{"request",trayRequest},{"outfits",Json::array({{{"index",0},{"category",0},{"number",1},{"outfit_id","0"}}})}}});
    check(tray::Forms(trayRows,77,"123"),"exact Tray source may use a different Sim/form from destination");
    auto wrongTray=trayRows;wrongTray[0]["request"]["runtime_pid"]=78;check(!tray::Forms(wrongTray,77,"123"),"stale runtime Tray view refused");
    wrongTray=trayRows;wrongTray.push_back(wrongTray[0]);check(!tray::Forms(wrongTray,77,"123"),"duplicate Tray form refused");
    wrongTray=trayRows;wrongTray[0]["request"]["sim_id"]="43";check(!tray::Forms(wrongTray,77,"123"),"Tray source lane cannot borrow another Sim");
    check(tray::Request(trayRows,0,0)["outfit_id"]=="0","existing source outfit chosen without activating destination");
    check(library::Workspace({{"layout","catalog"},{"columns",6},{"sidebar",false},{"tab","library"},{"preview_share",.3},{"gender","female"}}),"typed workspace layout and columns accepted");
    for(const auto& bad:std::vector<Json>{{{"columns",1}},{{"columns",true}},{{"preview_share",.9}},{{"layout","unknown"}},{{"sidebar",1}},{{"tab","camera"}},{{"gender","unclassified"}},{{"click",true}},Json::object()})
        check(!library::Workspace(bad),"unknown, untyped or out-of-range workspace option rejected");
    check(GameCanvas(42,42,true,false,true,1278,1376,L"Canvas-0123"), "actual owned visible Canvas needs no foreground condition");
    check(!GameCanvas(43,42,true,false,true,1278,1376,L"Canvas-0123"), "another process cannot supply a renderer window");
    check(!GameCanvas(42,42,false,false,true,1278,1376,L"Canvas-0123"), "hidden helper window is rejected");
    check(!GameCanvas(42,42,true,true,true,1278,1376,L"Canvas-0123"), "minimized window is rejected");
    check(!GameCanvas(42,42,true,false,false,1278,1376,L"Canvas-0123"), "child Canvas is rejected");
    check(!GameCanvas(42,42,true,false,true,0,1376,L"Canvas-0123"), "empty client is rejected");
    check(!GameCanvas(42,42,true,false,true,1278,1376,L"ApexHelper"), "visible auxiliary window is rejected");
    check(!GameCanvas(0,0,true,false,true,1278,1376,L"Canvas-0123"), "missing process owner is rejected");
    check(UniqueGameCanvas(true,1) && !UniqueGameCanvas(true,0) && !UniqueGameCanvas(true,2) && !UniqueGameCanvas(false,1), "exactly one owned Canvas must match the candidate");
    check(CaptureReady(true,2,false,false), "plain game backbuffer does not require a visible F11 frame");
    check(!CaptureReady(true,2,true,true) && !CaptureReady(true,3,true,false), "overlay image requires initialized and visible F11");
    check(CaptureReady(true,3,true,true) && !CaptureReady(false,3,false,false) && !CaptureReady(true,1,false,false), "unattached game capture is rejected");
    if (argc == 2) {
        std::ifstream stream(argv[1], std::ios::binary);
        const std::string raw((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
        const auto probe = ui::ParseObject(raw);
        check(raw.size() <= 1024 * 1024 && probe.contains("query") && probe.contains("page") && library::Page(probe["page"], probe["query"]), "actual host catalog page accepted by native validator");
        check(probe.contains("selection") && probe.contains("inspection") && library::Inspection(probe["inspection"], probe["selection"]), "actual selected CC resource accepted by native validator");
        if(probe.contains("gallery_query"))check(probe.contains("gallery_page")&&tray::Page(probe["gallery_page"],probe["gallery_query"]),"actual native Tray gallery page accepted by renderer validator");
    }
    PointerGate gate{20,30,200,300};
    check(gate.Owns(40,50,1,0,false), "first down within rendered overlay is owned without preceding hover frame");
    check(gate.Owns(400,500,0,1,false) && gate.held == 0, "release outside overlay still owns the captured gesture");
    check(!gate.Owns(400,500,1,0,false) && gate.held == 0, "outside gesture belongs to game when UI does not request it");
    check(gate.Owns(-1,-1,0,0,true), "popup ownership still follows ImGui capture");
    const Json query = {{"text","brows"},{"body_type",nullptr},{"origin",nullptr},{"name_mode","preferred"},
        {"offset",0},{"limit",60},{"view","all"}};
    check(library::Query(query), "typed library request permits all categories");
    for (const auto& field : {"text","body_type","origin","name_mode","offset","limit","view"}) {
        auto bad = query; bad.erase(field); check(!library::Query(bad), "incomplete library request rejected");
    }
    auto badQuery = query; badQuery["path"] = "C:/anything"; check(!library::Query(badQuery), "library request cannot carry arbitrary paths");
    badQuery = query; badQuery["limit"] = 241; check(!library::Query(badQuery), "oversized page rejected");
    Json item = {{"part_id",std::string(64,'a')},{"resource_sha256",std::string(64,'b')},{"package_sha256",std::string(64,'c')},
        {"resource_tgi","034AEECB:80000000:0000000000000001"},{"package_name","Actual_CC.package"},
        {"body_type",4095},{"favorite",false},{"name","Actual CC"},{"status","indexed"},{"origin","mod"}};
    Json page = {{"ok",true},{"index_sha256",std::string(64,'d')},{"query",query},{"items",Json::array({item})},
        {"categories",Json::array({{{"body_type",4095},{"count",1}}})},{"total",1},{"offset",0},{"next_offset",nullptr},
        {"snapshot",{{"parts",1},{"complete",true}}}};
    check(library::Page(page,query), "future body type and exact page accepted");
    auto grouped=query;grouped["author"]="";grouped["sort"]="name";grouped["grouped"]=true;
    check(library::Query(grouped),"native CAS family page accepted");grouped["grouped"]="yes";check(!library::Query(grouped),"untyped grouping refused");
    auto swatch=item;swatch["family_id"]=std::string(64,'e');swatch["variant_key"]=std::string(64,'f');
    swatch["metadata"]={{"swatch_order",2},{"swatch_colors_argb",Json::array({0xff123456ULL,0xffabcdefULL})}};
    Json swatches={{"available",true},{"family_id",swatch["family_id"]},{"items",Json::array({swatch})},{"total",1},{"offset",0},{"next_offset",nullptr}};
    check(library::Swatches(swatches,swatch),"actual ARGB swatch colors remain bound to a precise CASP variant");
    auto badSwatches=swatches;badSwatches["items"][0]["metadata"]["swatch_colors_argb"][0]=true;check(!library::Swatches(badSwatches,swatch),"boolean swatch colors refused");
    badSwatches=swatches;badSwatches["items"].push_back(swatch);check(!library::Swatches(badSwatches,swatch),"duplicate swatch variant refused");
    auto familyPage=page;familyPage["items"][0]=swatch;
    Json variant=swatch;variant["part_id"]=std::string(64,'1');variant["variant_key"]=std::string(64,'2');
    auto familySwatches=swatches;familySwatches["items"].push_back(variant);familySwatches["total"]=2;
    Json familyInspection={{"index_sha256",page["index_sha256"]},{"item",swatch},{"swatches",familySwatches}};
    Json choice={{"index_sha256",page["index_sha256"]},{"part_id",variant["part_id"]}};
    check(library::VisibleSelection(familyPage,familyInspection,choice),"typed CLI can select a nonrepresentative swatch in the visible family");
    auto staleFamily=familyPage;staleFamily["index_sha256"]=std::string(64,'3');check(!library::VisibleSelection(staleFamily,familyInspection,choice),"CLI swatch cannot borrow another index");
    staleFamily=familyPage;staleFamily["items"][0]["family_id"]=std::string(64,'4');check(!library::VisibleSelection(staleFamily,familyInspection,choice),"CLI swatch cannot escape currently visible families");
    Json trayQuery={{"text","family"},{"kind","household"},{"offset",0},{"limit",60}};
    check(tray::Query(trayQuery),"typed Gallery search accepted");auto wrongGallery=trayQuery;wrongGallery["path"]="C:/original";check(!tray::Query(wrongGallery),"gallery query cannot carry host paths");
    Json galleryPage={{"ok",true},{"library_sha256",std::string(64,'a')},{"query",trayQuery},{"game_contacted",false},{"source_files_written",false},
        {"items",Json::array({{{"item_id",std::string(64,'b')},{"name","Household"},{"creator",""},{"description",""},{"sim_count",1},{"image_count",2},{"kind","household"}}})},{"total",1},{"offset",0},{"next_offset",nullptr}};
    check(tray::Page(galleryPage,trayQuery),"native household with absent creator and empty description remains browsable");
    auto badGallery=galleryPage;badGallery["items"][0]["description"]=false;check(!tray::Page(badGallery,trayQuery),"untyped native gallery text refused");
    badGallery=galleryPage;badGallery["items"][0].erase("name");check(!tray::Page(badGallery,trayQuery),"missing native gallery text refused");
    check(tray::Decode64("Zg==")=="f","canonical gallery image bytes decoded");
    try{tray::Decode64("Zg====");check(false,"noncanonical image padding accepted");}catch(...){check(true,"noncanonical image padding refused");}
    auto badPage=page; badPage["items"][0]["package_path"]="C:/original"; check(!library::Page(badPage,query), "native page rejects host paths");
    badPage=page; badPage["items"].push_back(item); check(!library::Page(badPage,query), "duplicate item identity rejected");
    badPage=page; badPage["query"]["text"]="stale"; check(!library::Page(badPage,query), "stale query response rejected");
    badPage=page; badPage.erase("snapshot"); check(!library::Page(badPage,query), "missing snapshot cannot reach renderer");
    badPage=page; badPage["next_offset"]=0; check(!library::Page(badPage,query), "pager cannot loop the same offset");
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
    auto imageRow=row;imageRow["broker_port"]=8023;
    auto imagePage=page;imagePage["items"][0]["resource_tgi"]=tgi;
    imagePage["items"][0]["body_type"]=row["body_type"];
    imagePage["items"][0]["package_sha256"]=row["provenance"]["package_sha256"];
    Json imageRequest={{"part_ids",Json::array({item["part_id"]})},{"index_sha256",page["index_sha256"]},{"gender","female"}};
    Json imageReply={{"ok",true},{"part_ids",imageRequest["part_ids"]},{"index_sha256",imageRequest["index_sha256"]},
        {"gender","female"},{"items",Json::array({{{"part_id",item["part_id"]},{"resource",imageRow}}})}};
    check(library::ImagesPage(imageReply,imageRequest,imagePage),"column image binds exact page item, package, CASP bytes and thumbnail gender");
    auto badImages=imageReply;badImages["gender"]="male";
    check(!library::ImagesPage(badImages,imageRequest,imagePage),"wrong gender thumbnail rejected");
    badImages=imageReply;badImages["items"][0]["resource"]["provenance"]["package_sha256"]=std::string(64,'a');
    check(!library::ImagesPage(badImages,imageRequest,imagePage),"another package cannot supply a column image");
    auto badImageRequest=imageRequest;badImageRequest["part_ids"].push_back(item["part_id"]);
    check(!library::ImagesRequest(badImageRequest),"duplicate image request rejected");
    badImageRequest=imageRequest;badImageRequest["path"]="C:/arbitrary";
    check(!library::ImagesRequest(badImageRequest),"column image request cannot provide host paths");
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
