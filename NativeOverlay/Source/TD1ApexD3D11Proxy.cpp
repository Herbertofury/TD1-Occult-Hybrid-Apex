// TD1ApexD3D11Proxy.cpp
// Build target: d3d11.dll proxy for The Sims 4 DirectX 11.
// Purpose: render TD1 Occult Hybrid Apex command overlay with Dear ImGui; toggle with F11.
// V9.6 adds live-game BodyType corrections for Sims 4 1.124.63.1020.

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>

// The Windows SDK declares these imports in d3d11.h. This proxy must export
// the real names itself, so rename the SDK declarations in this translation
// unit and undef them immediately after the include.
#define D3D11CreateDevice TD1_SDK_D3D11CreateDevice
#define D3D11CreateDeviceAndSwapChain TD1_SDK_D3D11CreateDeviceAndSwapChain
#include <d3d11.h>
#undef D3D11CreateDevice
#undef D3D11CreateDeviceAndSwapChain

#include <dxgi1_2.h>
#include <atomic>
#include <mutex>
#include <thread>
#include <deque>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <cctype>

#include "ApexUiData.h"
#include "OverlayInput.h"
#include "MinHook.h"
#include "imgui.h"
#include "imgui_impl_win32.h"
#include "imgui_impl_dx11.h"

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "ws2_32.lib")

extern LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

namespace td1 {
using PFN_D3D11CreateDevice = HRESULT (WINAPI *)(IDXGIAdapter*, D3D_DRIVER_TYPE, HMODULE, UINT, const D3D_FEATURE_LEVEL*, UINT, UINT, ID3D11Device**, D3D_FEATURE_LEVEL*, ID3D11DeviceContext**);
using PFN_D3D11CreateDeviceAndSwapChain = HRESULT (WINAPI *)(IDXGIAdapter*, D3D_DRIVER_TYPE, HMODULE, UINT, const D3D_FEATURE_LEVEL*, UINT, UINT, const DXGI_SWAP_CHAIN_DESC*, IDXGISwapChain**, ID3D11Device**, D3D_FEATURE_LEVEL*, ID3D11DeviceContext**);
using PresentFn = HRESULT (STDMETHODCALLTYPE *)(IDXGISwapChain*, UINT, UINT);
using Present1Fn = HRESULT (STDMETHODCALLTYPE *)(IDXGISwapChain1*, UINT, UINT, const DXGI_PRESENT_PARAMETERS*);
using ResizeBuffersFn = HRESULT (STDMETHODCALLTYPE *)(IDXGISwapChain*, UINT, UINT, UINT, DXGI_FORMAT, UINT);

static HMODULE g_realD3D11 = nullptr;
static PFN_D3D11CreateDevice g_realCreateDevice = nullptr;
static PFN_D3D11CreateDeviceAndSwapChain g_realCreateDeviceAndSwapChain = nullptr;
static PresentFn g_realPresent = nullptr;
static Present1Fn g_realPresent1 = nullptr;
static std::atomic<int> g_renderedFrames{0};
static ResizeBuffersFn g_realResizeBuffers = nullptr;
static std::atomic<bool> g_hooked{false};
static std::atomic<bool> g_visible{false};
static std::atomic<bool> g_done{false};
static std::atomic<bool> g_workerActive{false};
static std::atomic<int> g_captureRequest{0}; // 1 face, 2 body, 3 full
static std::atomic<int> g_captureCompleted{0};
static std::atomic<int> g_toggleEvents{0};
static HWND g_hwnd = nullptr;
static IDXGISwapChain* g_swapChain = nullptr; // identity only; owned by the caller
static std::recursive_mutex g_renderMutex;
static std::mutex g_hookMutex;
static ToggleInput g_toggleInput;
static std::atomic<int> g_loaderStatus{0}; // 0 not started, 1 hooked, negative error
#ifdef APEX_NATIVE_SMOKE
static unsigned g_presentCount = 0;
#endif
static WNDPROC g_oldWndProc = nullptr;
static ID3D11Device* g_device = nullptr;
static ID3D11DeviceContext* g_context = nullptr;
static ID3D11RenderTargetView* g_rtv = nullptr;
static std::mutex g_dataMutex;
static std::string g_json = "{\"message\":\"Waiting for TD1 Apex Python server...\"}";
static std::string g_status = "Not connected";
static std::string g_commandReply = "{}";
static std::string g_selectedSim;
struct QueuedCommand { std::string path; uint64_t generation; };
static std::deque<QueuedCommand> g_commands;
static uint64_t g_selectionGeneration = 0;
static std::atomic<ULONGLONG> g_lastStatusMs{0};
static int g_activeTab = 0;
static bool g_wsStarted = false;
static std::vector<std::string> g_logLines;

static int g_selectedOccultIndex = 1;
static bool g_autoRepairToggle = false;
static bool g_mcccAutoRestoreToggle = false;
static bool g_mcccSoftHooksToggle = false;
static bool g_driftAfterCommandsToggle = true;
static char g_formLabel[160] = "";
static char g_formSearch[160] = "";
static char g_formSlot[220] = "";
static char g_rawFlags[64] = "";
static char g_rawCurrent[64] = "";
static char g_studioTarget[100] = "0:HAIR";
static char g_previewId[64] = "";
static char g_historyId[64] = "";
static char g_historySearch[160] = "";
static int g_studioOutfitIndex = 0;
static int g_studioPartIndex = 0;
static ui::Json g_studioData = ui::Json::object();
static std::string g_studioLastReply;
static std::string g_colorEditorKey;
static float g_colorValues[4]{};
static bool g_colorChanged[4]{};
static char g_checkpointLabel[160] = "";
static UINT g_toggleKey = VK_F11;
static bool g_configLoaded = false;
static std::string g_confirmPath;
static std::string g_confirmAction;
static uint64_t g_confirmGeneration = 0;
static bool g_openConfirmation = false;
static char g_casCategoryFilter[160] = "";

static const char* kOccults[] = {"ALIEN","VAMPIRE","MERMAID","WITCH","SPELLCASTER","WEREWOLF","FAIRY","PLANTSIM","ROBOT","SERVO","GHOST","SKELETON","SCARECROW"};

struct CasBodyTypeDef { const char* group; const char* key; const char* label; int fallbackValue; };
static const CasBodyTypeDef kCasBodyTypes[] = {
    {"Reserved / Utility", "NONE", "None / no body type", 0},
    {"Core Sim Body", "HAT", "Hat / headwear", 1},
    {"Core Sim Body", "HAIR", "Hair", 2},
    {"Core Sim Body", "HEAD", "Head", 3},
    {"Core Sim Body", "TEETH", "Teeth", 4},
    {"Core Sim Body", "FULL_BODY", "Full body outfit", 5},
    {"Core Sim Body", "UPPER_BODY", "Upper body top", 6},
    {"Core Sim Body", "LOWER_BODY", "Lower body bottom", 7},
    {"Core Sim Body", "SHOES", "Shoes / footwear", 8},
    {"Accessories", "CUMMERBUND", "Cummerbund", 9},
    {"Accessories", "EARRINGS", "Earrings", 10},
    {"Accessories", "GLASSES", "Glasses", 11},
    {"Accessories", "NECKLACE", "Necklace", 12},
    {"Accessories", "GLOVES", "Gloves", 13},
    {"Accessories", "WRIST_LEFT", "Left wrist", 14},
    {"Accessories", "WRIST_RIGHT", "Right wrist", 15},
    {"Piercings / Rings", "LIP_RING_LEFT", "Left lip ring", 16},
    {"Piercings / Rings", "LIP_RING_RIGHT", "Right lip ring", 17},
    {"Piercings / Rings", "NOSE_RING_LEFT", "Left nose ring", 18},
    {"Piercings / Rings", "NOSE_RING_RIGHT", "Right nose ring", 19},
    {"Piercings / Rings", "BROW_RING_LEFT", "Left brow ring", 20},
    {"Piercings / Rings", "BROW_RING_RIGHT", "Right brow ring", 21},
    {"Piercings / Rings", "INDEX_FINGER_LEFT", "Left index finger ring", 22},
    {"Piercings / Rings", "INDEX_FINGER_RIGHT", "Right index finger ring", 23},
    {"Piercings / Rings", "RING_FINGER_LEFT", "Left ring finger ring", 24},
    {"Piercings / Rings", "RING_FINGER_RIGHT", "Right ring finger ring", 25},
    {"Piercings / Rings", "MIDDLE_FINGER_LEFT", "Left middle finger ring", 26},
    {"Piercings / Rings", "MIDDLE_FINGER_RIGHT", "Right middle finger ring", 27},
    {"Makeup / Face", "FACIAL_HAIR", "Facial hair", 28},
    {"Makeup / Face", "LIPS_TICK", "Lipstick", 29},
    {"Makeup / Face", "EYE_SHADOW", "Eye shadow", 30},
    {"Makeup / Face", "EYE_LINER", "Eye liner", 31},
    {"Makeup / Face", "BLUSH", "Blush", 32},
    {"Makeup / Face", "FACEPAINT", "Face paint", 33},
    {"Makeup / Face", "EYEBROWS", "Eyebrows", 34},
    {"Makeup / Face", "EYECOLOR", "Eye color", 35},
    {"Accessories", "SOCKS", "Socks", 36},
    {"Makeup / Face", "EYELASHES", "Eyelashes", 37},
    {"Skin Details", "SKINDETAIL_CREASE_FOREHEAD", "Forehead crease skin detail", 38},
    {"Skin Details", "SKINDETAIL_FRECKLES", "Freckles skin detail", 39},
    {"Skin Details", "SKINDETAIL_DIMPLE_LEFT", "Left dimple skin detail", 40},
    {"Skin Details", "SKINDETAIL_DIMPLE_RIGHT", "Right dimple skin detail", 41},
    {"Accessories", "TIGHTS", "Tights / legwear", 42},
    {"Skin Details", "SKINDETAIL_MOLE_LIP_LEFT", "Left lip mole skin detail", 43},
    {"Skin Details", "SKINDETAIL_MOLE_LIP_RIGHT", "Right lip mole skin detail", 44},
    {"Tattoos", "TATTOO_ARM_LOWER_LEFT", "Lower left arm tattoo", 45},
    {"Tattoos", "TATTOO_ARM_UPPER_LEFT", "Upper left arm tattoo", 46},
    {"Tattoos", "TATTOO_ARM_LOWER_RIGHT", "Lower right arm tattoo", 47},
    {"Tattoos", "TATTOO_ARM_UPPER_RIGHT", "Upper right arm tattoo", 48},
    {"Tattoos", "TATTOO_LEG_LEFT", "Left leg tattoo", 49},
    {"Tattoos", "TATTOO_LEG_RIGHT", "Right leg tattoo", 50},
    {"Tattoos", "TATTOO_TORSO_BACK_LOWER", "Lower back torso tattoo", 51},
    {"Tattoos", "TATTOO_TORSO_BACK_UPPER", "Upper back torso tattoo", 52},
    {"Tattoos", "TATTOO_TORSO_FRONT_LOWER", "Lower front torso tattoo", 53},
    {"Tattoos", "TATTOO_TORSO_FRONT_UPPER", "Upper front torso tattoo", 54},
    {"Skin Details", "SKINDETAIL_MOLE_CHEEK_LEFT", "Left cheek mole skin detail", 55},
    {"Skin Details", "SKINDETAIL_MOLE_CHEEK_RIGHT", "Right cheek mole skin detail", 56},
    {"Skin Details", "SKINDETAIL_CREASE_MOUTH", "Mouth crease skin detail", 57},
    {"Skin Details", "SKIN_OVERLAY", "Skin overlay", 58},
    {"Occult / Creature", "FUR_BODY", "Fur body", 59},
    {"Occult / Creature", "EARS", "Ears", 60},
    {"Occult / Creature", "TAIL", "Tail", 61},
    {"Skin Details", "SKINDETAIL_NOSE_COLOR", "Nose color skin detail", 62},
    {"Makeup / Face", "EYECOLOR_SECONDARY", "Secondary eye color", 63},
    {"Occult / Creature", "OCCULT_BROW", "Occult brow", 64},
    {"Occult / Creature", "OCCULT_EYE_SOCKET", "Occult eye socket", 65},
    {"Occult / Creature", "OCCULT_EYE_LID", "Occult eye lid", 66},
    {"Occult / Creature", "OCCULT_MOUTH", "Occult mouth", 67},
    {"Occult / Creature", "OCCULT_LEFT_CHEEK", "Occult left cheek", 68},
    {"Occult / Creature", "OCCULT_RIGHT_CHEEK", "Occult right cheek", 69},
    {"Occult / Creature", "OCCULT_NECK_SCAR", "Occult neck scar", 70},
    {"Skin Details", "FOREARM_SCAR", "Forearm scar", 71},
    {"Skin Details", "ACNE", "Acne", 72},
    {"Accessories", "FINGERNAIL", "Fingernails", 73},
    {"Accessories", "TOENAIL", "Toenails", 74},
    {"Makeup / Face", "HAIRCOLOR_OVERRIDE", "Hair color override", 75},
    {"Occult / Creature", "BITE", "Bite mark", 76},
    {"Skin Details", "BODYFRECKLES", "Body freckles", 77},
    {"Body Hair / Scars", "BODYHAIR_ARM", "Arm body hair", 78},
    {"Body Hair / Scars", "BODYHAIR_LEG", "Leg body hair", 79},
    {"Body Hair / Scars", "BODYHAIR_TORSOFRONT", "Front torso body hair", 80},
    {"Body Hair / Scars", "BODYHAIR_TORSOBACK", "Back torso body hair", 81},
    {"Body Hair / Scars", "BODYSCAR_ARMLEFT", "Left arm body scar", 82},
    {"Body Hair / Scars", "BODYSCAR_ARMRIGHT", "Right arm body scar", 83},
    {"Body Hair / Scars", "BODYSCAR_TORSOFRONT", "Front torso body scar", 84},
    {"Body Hair / Scars", "BODYSCAR_TORSOBACK", "Back torso body scar", 85},
    {"Body Hair / Scars", "BODYSCAR_LEGLEFT", "Left leg body scar", 86},
    {"Body Hair / Scars", "BODYSCAR_LEGRIGHT", "Right leg body scar", 87},
    {"Occult / Creature", "ATTACHMENT_BACK", "Back attachment", 88},
    {"Skin Details", "SKINDETAIL_ACNE_PUBERTY", "Puberty acne skin detail", 89},
    {"Body Hair / Scars", "SCARFACE", "Face scar", 90},
    {"Skin Details", "BIRTHMARKFACE", "Face birthmark", 91},
    {"Skin Details", "BIRTHMARKTORSOBACK", "Back torso birthmark", 92},
    {"Skin Details", "BIRTHMARKTORSOFRONT", "Front torso birthmark", 93},
    {"Skin Details", "BIRTHMARKARMS", "Arm birthmarks", 94},
    {"Skin Details", "MOLEFACE", "Face mole", 95},
    {"Skin Details", "MOLECHESTUPPER", "Upper chest mole", 96},
    {"Skin Details", "MOLEBACKUPPER", "Upper back mole", 97},
    {"Skin Details", "BIRTHMARKLEGS", "Leg birthmarks", 98},
    {"Skin Details", "STRETCHMARKS_FRONT", "Front stretch marks", 99},
    {"Skin Details", "STRETCHMARKS_BACK", "Back stretch marks", 100},
    {"Horse / Animal", "SADDLE", "Saddle", 101},
    {"Horse / Animal", "BRIDLE", "Bridle", 102},
    {"Horse / Animal", "REINS", "Reins", 103},
    {"Horse / Animal", "BLANKET", "Blanket", 104},
    {"Horse / Animal", "SKINDETAIL_HOOF_COLOR", "Hoof color skin detail", 105},
    {"Horse / Animal", "HAIR_MANE", "Mane hair", 106},
    {"Horse / Animal", "HAIR_TAIL", "Tail hair", 107},
    {"Horse / Animal", "HAIR_FORELOCK", "Forelock hair", 108},
    {"Horse / Animal", "HAIR_FEATHERS", "Feathering hair", 109},
    {"Horse / Animal", "HORN", "Horn", 110},
    {"Horse / Animal", "TAIL_BASE", "Tail base", 111},
    {"Latest / Runtime Resolved", "BIRTHMARKOCCULT", "Occult birthmark", 112},
    {"Latest / Runtime Resolved", "TATTOO_HEAD", "Head tattoo", 113},
    {"Latest / Runtime Resolved", "WINGS", "Wings", 114},
    {"Latest / Runtime Resolved", "HEADDECO", "Head decoration", 115},
    {"Latest / Runtime Resolved", "SKINSPECULARITY", "Skin specularity", 116},
    {"Latest / Runtime Resolved", "BASE_LAYER", "Base Layer", 117},
    {"Reserved / Utility", "UNUSED", "Unused / reserved", 118},
};


static void Debug(const char* text) {
    OutputDebugStringA("[TD1 Apex Overlay] ");
    OutputDebugStringA(text);
    OutputDebugStringA("\n");
}

static std::wstring SystemD3D11Path() {
    wchar_t buf[MAX_PATH] = {};
    UINT n = GetSystemDirectoryW(buf, MAX_PATH);
    std::wstring out(buf, buf + n);
    if (!out.empty() && out.back() != L'\\') out += L'\\';
    out += L"d3d11.dll";
    return out;
}

static bool LoadRealD3D11() {
    if (g_realD3D11) return true;
    std::wstring path = SystemD3D11Path();
    g_realD3D11 = LoadLibraryW(path.c_str());
    if (!g_realD3D11) { Debug("LoadLibraryW(system d3d11.dll) failed"); return false; }
    g_realCreateDevice = reinterpret_cast<PFN_D3D11CreateDevice>(GetProcAddress(g_realD3D11, "D3D11CreateDevice"));
    g_realCreateDeviceAndSwapChain = reinterpret_cast<PFN_D3D11CreateDeviceAndSwapChain>(GetProcAddress(g_realD3D11, "D3D11CreateDeviceAndSwapChain"));
    if (!g_realCreateDevice || !g_realCreateDeviceAndSwapChain) { Debug("GetProcAddress for d3d11 exports failed"); return false; }
    return true;
}

static std::string UrlEncode(const std::string& s) {
    static const char* hex = "0123456789ABCDEF";
    std::string out;
    for (unsigned char c : s) {
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') out.push_back((char)c);
        else { out.push_back('%'); out.push_back(hex[c >> 4]); out.push_back(hex[c & 15]); }
    }
    return out;
}

static bool HttpGet(const std::string& path, std::string& body) {
    if (!g_wsStarted) {
        WSADATA wsa{};
        if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) return false;
        g_wsStarted = true;
    }
    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) return false;
    // This is a transport worker. A game-thread command can take several frames;
    // a 350 ms deadline previously discarded its result while it still executed.
    DWORD timeout = 12000;
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(8017);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    if (connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == SOCKET_ERROR) { closesocket(s); return false; }
    std::string req = "GET " + path + " HTTP/1.1\r\nHost: 127.0.0.1:8017\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n";
    size_t sent = 0;
    while (sent < req.size()) {
        int n = send(s, req.data() + sent, static_cast<int>(req.size() - sent), 0);
        if (n <= 0) { closesocket(s); return false; }
        sent += static_cast<size_t>(n);
    }
    std::string raw;
    char buf[8192];
    for (;;) {
        int n = recv(s, buf, sizeof(buf), 0);
        if (n < 0) { closesocket(s); return false; }
        if (n == 0) break;
        raw.append(buf, buf + n);
        if (raw.size() > 1024 * 512) { closesocket(s); return false; }
    }
    closesocket(s);
    size_t pos = raw.find("\r\n\r\n");
    if (pos == std::string::npos || raw.find("HTTP/1.1 200 ") != 0) return false;
    body = raw.substr(pos + 4);
    size_t lengthKey = raw.find("Content-Length:");
    if (lengthKey == std::string::npos || lengthKey >= pos) return false;
    const char* begin = raw.c_str() + lengthKey + strlen("Content-Length:");
    char* end = nullptr;
    unsigned long declared = strtoul(begin, &end, 10);
    if (!end || end == begin || *end != '\r' || declared != body.size()) return false;
    size_t last = body.find_last_not_of(" \t\r\n");
    return last != std::string::npos && body[last] == '}' && !ui::ReadObject(body).empty();
}

static std::vector<std::string> ExtractHistory(const std::string& json) {
    return ui::Logs(ui::ReadObject(json));
}

static std::string ExtractJsonValue(const std::string& json, const char* keyName) {
    return ui::Scalar(ui::ReadObject(json), keyName);
}

static void QueueCommand(const std::string& path) {
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if (g_commands.size() >= 48) {
        g_status = "Queue full: this command was rejected; earlier commands were retained";
        return;
    }
    g_commands.push_back({path, g_selectionGeneration});
}

static std::string CurrentSimQuery() {
    std::string sim;
    { std::lock_guard<std::mutex> lock(g_dataMutex); sim = g_selectedSim; }
    if (sim.empty()) return std::string();
    return std::string("&sim_id=") + UrlEncode(sim);
}

static std::string BuildCommandPath(const char* action, const char* occult = nullptr, const char* value = nullptr) {
    std::string path = "/api/command?action=" + UrlEncode(action ? action : "status");
    path += CurrentSimQuery();
    if (occult && occult[0]) path += "&occult=" + UrlEncode(occult);
    if (value && value[0]) path += "&value=" + UrlEncode(value);
    return path;
}

static void QueueAction(const char* action, const char* occult = nullptr, const char* value = nullptr) {
    std::string name = action ? action : "status";
    bool destructive = name == "purge" || name == "remove" || name == "gameplay_remove" ||
        name == "delete_form" || name == "delete_saved_form" || name == "add_all" ||
        name == "repair_all" || name == "deep_repair_all" || name == "toggle_flag" ||
        name.find("set_flags") == 0 || name.find("set_current") == 0 ||
        name.find("_to_all_forms") != std::string::npos || name.find("force_apply") == 0 ||
        name.find("cas_prepare") == 0 || name.find("mccc_prepare") == 0;
    std::string path = BuildCommandPath(action, occult, value);
    if (destructive) {
        g_confirmPath = path;
        g_confirmAction = name + (occult ? std::string(" / ") + occult : "");
        { std::lock_guard<std::mutex> lock(g_dataMutex); g_confirmGeneration = g_selectionGeneration; }
        g_openConfirmation = true;
        return;
    }
    QueueCommand(path);
}

static bool ActionButton(const char* label, const char* action, const char* occult = nullptr, const char* value = nullptr, const ImVec2& size = ImVec2(-1, 0)) {
    if (!ImGui::Button(label, size)) return false;
    QueueAction(action, occult, value);
    return true;
}

static void WorkerLoop() {
    g_workerActive = true;
    while (!g_done) {
        QueuedCommand command;
        {
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if (!g_commands.empty()) { command = g_commands.front(); g_commands.pop_front(); }
        }
        if (!command.path.empty()) {
            std::string body;
            bool ok = HttpGet(command.path, body);
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if (command.generation == g_selectionGeneration) {
                g_status = !ok ? "Command request failed" :
                    (ExtractJsonValue(body, "ok") == "true" ? "Command completed; see its result" : "Command rejected; see its reason");
                if (ok) { g_json = body; g_commandReply = body; auto lines = ExtractHistory(body); if (!lines.empty()) g_logLines = lines; }
            }
            continue;
        }
        if (g_visible.load()) {
            ULONGLONG now = GetTickCount64();
            if (now - g_lastStatusMs >= 1300) {
                g_lastStatusMs = now;
                std::string body;
                std::string sim;
                uint64_t generation;
                { std::lock_guard<std::mutex> lock(g_dataMutex); sim = g_selectedSim; generation = g_selectionGeneration; }
                std::string path = "/api/overlay/state?count=220";
                if (!sim.empty()) path += "&sim_id=" + UrlEncode(sim);
                bool ok = HttpGet(path, body);
                std::lock_guard<std::mutex> lock(g_dataMutex);
                if (generation != g_selectionGeneration) continue;
                g_status = ok ? "Connected to TD1 Apex" : "Waiting for 127.0.0.1:8017";
                if (ok) {
                    g_json = body;
                    auto lines = ExtractHistory(body);
                    if (!lines.empty()) g_logLines = lines;
                    std::string sid = ui::StatusScalar(ui::ReadObject(body), "sim_id");
                    if (!sid.empty() && g_selectedSim.empty()) { g_selectedSim = sid; ++g_selectionGeneration; }
                }
            }
        }
        Sleep(g_visible.load() ? 120 : 250);
    }
    g_workerActive = false;
}

static void EnsureWorker() {
    static bool started = false;
    if (!started) { started = true; std::thread(WorkerLoop).detach(); }
}

static void CreateRenderTarget(IDXGISwapChain* sc) {
    if (g_rtv || !g_device) return;
    ID3D11Texture2D* backBuffer = nullptr;
    if (SUCCEEDED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), reinterpret_cast<void**>(&backBuffer))) && backBuffer) {
        g_device->CreateRenderTargetView(backBuffer, nullptr, &g_rtv);
        backBuffer->Release();
    }
}

static void CleanupRenderTarget() {
    if (g_rtv) { g_rtv->Release(); g_rtv = nullptr; }
}

static void WriteLE16(std::ofstream& f, uint16_t v) { f.put(char(v & 255)); f.put(char((v >> 8) & 255)); }
static void WriteLE32(std::ofstream& f, uint32_t v) { f.put(char(v & 255)); f.put(char((v >> 8) & 255)); f.put(char((v >> 16) & 255)); f.put(char((v >> 24) & 255)); }

static std::string ScreenshotFolder() {
    char user[MAX_PATH] = {};
    DWORD n = GetEnvironmentVariableA("USERPROFILE", user, MAX_PATH);
    std::string base = (n > 0 && n < MAX_PATH) ? std::string(user) : std::string(".");
    std::string dir = base + "\\Documents\\Electronic Arts\\The Sims 4\\TD1ApexScreenshots";
    CreateDirectoryA(dir.c_str(), nullptr);
    return dir;
}

static std::string TimestampName(const char* mode) {
    std::time_t t = std::time(nullptr);
    std::tm tm{};
    localtime_s(&tm, &t);
    std::ostringstream ss;
    ss << ScreenshotFolder() << "\\TD1Apex_" << mode << "_" << std::put_time(&tm, "%Y%m%d_%H%M%S")
       << "_" << GetTickCount64() << ".bmp";
    return ss.str();
}

static bool SaveBackbufferBmp(IDXGISwapChain* sc, int mode) {
    if (!sc || !g_device || !g_context) return false;
    ID3D11Texture2D* backBuffer = nullptr;
    if (FAILED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), reinterpret_cast<void**>(&backBuffer))) || !backBuffer) return false;
    D3D11_TEXTURE2D_DESC desc{};
    backBuffer->GetDesc(&desc);
    const bool rgba = desc.Format == DXGI_FORMAT_R8G8B8A8_UNORM || desc.Format == DXGI_FORMAT_R8G8B8A8_UNORM_SRGB;
    const bool bgra = desc.Format == DXGI_FORMAT_B8G8R8A8_UNORM || desc.Format == DXGI_FORMAT_B8G8R8A8_UNORM_SRGB;
    if ((!rgba && !bgra) || !desc.Width || !desc.Height || desc.Width > 8192 || desc.Height > 8192) {
        backBuffer->Release(); return false;
    }
    ID3D11Texture2D* sourceTex = backBuffer;
    ID3D11Texture2D* resolveTex = nullptr;
    D3D11_TEXTURE2D_DESC readableDesc = desc;
    if (desc.SampleDesc.Count > 1) {
        readableDesc.SampleDesc.Count = 1;
        readableDesc.SampleDesc.Quality = 0;
        readableDesc.Usage = D3D11_USAGE_DEFAULT;
        readableDesc.BindFlags = 0;
        readableDesc.CPUAccessFlags = 0;
        readableDesc.MiscFlags = 0;
        if (SUCCEEDED(g_device->CreateTexture2D(&readableDesc, nullptr, &resolveTex)) && resolveTex) {
            g_context->ResolveSubresource(resolveTex, 0, backBuffer, 0, desc.Format);
            sourceTex = resolveTex;
        }
    }
    D3D11_TEXTURE2D_DESC staging = readableDesc;
    staging.BindFlags = 0;
    staging.MiscFlags = 0;
    staging.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    staging.Usage = D3D11_USAGE_STAGING;
    ID3D11Texture2D* copyTex = nullptr;
    if (FAILED(g_device->CreateTexture2D(&staging, nullptr, &copyTex)) || !copyTex) { if (resolveTex) resolveTex->Release(); backBuffer->Release(); return false; }
    g_context->CopyResource(copyTex, sourceTex);
    D3D11_MAPPED_SUBRESOURCE mapped{};
    if (FAILED(g_context->Map(copyTex, 0, D3D11_MAP_READ, 0, &mapped))) { copyTex->Release(); if (resolveTex) resolveTex->Release(); backBuffer->Release(); return false; }

    int w = static_cast<int>(readableDesc.Width);
    int h = static_cast<int>(readableDesc.Height);
    int x = 0, y = 0, cw = w, ch = h;
    const char* modeName = "full";
    if (mode == 1) { modeName = "face"; x = w / 4; y = h / 14; cw = w / 2; ch = h / 2; }
    else if (mode == 2) { modeName = "body"; x = w / 5; y = h / 20; cw = (w * 3) / 5; ch = (h * 9) / 10; }
    if (x < 0) x = 0; if (y < 0) y = 0; if (x + cw > w) cw = w - x; if (y + ch > h) ch = h - y;
    int rowBytes = ((cw * 3 + 3) / 4) * 4;
    uint32_t pixelDataSize = static_cast<uint32_t>(rowBytes * ch);
    uint32_t fileSize = 14 + 40 + pixelDataSize;
    std::string path = TimestampName(modeName);
    std::ofstream f(path, std::ios::binary);
    if (!f) { g_context->Unmap(copyTex, 0); copyTex->Release(); if (resolveTex) resolveTex->Release(); backBuffer->Release(); return false; }
    f.put('B'); f.put('M'); WriteLE32(f, fileSize); WriteLE16(f, 0); WriteLE16(f, 0); WriteLE32(f, 54);
    WriteLE32(f, 40); WriteLE32(f, static_cast<uint32_t>(cw)); WriteLE32(f, static_cast<uint32_t>(-ch)); WriteLE16(f, 1); WriteLE16(f, 24); WriteLE32(f, 0); WriteLE32(f, pixelDataSize); WriteLE32(f, 2835); WriteLE32(f, 2835); WriteLE32(f, 0); WriteLE32(f, 0);
    std::vector<unsigned char> row(static_cast<size_t>(rowBytes), 0);
    for (int yy = 0; yy < ch; ++yy) {
        const unsigned char* src = static_cast<const unsigned char*>(mapped.pData) + (y + yy) * mapped.RowPitch + x * 4;
        std::fill(row.begin(), row.end(), static_cast<unsigned char>(0));
        for (int xx = 0; xx < cw; ++xx) {
            const unsigned char* px = src + xx * 4;
            unsigned char r = bgra ? px[2] : px[0];
            unsigned char g = px[1];
            unsigned char b = bgra ? px[0] : px[2];
            row[xx * 3 + 0] = b;
            row[xx * 3 + 1] = g;
            row[xx * 3 + 2] = r;
        }
        f.write(reinterpret_cast<const char*>(row.data()), rowBytes);
    }
    f.flush();
    const bool written = f.good();
    g_context->Unmap(copyTex, 0);
    copyTex->Release();
    if (resolveTex) resolveTex->Release();
    backBuffer->Release();
    if (!written) return false;
    ++g_captureCompleted;
    {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        g_status = std::string("Saved reference screenshot: ") + path;
        g_logLines.push_back(std::string("[overlay] Saved ") + modeName + " reference screenshot: " + path);
        if (g_logLines.size() > 260) g_logLines.erase(g_logLines.begin(), g_logLines.end() - 260);
    }
    return true;
}

static void RequestScreenshot(int mode) {
    g_captureRequest = mode;
    const char* label = mode == 1 ? "face" : (mode == 2 ? "body" : "full");
    QueueAction("reference_shot_note", nullptr, label);
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    {
    std::lock_guard<std::recursive_mutex> renderLock(g_renderMutex);
    if (g_visible.load() && ImGui::GetCurrentContext()) {
        if (ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam)) return TRUE;
        ImGuiIO& io = ImGui::GetIO();
        const bool mouse = (msg >= WM_MOUSEFIRST && msg <= WM_MOUSELAST);
        const bool key = (msg >= WM_KEYFIRST && msg <= WM_KEYLAST);
        if ((mouse && io.WantCaptureMouse) || (key && io.WantCaptureKeyboard)) return TRUE;
    }
    }
    return g_oldWndProc ? CallWindowProcW(g_oldWndProc, hwnd, msg, wParam, lParam) : DefWindowProcW(hwnd, msg, wParam, lParam);
}

static void InitImGui(IDXGISwapChain* sc) {
    if (g_device) return;
    if (FAILED(sc->GetDevice(__uuidof(ID3D11Device), reinterpret_cast<void**>(&g_device))) || !g_device) return;
    g_device->GetImmediateContext(&g_context);
    DXGI_SWAP_CHAIN_DESC desc{};
    sc->GetDesc(&desc);
    g_hwnd = desc.OutputWindow;
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    io.IniFilename = nullptr;
    ImGui::StyleColorsDark();
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 14.0f; style.FrameRounding = 9.0f; style.ScrollbarRounding = 9.0f; style.GrabRounding = 9.0f; style.WindowPadding = ImVec2(16, 14);
    if (!ImGui_ImplWin32_Init(g_hwnd) || !ImGui_ImplDX11_Init(g_device, g_context)) {
        Debug("ImGui backend initialization failed");
        if (ImGui::GetIO().BackendPlatformUserData) ImGui_ImplWin32_Shutdown();
        ImGui::DestroyContext();
        if (g_context) { g_context->Release(); g_context = nullptr; }
        g_device->Release(); g_device = nullptr;
        return;
    }
    if (g_hwnd) {
        SetLastError(0);
        g_oldWndProc = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(g_hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(WndProc)));
        if (!g_oldWndProc && GetLastError() != 0) Debug("SetWindowLongPtrW failed; input capture will be disabled");
    }
    CreateRenderTarget(sc);
#ifndef APEX_NATIVE_SMOKE
    EnsureWorker();
#endif
    Debug("ImGui initialized");
    g_loaderStatus = 3;
}

static const char* ActiveOccultName() {
    if (g_selectedOccultIndex < 0 || g_selectedOccultIndex >= IM_ARRAYSIZE(kOccults)) g_selectedOccultIndex = 0;
    return kOccults[g_selectedOccultIndex];
}


static bool TextContainsNoCase(const char* haystack, const char* needle) {
    if (!needle || !needle[0]) return true;
    std::string h = haystack ? haystack : "";
    std::string n = needle ? needle : "";
    std::transform(h.begin(), h.end(), h.begin(), [](unsigned char c){ return (char)std::tolower(c); });
    std::transform(n.begin(), n.end(), n.begin(), [](unsigned char c){ return (char)std::tolower(c); });
    return h.find(n) != std::string::npos;
}

static bool CategoryMatches(const CasBodyTypeDef& item, const char* filter) {
    return TextContainsNoCase(item.group, filter) || TextContainsNoCase(item.key, filter) || TextContainsNoCase(item.label, filter);
}

static bool CategoryButton(const char* label, const char* action, const char* key) {
    if (!ImGui::SmallButton(label)) return false;
    QueueAction(action, nullptr, key);
    return true;
}

static void DrawOccultSelector() {
    ImGui::SetNextItemWidth(230);
    ImGui::Combo("Selected Occult", &g_selectedOccultIndex, kOccults, IM_ARRAYSIZE(kOccults));
}

static void DrawOccultCards(const char* action1, const char* label1, const char* action2, const char* label2, const char* action3 = nullptr, const char* label3 = nullptr, const char* action4 = nullptr, const char* label4 = nullptr) {
    if (ImGui::BeginTable("occult_grid", 3, ImGuiTableFlags_BordersInnerV | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchSame)) {
        for (int i = 0; i < IM_ARRAYSIZE(kOccults); ++i) {
            ImGui::TableNextColumn();
            ImGui::PushID(kOccults[i]);
            ImGui::TextColored(ImVec4(0.85f, 0.88f, 1.0f, 1.0f), "%s", kOccults[i]);
            ActionButton(label1, action1, kOccults[i]);
            ActionButton(label2, action2, kOccults[i]);
            if (action3 && label3) ActionButton(label3, action3, kOccults[i]);
            if (action4 && label4) ActionButton(label4, action4, kOccults[i]);
            ImGui::PopID();
        }
        ImGui::EndTable();
    }
}

static void DrawLogDock(const std::vector<std::string>& logs) {
    ImGui::Text("Running Log");
    ImGui::SameLine(); if (ImGui::SmallButton("Refresh")) QueueAction("status");
    ImGui::SameLine(); if (ImGui::SmallButton("Clear")) QueueAction("clear_logs");
    ImGui::BeginChild("logdock", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
    if (logs.empty()) ImGui::TextDisabled("No log lines yet. Run a command or press Refresh.");
    for (const auto& line : logs) {
        ImVec4 color(0.85f, 0.88f, 1.0f, 1.0f);
        if (line.find("DONE") != std::string::npos || line.find("Saved") != std::string::npos || line.find("Committed") != std::string::npos || line.find("restored") != std::string::npos) color = ImVec4(0.55f, 1.0f, 0.65f, 1.0f);
        else if (line.find("FAIL") != std::string::npos || line.find("ERROR") != std::string::npos || line.find("WARNING") != std::string::npos || line.find("failed") != std::string::npos) color = ImVec4(1.0f, 0.45f, 0.58f, 1.0f);
        else if (line.find("QUEUED") != std::string::npos || line.find("START") != std::string::npos || line.find("armed") != std::string::npos) color = ImVec4(1.0f, 0.85f, 0.45f, 1.0f);
        ImGui::TextColored(color, "%s", line.c_str());
    }
    if (ImGui::GetScrollY() >= ImGui::GetScrollMaxY() - 8.0f) ImGui::SetScrollHereY(1.0f);
    ImGui::EndChild();
}

static void DrawApexTab() {
    ImGui::TextWrapped("Core commands. Apex stays timerless unless you deliberately enable a feature; commands run once through the Sims Python queue.");
    ImGui::Columns(3, nullptr, false);
    ActionButton("Repair Active", "repair"); ActionButton("Deep Repair", "deep_repair"); ActionButton("Normalize", "normalize"); ActionButton("Recalculate", "recalc");
    if (ImGui::Checkbox("Auto Repair", &g_autoRepairToggle)) QueueAction(g_autoRepairToggle ? "auto_on" : "auto_off");
    ImGui::NextColumn();
    ActionButton("Add All Occults", "add_all"); ActionButton("Purge Non-Human", "purge"); ActionButton("Force Form Available", "force_form_available"); ActionButton("Generate All Forms", "generate_all_forms");
    ImGui::NextColumn();
    ActionButton("Repair All Sims", "repair_all"); ActionButton("Deep Repair All Sims", "deep_repair_all"); ActionButton("Sync Traits -> Flags", "sync_traits_to_flags"); ActionButton("Sync Flags -> Traits", "sync_flags_to_traits");
    ImGui::Columns(1);
}

static void DrawFormsTab() {
    DrawOccultSelector();
    ImGui::SameLine(); if (ImGui::Button("Switch Selected")) QueueAction("switch", ActiveOccultName());
    ImGui::SameLine(); if (ImGui::Button("Commit Current -> Selected Occult")) QueueAction("commit_current_to_occult", ActiveOccultName(), g_formLabel);
    ImGui::TextWrapped("After CAS editing, use Commit Current -> Selected Occult. This copies the visible/current appearance into the stored occult sim_info, saves a baseline, and mirrors it into saved forms.");
    ImGui::SeparatorText("Form data commands");
    DrawOccultCards("generate_form", "Generate", "delete_form", "Delete", "copy_human_to_form", "Human -> Form", "copy_current_to_form", "Current -> Form");
    ImGui::SeparatorText("Direct occult control");
    DrawOccultCards("add", "Add", "remove", "Remove", "switch", "Switch", "gameplay_add", "Gameplay Init");
    ImGui::SeparatorText("Human-looking Werewolf");
    ImGui::TextWrapped("Copy the Human look into the Werewolf appearance while keeping Werewolf gameplay. The original look is retained. Restore refuses to overwrite newer CAS edits.");
    if (ImGui::Button("Use Human look")) QueueAction("werewolf_human_on");
    ImGui::SameLine(); if (ImGui::Button("Restore original Werewolf look")) QueueAction("werewolf_human_off");
    ImGui::SameLine(); if (ImGui::Button("Werewolf appearance status")) QueueAction("werewolf_human_status");
}

static void DrawSavedFormsTab() {
    DrawOccultSelector();
    ImGui::InputText("Save Label", g_formLabel, sizeof(g_formLabel));
    ImGui::InputText("Search Saved Forms", g_formSearch, sizeof(g_formSearch));
    ImGui::InputText("Slot ID / Label to Apply", g_formSlot, sizeof(g_formSlot));
    ImGui::Columns(2, nullptr, false);
    if (ImGui::Button("Save Current as Selected Occult", ImVec2(-1, 0))) QueueAction("save_current_form", ActiveOccultName(), g_formLabel);
    if (ImGui::Button("Save Existing Occult Form", ImVec2(-1, 0))) QueueAction("save_occult_form", ActiveOccultName(), g_formLabel);
    if (ImGui::Button("Search / Refresh Saved Forms", ImVec2(-1, 0))) QueueAction("list_saved_forms", nullptr, g_formSearch);
    ImGui::NextColumn();
    if (ImGui::Button("Force Apply Slot to Selected Occult", ImVec2(-1, 0))) QueueAction("force_apply_saved_form", ActiveOccultName(), g_formSlot);
    if (ImGui::Button("Apply Slot to Current Sim", ImVec2(-1, 0))) QueueAction("apply_saved_form_current", ActiveOccultName(), g_formSlot);
    if (ImGui::Button("Delete Slot", ImVec2(-1, 0))) QueueAction("delete_saved_form", nullptr, g_formSlot);
    ImGui::Columns(1);
    ImGui::TextWrapped("Saved forms automatically become Drift Guard baselines, so Apex can warn if the form changes later.");
}

static void DrawDriftGuardTab() {
    DrawOccultSelector();
    if (ImGui::Checkbox("Scan after Apex button commands", &g_driftAfterCommandsToggle)) QueueAction(g_driftAfterCommandsToggle ? "drift_scan_after_commands_on" : "drift_scan_after_commands_off");
    ImGui::TextWrapped("Fire-once drift guard: no constant timer. Scan manually, or scan once after Apex commands. If the stored occult form no longer matches its baseline, a warning appears and the Fix button restores it. If current CAS edits were not committed, Fix commits current -> occult instead of overwriting your work.");
    ImGui::Columns(2, nullptr, false);
    ActionButton("Scan Selected Occult", "scan_occult_drift", ActiveOccultName());
    ActionButton("Scan All Active Occults", "scan_occult_drift");
    ActionButton("Fix Selected Warning", "fix_occult_drift", ActiveOccultName());
    ActionButton("Fix All Warnings", "fix_occult_drift");
    ImGui::NextColumn();
    ActionButton("Accept Selected as Baseline", "accept_occult_baseline", ActiveOccultName(), g_formLabel);
    ActionButton("Commit Current -> Selected Occult", "commit_current_to_occult", ActiveOccultName(), g_formLabel);
    ActionButton("Commit Current -> All Active Forms", "commit_current_to_all_forms", nullptr, g_formLabel);
    ActionButton("Clear Drift Warnings", "clear_drift_warnings");
    ImGui::Columns(1);
    ImGui::SeparatorText("What the warning means");
    ImGui::BulletText("appearance_drift: stored form differs from accepted/saved baseline.");
    ImGui::BulletText("current_not_committed: CAS changed the visible form but the occult form did not save it yet.");
    ImGui::BulletText("missing_baseline: save or accept the expected look once so future drift can be detected.");
}

static void DrawReferenceShotTab() {
    ImGui::TextWrapped("Frame the Sim in-game, then capture. The overlay saves BMP reference shots before ImGui is drawn, so the menu is not in the image. Use face/body shots as visual proof of what each occult form should look like.");
    DrawOccultSelector();
    ImGui::Columns(3, nullptr, false);
    if (ImGui::Button("Face Reference Screenshot", ImVec2(-1, 0))) RequestScreenshot(1);
    ImGui::TextWrapped("Crops the upper center of the current game frame. Zoom to the face first.");
    ImGui::NextColumn();
    if (ImGui::Button("Body Reference Screenshot", ImVec2(-1, 0))) RequestScreenshot(2);
    ImGui::TextWrapped("Crops most of the Sim/body area. Frame the full body first.");
    ImGui::NextColumn();
    if (ImGui::Button("Full Frame Screenshot", ImVec2(-1, 0))) RequestScreenshot(3);
    ImGui::TextWrapped("Captures the full game frame as a BMP reference.");
    ImGui::Columns(1);
    ImGui::SeparatorText("Folder");
    ImGui::TextWrapped("Documents\\Electronic Arts\\The Sims 4\\TD1ApexScreenshots");
    ImGui::SeparatorText("Recommended flow");
    ImGui::BulletText("Switch to the occult form.");
    ImGui::BulletText("Frame the face/body in Live Mode or CAS preview.");
    ImGui::BulletText("Capture face and body, then Save Current/Accept Baseline.");
}

static void DrawCasToolsTab() {
    ImGui::TextWrapped("Appearance tools are scoped so they do not paste occult identity flags. They help maintain hair, makeup, tattoos/details, skin, body, and voice across hybrid forms.");
    ImGui::Columns(3, nullptr, false);
    ActionButton("Copy Full CAS", "copy_cas"); ActionButton("Paste Full CAS", "paste_cas"); ActionButton("Apply CAS to All Forms", "apply_cas_to_all_forms");
    ImGui::NextColumn();
    ActionButton("Copy Wardrobe", "copy_wardrobe"); ActionButton("Paste Wardrobe", "paste_wardrobe"); ActionButton("Apply Wardrobe to All Forms", "apply_wardrobe_to_all_forms");
    ImGui::NextColumn();
    ActionButton("Copy Body", "copy_body"); ActionButton("Paste Body", "paste_body"); ActionButton("Apply Body to All Forms", "apply_body_to_all_forms");
    ImGui::Columns(1); ImGui::Separator(); ImGui::Columns(3, nullptr, false);
    ActionButton("Copy Skin", "copy_skin"); ActionButton("Paste Skin", "paste_skin"); ActionButton("Apply Skin to All Forms", "apply_skin_to_all_forms");
    ImGui::NextColumn();
    ActionButton("Copy Tattoos/Details", "copy_tattoos"); ActionButton("Paste Tattoos/Details", "paste_tattoos"); ActionButton("Apply Tattoos to All Forms", "apply_tattoos_to_all_forms");
    ImGui::NextColumn();
    ActionButton("Copy Voice", "copy_voice"); ActionButton("Paste Voice", "paste_voice"); ActionButton("Apply Voice to All Forms", "apply_voice_to_all_forms");
    ImGui::Columns(1);
}


static void DrawCasCategoryTab() {
    ImGui::TextWrapped("Every Sims 4 BodyType/CAS slot gets its own fire-on-click copy/paste/apply command. These commands copy only the selected category and never run on a timer. Patch-sensitive categories such as Head Decoration, Skin Specularity, Wings, and Base Layer fail closed unless the live game runtime exposes the matching BodyType enum.");
    ImGui::InputText("Search CAS category", g_casCategoryFilter, sizeof(g_casCategoryFilter));
    ImGui::SameLine(); if (ImGui::Button("Category Status")) QueueAction("cas_category_status");
    ImGui::SameLine(); if (ImGui::Button("Clear Search")) g_casCategoryFilter[0] = '\0';
    ImGui::Separator();
    ImGui::BeginChild("cas_category_scroll", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
    const char* lastGroup = "";
    int shown = 0;
    for (int i = 0; i < IM_ARRAYSIZE(kCasBodyTypes); ++i) {
        const CasBodyTypeDef& item = kCasBodyTypes[i];
        if (!CategoryMatches(item, g_casCategoryFilter)) continue;
        if (std::strcmp(lastGroup, item.group) != 0) {
            if (shown > 0) ImGui::Spacing();
            ImGui::SeparatorText(item.group);
            lastGroup = item.group;
        }
        ImGui::PushID(item.key);
        ImGui::Text("%s", item.label);
        ImGui::SameLine(260); ImGui::TextDisabled("%s  [%d]", item.key, item.fallbackValue);
        ImGui::SameLine(520); CategoryButton("Copy", "copy_cas_category", item.key);
        ImGui::SameLine(); CategoryButton("Paste", "paste_cas_category", item.key);
        ImGui::SameLine(); CategoryButton("Apply All Forms", "apply_cas_category_to_all_forms", item.key);
        ImGui::PopID();
        ++shown;
    }
    if (shown == 0) ImGui::TextDisabled("No categories matched the search.");
    ImGui::EndChild();
}

static void DrawMcccTab() {
    ImGui::TextWrapped("MCCC compatibility shield: prepare before MCCC > Sim Commands > Modify in CAS, restore after returning, then use Drift Guard Commit if current edits were not saved into the occult form.");
    DrawOccultSelector();
    if (ImGui::Checkbox("MCCC Auto-Restore", &g_mcccAutoRestoreToggle)) QueueAction(g_mcccAutoRestoreToggle ? "mccc_auto_restore_on" : "mccc_auto_restore_off");
    ImGui::SameLine();
    ImGui::TextDisabled("MCCC private/soft hooks are locked off in V9.5; use explicit Arm/Restore only.");
    if (ImGui::SmallButton("Verify Hook Lockdown")) QueueAction("mccc_soft_hooks_on");
    ImGui::Columns(2, nullptr, false);
    ActionButton("Detect MCCC Modules", "mccc_detect"); ActionButton("Arm Active - Keep Human", "mccc_prepare_active"); ActionButton("Arm Household - Keep Human", "mccc_prepare_household"); ActionButton("Restore Active After MCCC CAS", "mccc_restore_active");
    ImGui::NextColumn();
    if (ImGui::Button("Arm Active - Keep Selected Occult", ImVec2(-1, 0))) QueueAction("mccc_prepare_active", ActiveOccultName());
    if (ImGui::Button("Arm Household - Keep Selected Occult", ImVec2(-1, 0))) QueueAction("mccc_prepare_household", ActiveOccultName());
    ActionButton("Restore Household After MCCC CAS", "mccc_restore_household"); ActionButton("Register Lot51 Events", "lot51_register_events");
    ImGui::Columns(1);
}

static void DrawRawTab() {
    ImGui::InputText("occult_types", g_rawFlags, sizeof(g_rawFlags)); ImGui::SameLine(); if (ImGui::Button("Set Normalized Flags")) QueueAction("set_flags_normalized", nullptr, g_rawFlags);
    ImGui::InputText("current_occult_types", g_rawCurrent, sizeof(g_rawCurrent)); ImGui::SameLine(); if (ImGui::Button("Set Normalized Current")) QueueAction("set_current_normalized", nullptr, g_rawCurrent);
    ImGui::SeparatorText("Raw occult helpers");
    DrawOccultCards("toggle_flag", "Toggle Raw", "on_add_actions", "On-Add Actions", "lock_perks", "Lock Perks", "unlock_perks", "Unlock Perks");
}

static void UpdateStudioData(const std::string& reply) {
    if (reply == g_studioLastReply) return;
    g_studioLastReply = reply;
    const auto& parsed = ui::ReadObject(reply);
    if (!ui::StudioDocument(parsed)) return;
    if (ui::Scalar(parsed, "history_lane") != ui::Scalar(g_studioData, "history_lane")) {
        g_studioData = ui::Json::object();
        g_historyId[0] = '\0';
        g_studioOutfitIndex = 0; g_studioPartIndex = 0;
    }
    for (auto item = parsed.begin(); item != parsed.end(); ++item) g_studioData[item.key()] = item.value();
    // Successful Apply/Cancel replies include null; an old token must vanish.
    if (parsed.contains("pending_preview"))
        strncpy_s(g_previewId, ui::Scalar(parsed, "pending_preview").c_str(), _TRUNCATE);
    // Refresh the inventory explicitly after a write; never present pre-write
    // part metadata as current. History nodes remain useful after the change.
    const auto message = ui::Scalar(parsed, "message");
    if (message.find("Appearance write matches") == 0) {
        g_studioData.erase("outfit_inventory"); g_studioData.erase("color_editor"); g_colorEditorKey.clear();
    }
    if (parsed.contains("appearance_sha256") && g_studioData.contains("color_editor") &&
        ui::Scalar(parsed, "appearance_sha256") != ui::Scalar(g_studioData["color_editor"], "appearance_sha256")) {
        g_studioData.erase("color_editor"); g_colorEditorKey.clear();
    }
}

static void DrawNumericColor(const std::string& target) {
    const auto found = g_studioData.find("color_editor");
    if (found == g_studioData.end() || ui::Scalar(*found, "target") != target) {
        ImGui::TextDisabled("Inspect this part's slider bounds to enable numeric editing."); return;
    }
    const auto& editor = *found;
    const auto editorKey = target + ui::Scalar(g_studioData, "history_lane") +
        ui::Scalar(editor, "appearance_sha256") + ui::Scalar(editor, "resource_sha256") + ui::Scalar(editor, "color_hex");
    const char* names[] = {"hue", "saturation", "brightness", "opacity"};
    if (g_colorEditorKey != editorKey) {
        g_colorEditorKey = editorKey;
        for (unsigned index = 0; index < 4; ++index) {
            g_colorValues[index] = editor["channels"][names[index]]["value"].get<float>();
            g_colorChanged[index] = false;
        }
    }
    ImGui::SeparatorText("Numeric color / selected part");
    ImGui::TextUnformatted(ui::Scalar(editor, "part_name").c_str());
    bool changes = false;
    for (unsigned index = 0; index < 4; ++index) {
        const auto& channel = editor["channels"][names[index]];
        ImGui::PushID(static_cast<int>(index));
        ImGui::BeginDisabled(!channel["enabled"].get<bool>());
        const float low = channel["min"].get<float>(), high = channel["max"].get<float>();
        if (ImGui::SliderFloat(names[index], &g_colorValues[index], low, high, "%.6f")) g_colorChanged[index] = true;
        ImGui::SameLine();
        if (ImGui::SmallButton("Reset")) {
            const float neutral = index == 3 ? 1.0f : 0.0f;
            if (neutral >= low && neutral <= high) { g_colorValues[index] = neutral; g_colorChanged[index] = true; }
        }
        ImGui::EndDisabled();
        ImGui::TextDisabled("Range %.6g to %.6g | CAS increment %.6g%s", low, high,
            channel["step"].get<double>(), g_colorChanged[index] ? " | edited" : "");
        changes = changes || g_colorChanged[index];
        ImGui::PopID();
    }
    ImGui::BeginDisabled(!changes);
    if (ImGui::Button("Prepare numeric color preview")) {
        ui::Json edits = ui::Json::object();
        for (unsigned index = 0; index < 4; ++index) if (g_colorChanged[index]) edits[names[index]] = g_colorValues[index];
        const ui::Json request = {{"target", target}, {"lane", ui::Scalar(g_studioData, "history_lane")},
            {"cas_part_id", editor["cas_part_id"]}, {"color_hex", editor["color_hex"]},
            {"appearance_sha256", editor["appearance_sha256"]}, {"resource_sha256", editor["resource_sha256"]}, {"edits", edits}};
        const auto payload = request.dump(); QueueAction("studio_color_edit", nullptr, payload.c_str());
    }
    ImGui::EndDisabled();
    ImGui::TextWrapped("Only edited lanes change. Preview reports the exact Q14 result; Apply commits it. Texture compatibility is separate from slider metadata. Skin specularity uses the brightness lane for gloss in the baseline CAS UI.");
}

static void DrawStudioParts() {
    const auto found = g_studioData.find("outfit_inventory");
    if (found == g_studioData.end() || found->empty()) {
        ImGui::TextDisabled("Inspect outfits to choose the current form's actual parts.");
        return;
    }
    const auto& outfits = *found;
    g_studioOutfitIndex = std::clamp(g_studioOutfitIndex, 0, static_cast<int>(outfits.size()) - 1);
    const auto& outfit = outfits[static_cast<size_t>(g_studioOutfitIndex)];
    const auto outfitLabel = "Outfit " + ui::Scalar(outfit, "index") + " | category " + ui::Scalar(outfit, "category");
    if (ImGui::BeginCombo("Outfit", outfitLabel.c_str())) {
        for (size_t i = 0; i < outfits.size(); ++i) {
            const auto label = "Outfit " + ui::Scalar(outfits[i], "index") + " | category " + ui::Scalar(outfits[i], "category");
            if (ImGui::Selectable(label.c_str(), g_studioOutfitIndex == static_cast<int>(i))) {
                g_studioOutfitIndex = static_cast<int>(i); g_studioPartIndex = 0;
            }
        }
        ImGui::EndCombo();
    }
    // Read again after a combo selection changed the outfit.
    const auto& selected = outfits[static_cast<size_t>(g_studioOutfitIndex)];
    const auto& parts = selected["parts"];
    if (parts.empty()) { ImGui::TextDisabled("This outfit has no serialized CAS parts."); return; }
    g_studioPartIndex = std::clamp(g_studioPartIndex, 0, static_cast<int>(parts.size()) - 1);
    auto partLabel = [](const ui::Json& part) {
        return ui::Scalar(part, "label") + " | row " + ui::Scalar(part, "index") + " | " + ui::Scalar(part, "cas_part_hex");
    };
    const auto label = partLabel(parts[static_cast<size_t>(g_studioPartIndex)]);
    if (ImGui::BeginCombo("CAS part / layer", label.c_str())) {
        for (size_t i = 0; i < parts.size(); ++i) {
            ImGui::PushID(static_cast<int>(i));
            if (ImGui::Selectable(partLabel(parts[i]).c_str(), g_studioPartIndex == static_cast<int>(i)))
                g_studioPartIndex = static_cast<int>(i);
            ImGui::PopID();
        }
        ImGui::EndCombo();
    }
    const auto& part = parts[static_cast<size_t>(g_studioPartIndex)];
    const auto target = ui::Scalar(part, "target");
    const auto color = ui::Scalar(part, "color_hex");
    ImGui::Text("CAS resource: %s | object: %s | layer: %s", ui::Scalar(part, "cas_part_hex").c_str(),
        ui::Scalar(part, "object_id").c_str(), ui::Scalar(part, "layer_id").c_str());
    ImGui::Text("Exact color: %s", color.empty() ? "absent (preserved)" : color.c_str());
    const bool supported = part["target_supported"].get<bool>() && !color.empty();
    ImGui::BeginDisabled(!supported);
    if (ImGui::Button("Copy selected part color")) QueueAction("studio_color_copy", nullptr, target.c_str());
    ImGui::SameLine(); if (ImGui::Button("Preview paste to selected part")) QueueAction("studio_color_preview", nullptr, target.c_str());
    if (ImGui::Button("Inspect selected part slider bounds")) QueueAction("studio_color_inspect", nullptr, target.c_str());
    ImGui::EndDisabled();
    if (!supported) ImGui::TextWrapped("Unavailable: %s", color.empty() ? "this part has no explicit slider state" : ui::Scalar(part, "target_reason").c_str());
    if (supported) DrawNumericColor(target);
}

static void DrawStudioTimeline() {
    ImGui::InputText("Search history", g_historySearch, sizeof(g_historySearch));
    ImGui::SeparatorText("Preserved history branches");
    const auto found = g_studioData.find("history_nodes");
    if (found == g_studioData.end() || found->empty()) {
        ImGui::TextDisabled("Capture a checkpoint to start this save/Sim/form lane."); return;
    }
    if (ImGui::BeginTable("studio_timeline", 3, ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Checkpoint / operation"); ImGui::TableSetupColumn("Branch parent");
        ImGui::TableSetupColumn("Identity"); ImGui::TableHeadersRow();
        for (const auto& node : *found) {
            const auto id = ui::Scalar(node, "id");
            const auto label = ui::Scalar(node, "label");
            if (!TextContainsNoCase(label.c_str(), g_historySearch) && !TextContainsNoCase(id.c_str(), g_historySearch)) continue;
            const bool current = id == ui::Scalar(g_studioData, "history_cursor");
            ImGui::PushID(id.c_str()); ImGui::TableNextRow(); ImGui::TableNextColumn();
            if (ImGui::Selectable(((current ? "* " : "") + label).c_str(), id == g_historyId, ImGuiSelectableFlags_SpanAllColumns))
                strncpy_s(g_historyId, id.c_str(), _TRUNCATE);
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s\nCaptured: %.0f (UTC epoch)\nReadback proof is separate from save/reload proof.", id.c_str(), node["time"].get<double>());
            ImGui::TableNextColumn(); const auto parent = ui::Scalar(node, "parent");
            ImGui::TextUnformatted(parent.empty() ? "Root" : parent.substr(0, 8).c_str());
            ImGui::TableNextColumn(); ImGui::TextUnformatted(id.substr(0, 8).c_str()); ImGui::PopID();
        }
        ImGui::EndTable();
    }
}

static void DrawStudioTab(const std::string& reply, bool history) {
    UpdateStudioData(reply);
    ImGui::TextWrapped("Target: selected Sim's current form. Preview and Apply are separate; stale previews are rejected. Readback verification does not prove save/reload persistence.");
    ActionButton("Inspect outfits / history", "studio_status");
    std::string outfits = ExtractJsonValue(reply, "outfit_text");
    if (!outfits.empty()) ImGui::TextUnformatted(outfits.c_str());
    if (history) {
        ImGui::InputText("Checkpoint label", g_checkpointLabel, sizeof(g_checkpointLabel));
        if (ImGui::Button("Capture named checkpoint")) QueueAction("studio_checkpoint", nullptr, g_checkpointLabel);
        DrawStudioTimeline();
        ImGui::InputText("Selected history node / redo branch", g_historyId, sizeof(g_historyId));
        if (ImGui::Button("Preview Undo")) QueueAction("studio_undo");
        ImGui::SameLine(); if (ImGui::Button("Preview Redo")) QueueAction("studio_redo", nullptr, g_historyId);
        ImGui::SameLine(); ImGui::BeginDisabled(!g_historyId[0]);
        if (ImGui::Button("Preview Jump")) QueueAction("studio_jump", nullptr, g_historyId);
        ImGui::EndDisabled();
        if (ImGui::Button("Resolve interrupted transaction")) QueueAction("studio_recover");
    } else {
        DrawStudioParts();
        if (ImGui::CollapsingHeader("Advanced explicit target")) {
            ImGui::InputText("Outfit : BodyType : optional part row", g_studioTarget, sizeof(g_studioTarget));
            ImGui::TextDisabled("Example: 0:HAIR or 0:HAIR:2. Layered slots require an explicit row.");
            if (ImGui::Button("Copy exact part color")) QueueAction("studio_color_copy", nullptr, g_studioTarget);
            ImGui::SameLine(); if (ImGui::Button("Preview color paste")) QueueAction("studio_color_preview", nullptr, g_studioTarget);
        }
        std::string color = ExtractJsonValue(reply, "raw_color_hex");
        if (!color.empty()) ImGui::Text("Exact uint64 color state: %s", color.c_str());
        ImGui::TextWrapped("Color-only paste requires the identical CAS part. Numeric editing reads the effective part resource and rejects stale Sim/form/save, appearance and resource revisions.");
    }
    std::string diff = ExtractJsonValue(reply, "preview_diff");
    if (!diff.empty()) ImGui::TextWrapped("%s", diff.c_str());
    ImGui::SeparatorText("Explicit transaction control");
    ImGui::InputText("Preview ID", g_previewId, sizeof(g_previewId));
    ImGui::BeginDisabled(!g_previewId[0]);
    if (ImGui::Button("Apply accepted preview")) QueueAction("studio_apply", nullptr, g_previewId);
    ImGui::SameLine(); if (ImGui::Button("Cancel preview")) QueueAction("studio_cancel", nullptr, g_previewId);
    ImGui::EndDisabled();
}

static void DrawConfirmation() {
    if (g_openConfirmation) { ImGui::OpenPopup("Confirm state-changing operation"); g_openConfirmation = false; }
    if (ImGui::BeginPopupModal("Confirm state-changing operation", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::TextWrapped("Operation: %s", g_confirmAction.c_str());
        ImGui::TextWrapped("This can remove or replace form/trait data, change multiple Sims, or prepare CAS by temporarily hiding occult traits. Capture the relevant forms first. Legacy operations are not yet covered by Studio Undo.");
        if (ImGui::Button("Run this operation")) {
            bool sameSelection;
            { std::lock_guard<std::mutex> lock(g_dataMutex); sameSelection = g_confirmGeneration == g_selectionGeneration; }
            if (sameSelection) QueueCommand(g_confirmPath);
            else { std::lock_guard<std::mutex> lock(g_dataMutex); g_status = "Selection changed; confirmation cancelled"; }
            g_confirmPath.clear(); ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine(); if (ImGui::Button("Cancel")) { g_confirmPath.clear(); ImGui::CloseCurrentPopup(); }
        ImGui::EndPopup();
    }
}

static void LoadOverlayConfig() {
    if (g_configLoaded) return;
    g_configLoaded = true;
    HMODULE ownModule = nullptr;
    wchar_t path[MAX_PATH] = {};
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(&LoadOverlayConfig), &ownModule)) return;
    DWORD length = GetModuleFileNameW(ownModule, path, MAX_PATH);
    if (!length || length >= MAX_PATH) return;
    std::wstring config(path);
    size_t slash = config.find_last_of(L"\\/");
    if (slash == std::wstring::npos) return;
    config = config.substr(0, slash + 1) + L"ApexOverlay.ini";
    wchar_t key[16] = {};
    GetPrivateProfileStringW(L"Overlay", L"ToggleKey", L"F11", key, 16, config.c_str());
    if (key[0] == L'F' && key[1] >= L'0' && key[1] <= L'9') {
        wchar_t* end = nullptr;
        long number = wcstol(key + 1, &end, 10);
        if (end && !*end && number >= 1 && number <= 24) g_toggleKey = VK_F1 + static_cast<UINT>(number - 1);
    }
}

static void DrawOverlay() {
    ImGui::SetNextWindowSize(ImVec2(1320, 820), ImGuiCond_FirstUseEver);
    ImGui::Begin("Apex Occult Hybrid - Authorized Baseline Development Build", nullptr, ImGuiWindowFlags_NoCollapse);
    std::string status, json, sim, reply;
    std::vector<std::string> logs;
    { std::lock_guard<std::mutex> lock(g_dataMutex); status = g_status; json = g_json; logs = g_logLines; sim = g_selectedSim; reply = g_commandReply; }

    ImGui::TextColored(ImVec4(0.45f, 0.95f, 1.0f, 1.0f), "%s", status.c_str());
    ImGui::SameLine(); ImGui::TextDisabled("F%u toggle | hidden: no HTTP polling", g_toggleKey - VK_F1 + 1);
    std::string commandMessage = ExtractJsonValue(reply, "message");
    if (!commandMessage.empty()) ImGui::TextWrapped("Last command: %s", commandMessage.c_str());
    char simBuf[64] = {};
    strncpy_s(simBuf, sim.c_str(), _TRUNCATE);
    ImGui::SetNextItemWidth(260);
    if (ImGui::InputText("Target Sim ID", simBuf, sizeof(simBuf))) {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        g_selectedSim = simBuf;
        ++g_selectionGeneration;
        g_json = "{}";
        g_commandReply = "{}";
        g_previewId[0] = '\0'; g_historyId[0] = '\0';
        g_studioData = ui::Json::object(); g_studioLastReply.clear();
        g_studioOutfitIndex = 0; g_studioPartIndex = 0;
        g_status = "Selection changed; waiting for current data";
        g_lastStatusMs = 0;
    }
    ImGui::SameLine(); ActionButton("Refresh", "status", nullptr, nullptr, ImVec2(86,0));
    ImGui::SameLine(); ActionButton("Health", "health", nullptr, nullptr, ImVec2(86,0));
    ImGui::SameLine(); ActionButton("Diagnostics", "diagnostics", nullptr, nullptr, ImVec2(112,0));
    ImGui::SameLine(); ActionButton("QA Self-Test", "qa_self_test", nullptr, nullptr, ImVec2(128,0));
    ImGui::SameLine(); ActionButton("Code Audit", "code_audit", nullptr, nullptr, ImVec2(112,0));
    ImGui::SameLine(); ActionButton("Research Audit", "research_audit", nullptr, nullptr, ImVec2(136,0));
    ImGui::SameLine(); ActionButton("Final Audit", "final_audit", nullptr, nullptr, ImVec2(116,0));
    std::string warn = ui::StatusScalar(ui::ReadObject(json), "drift_warning_count");
    if (!warn.empty() && warn != "0") {
        ImGui::Separator();
        ImGui::TextColored(ImVec4(1.0f, 0.35f, 0.40f, 1.0f), "DRIFT WARNING: %s issue(s) found. Open Drift Guard or press Fix.", warn.c_str());
        ImGui::SameLine(); if (ImGui::Button("Fix Selected")) QueueAction("fix_occult_drift", ActiveOccultName());
        ImGui::SameLine(); if (ImGui::Button("Scan Again")) QueueAction("scan_occult_drift");
    }
    ImGui::Separator();

    const char* tabs[] = {"Apex", "Forms", "Saved Forms", "Drift Guard", "Reference Shots", "CAS Tools", "CAS Categories", "MCCC Shield", "Raw Flags", "Sims/API", "Log", "CAS History", "Color Studio"};
    ImGui::BeginChild("navigation", ImVec2(160, 0), true);
    for (int i = 0; i < IM_ARRAYSIZE(tabs); ++i) {
        if (ImGui::Selectable(tabs[i], g_activeTab == i)) g_activeTab = i;
    }
    ImGui::EndChild();
    ImGui::SameLine();

    ImGui::BeginChild("main_left", ImVec2(ImGui::GetContentRegionAvail().x * 0.65f, 0), false);
    if (g_activeTab == 0) DrawApexTab();
    else if (g_activeTab == 1) DrawFormsTab();
    else if (g_activeTab == 2) DrawSavedFormsTab();
    else if (g_activeTab == 3) DrawDriftGuardTab();
    else if (g_activeTab == 4) DrawReferenceShotTab();
    else if (g_activeTab == 5) DrawCasToolsTab();
    else if (g_activeTab == 6) DrawCasCategoryTab();
    else if (g_activeTab == 7) DrawMcccTab();
    else if (g_activeTab == 8) DrawRawTab();
    else if (g_activeTab == 9) {
        ActionButton("List Sims", "list_sims", nullptr, nullptr, ImVec2(110,0)); ImGui::SameLine();
        ActionButton("Overlay Capabilities", "overlay_capabilities", nullptr, nullptr, ImVec2(180,0)); ImGui::SameLine();
        ActionButton("Drift Status", "drift_status", nullptr, nullptr, ImVec2(120,0)); ImGui::SameLine();
        ActionButton("MCCC Status", "mccc_status", nullptr, nullptr, ImVec2(120,0));
        ImGui::BeginChild("json", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar); ImGui::TextUnformatted(json.c_str()); ImGui::EndChild();
    } else if (g_activeTab == 10) DrawLogDock(logs);
    else if (g_activeTab == 11) DrawStudioTab(reply, true);
    else if (g_activeTab == 12) DrawStudioTab(reply, false);
    ImGui::EndChild();
    ImGui::SameLine();
    ImGui::BeginChild("right_dock", ImVec2(0, 0), true);
    DrawLogDock(logs);
    ImGui::EndChild();
    DrawConfirmation();
    ImGui::End();
}

static void ResetRenderer() {
    g_visible = false;
    CleanupRenderTarget();
    if (g_hwnd && IsWindow(g_hwnd) && g_oldWndProc &&
        reinterpret_cast<WNDPROC>(GetWindowLongPtrW(g_hwnd, GWLP_WNDPROC)) == WndProc)
        SetWindowLongPtrW(g_hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_oldWndProc));
    if (ImGui::GetCurrentContext()) {
        ImGui_ImplDX11_Shutdown(); ImGui_ImplWin32_Shutdown(); ImGui::DestroyContext();
    }
    if (g_context) { g_context->Release(); g_context = nullptr; }
    if (g_device) { g_device->Release(); g_device = nullptr; }
    g_swapChain = nullptr; g_hwnd = nullptr; g_oldWndProc = nullptr;
    g_toggleInput = ToggleInput(); g_loaderStatus = 1;
}

static bool SelectSwapChain(IDXGISwapChain* sc) {
    if (g_swapChain && !IsWindow(g_hwnd)) ResetRenderer();
    if (g_swapChain) return sc == g_swapChain;
    DXGI_SWAP_CHAIN_DESC desc{};
    DWORD process = 0;
    RECT client{};
    if (!sc || FAILED(sc->GetDesc(&desc)) || !IsWindow(desc.OutputWindow)) return false;
    GetWindowThreadProcessId(desc.OutputWindow, &process);
    if (process != GetCurrentProcessId() || !GetClientRect(desc.OutputWindow, &client) ||
        client.right <= client.left || client.bottom <= client.top) return false;
#ifndef APEX_NATIVE_SMOKE
    if (!IsWindowVisible(desc.OutputWindow) || GetAncestor(GetForegroundWindow(), GA_ROOT) !=
        GetAncestor(desc.OutputWindow, GA_ROOT)) return false;
#endif
    // Discover the actual window before the first keypress. The previous code
    // checked a null handle, then initialized it only after a successful toggle.
    g_hwnd = desc.OutputWindow;
    g_swapChain = sc;
    g_loaderStatus = 2;
    return true;
}

struct RestoreRenderTargets {
    ID3D11DeviceContext* context;
    ID3D11RenderTargetView* views[D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT]{};
    ID3D11DepthStencilView* depth = nullptr;
    explicit RestoreRenderTargets(ID3D11DeviceContext* owner) : context(owner) {
        context->OMGetRenderTargets(D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT, views, &depth);
    }
    ~RestoreRenderTargets() {
        context->OMSetRenderTargets(D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT, views, depth);
        for (auto* view : views) if (view) view->Release();
        if (depth) depth->Release();
    }
};

static void RenderOverlayFrame(IDXGISwapChain* sc) {
#ifdef APEX_NATIVE_SMOKE
    ++g_presentCount;
#endif
    LoadOverlayConfig();
    const bool foreground = GetAncestor(GetForegroundWindow(), GA_ROOT) == GetAncestor(g_hwnd, GA_ROOT);
    if (g_toggleInput.sample(foreground, (GetAsyncKeyState(g_toggleKey) & 0x8000) != 0)) {
        g_visible = !g_visible.load();
        ++g_toggleEvents;
    }
    if (g_captureRequest.load() && g_loaderStatus.load() >= 3) {
        const int capture = g_captureRequest.exchange(0);
        if (capture) SaveBackbufferBmp(sc, capture);
    }
    if (g_visible.load()) {
        InitImGui(sc);
        if (g_device && g_context) {
            CreateRenderTarget(sc);
            ImGui_ImplDX11_NewFrame();
            ImGui_ImplWin32_NewFrame();
            ImGui::NewFrame();
            DrawOverlay();
            ImGui::Render();
            if (g_rtv) {
                // Capture before setting our target; the ImGui backend captures
                // after this point and cannot restore the original game targets.
                RestoreRenderTargets restore(g_context);
                g_context->OMSetRenderTargets(1, &g_rtv, nullptr);
                ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
                if (g_renderedFrames.load() < 1000000000) ++g_renderedFrames;
            }
        }
    }
}

static thread_local unsigned g_presentDepth = 0;
struct PresentDepth {
    PresentDepth() { ++g_presentDepth; }
    ~PresentDepth() { --g_presentDepth; }
};

static HRESULT STDMETHODCALLTYPE HookPresent(IDXGISwapChain* sc, UINT sync, UINT flags) {
    std::lock_guard<std::recursive_mutex> renderLock(g_renderMutex);
    const bool outer = g_presentDepth == 0;
    PresentDepth depth;
    if (outer && !(flags & DXGI_PRESENT_TEST) && SelectSwapChain(sc)) RenderOverlayFrame(sc);
    const HRESULT result = g_realPresent(sc, sync, flags);
    if (result == DXGI_ERROR_DEVICE_REMOVED || result == DXGI_ERROR_DEVICE_RESET) ResetRenderer();
    return result;
}

static HRESULT STDMETHODCALLTYPE HookPresent1(IDXGISwapChain1* sc, UINT sync, UINT flags,
                                               const DXGI_PRESENT_PARAMETERS* parameters) {
    std::lock_guard<std::recursive_mutex> renderLock(g_renderMutex);
    const bool outer = g_presentDepth == 0;
    PresentDepth depth;
    const bool selected = outer && !(flags & DXGI_PRESENT_TEST) && SelectSwapChain(sc);
    if (selected) RenderOverlayFrame(sc);
    // An overlay can paint beyond the caller's dirty region. Request a full
    // presentation only while visible; hidden/test calls keep exact parameters.
    DXGI_PRESENT_PARAMETERS fullFrame{};
    const auto* forwarded = selected && g_visible.load() && parameters ? &fullFrame : parameters;
    const HRESULT result = g_realPresent1(sc, sync, flags, forwarded);
    if (result == DXGI_ERROR_DEVICE_REMOVED || result == DXGI_ERROR_DEVICE_RESET) ResetRenderer();
    return result;
}

static HRESULT STDMETHODCALLTYPE HookResizeBuffers(IDXGISwapChain* sc, UINT count, UINT width, UINT height, DXGI_FORMAT format, UINT flags) {
    std::lock_guard<std::recursive_mutex> renderLock(g_renderMutex);
    if (sc == g_swapChain) CleanupRenderTarget();
    return g_realResizeBuffers ? g_realResizeBuffers(sc, count, width, height, format, flags) : E_FAIL;
}

static bool SystemHookTarget(void* address) {
    MEMORY_BASIC_INFORMATION info{};
    if (!VirtualQuery(address, &info, sizeof(info)) || info.Type != MEM_IMAGE) return false;
    wchar_t module[MAX_PATH]{}, system[MAX_PATH]{};
    if (!GetModuleFileNameW(static_cast<HMODULE>(info.AllocationBase), module, MAX_PATH) ||
        !GetSystemDirectoryW(system, MAX_PATH)) return false;
    const std::wstring base = std::wstring(system) + L"\\";
    return _wcsicmp(module, (base + L"dxgi.dll").c_str()) == 0 ||
           _wcsicmp(module, (base + L"d3d11.dll").c_str()) == 0;
}

static bool HookSwapChain(IDXGISwapChain* sc) {
    std::lock_guard<std::mutex> hookLock(g_hookMutex);
    if (g_hooked.load()) return true;
    if (!sc) return false;
    void** vtbl = *reinterpret_cast<void***>(sc);
    IDXGISwapChain1* newer = nullptr;
    void* present1 = nullptr;
    if (SUCCEEDED(sc->QueryInterface(__uuidof(IDXGISwapChain1), reinterpret_cast<void**>(&newer))) && newer) {
        present1 = (*reinterpret_cast<void***>(newer))[22];
        newer->Release();
        if (!SystemHookTarget(present1)) return false;
    }
    if (!SystemHookTarget(vtbl[8]) || !SystemHookTarget(vtbl[13])) {
        Debug("Refusing foreign DXGI swapchain implementation");
        return false;
    }
    // Each linked MinHook owns its own registry. Detect an existing jump to
    // foreign code so another overlay/proxy never gets silently overwritten.
    std::vector<void*> targets{vtbl[8], vtbl[13]};
    if (present1) targets.push_back(present1);
    for (void* address : targets) {
        const auto* p = static_cast<const unsigned char*>(address);
        if (p[0] == 0xE9) {
            int32_t offset = 0; memcpy(&offset, p + 1, sizeof(offset));
            if (!SystemHookTarget(const_cast<unsigned char*>(p + 5 + offset))) return false;
        } else if (p[0] == 0xFF && p[1] == 0x25) {
            int32_t offset = 0; memcpy(&offset, p + 2, sizeof(offset));
            const auto* pointer = p + 6 + offset;
            MEMORY_BASIC_INFORMATION region{};
            if (!VirtualQuery(pointer, &region, sizeof(region)) || region.State != MEM_COMMIT ||
                (region.Protect & (PAGE_GUARD | PAGE_NOACCESS)) ||
                reinterpret_cast<uintptr_t>(pointer) + sizeof(void*) >
                reinterpret_cast<uintptr_t>(region.BaseAddress) + region.RegionSize) return false;
            void* target = nullptr; memcpy(&target, pointer, sizeof(target));
            if (!SystemHookTarget(target)) return false;
        }
    }
    MH_STATUS status = MH_Initialize();
    if (status != MH_OK && status != MH_ERROR_ALREADY_INITIALIZED) return false;
    if (MH_CreateHook(vtbl[8], reinterpret_cast<void*>(&HookPresent), reinterpret_cast<void**>(&g_realPresent)) != MH_OK)
        return false;
    if (MH_CreateHook(vtbl[13], reinterpret_cast<void*>(&HookResizeBuffers), reinterpret_cast<void**>(&g_realResizeBuffers)) != MH_OK) {
        MH_RemoveHook(vtbl[8]); return false;
    }
    if (present1 && MH_CreateHook(present1, reinterpret_cast<void*>(&HookPresent1), reinterpret_cast<void**>(&g_realPresent1)) != MH_OK) {
        MH_RemoveHook(vtbl[8]); MH_RemoveHook(vtbl[13]); return false;
    }
    // Active trampolines must never outlive this DLL. Do this outside DllMain.
    HMODULE pinned = nullptr;
    bool pin = GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCWSTR>(&HookPresent), &pinned) != 0;
    bool queued = pin;
    for (void* address : targets) queued = queued && MH_QueueEnableHook(address) == MH_OK;
    if (!queued || MH_ApplyQueued() != MH_OK) {
        for (void* address : targets) { MH_DisableHook(address); MH_RemoveHook(address); }
        return false;
    }
    g_hooked = true;
    g_loaderStatus = 1;
    Debug(present1 ? "System DXGI Present/Present1/ResizeBuffers hooks installed" : "System DXGI Present/ResizeBuffers hooks installed");
    return true;
}

static HWND CreateDummyWindow() {
    static const wchar_t* kClass = L"TD1ApexOverlayDummyWindow";
    static bool registered = false;
    if (!registered) {
        WNDCLASSEXW wc{};
        wc.cbSize = sizeof(wc);
        wc.lpfnWndProc = DefWindowProcW;
        wc.hInstance = GetModuleHandleW(nullptr);
        wc.lpszClassName = kClass;
        RegisterClassExW(&wc);
        registered = true;
    }
    return CreateWindowExW(0, kClass, L"TD1 Apex Overlay Dummy", WS_OVERLAPPEDWINDOW, 0, 0, 64, 64, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
}

static void HookFromDevice(ID3D11Device* device) {
    if (!device || g_hooked.load()) return;
    IDXGIDevice* dxgiDevice = nullptr;
    IDXGIAdapter* adapter = nullptr;
    IDXGIFactory* factory = nullptr;
    IDXGISwapChain* dummySwap = nullptr;
    HWND dummyWindow = nullptr;
    do {
        if (FAILED(device->QueryInterface(__uuidof(IDXGIDevice), reinterpret_cast<void**>(&dxgiDevice))) || !dxgiDevice) break;
        if (FAILED(dxgiDevice->GetAdapter(&adapter)) || !adapter) break;
        if (FAILED(adapter->GetParent(__uuidof(IDXGIFactory), reinterpret_cast<void**>(&factory))) || !factory) break;
        dummyWindow = CreateDummyWindow();
        if (!dummyWindow) break;
        DXGI_SWAP_CHAIN_DESC desc{};
        desc.BufferCount = 1;
        desc.BufferDesc.Width = 64;
        desc.BufferDesc.Height = 64;
        desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
        desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
        desc.OutputWindow = dummyWindow;
        desc.SampleDesc.Count = 1;
        desc.Windowed = TRUE;
        desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
        if (SUCCEEDED(factory->CreateSwapChain(device, &desc, &dummySwap)) && dummySwap) HookSwapChain(dummySwap);
    } while (false);
    if (dummySwap) dummySwap->Release();
    if (factory) factory->Release();
    if (adapter) adapter->Release();
    if (dxgiDevice) dxgiDevice->Release();
    if (dummyWindow) DestroyWindow(dummyWindow);
}
} // namespace td1

extern "C" __declspec(dllexport) int WINAPI ApexOverlayProtocolVersion() { return 1; }
extern "C" __declspec(dllexport) int WINAPI ApexOverlayStatus() { return td1::g_loaderStatus.load(); }
extern "C" __declspec(dllexport) int WINAPI ApexOverlayRenderedFrames() { return td1::g_renderedFrames.load(); }
extern "C" __declspec(dllexport) int WINAPI ApexOverlayVisible() { return td1::g_visible.load() ? 1 : 0; }
extern "C" __declspec(dllexport) int WINAPI ApexOverlayToggleEvents() { return td1::g_toggleEvents.load(); }
extern "C" __declspec(dllexport) int WINAPI ApexCaptureCompleted() { return td1::g_captureCompleted.load(); }
extern "C" __declspec(dllexport) int WINAPI ApexCaptureFull() {
    if (!td1::g_hooked.load() || td1::g_loaderStatus.load() < 3) return -1;
    int idle = 0;
    return td1::g_captureRequest.compare_exchange_strong(idle, 3) ? 0 : -2;
}
// Disposable-profile CLI input runs inside the already-authorized game. It
// cannot address EA/UAC/another process, and stale viewport coordinates fail.
extern "C" __declspec(dllexport) int WINAPI ApexGameInput(int command, int x, int y, int width, int height) {
    std::lock_guard<std::recursive_mutex> renderLock(td1::g_renderMutex);
    HWND hwnd = td1::g_hwnd;
    DWORD owner = 0;
    RECT rect{};
    if (!td1::g_hooked.load() || !hwnd || !IsWindow(hwnd) || !IsWindowVisible(hwnd)) return -1;
    GetWindowThreadProcessId(hwnd, &owner);
    if (owner != GetCurrentProcessId() || GetAncestor(GetForegroundWindow(), GA_ROOT) != GetAncestor(hwnd, GA_ROOT)) return -2;
    if (!GetClientRect(hwnd, &rect) || rect.right - rect.left != width || rect.bottom - rect.top != height) return -3;
    if (command == 2) {
        if (x != VK_F11 && x != VK_ESCAPE && x != VK_RETURN && x != VK_TAB && x != VK_SPACE) return -4;
        // Do not hold renderLock while F11 is sampled on the render thread.
        INPUT down{}; down.type = INPUT_KEYBOARD; down.ki.wVk = static_cast<WORD>(x);
        if (SendInput(1, &down, sizeof(INPUT)) != 1) return -5;
        // The matching release is scheduled by a short-lived game-owned worker;
        // accepting the input does not claim the UI transition completed.
        std::thread([key = static_cast<WORD>(x)] {
            Sleep(80);
            INPUT up{}; up.type = INPUT_KEYBOARD; up.ki.wVk = key; up.ki.dwFlags = KEYEVENTF_KEYUP;
            SendInput(1, &up, sizeof(INPUT));
        }).detach();
        return 0;
    }
    if (command != 1 || x < 0 || y < 0 || x >= width || y >= height) return -4;
    POINT point{x, y};
    if (!ClientToScreen(hwnd, &point)) return -3;
    const int left = GetSystemMetrics(SM_XVIRTUALSCREEN), top = GetSystemMetrics(SM_YVIRTUALSCREEN);
    const int sw = GetSystemMetrics(SM_CXVIRTUALSCREEN), sh = GetSystemMetrics(SM_CYVIRTUALSCREEN);
    if (sw <= 1 || sh <= 1 || point.x < left || point.y < top || point.x >= left + sw || point.y >= top + sh) return -3;
    INPUT input[3]{};
    for (auto& event : input) event.type = INPUT_MOUSE;
    input[0].mi.dx = MulDiv(point.x - left, 65535, sw - 1);
    input[0].mi.dy = MulDiv(point.y - top, 65535, sh - 1);
    input[0].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
    input[1].mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
    input[2].mi.dwFlags = MOUSEEVENTF_LEFTUP;
    // Sims polls mouse state between frames. An immediate down/up batch can
    // move the cursor without ever delivering a held button to that poll.
    if (SendInput(2, input, sizeof(INPUT)) != 2) {
        SendInput(1, &input[2], sizeof(INPUT));
        return -5;
    }
    std::thread([] {
        Sleep(100);
        INPUT up{}; up.type = INPUT_MOUSE; up.mi.dwFlags = MOUSEEVENTF_LEFTUP;
        SendInput(1, &up, sizeof(INPUT));
    }).detach();
    return 0;
}
extern "C" __declspec(dllexport) int WINAPI ApexOverlayShow() {
    if (!td1::g_hooked.load()) return -1;
    td1::g_visible = true;
    return 0;
}
extern "C" __declspec(dllexport) int WINAPI ApexOverlayHide() {
    if (!td1::g_hooked.load()) return -1;
    td1::g_visible = false;
    return 0;
}
extern "C" __declspec(dllexport) int WINAPI ApexOverlayStart() {
    wchar_t executable[MAX_PATH]{};
    if (!GetModuleFileNameW(nullptr, executable, MAX_PATH)) return -1;
    const wchar_t* name = wcsrchr(executable, L'\\');
    name = name ? name + 1 : executable;
    if (_wcsicmp(name, L"TS4_x64.exe") || !GetModuleHandleW(L"python37_x64.dll") ||
        !GetModuleHandleW(L"Simulation_x64.dll")) return -1;
    if (td1::g_hooked.load()) return 0;
    // A loaded household in DX11 already has this module. Never force a DX9
    // game onto another renderer or modify the EA executable/activation layer.
    if (!GetModuleHandleW(L"d3d11.dll")) return -2;
    if (!td1::LoadRealD3D11()) return -3;
    HWND window = td1::CreateDummyWindow();
    if (!window) return -3;
    DXGI_SWAP_CHAIN_DESC desc{};
    desc.BufferCount = 1;
    desc.BufferDesc.Width = desc.BufferDesc.Height = 64;
    desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.OutputWindow = window;
    desc.SampleDesc.Count = 1;
    desc.Windowed = TRUE;
    desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
    IDXGISwapChain* swap = nullptr;
    ID3D11Device* device = nullptr;
    ID3D11DeviceContext* context = nullptr;
    HRESULT hr = td1::g_realCreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0,
        nullptr, 0, D3D11_SDK_VERSION, &desc, &swap, &device, nullptr, &context);
    const bool hooked = SUCCEEDED(hr) && td1::HookSwapChain(swap);
    if (context) context->Release();
    if (device) device->Release();
    if (swap) swap->Release();
    DestroyWindow(window);
    if (!hooked) { td1::g_loaderStatus = -4; return -4; }
    return 0;
}

#ifndef APEX_SIDECAR
extern "C" __declspec(dllexport)
HRESULT WINAPI D3D11CreateDevice(IDXGIAdapter* pAdapter, D3D_DRIVER_TYPE DriverType, HMODULE Software, UINT Flags, const D3D_FEATURE_LEVEL* pFeatureLevels, UINT FeatureLevels, UINT SDKVersion, ID3D11Device** ppDevice, D3D_FEATURE_LEVEL* pFeatureLevel, ID3D11DeviceContext** ppImmediateContext) {
    if (!td1::LoadRealD3D11()) return E_FAIL;
    HRESULT hr = td1::g_realCreateDevice(pAdapter, DriverType, Software, Flags, pFeatureLevels, FeatureLevels, SDKVersion, ppDevice, pFeatureLevel, ppImmediateContext);
    if (SUCCEEDED(hr) && ppDevice && *ppDevice) td1::HookFromDevice(*ppDevice);
    return hr;
}

extern "C" __declspec(dllexport)
HRESULT WINAPI D3D11CreateDeviceAndSwapChain(IDXGIAdapter* pAdapter, D3D_DRIVER_TYPE DriverType, HMODULE Software, UINT Flags, const D3D_FEATURE_LEVEL* pFeatureLevels, UINT FeatureLevels, UINT SDKVersion, const DXGI_SWAP_CHAIN_DESC* pSwapChainDesc, IDXGISwapChain** ppSwapChain, ID3D11Device** ppDevice, D3D_FEATURE_LEVEL* pFeatureLevel, ID3D11DeviceContext** ppImmediateContext) {
    if (!td1::LoadRealD3D11()) return E_FAIL;
    HRESULT hr = td1::g_realCreateDeviceAndSwapChain(pAdapter, DriverType, Software, Flags, pFeatureLevels, FeatureLevels, SDKVersion, pSwapChainDesc, ppSwapChain, ppDevice, pFeatureLevel, ppImmediateContext);
    if (SUCCEEDED(hr) && ppSwapChain && *ppSwapChain) td1::HookSwapChain(*ppSwapChain);
    return hr;
}
#endif

BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(hInst);
    else if (reason == DLL_PROCESS_DETACH) { td1::g_done = true; }
    return TRUE;
}

#ifdef APEX_NATIVE_SMOKE
// Compiled only into the independent test EXE. No network worker, console
// input, game processes, files, or exports that bypass the production guard.
extern "C" int ApexRunNativeSmoke() {
    using namespace td1;
    if (!LoadRealD3D11()) return 10;
    HWND window = CreateDummyWindow();
    if (!window) return 11;
    DXGI_SWAP_CHAIN_DESC desc{};
    desc.BufferCount = 1; desc.BufferDesc.Width = desc.BufferDesc.Height = 64;
    desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.OutputWindow = window; desc.SampleDesc.Count = 1; desc.Windowed = TRUE;
    IDXGISwapChain* swap = nullptr; ID3D11Device* device = nullptr; ID3D11DeviceContext* context = nullptr;
    HRESULT hr = g_realCreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, 0,
        nullptr, 0, D3D11_SDK_VERSION, &desc, &swap, &device, nullptr, &context);
    if (FAILED(hr)) return 12;
    if (!HookSwapChain(swap)) return 13;
    D3D11_TEXTURE2D_DESC texture{};
    texture.Width = texture.Height = 64; texture.MipLevels = texture.ArraySize = 1;
    texture.Format = DXGI_FORMAT_R8G8B8A8_UNORM; texture.SampleDesc.Count = 1;
    texture.BindFlags = D3D11_BIND_RENDER_TARGET;
    ID3D11Texture2D* targets[2]{}; ID3D11RenderTargetView* views[8]{};
    if (FAILED(device->CreateTexture2D(&texture, nullptr, &targets[0])) ||
        FAILED(device->CreateTexture2D(&texture, nullptr, &targets[1])) ||
        FAILED(device->CreateRenderTargetView(targets[0], nullptr, &views[0])) ||
        FAILED(device->CreateRenderTargetView(targets[1], nullptr, &views[7]))) return 14;
    texture.Format = DXGI_FORMAT_D24_UNORM_S8_UINT; texture.BindFlags = D3D11_BIND_DEPTH_STENCIL;
    ID3D11Texture2D* depthTexture = nullptr; ID3D11DepthStencilView* depth = nullptr;
    if (FAILED(device->CreateTexture2D(&texture, nullptr, &depthTexture)) ||
        FAILED(device->CreateDepthStencilView(depthTexture, nullptr, &depth))) return 15;
    context->OMSetRenderTargets(8, views, depth);
    // Exercise the actual DXGI function detour and all ImGui rendering code.
    // No synthesized physical key events are sent to any application.
    g_visible = true;
    swap->Present(0, 0);
    if (g_presentCount != 1 || !g_device || !ImGui::GetCurrentContext() || g_hwnd != window) return 16;
    ID3D11RenderTargetView* restored[8]{}; ID3D11DepthStencilView* restoredDepth = nullptr;
    context->OMGetRenderTargets(8, restored, &restoredDepth);
    for (unsigned index = 0; index < 8; ++index) {
        if (restored[index] != views[index]) return 17;
        if (restored[index]) restored[index]->Release();
    }
    if (restoredDepth != depth) return 18;
    restoredDepth->Release();
    context->OMSetRenderTargets(0, nullptr, nullptr);
    hr = swap->ResizeBuffers(1, 96, 96, DXGI_FORMAT_UNKNOWN, 0);
    if (FAILED(hr) || g_rtv) return 19;
    ui::Json numeric = {{"ok", true}, {"history_lane", "native-smoke"}, {"history_nodes", ui::Json::array()},
        {"outfit_inventory", ui::Json::array({{{"index", 0u}, {"category", 0u}, {"outfit_id", "1"},
            {"parts", ui::Json::array({{{"index", 0u}, {"target", "0:7:0"}, {"label", "Test part"},
                {"target_supported", true}, {"cas_part_hex", "00000000000003E7"}, {"color_hex", "4000000000000000"}}})}}})},
        {"color_editor", {{"target", "0:7:0"}, {"cas_part_id", "999"}, {"color_hex", "4000000000000000"},
            {"appearance_sha256", std::string(64, 'a')}, {"resource_sha256", std::string(64, 'b')}, {"part_name", "Test part"}}}};
    for (const auto* name : {"hue", "saturation", "brightness", "opacity"})
        numeric["color_editor"]["channels"][name] = {{"value", 0.0}, {"min", -0.5}, {"max", 0.5}, {"step", 0.05}, {"enabled", true}};
    g_commandReply = numeric.dump(); g_activeTab = 12;
    swap->Present(0, 0);
    if (g_colorEditorKey.empty() || !g_studioData.contains("color_editor")) return 22;
    g_visible = false;
    swap->Present(0, 0);
    if (g_presentCount != 3 || g_workerActive.load()) return 20;
    ResetRenderer();
    if (g_device || g_context || g_hwnd || ImGui::GetCurrentContext() || g_loaderStatus != 1) return 23;
    g_visible = true; swap->Present(0, 0);
    if (!g_device || g_loaderStatus != 3 || g_presentCount != 4) return 24;
    IDXGISwapChain1* newer = nullptr;
    if (FAILED(swap->QueryInterface(__uuidof(IDXGISwapChain1), reinterpret_cast<void**>(&newer))) || !g_realPresent1) return 25;
    DXGI_PRESENT_PARAMETERS parameters{};
    hr = newer->Present1(0, 0, &parameters);
    newer->Release();
    if (FAILED(hr) || g_presentCount != 5 || !g_device) return 26;
    ToggleInput input;
    if (!input.sample(true, true) || input.sample(true, true) || input.sample(true, false) ||
        input.sample(false, true) || input.sample(true, true) || input.sample(false, false) ||
        !input.sample(true, true)) return 21;
    printf("DX11 WARP: actual Present detour/menu + numeric color render, 8 RTVs+depth restored, ResizeBuffers, renderer teardown/reinit, hidden zero worker, first keypress/held/focus edges passed\n");
    // COM/UI cleanup while the hidden test window still exists.
    CleanupRenderTarget();
    SetWindowLongPtrW(window, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_oldWndProc));
    ImGui_ImplDX11_Shutdown(); ImGui_ImplWin32_Shutdown(); ImGui::DestroyContext();
    g_context->Release(); g_device->Release(); g_context = nullptr; g_device = nullptr;
    for (auto* view : views) if (view) view->Release();
    for (auto* target : targets) target->Release();
    depth->Release(); depthTexture->Release();
    context->Release(); device->Release(); swap->Release(); DestroyWindow(window);
    return 0;
}
#endif
