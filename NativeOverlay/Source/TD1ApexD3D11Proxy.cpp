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

#include <dxgi.h>
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
using ResizeBuffersFn = HRESULT (STDMETHODCALLTYPE *)(IDXGISwapChain*, UINT, UINT, UINT, DXGI_FORMAT, UINT);

static HMODULE g_realD3D11 = nullptr;
static PFN_D3D11CreateDevice g_realCreateDevice = nullptr;
static PFN_D3D11CreateDeviceAndSwapChain g_realCreateDeviceAndSwapChain = nullptr;
static PresentFn g_realPresent = nullptr;
static ResizeBuffersFn g_realResizeBuffers = nullptr;
static std::atomic<bool> g_hooked{false};
static std::atomic<bool> g_visible{false};
static std::atomic<bool> g_done{false};
static std::atomic<bool> g_workerActive{false};
static std::atomic<int> g_captureRequest{0}; // 1 face, 2 body, 3 full
static HWND g_hwnd = nullptr;
static WNDPROC g_oldWndProc = nullptr;
static ID3D11Device* g_device = nullptr;
static ID3D11DeviceContext* g_context = nullptr;
static ID3D11RenderTargetView* g_rtv = nullptr;
static std::mutex g_dataMutex;
static std::string g_json = "{\"message\":\"Waiting for TD1 Apex Python server...\"}";
static std::string g_status = "Not connected";
static std::string g_selectedSim;
static std::deque<std::string> g_commands;
static ULONGLONG g_lastStatusMs = 0;
static int g_activeTab = 0;
static bool g_wsStarted = false;
static std::vector<std::string> g_logLines;

static int g_selectedOccultIndex = 1;
static bool g_autoRepairToggle = false;
static bool g_mcccAutoRestoreToggle = true;
static bool g_mcccSoftHooksToggle = false;
static bool g_driftAfterCommandsToggle = true;
static char g_formLabel[160] = "";
static char g_formSearch[160] = "";
static char g_formSlot[220] = "";
static char g_rawFlags[64] = "";
static char g_rawCurrent[64] = "";
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
    DWORD timeout = 350;
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(8017);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    if (connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == SOCKET_ERROR) { closesocket(s); return false; }
    std::string req = "GET " + path + " HTTP/1.1\r\nHost: 127.0.0.1:8017\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n";
    int sent = send(s, req.c_str(), static_cast<int>(req.size()), 0);
    if (sent <= 0) { closesocket(s); return false; }
    std::string raw;
    char buf[8192];
    for (;;) {
        int n = recv(s, buf, sizeof(buf), 0);
        if (n <= 0) break;
        raw.append(buf, buf + n);
        if (raw.size() > 1024 * 512) break;
    }
    closesocket(s);
    size_t pos = raw.find("\r\n\r\n");
    body = (pos == std::string::npos) ? raw : raw.substr(pos + 4);
    return !body.empty();
}

static std::string JsonUnescape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        char c = s[i];
        if (c == '\\' && i + 1 < s.size()) {
            char n = s[++i];
            if (n == 'n') out.push_back('\n');
            else if (n == 'r') out.push_back('\r');
            else if (n == 't') out.push_back('\t');
            else out.push_back(n);
        } else out.push_back(c);
    }
    return out;
}

static std::vector<std::string> ExtractHistory(const std::string& json) {
    std::vector<std::string> out;
    size_t key = json.find("\"logs\"");
    if (key == std::string::npos) key = json.find("\"history\"");
    if (key == std::string::npos) return out;
    size_t lb = json.find('[', key);
    size_t rb = json.find(']', lb == std::string::npos ? key : lb);
    if (lb == std::string::npos || rb == std::string::npos || rb <= lb) return out;
    bool in = false, esc = false;
    std::string cur;
    for (size_t i = lb + 1; i < rb; ++i) {
        char c = json[i];
        if (!in) { if (c == '"') { in = true; cur.clear(); } continue; }
        if (esc) { cur.push_back('\\'); cur.push_back(c); esc = false; continue; }
        if (c == '\\') { esc = true; continue; }
        if (c == '"') { out.push_back(JsonUnescape(cur)); in = false; continue; }
        cur.push_back(c);
    }
    if (out.size() > 260) out.erase(out.begin(), out.end() - 260);
    return out;
}

static std::string ExtractJsonValue(const std::string& json, const char* keyName) {
    std::string key = std::string("\"") + keyName + "\"";
    size_t k = json.find(key);
    if (k == std::string::npos) return {};
    size_t colon = json.find(':', k);
    if (colon == std::string::npos) return {};
    size_t p = json.find_first_not_of(" \t\r\n", colon + 1);
    if (p == std::string::npos) return {};
    if (json[p] == '"') {
        size_t e = p + 1;
        bool esc = false;
        for (; e < json.size(); ++e) {
            char c = json[e];
            if (esc) { esc = false; continue; }
            if (c == '\\') { esc = true; continue; }
            if (c == '"') break;
        }
        if (e >= json.size()) return {};
        return JsonUnescape(json.substr(p + 1, e - p - 1));
    }
    size_t e = json.find_first_of(",}\r\n", p);
    std::string v = json.substr(p, e == std::string::npos ? std::string::npos : e - p);
    while (!v.empty() && (v.back() == ' ' || v.back() == '\t')) v.pop_back();
    return v;
}

static void QueueCommand(const std::string& path) {
    std::lock_guard<std::mutex> lock(g_dataMutex);
    g_commands.push_back(path);
    if (g_commands.size() > 48) g_commands.pop_front();
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
    QueueCommand(BuildCommandPath(action, occult, value));
}

static bool ActionButton(const char* label, const char* action, const char* occult = nullptr, const char* value = nullptr, const ImVec2& size = ImVec2(-1, 0)) {
    if (!ImGui::Button(label, size)) return false;
    QueueAction(action, occult, value);
    return true;
}

static void WorkerLoop() {
    g_workerActive = true;
    while (!g_done) {
        std::string command;
        {
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if (!g_commands.empty()) { command = g_commands.front(); g_commands.pop_front(); }
        }
        if (!command.empty()) {
            std::string body;
            bool ok = HttpGet(command, body);
            std::lock_guard<std::mutex> lock(g_dataMutex);
            g_status = ok ? "Command finished" : "Command request failed";
            if (ok) { g_json = body; auto lines = ExtractHistory(body); if (!lines.empty()) g_logLines = lines; }
            continue;
        }
        if (g_visible.load()) {
            ULONGLONG now = GetTickCount64();
            if (now - g_lastStatusMs >= 1300) {
                g_lastStatusMs = now;
                std::string body;
                std::string sim;
                { std::lock_guard<std::mutex> lock(g_dataMutex); sim = g_selectedSim; }
                std::string path = "/api/overlay/state?count=220";
                if (!sim.empty()) path += "&sim_id=" + UrlEncode(sim);
                bool ok = HttpGet(path, body);
                std::lock_guard<std::mutex> lock(g_dataMutex);
                g_status = ok ? "Connected to TD1 Apex" : "Waiting for 127.0.0.1:8017";
                if (ok) {
                    g_json = body;
                    auto lines = ExtractHistory(body);
                    if (!lines.empty()) g_logLines = lines;
                    std::string sid = ExtractJsonValue(body, "sim_id");
                    if (!sid.empty() && g_selectedSim.empty()) g_selectedSim = sid;
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
    ss << ScreenshotFolder() << "\\TD1Apex_" << mode << "_" << std::put_time(&tm, "%Y%m%d_%H%M%S") << ".bmp";
    return ss.str();
}

static bool SaveBackbufferBmp(IDXGISwapChain* sc, int mode) {
    if (!sc || !g_device || !g_context) return false;
    ID3D11Texture2D* backBuffer = nullptr;
    if (FAILED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), reinterpret_cast<void**>(&backBuffer))) || !backBuffer) return false;
    D3D11_TEXTURE2D_DESC desc{};
    backBuffer->GetDesc(&desc);
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
    bool bgra = (desc.Format == DXGI_FORMAT_B8G8R8A8_UNORM || desc.Format == DXGI_FORMAT_B8G8R8A8_UNORM_SRGB);
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
    g_context->Unmap(copyTex, 0);
    copyTex->Release();
    if (resolveTex) resolveTex->Release();
    backBuffer->Release();
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
    if (g_visible.load()) {
        if (ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam)) return TRUE;
        ImGuiIO& io = ImGui::GetIO();
        const bool mouse = (msg >= WM_MOUSEFIRST && msg <= WM_MOUSELAST);
        const bool key = (msg >= WM_KEYFIRST && msg <= WM_KEYLAST);
        if ((mouse && io.WantCaptureMouse) || (key && io.WantCaptureKeyboard)) return TRUE;
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
    ImGui_ImplWin32_Init(g_hwnd);
    ImGui_ImplDX11_Init(g_device, g_context);
    if (g_hwnd) {
        g_oldWndProc = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(g_hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(WndProc)));
        if (!g_oldWndProc && GetLastError() != 0) Debug("SetWindowLongPtrW failed; input capture will be disabled");
    }
    CreateRenderTarget(sc);
    EnsureWorker();
    Debug("ImGui initialized");
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

static void DrawOverlay() {
    ImGui::SetNextWindowSize(ImVec2(1320, 820), ImGuiCond_FirstUseEver);
    ImGui::Begin("TD1 Occult Hybrid Apex V9.6 - Live BodyType Safe  (F11)", nullptr, ImGuiWindowFlags_NoCollapse);
    std::string status, json, sim;
    std::vector<std::string> logs;
    { std::lock_guard<std::mutex> lock(g_dataMutex); status = g_status; json = g_json; logs = g_logLines; sim = g_selectedSim; }

    ImGui::TextColored(ImVec4(0.45f, 0.95f, 1.0f, 1.0f), "%s", status.c_str());
    ImGui::SameLine(); ImGui::TextDisabled("Hidden mode: no HTTP polling | Drift Guard: fire-once / no timers");
    char simBuf[64] = {};
    strncpy_s(simBuf, sim.c_str(), _TRUNCATE);
    ImGui::SetNextItemWidth(260);
    if (ImGui::InputText("Target Sim ID", simBuf, sizeof(simBuf))) { std::lock_guard<std::mutex> lock(g_dataMutex); g_selectedSim = simBuf; }
    ImGui::SameLine(); ActionButton("Refresh", "status", nullptr, nullptr, ImVec2(86,0));
    ImGui::SameLine(); ActionButton("Health", "health", nullptr, nullptr, ImVec2(86,0));
    ImGui::SameLine(); ActionButton("Diagnostics", "diagnostics", nullptr, nullptr, ImVec2(112,0));
    ImGui::SameLine(); ActionButton("QA Self-Test", "qa_self_test", nullptr, nullptr, ImVec2(128,0));
    ImGui::SameLine(); ActionButton("Code Audit", "code_audit", nullptr, nullptr, ImVec2(112,0));
    ImGui::SameLine(); ActionButton("Research Audit", "research_audit", nullptr, nullptr, ImVec2(136,0));
    ImGui::SameLine(); ActionButton("Final Audit", "final_audit", nullptr, nullptr, ImVec2(116,0));
    std::string warn = ExtractJsonValue(json, "drift_warning_count");
    if (!warn.empty() && warn != "0") {
        ImGui::Separator();
        ImGui::TextColored(ImVec4(1.0f, 0.35f, 0.40f, 1.0f), "DRIFT WARNING: %s issue(s) found. Open Drift Guard or press Fix.", warn.c_str());
        ImGui::SameLine(); if (ImGui::Button("Fix Selected")) QueueAction("fix_occult_drift", ActiveOccultName());
        ImGui::SameLine(); if (ImGui::Button("Scan Again")) QueueAction("scan_occult_drift");
    }
    ImGui::Separator();

    const char* tabs[] = {"Apex", "Forms", "Saved Forms", "Drift Guard", "Reference Shots", "CAS Tools", "CAS Categories", "MCCC Shield", "Raw Flags", "Sims/API", "Log"};
    for (int i = 0; i < IM_ARRAYSIZE(tabs); ++i) { if (i) ImGui::SameLine(); if (ImGui::Selectable(tabs[i], g_activeTab == i, 0, ImVec2(132, 0))) g_activeTab = i; }
    ImGui::Separator();

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
    ImGui::EndChild();
    ImGui::SameLine();
    ImGui::BeginChild("right_dock", ImVec2(0, 0), true);
    DrawLogDock(logs);
    ImGui::EndChild();
    ImGui::End();
}

static HRESULT STDMETHODCALLTYPE HookPresent(IDXGISwapChain* sc, UINT sync, UINT flags) {
    if ((GetAsyncKeyState(VK_F11) & 1) != 0) g_visible = !g_visible.load();
    if (g_visible.load()) {
        InitImGui(sc);
        if (g_device && g_context) {
            CreateRenderTarget(sc);
            int capture = g_captureRequest.exchange(0);
            if (capture != 0) SaveBackbufferBmp(sc, capture);
            ImGui_ImplDX11_NewFrame();
            ImGui_ImplWin32_NewFrame();
            ImGui::NewFrame();
            DrawOverlay();
            ImGui::Render();
            g_context->OMSetRenderTargets(1, &g_rtv, nullptr);
            ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
        }
    }
    return g_realPresent(sc, sync, flags);
}

static HRESULT STDMETHODCALLTYPE HookResizeBuffers(IDXGISwapChain* sc, UINT count, UINT width, UINT height, DXGI_FORMAT format, UINT flags) {
    CleanupRenderTarget();
    return g_realResizeBuffers ? g_realResizeBuffers(sc, count, width, height, format, flags) : E_FAIL;
}

static void HookSwapChain(IDXGISwapChain* sc) {
    if (!sc || g_hooked.exchange(true)) return;
    void** vtbl = *reinterpret_cast<void***>(sc);
    DWORD old = 0;
    if (VirtualProtect(&vtbl[8], sizeof(void*) * 6, PAGE_EXECUTE_READWRITE, &old)) {
        g_realPresent = reinterpret_cast<PresentFn>(vtbl[8]);
        g_realResizeBuffers = reinterpret_cast<ResizeBuffersFn>(vtbl[13]);
        vtbl[8] = reinterpret_cast<void*>(&HookPresent);
        vtbl[13] = reinterpret_cast<void*>(&HookResizeBuffers);
        DWORD ignored = 0; VirtualProtect(&vtbl[8], sizeof(void*) * 6, old, &ignored);
        Debug("SwapChain vtable hooked");
    }
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

BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) { DisableThreadLibraryCalls(hInst); td1::Debug("v9.6 loaded; waiting for D3D11CreateDeviceAndSwapChain"); }
    else if (reason == DLL_PROCESS_DETACH) { td1::g_done = true; }
    return TRUE;
}
