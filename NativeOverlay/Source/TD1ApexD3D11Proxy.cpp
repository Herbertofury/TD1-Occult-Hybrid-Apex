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
#include <map>
#include <set>
#include <memory>

#include "ApexUiData.h"
#include "ApexResourceImage.h"
#include "ApexOccultImage.h"
#include "ApexSimPreview.h"
#include "ApexLiveCatalog.h"
#include "ApexSliderLibrary.h"
#include "ApexPointerGate.h"
#include "ApexGameWindow.h"
#include "ApexStudioItems.h"
#include "ApexTrayView.h"
#include "ApexTrayGallery.h"
#include "ApexPartColorControls.h"
#include "ApexOwnerCommand.h"
#include "ApexCasBank.h"
#include "ApexCasReviewControl.h"
#include "ApexCasRoom.h"
#include "OverlayInput.h"
#include "MinHook.h"
#include "imgui.h"
#include "imgui_impl_win32.h"
#include "imgui_impl_dx11.h"

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "windowscodecs.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "bcrypt.lib")

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
static std::atomic<int> g_inputState{0}; // 1 staging, 2 cursor verified, 3 held, 4 released; negative refused
static std::atomic<bool> g_inputBusy{false};
static std::atomic<int> g_cursorX{-1}, g_cursorY{-1};
static std::atomic<int> g_toggleEvents{0};
static HWND g_hwnd = nullptr;
static IDXGISwapChain* g_swapChain = nullptr; // identity only; owned by the caller
static std::recursive_mutex g_renderMutex;
static std::mutex g_hookMutex;
static ToggleInput g_toggleInput;
static PointerGate g_pointerGate; // g_renderMutex
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
static ui::Json g_qolReceipt = ui::Json::object(); // worker/readback, g_dataMutex
static ULONGLONG g_commandReplyMs = 0;
static std::string g_selectedSim;
struct QueuedCommand { std::string path; uint64_t generation; bool automaticCasRefresh = false; std::string sim;
    bool automaticCasReconcile = false; std::string casRequestId;
    bool automaticStudioItems = false;
    bool occultIcons = false;
    bool simPreview = false;
    bool trayClipboard = false;
    int resourceOperation = 0; ui::Json resourceRow = ui::Json::object(); uint64_t resourceSelection = 0;
    bool ownerObservation = false; std::string ownerRequestId;
    std::string casBankAction; };
static std::deque<QueuedCommand> g_commands;
static bool g_occultIconsRequested = false; // render thread; one session read
static std::map<std::string,resource::Pixels> g_occultIconPixels; // worker -> render, g_dataMutex
static std::map<std::string,ID3D11ShaderResourceView*> g_occultIconTextures; // render thread
static bool RetainCommandOwner(const QueuedCommand&,const std::string&);
static uint64_t g_selectionGeneration = 0;
static std::atomic<bool> g_simPreviewBusy{false};
static std::atomic<bool> g_sliderLibraryBusy{false};
static ui::Json g_sliderLibraryPage=ui::Json::object();
static std::string g_sliderLibraryStatus;
static std::shared_ptr<td1::preview::Scene> g_simPreviewScene;
static std::string g_simPreviewContext, g_simPreviewStatus;
static td1::preview::Renderer g_simPreview;
static td1::preview::View g_simPreviewSavedView;
static std::string g_simPreviewSavedSim;
static bool g_simPreviewKeepCamera = true;
static bool g_simPreviewAutomatic = true;
static bool g_simPreviewFocusRequested = false;
static std::string g_simPreviewAttemptedContext;
static std::atomic<bool> g_thumbnailBusy{false};
static bool g_generateMissingThumbnails=true;
static std::set<std::string> g_thumbnailAttempted;
static std::shared_ptr<td1::preview::Scene> g_thumbnailScene;
static ui::Json g_thumbnailBinding=ui::Json::object(),g_thumbnailReceipt=ui::Json::object();
static ui::OwnerObservation g_ownerObservation; // worker/render, g_dataMutex
static QueuedCommand g_ownerOriginalCommand;
static std::atomic<bool> g_ownerBlocked{false};
static std::atomic<bool> g_ownerNativeDeliveryBusy{false};
static std::atomic<bool> g_ownerSubmissionBusy{false};
static ui::CasBankView g_casBank; // owner worker/render, protected by g_dataMutex
static std::atomic<bool> g_casBankBusy{false};
static std::string g_ownerDeliveredNativeReply; // g_dataMutex
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
static char g_partSearch[160] = "";
static int g_partReplacementIndex = 0;
static int g_studioFormIndex = 0;
static bool g_showEmptySlots = true;
static bool g_livePartColor = false;
static int g_equippedSort = 0;
static int g_itemNameMode = 0;
static int g_casGroupIndex = 0;
static int g_studioOutfitIndex = 0;
static int g_studioPartIndex = 0;
static ui::Json g_studioData = ui::Json::object();
static ui::Json g_appearanceClipboard = ui::Json::object(), g_clipboardFields = ui::Json::array(), g_clipboardOutfits = ui::Json::array();
static bool g_trayPreviewActive = false;
static ui::Json g_trayPreviewForms = ui::Json::array();
static int g_trayPreviewFormIndex = 0, g_trayPreviewOutfitIndex = 0;
static std::atomic<bool> g_trayClipboardBusy{false};
static ui::Json g_trayClipboardResult = ui::Json::object();
static ui::Json g_galleryPage=ui::Json::object(),g_galleryInspection=ui::Json::object();
static std::string g_galleryStatus="Browse native Tray households, lots and rooms.";
static char g_gallerySearch[201]="";
static int g_galleryKind=0,g_gallerySimIndex=0;
static size_t g_galleryOffset=0;
static std::atomic<bool> g_galleryBusy{false},g_galleryImageBusy{false};
static std::atomic<uint64_t> g_gallerySerial{0};
static bool g_galleryQueryNeeded=true;
static std::string g_gallerySelected,g_galleryImageContext;
static std::set<std::string> g_galleryImageAttempted;
static std::map<std::string,resource::Pixels> g_galleryPixels;
static std::map<std::string,Microsoft::WRL::ComPtr<ID3D11ShaderResourceView>> g_galleryTextures;
static std::map<std::string,ImVec2> g_gallerySizes;
static std::set<std::string> g_pasteFields;
static std::set<int> g_pasteBodies;
static int g_pasteScope = 1, g_pasteSourceOutfit = 0;
static std::string g_studioLastReply;
static bool g_nativeCasView = false;
static ui::Json g_casClientData = ui::Json::object();
static ui::Json g_casRoomData = ui::Json::object();
static ui::Json g_casSelectedItem = ui::Json::object();
static std::string g_casSelectedPanel;
static bool g_casSelectedPreset = false;
static std::string g_casLastReply;
static char g_casPendingId[40] = "";
static std::atomic<bool> g_casSubmissionBusy{false};
static ULONGLONG g_casSnapshotMs = 0;
static int g_casCatalogSort = 1;
static ui::Json g_casDiagnostics = ui::Json::object();
static bool g_casAutoRefresh = true;
static std::atomic<bool> g_casAutoRefreshEnabled{true};
static ui::CasRefreshClock g_casRefreshClock;
static std::atomic<bool> g_nativeCasPaneVisible{false};
static std::atomic<ULONGLONG> g_nativeCasPaneMs{0};
// Worker receipts are copied under g_dataMutex; all presentation state stays
// on the render thread. A diagnostics fetch never scans gameplay Sim records.
static std::string g_casDiagnosticReply;
static ULONGLONG g_casDiagnosticMs = 0;
static uint64_t g_casRefreshReceipt = 0;
static bool g_casRefreshFailed = false, g_casRefreshUnresolved = false;
static std::string g_casRefreshMessage;
static std::string g_casRefreshNativeId;
static uint64_t g_casRefreshSeen = 0;
static ULONGLONG g_casDiagnosticsSeenMs = 0;
static std::string g_casAutoMessage;
static std::string g_casAutoRetainedId;
static ui::CasRefreshClock g_casReconcileClock;
static std::string g_casReconcileReply, g_casReconcileNativeId, g_casReconcileSim;
static bool g_casReconcileOk = false;
static uint64_t g_casReconcileReceipt = 0, g_casReconcileSeen = 0;
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
// Fixed local broker returns pinned resources, never shell commands or paths.
static ui::Json g_resourceCatalog = ui::Json::object(); // worker, g_dataMutex
static std::string g_resourceCatalogStatus = "Resource broker has not been queried.";
static std::atomic<bool> g_resourceCatalogBusy{false}, g_resourceImageBusy{false}, g_resourceOpenBusy{false};
static bool g_resourceCatalogAttempted = false; // render thread
static std::atomic<uint64_t> g_resourceSelectionSerial{0};
static std::string g_resourceViewKey, g_resourceRequestedImage; // render thread
static std::string g_resourceImageKey, g_resourceImageStatus, g_resourceOpenKey, g_resourceOpenStatus;
static resource::Pixels g_resourcePixels; // worker, g_dataMutex
static uint64_t g_resourcePixelReceipt = 0, g_resourceTextureReceipt = 0;
static ID3D11ShaderResourceView* g_resourceTexture = nullptr; // render thread only
static std::string g_resourceTextureKey;
static std::map<std::string, ui::Json> g_resourceInspections; // render thread, bounded1024
static ui::Json g_studioItemRequest = ui::Json::object(), g_studioItemRows = ui::Json::object();
static std::atomic<bool> g_studioItemsBusy{false};
static std::string g_studioItemsReply, g_studioItemsContext, g_studioItemsMessage;
static uint64_t g_studioItemsReceipt = 0, g_studioItemsSeen = 0;
static std::atomic<bool> g_libraryBusy{false};
static std::atomic<uint64_t> g_librarySerial{0};
static ui::Json g_libraryPage = ui::Json::object(), g_libraryInspection = ui::Json::object(); // g_dataMutex
static std::string g_libraryStatus = "Start the Live CAS catalog CLI service to browse installed parts.";
static char g_librarySearch[801] = "";
static std::string g_libraryAuthor;
static int g_librarySort = 0;
static bool g_studioEquippedSidebar = false;
static int g_libraryColumns = 4, g_libraryOrigin = 0, g_libraryView = 0;
static int64_t g_libraryBody = -1;
static size_t g_libraryOffset = 0;
static bool g_libraryQueryNeeded = true;
static bool g_libraryFocusRequested = true;
static std::string g_libraryQueryKey, g_librarySelected;
static int g_libraryTargetRow = 0;
static bool g_libraryShowImages = true;
static int g_libraryImageGender = 1;
static std::atomic<bool> g_libraryImagesBusy{false};
static std::atomic<uint64_t> g_libraryImageSerial{0};
static std::map<std::string,resource::Pixels> g_libraryImagePixels; // worker receipt, g_dataMutex
static std::map<std::string,std::string> g_libraryImageErrors; // worker receipt, g_dataMutex
static std::map<std::string,ID3D11ShaderResourceView*> g_libraryImageTextures; // render thread
static std::map<std::string,ImVec2> g_libraryImageSizes;
static std::set<std::string> g_libraryImageAttempted;
static std::string g_libraryImageContext;
static float g_studioPreviewShare = .38f;
static int g_studioLayout = 0;
static int g_workspaceFocusRequested = -1;
static size_t g_studioItemsCursor = 0;
static ULONGLONG g_studioItemsNextMs = 0;
static bool g_studioItemsComplete = false;

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

static bool HttpGet(const std::string& path, std::string& body, ULONGLONG deadline = 0) {
    if (!deadline) deadline = GetTickCount64() + 12000;
    if (!g_wsStarted) {
        WSADATA wsa{};
        if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) return false;
        g_wsStarted = true;
    }
    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) return false;
    // This is a transport worker. A game-thread command can take several frames;
    // a 350 ms deadline previously discarded its result while it still executed.
    auto remainingTimeout = [&]() -> DWORD {
        const auto now = GetTickCount64();
        return now < deadline ? static_cast<DWORD>(std::min<ULONGLONG>(deadline - now, 12000)) : 0;
    };
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(8017);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    u_long nonblocking = 1;
    if (ioctlsocket(s, FIONBIO, &nonblocking) == SOCKET_ERROR) { closesocket(s); return false; }
    if (connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == SOCKET_ERROR) {
        if (WSAGetLastError() != WSAEWOULDBLOCK) { closesocket(s); return false; }
        const auto remaining = remainingTimeout();
        if (!remaining) { closesocket(s); return false; }
        fd_set writable, errors; FD_ZERO(&writable); FD_ZERO(&errors); FD_SET(s, &writable); FD_SET(s, &errors);
        timeval wait{static_cast<long>(remaining / 1000), static_cast<long>((remaining % 1000) * 1000)};
        int error = 0, errorSize = sizeof(error);
        if (select(0, nullptr, &writable, &errors, &wait) <= 0 || FD_ISSET(s, &errors) ||
            getsockopt(s, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&error), &errorSize) == SOCKET_ERROR || error) {
            closesocket(s); return false;
        }
    }
    nonblocking = 0;
    if (ioctlsocket(s, FIONBIO, &nonblocking) == SOCKET_ERROR) { closesocket(s); return false; }
    std::string req = "GET " + path + " HTTP/1.1\r\nHost: 127.0.0.1:8017\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n";
    size_t sent = 0;
    while (sent < req.size()) {
        DWORD timeout = remainingTimeout();
        if (!timeout) { closesocket(s); return false; }
        setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        int n = send(s, req.data() + sent, static_cast<int>(req.size() - sent), 0);
        if (n <= 0) { closesocket(s); return false; }
        sent += static_cast<size_t>(n);
    }
    std::string raw;
    char buf[8192];
    for (;;) {
        DWORD timeout = remainingTimeout();
        if (!timeout) { closesocket(s); return false; }
        setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        int n = recv(s, buf, sizeof(buf), 0);
        if (n < 0) { closesocket(s); return false; }
        if (n == 0) break;
        raw.append(buf, buf + n);
        if (raw.size() > ui::kMaxOwnerJsonBytes + 16384) { closesocket(s); return false; }
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

static bool HttpOwnedCommand(const std::string& path, std::string& body) {
    if (path.rfind("/api/command?",0)!=0) return HttpGet(path,body);
    GUID guid{};
    if (FAILED(CoCreateGuid(&guid))) {
        body=ui::Json{{"ok",false},{"state","rejected"},{"message","Owner identity could not be generated; no HTTP request was submitted."}}.dump();
        return true; // Proven refusal before any HTTP call, not uncertainty.
    }
    const auto bytes=reinterpret_cast<const unsigned char*>(&guid);
    const char* hex="0123456789abcdef"; std::string id;
    for(size_t i=0;i<sizeof(guid);++i) { id.push_back(hex[bytes[i]>>4]); id.push_back(hex[bytes[i]&15]); }
    if(path.find("request_id=")!=std::string::npos) {
        body=ui::Json{{"ok",false},{"state","rejected"},{"message","A caller-supplied owner identity is forbidden; no HTTP request was submitted."}}.dump();
        return true;
    }
    const bool review=path.rfind("/api/command?action=cas_bank_ui_",0)==0;
    const auto deadline=GetTickCount64()+(review?180000:15000);
    bool received=HttpGet(path+"&request_id="+id,body,deadline);
    auto submission=received ? ui::ReadOwnerSubmission(ui::ParseObject(body),id) : ui::OwnerReply::Pending;
    if(submission==ui::OwnerReply::Terminal || submission==ui::OwnerReply::Rejected) return true;
    // Retain the same owner identity even when its first response was lost.
    // Polling observes execution; it never repeats the command submission.
    while(!g_done && submission!=ui::OwnerReply::Invalid && GetTickCount64()<deadline) {
        std::string raw; ui::Json result;
        if(!HttpGet("/api/requests/status?request_id="+id,raw,deadline)) break;
        submission=ui::ReadOwnerCompletion(ui::ParseObject(raw),id,result);
        if(submission==ui::OwnerReply::Terminal) { body=result.dump(); return true; }
        if(submission==ui::OwnerReply::Invalid) break;
        Sleep(120);
    }
    body=ui::Json({{"ok",false},{"outcome","unresolved"},{"request_id",id},{"request_state","unknown"},
        {"message","Command result is unverified. Observe this retained owner ID; do not repeat the action."}}).dump();
    return true;
}

static std::string ResourceKey(const ui::Json& row) {
    return ui::Scalar(row, "resource_id") + ":" + ui::Scalar(row, "cache_proof");
}

static bool ResourceHttp(int operation, const ui::Json& row, std::string& body) {
    body.clear();
    if (operation < 1 || operation > 10) return false;
    if (operation > 1 && operation < 4 && !resource::CatalogIdentities({{"schema", 1}, {"items", ui::Json::array({row})}})) return false;
    if (operation == 4 && !library::Query(row) || operation == 5 && !library::Selection(row) ||
        operation == 6 && !library::Selection(row, true) || operation == 7 && !library::ImagesRequest(row)) return false;
    if(operation==8&&!tray::Query(row)||operation==9&&!tray::Selection(row)||operation==10&&!tray::Selection(row,true))return false;
    if (!g_wsStarted) {
        WSADATA wsa{};
        if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return false;
        g_wsStarted = true;
    }
    const size_t bound = operation == 2 || operation==9 || operation==10 ? 8 * 1024 * 1024 : 512 * 1024;
    const std::string path = operation == 1 ? "/v1/resources" : operation == 2 ?
        "/v1/resources/" + ui::Scalar(row, "resource_id") + "/thumbnail" : operation == 3 ? "/v1/open" :
        operation == 4 ? "/v1/catalog/query" : operation == 5 ? "/v1/catalog/inspect" : operation==7 ? "/v1/catalog/images" :
        operation==8?"/v1/tray/query":operation==9?"/v1/tray/inspect":operation==10?"/v1/tray/image":"/v1/catalog/favorite";
    const std::string payload = operation == 3 ? ui::Json({{"resource_id", row["resource_id"]},
        {"cache_proof", row["cache_proof"]}}).dump() : operation >= 4 ? row.dump() : "";
    const unsigned port = operation >= 4 || row.value("broker_port", ui::Json()) == 8023 ? 8023 : 8022;
    std::string request = std::string(operation >= 3 ? "POST " : "GET ") + path +
        " HTTP/1.1\r\nHost: 127.0.0.1:" + std::to_string(port) + "\r\nConnection: close\r\nCache-Control: no-store\r\n";
    if (operation >= 3) request += "Content-Type: application/json\r\nContent-Length: " + std::to_string(payload.size()) + "\r\n";
    request += "\r\n" + payload;
    SOCKET socketHandle = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socketHandle == INVALID_SOCKET) return false;
    sockaddr_in address{}; address.sin_family = AF_INET; address.sin_port = htons(static_cast<u_short>(port));
    inet_pton(AF_INET, "127.0.0.1", &address.sin_addr);
    DWORD timeout = 12000;
    setsockopt(socketHandle, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    if (connect(socketHandle, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == SOCKET_ERROR) {
        closesocket(socketHandle); return false;
    }
    const auto deadline = GetTickCount64() + 12000;
    size_t sent = 0;
    while (sent < request.size()) {
        const int amount = send(socketHandle, request.data() + sent, static_cast<int>(request.size() - sent), 0);
        if (amount <= 0 || GetTickCount64() >= deadline) { closesocket(socketHandle); return false; }
        sent += static_cast<size_t>(amount);
    }
    std::string raw; char buffer[8192];
    for (;;) {
        const auto now = GetTickCount64();
        if (now >= deadline) { closesocket(socketHandle); return false; }
        timeout = static_cast<DWORD>(deadline - now);
        setsockopt(socketHandle, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        const int amount = recv(socketHandle, buffer, sizeof(buffer), 0);
        if (amount < 0) { closesocket(socketHandle); return false; }
        if (!amount) break;
        raw.append(buffer, static_cast<size_t>(amount));
        const auto header = raw.find("\r\n\r\n");
        if (raw.size() > bound + 16388 || (header == std::string::npos && raw.size() > 16384)) {
            closesocket(socketHandle); return false;
        }
    }
    closesocket(socketHandle);
    return resource::HttpBody(raw, bound, body);
}

static bool PreviewHttp(const std::string& path, std::string& body, const std::string& payload = "", size_t bound = 8*1024*1024) {
    if (path.rfind("/v1/",0)!=0 || path.find_first_of("\r\n ")!=std::string::npos || payload.size()>12*1024*1024) return false;
    if(!g_wsStarted){WSADATA data{};if(WSAStartup(MAKEWORD(2,2),&data))return false;g_wsStarted=true;}
    SOCKET s=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);if(s==INVALID_SOCKET)return false;
    sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(8024);inet_pton(AF_INET,"127.0.0.1",&address.sin_addr);
    DWORD timeout=5000;setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,reinterpret_cast<const char*>(&timeout),sizeof(timeout));
    if(connect(s,reinterpret_cast<sockaddr*>(&address),sizeof(address))==SOCKET_ERROR){closesocket(s);return false;}
    std::string request=std::string(payload.empty()?"GET ":"POST ")+path+" HTTP/1.1\r\nHost: 127.0.0.1:8024\r\nConnection: close\r\n";
    if(!payload.empty())request+="Content-Type: application/json\r\nContent-Length: "+std::to_string(payload.size())+"\r\n";
    request+="\r\n"+payload;size_t sent=0;const auto deadline=GetTickCount64()+5000;
    while(sent<request.size()){const int n=send(s,request.data()+sent,static_cast<int>(request.size()-sent),0);if(n<=0||GetTickCount64()>=deadline){closesocket(s);return false;}sent+=n;}
    std::string raw;char bytes[16384];
    for(;;){const auto now=GetTickCount64();if(now>=deadline){closesocket(s);return false;}timeout=static_cast<DWORD>(deadline-now);setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,reinterpret_cast<const char*>(&timeout),sizeof(timeout));
        const int n=recv(s,bytes,sizeof(bytes),0);if(n<0){closesocket(s);return false;}if(!n)break;raw.append(bytes,n);if(raw.size()>bound+16384){closesocket(s);return false;}}
    closesocket(s);return resource::HttpBody(raw,bound,body);
}

static void RunSimPreview(const QueuedCommand& command) {
    struct Finish{~Finish(){g_simPreviewBusy=false;}} finish;
    auto current=[&](){std::lock_guard<std::mutex> lock(g_dataMutex);return command.generation==g_selectionGeneration&&command.resourceRow.value("context",std::string())==g_simPreviewContext;};
    auto message=[&](const std::string& text){std::lock_guard<std::mutex> lock(g_dataMutex);if(command.generation==g_selectionGeneration)g_simPreviewStatus=text;};
    try {
        if(!current())return;
        std::string raw;if(!PreviewHttp("/v1/preview/health",raw))throw std::runtime_error("The preview helper is unavailable. Start the Apex preview service.");
        ui::Json request=ui::Json::object();
        if(command.resourceRow.contains("job")){
            request=command.resourceRow.at("job");
            if(!PreviewHttp("/v1/preview/status/"+ui::Scalar(request,"request_id"),raw))throw std::runtime_error("Prepared preview job unavailable.");
        }else if(command.resourceRow.contains("tray_request")){
            request=command.resourceRow.at("tray_request");
            if(!PreviewHttp("/v1/preview/prepare",raw,request.dump()))throw std::runtime_error("Tray appearance assembly was not accepted.");
        }else{
            if(g_ownerBlocked||g_ownerNativeDeliveryBusy||g_casSubmissionBusy||g_casBankBusy)throw std::runtime_error("Resolve the current appearance operation before previewing.");
            {
                g_ownerSubmissionBusy=true;
                struct OwnerGuard{~OwnerGuard(){g_ownerSubmissionBusy=false;}} owner;
                const bool acknowledged=HttpOwnedCommand(command.path,raw);
                RetainCommandOwner(command,raw);
                if(!acknowledged)throw std::runtime_error("The exact appearance snapshot was not acknowledged; no request replayed.");
            }
            auto snapshot=ui::ParseObject(raw);if(!snapshot.value("ok",false))throw std::runtime_error("Appearance snapshot refused: "+ui::Scalar(snapshot,"message"));
            for(const auto* name:{"ok","sim_id","form","fields","native_sim","native_sha256","lane","appearance_sha256","outfit_index","outfit_id","appearance_source","save_guid","runtime_pid","save_file_written","history_written","preview_id","render_sha256"})request[name]=snapshot.at(name);
            if(snapshot.contains("visual_form"))request["visual_form"]=snapshot.at("visual_form");
            if(!current())return;
            if(!PreviewHttp("/v1/preview/prepare",raw,request.dump()))throw std::runtime_error("Preview assembly was not accepted.");
        }
        auto status=ui::ParseObject(raw);const auto id=ui::Scalar(status,"request_id");if(!resource::Hex(id,64))throw std::runtime_error("Preview job identity is absent.");
        message("Assembling this form and outfit in memory...");const auto deadline=GetTickCount64()+90000;
        while(status.value("state",std::string())=="assembling"){
            if(g_done||!current())return;if(GetTickCount64()>deadline)throw std::runtime_error("Preview assembly deadline exceeded; no request replayed.");
            Sleep(150);if(!PreviewHttp("/v1/preview/status/"+id,raw))throw std::runtime_error("Preview job status unavailable.");status=ui::ParseObject(raw);
        }
        if(!status.value("ok",false)||status.value("state",std::string())!="ready")throw std::runtime_error("Preview assembly refused: "+ui::Scalar(status,"reason"));
        for(const auto* name:{"sim_id","form","outfit_id","outfit_index","runtime_pid","appearance_sha256","lane","render_sha256","preview_id"})if(status.at(name)!=request.at(name))throw std::runtime_error("Completed preview belongs to a different owner.");
        const auto sceneId=ui::Scalar(status,"scene_id");if(!resource::Hex(sceneId,64)||!PreviewHttp("/v1/scenes/"+sceneId+"/scene.json",raw)||resource::HashBytes(raw)!=sceneId)throw std::runtime_error("Preview manifest hash differs.");
        const auto manifest=ui::ParseObject(raw);
        auto scene=std::make_shared<td1::preview::Scene>(td1::preview::Decode(manifest,[&](const std::string& name,const std::string&,size_t bound){
            std::string asset;if(!PreviewHttp("/v1/scenes/"+sceneId+"/"+name,asset,"",bound))throw std::runtime_error("Preview asset unavailable.");return asset;},sceneId));
        if(!current())return;
        {std::lock_guard<std::mutex> lock(g_dataMutex);g_simPreviewScene=std::move(scene);g_simPreviewStatus="Ready / independent 3D preview / package resources read in place";}
    }catch(const std::exception& e){message(e.what());}
}

static void RunTrayClipboard(const QueuedCommand& command) {
    struct Finish{~Finish(){g_trayClipboardBusy=false;g_ownerSubmissionBusy=false;}} finish;
    g_ownerSubmissionBusy=true;
    auto current=[&](){std::lock_guard<std::mutex> lock(g_dataMutex);return command.generation==g_selectionGeneration&&command.sim==g_selectedSim;};
    std::string raw;
    try {
        if(!current()||g_ownerBlocked||g_ownerNativeDeliveryBusy||g_casSubmissionBusy||g_casBankBusy)throw std::runtime_error("Resolve the current owner before copying the displayed Tray form.");
        const auto& r=command.resourceRow.at("tray_request");
        const std::string payload=ui::Json{{"fields",r.at("fields")},{"source",{{"kind","tray"},{"sim_id",r.at("sim_id")},{"form",r.at("form")},{"label",command.resourceRow.at("label")}}}}.dump(-1,' ',true);
        if(payload.empty()||payload.size()>8*1024*1024)throw std::runtime_error("Tray clipboard exceeds its bound.");
        auto call=[&](const std::string& action,const ui::Json& value){
            if(!current())throw std::runtime_error("Destination changed during copy; no command was replayed.");
            const ui::Json envelope={{"form",command.resourceRow.at("target_form")},{"value",value.dump()}};
            QueuedCommand owned=command;owned.path="/api/command?action="+action+"&sim_id="+UrlEncode(command.sim)+"&value="+UrlEncode(envelope.dump());
            if(!HttpOwnedCommand(owned.path,raw))throw std::runtime_error("Tray clipboard owner was not acknowledged.");
            RetainCommandOwner(owned,raw);const auto reply=ui::ParseObject(raw);
            if(!reply.value("ok",false))throw std::runtime_error("Tray clipboard copy: "+ui::Scalar(reply,"message"));return reply;
        };
        const auto begin=call("studio_clipboard_begin",{{"bytes",payload.size()},{"sha256",resource::HashBytes(payload)}});
        const auto upload=ui::Scalar(begin,"upload_id");if(!resource::Hex(upload,32))throw std::runtime_error("Exact clipboard upload identity missing.");
        unsigned index=0;for(size_t offset=0;offset<payload.size();offset+=3072)call("studio_clipboard_chunk",{{"upload_id",upload},{"index",index++},{"data",tray::Base64(payload.substr(offset,3072))}});
        call("studio_clipboard_finish",{{"upload_id",upload}});
    }catch(const std::exception& e){if(!ui::OwnerCommandUnresolved(ui::ParseObject(raw)))raw=ui::Json{{"ok",false},{"message",e.what()}}.dump();}
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if(command.generation==g_selectionGeneration){
        g_commandReply=raw;g_commandReplyMs=GetTickCount64();
        const auto result=ui::ParseObject(raw);
        g_trayClipboardResult={{"ok",result.value("ok",false)},{"message",ui::Scalar(result,"message")},
            {"request_id",ui::Scalar(result,"request_id")},{"request_state",ui::Scalar(result,"request_state")}};
    }
}

static bool QueueResource(int operation, const ui::Json& row = ui::Json::object()) {
    if (operation < 1 || operation > 3 || (operation != 1 &&
        !resource::Catalog({{"schema", 1}, {"items", ui::Json::array({row})}}))) return false;
    std::lock_guard<std::mutex> lock(g_dataMutex);
    auto& busy = operation == 1 ? g_resourceCatalogBusy : operation == 2 ? g_resourceImageBusy : g_resourceOpenBusy;
    if (busy.load() || g_commands.size() >= 48) return false;
    QueuedCommand command{"", g_selectionGeneration};
    command.resourceOperation = operation; command.resourceRow = row;
    command.resourceSelection = g_resourceSelectionSerial.load();
    if (operation == 3) {
        g_resourceOpenKey = ResourceKey(row);
        g_resourceOpenStatus = "Opening the verified containing package copy; request is submitted once.";
    }
    busy = true; g_commands.push_back(std::move(command));
    return true;
}

static bool QueueLibrary(int operation, const ui::Json& request,bool dataLocked=false) {
    if ((operation == 4 && !library::Query(request)) || (operation == 5 && !library::Selection(request)) ||
        (operation == 6 && !library::Selection(request, true)) || operation < 4 || operation > 6) return false;
    std::unique_lock<std::mutex> lock(g_dataMutex,std::defer_lock);if(!dataLocked)lock.lock();
    if (g_libraryBusy.load() || g_commands.size() >= 48) return false;
    QueuedCommand command{"", g_selectionGeneration};
    command.resourceOperation = operation; command.resourceRow = request;
    command.resourceSelection = ++g_librarySerial;
    g_libraryBusy = true; g_commands.push_back(std::move(command));
    return true;
}

static bool QueueGallery(int operation,const ui::Json& request,bool dataLocked=false) {
    if(operation<8||operation>10||operation==8&&!tray::Query(request)||operation==9&&!tray::Selection(request)||operation==10&&!tray::Selection(request,true))return false;
    std::unique_lock<std::mutex> lock(g_dataMutex,std::defer_lock);if(!dataLocked)lock.lock();
    auto& busy=operation==10?g_galleryImageBusy:g_galleryBusy;
    if(busy||g_commands.size()>=48)return false;
    QueuedCommand command{"",g_selectionGeneration};command.resourceOperation=operation;command.resourceRow=request;
    command.resourceSelection=operation==10?g_gallerySerial.load():++g_gallerySerial;
    busy=true;g_commands.push_back(std::move(command));return true;
}

static bool QueueThumbnail(const ui::Json& item,bool dataLocked=false) {
    if(g_thumbnailBusy||g_simPreviewBusy||g_simPreview.scene.id.empty()||g_trayPreviewActive||!resource::Hash(item,"part_id")||
       !resource::Hash(item,"resource_sha256")||!resource::Tgi(ui::Scalar(item,"resource_tgi"))||!item.contains("body_type")||!ui::CasInt(item["body_type"],0,0xffffffffLL))return false;
    std::unique_lock<std::mutex> lock(g_dataMutex,std::defer_lock);if(!dataLocked)lock.lock();if(g_commands.size()>=48||g_thumbnailScene)return false;
    QueuedCommand command{"",g_selectionGeneration};command.resourceOperation=11;command.resourceSelection=g_libraryImageSerial.load();
    command.resourceRow={{"part_id",item["part_id"]},{"base_scene_id",g_simPreview.scene.id},{"resource_tgi",item["resource_tgi"]},{"resource_sha256",item["resource_sha256"]},{"body_type",item["body_type"]}};
    g_thumbnailAttempted.insert(ui::Scalar(item,"part_id"));g_commands.push_back(std::move(command));g_thumbnailBusy=true;return true;
}

static void RunResourceCommand(const QueuedCommand& command) {
    const int operation = command.resourceOperation;
    if(operation==12) {
        struct Finish{~Finish(){g_sliderLibraryBusy=false;}} finish;
        std::string raw;ui::Json page;bool valid=false;
        try {
            if(!td1::sliders::Query(command.resourceRow))throw std::runtime_error("Invalid slider library query.");
            if(!PreviewHttp("/v1/sliders/query",raw,command.resourceRow.dump(),8*1024*1024))throw std::runtime_error("Slider catalog broker unavailable.");
            page=ui::ParseObject(raw);valid=td1::sliders::Page(page,command.resourceRow);
            if(!valid)throw std::runtime_error("Slider catalog response differs from the requested page.");
        } catch(const std::exception& e) {
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if(command.generation==g_selectionGeneration)g_sliderLibraryStatus=e.what();return;
        }
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if(command.generation==g_selectionGeneration){g_sliderLibraryPage=std::move(page);g_sliderLibraryStatus="Package definitions read / native load source checked on Apply";}return;
    }
    if(operation==11) {
        struct Finish{~Finish(){g_thumbnailBusy=false;}} finish;
        const auto current=[&](){return command.generation==g_selectionGeneration&&command.resourceSelection==g_libraryImageSerial.load();};
        std::string raw,reason;ui::Json result;
        try{
            if(!current())return;auto request=command.resourceRow;request.erase("part_id");
            if(!PreviewHttp("/v1/thumbnail/prepare",raw,request.dump()))throw std::runtime_error("Detached thumbnail preparation was refused.");
            result=ui::ParseObject(raw);if(!result.value("ok",false)||result.value("thumbnail_request",ui::Json())!=request)throw std::runtime_error("Thumbnail candidate identity differs: "+ui::Scalar(result,"reason"));
            const auto id=ui::Scalar(result,"request_id");if(!resource::Hex(id,64))throw std::runtime_error("Thumbnail job identity missing.");
            const auto deadline=GetTickCount64()+90000;
            while(result.value("state",std::string())=="assembling"){
                if(g_done||!current())return;if(GetTickCount64()>deadline)throw std::runtime_error("Thumbnail assembly deadline exceeded.");
                Sleep(150);if(!PreviewHttp("/v1/preview/status/"+id,raw))throw std::runtime_error("Thumbnail job status unavailable.");result=ui::ParseObject(raw);}
            if(!result.value("ok",false)||result.value("state",std::string())!="ready")throw std::runtime_error("Thumbnail assembly: "+ui::Scalar(result,"reason"));
            const auto sceneId=ui::Scalar(result,"scene_id");if(!resource::Hex(sceneId,64)||!PreviewHttp("/v1/scenes/"+sceneId+"/scene.json",raw)||resource::HashBytes(raw)!=sceneId)throw std::runtime_error("Thumbnail scene hash differs.");
            auto scene=std::make_shared<td1::preview::Scene>(td1::preview::Decode(ui::ParseObject(raw),[&](const std::string& name,const std::string&,size_t bound){std::string bytes;if(!PreviewHttp("/v1/scenes/"+sceneId+"/"+name,bytes,"",bound))throw std::runtime_error("Thumbnail asset unavailable.");return bytes;},sceneId));
            std::lock_guard<std::mutex> lock(g_dataMutex);if(current()){g_thumbnailScene=std::move(scene);g_thumbnailBinding=command.resourceRow;g_thumbnailReceipt={{"ok",true},{"state","staged"},{"part_id",command.resourceRow["part_id"]},{"scene_id",sceneId},{"game_appearance_written",false}};}
        }catch(const std::exception& e){std::lock_guard<std::mutex> lock(g_dataMutex);if(current()){
            g_libraryImageErrors[ui::Scalar(command.resourceRow,"part_id")]=e.what();g_thumbnailReceipt={{"ok",false},{"state","failed"},{"reason",e.what()},{"part_id",command.resourceRow["part_id"]}};}}
        return;
    }
    if(operation>=8&&operation<=10) {
        struct Finish{bool image;~Finish(){if(image)g_galleryImageBusy=false;else g_galleryBusy=false;}} finish{operation==10};
        std::string raw;const bool received=ResourceHttp(operation,command.resourceRow,raw);auto result=ui::ParseObject(raw);
        bool valid=received&&result.value("ok",false);
        resource::Pixels pixels;std::string reason;
        try{
            if(operation==8)valid=valid&&tray::Page(result,command.resourceRow);
            else {
                valid=valid&&result.value("item_id",ui::Json())==command.resourceRow["item_id"]&&result.value("library_sha256",ui::Json())==command.resourceRow["library_sha256"]&&
                    result.value("game_contacted",ui::Json())==false&&result.value("source_files_written",ui::Json(false))==false;
                if(operation==10&&valid){valid=result.value("image_index",ui::Json())==command.resourceRow["image_index"];
                    const auto png=tray::Decode64(ui::Scalar(result,"png_base64"));
                    valid=valid&&resource::DecodeThumbnail(png,{{"thumbnail",{{"status","resolved"},{"sha256",result.at("sha256")},{"width",result.at("width")},{"height",result.at("height")}}}},pixels,reason);}
                if(operation==9&&valid){const auto& context=command.resourceRow.at("context");const auto lane=ui::Scalar(context,"history_lane");
                    valid=result.contains("preview_sims")&&result["preview_sims"].is_array()&&!result["preview_sims"].empty()&&result["preview_sims"].size()<=128;
                    if(valid)for(const auto& sim:result["preview_sims"])if(!tray::Forms(sim.at("forms"),GetCurrentProcessId(),lane.substr(0,lane.find(':'))))valid=false;}
            }
        }catch(const std::exception& e){valid=false;reason=e.what();}
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if(command.generation==g_selectionGeneration&&command.resourceSelection==g_gallerySerial.load()) {
            if(valid){if(operation==8)g_galleryPage=std::move(result);else if(operation==9)g_galleryInspection=std::move(result);else g_galleryPixels[ui::Scalar(command.resourceRow,"item_id")]=std::move(pixels);}
            g_galleryStatus=valid?(operation==9?"Household source ready / choose a Sim and form":"Native Tray gallery ready"):"Tray browser: "+(reason.empty()?ui::Scalar(result,"reason"):reason);
        }return;
    }
    if(operation==7) {
        struct Finish {~Finish(){g_libraryImagesBusy=false;}} finish;
        ui::Json page;{std::lock_guard<std::mutex> lock(g_dataMutex);page=g_libraryPage;}
        const auto current=[&](){return command.generation==g_selectionGeneration&&command.resourceSelection==g_libraryImageSerial.load();};
        if(!current())return;
        std::string raw;const bool received=ResourceHttp(7,command.resourceRow,raw);
        const auto result=ui::ParseObject(raw);
        const bool valid=received&&library::ImagesPage(result,command.resourceRow,page);
        std::map<std::string,resource::Pixels> decoded;std::map<std::string,std::string> errors;
        if(valid)for(const auto& item:result["items"]) {
            const auto id=ui::Scalar(item,"part_id");const auto& row=item["resource"];std::string reason;resource::Pixels pixels;
            if(row["thumbnail"]["status"]!="resolved")errors[id]=ui::Scalar(row["thumbnail"],"reason");
            else if(current()&&ResourceHttp(2,row,raw)&&resource::DecodeThumbnail(raw,row,pixels,reason))decoded[id]=std::move(pixels);
            else errors[id]=reason.empty()?"Image verification or transport failed.":reason;
        }else for(const auto& id:command.resourceRow["part_ids"])errors[id.get<std::string>()]="Images unavailable: "+ui::Scalar(result,"reason");
        if(current()){std::lock_guard<std::mutex> lock(g_dataMutex);g_libraryImagePixels=std::move(decoded);g_libraryImageErrors=std::move(errors);}
        return;
    }
    if (operation >= 4) {
        bool current;
        { std::lock_guard<std::mutex> lock(g_dataMutex); current = command.generation == g_selectionGeneration && command.resourceSelection == g_librarySerial.load(); }
        std::string body;
        const bool received = current && ResourceHttp(operation, command.resourceRow, body);
        const auto value = ui::ParseObject(body);
        const bool valid = received && (operation == 4 ? library::Page(value, command.resourceRow) :
            operation == 5 ? library::Inspection(value, command.resourceRow) :
            value.value("ok", ui::Json(false)) == true && value.value("part_id", ui::Json()) == command.resourceRow["part_id"] &&
            value.value("index_sha256", ui::Json()) == command.resourceRow["index_sha256"] && value.value("enabled", ui::Json()) == command.resourceRow["enabled"]);
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if (command.generation == g_selectionGeneration && command.resourceSelection == g_librarySerial.load()) {
            if (valid && operation == 4) g_libraryPage = value;
            if (valid && operation == 5) g_libraryInspection = value;
            g_libraryStatus = valid ? (operation == 5 ? "Selected package and CASP bytes verified. Compatibility is checked in the game before preview." : "Catalog page received. Browsing has not changed the Sim.") :
                "Catalog unavailable or request refused. " + ui::Scalar(value, "reason");
        }
        g_libraryBusy = false;
        return;
    }
    bool current;
    {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        current = command.generation == g_selectionGeneration &&
            (operation == 1 || command.resourceSelection == g_resourceSelectionSerial.load());
    }
    std::string body, message; resource::Pixels pixels;
    bool ok = current && ResourceHttp(operation, command.resourceRow, body);
    ui::Json catalog = ui::Json::object();
    if (operation == 1) {
        catalog = ui::ParseObject(body); ok = ok && resource::CatalogIdentities(catalog);
        message = ok ? "Pinned resource cache received from 127.0.0.1:8022." :
            "Resource broker unavailable or its complete pinned catalog was rejected.";
    } else if (operation == 2) {
        if (ok) ok = resource::DecodeThumbnail(body, command.resourceRow, pixels, message);
        if (ok) message = "Verified cached PNG bytes and dimensions; decoded with WIC.";
        else if (message.empty()) message = current ? "Thumbnail transport failed; no substitute image was used." : "Thumbnail selection changed before delivery.";
    } else if (operation == 3) {
        const auto receipt = ui::ParseObject(body);
        ok = ok && resource::OpenReceipt(receipt, ui::Scalar(command.resourceRow, "resource_id"));
        message = ok ? "Studio received the verified containing package copy. Selecting the individual resource is unsupported." :
            (current ? "Studio open outcome is unverified or rejected. The request was not replayed." : "Selection changed; Studio request was canceled before delivery.");
    }
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if (operation == 1) {
        if (ok) g_resourceCatalog = std::move(catalog);
        g_resourceCatalogStatus = message; g_resourceCatalogBusy = false;
    } else if (operation == 2) {
        g_resourceImageKey = ResourceKey(command.resourceRow); g_resourceImageStatus = message;
        g_resourcePixels = std::move(pixels); ++g_resourcePixelReceipt; g_resourceImageBusy = false;
    } else if (operation == 3) {
        g_resourceOpenKey = ResourceKey(command.resourceRow); g_resourceOpenStatus = message; g_resourceOpenBusy = false;
    }
}

static std::vector<std::string> ExtractHistory(const std::string& json) {
    return ui::Logs(ui::ReadObject(json));
}

// Called with g_dataMutex held. Native replies reserve their UUID until the
// render thread has consumed this exact body, including normal submissions.
static void PublishCommandReply(const std::string& body, ULONGLONG receivedMs) {
    g_json = body; g_commandReply = body; g_commandReplyMs = receivedMs;
    const auto receipt = ui::ParseObject(body);
    if (receipt.contains("qol") && receipt["qol"].is_object() &&
        receipt["qol"].contains("schema") && receipt["qol"]["schema"].is_number_integer() &&
        receipt["qol"]["schema"].get<int>() == 1) g_qolReceipt = receipt["qol"];
    if (receipt.contains("cas_request_id") && ui::CasRequestIdentity(receipt["cas_request_id"])) {
        g_ownerNativeDeliveryBusy = true; g_ownerDeliveredNativeReply = body;
    }
    auto lines = ExtractHistory(body); if (!lines.empty()) g_logLines = std::move(lines);
}

static std::string ExtractJsonValue(const std::string& json, const char* keyName) {
    return ui::Scalar(ui::ReadObject(json), keyName);
}

static bool QueueCommand(const std::string& path, const std::string& nativeId = {}) {
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if ((g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() || g_casBankBusy.load()) && path.rfind("/api/command?", 0) == 0) {
        g_status = "An owner result is unresolved; check its retained ID before another command";
        return false;
    }
    if (g_commands.size() >= 48) {
        g_status = "Queue full: this command was rejected; earlier commands were retained";
        return false;
    }
    QueuedCommand command{path, g_selectionGeneration}; command.sim = g_selectedSim;
    if (ui::CasRequestIdentity(ui::Json(nativeId))) command.casRequestId = nativeId;
    g_commands.push_back(std::move(command));
    return true;
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

// Queue only typed review intent. Native owner reads and writes stay on the
// authenticated game thread; the renderer receives canonical owner receipts.
static bool QueueCasBankActionLocked(const std::string& action) {
    if (g_done.load() || g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() ||
        g_ownerSubmissionBusy.load() || g_casSubmissionBusy.load() || g_casBankBusy.load() ||
        g_casPendingId[0] || !g_commands.empty() || !ui::ExactUint64Identity(ui::Json(g_selectedSim))) {
        g_status="CAS review waits for the existing request; nothing was submitted."; return false;
    }
    if (!ui::BankCurrent(g_casBank,g_selectedSim,g_selectionGeneration)) {
        g_casBank={}; g_casBank.sim=g_selectedSim; g_casBank.generation=g_selectionGeneration;
    }
    ui::Json argument;
    if (!ui::BankRequest(g_casBank,action,argument)) {
        g_status="CAS review requires its exact previous receipt and explicit decisions."; return false;
    }
    const auto route=ui::BankRoute(action);
    if (!route[0]) return false;
    std::string path="/api/command?action="+UrlEncode(route)+"&sim_id="+UrlEncode(g_selectedSim);
    if (!argument.is_null()) path+="&value="+UrlEncode(argument.dump());
    QueuedCommand command{path,g_selectionGeneration}; command.sim=g_selectedSim; command.casBankAction=action;
    ui::BankSubmitted(g_casBank,action); g_casBankBusy=true;
    g_commands.push_back(std::move(command)); return true;
}
static bool QueueCasBankAction(const std::string& action) {
    std::lock_guard<std::mutex> lock(g_dataMutex);
    return QueueCasBankActionLocked(action);
}

static void QueueAction(const char* action, const char* occult = nullptr, const char* value = nullptr) {
    std::string name = action ? action : "status";
    if (name.rfind("cas_bank_",0)==0) { QueueCasBankAction(name); return; }
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
    QueueCommand(path, name == "cas_ui_result" && value ? value : "");
}

static bool OccultButton(const char* label,const char* occult,const ImVec2& size=ImVec2(0,0)) {
    const auto icon=g_occultIconTextures.find(occult&&std::strcmp(occult,"SPELLCASTER")==0?"WITCH":occult?occult:"");
    if(icon==g_occultIconTextures.end())return ImGui::Button(label,size);
    const auto height=ImGui::GetFrameHeight();
    const bool clicked=ImGui::Button((std::string("      ")+label).c_str(),size);
    const auto pos=ImGui::GetItemRectMin();const auto side=height-4;
    ImGui::GetWindowDrawList()->AddImage(reinterpret_cast<ImTextureID>(icon->second),
        ImVec2(pos.x+2,pos.y+2),ImVec2(pos.x+2+side,pos.y+2+side));
    return clicked;
}

static bool ActionButton(const char* label, const char* action, const char* occult = nullptr, const char* value = nullptr, const ImVec2& size = ImVec2(-1, 0)) {
    if (!OccultButton(label, occult, size)) return false;
    QueueAction(action, occult, value);
    return true;
}

static bool AutomaticCasPaneVisible() {
    const auto now = GetTickCount64(), observed = g_nativeCasPaneMs.load();
    return g_visible.load() && g_nativeCasPaneVisible.load() && observed && now >= observed && now - observed <= 1000;
}

static bool RetainCommandOwner(const QueuedCommand& command, const std::string& body) {
    const auto receipt = ui::ParseObject(body);
    if (!ui::OwnerCommandUnresolved(receipt)) return false;
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if (ui::RetainOwnerObservation(g_ownerObservation, receipt, command.generation, command.sim,
        command.casRequestId, GetTickCount64())) {
        g_ownerOriginalCommand = command;
        g_ownerBlocked = true;
    }
    return g_ownerBlocked.load();
}

static bool QueueOwnerObservation(bool explicitCheck) {
    std::lock_guard<std::mutex> lock(g_dataMutex);
    const auto now = GetTickCount64();
    if (g_done.load() || g_commands.size() >= 48 || !ui::OwnerObservationDue(g_ownerObservation, now,
        g_visible.load(), explicitCheck)) return false;
    QueuedCommand command{ui::OwnerObservationPath(g_ownerObservation), g_ownerObservation.generation};
    command.sim = g_ownerObservation.sim; command.ownerObservation = true;
    command.ownerRequestId = g_ownerObservation.requestId;
    g_ownerObservation.checking = true; g_ownerObservation.lastCheckMs = now;
    g_commands.push_back(std::move(command));
    return true;
}

static bool BeginOwnerObservation(const QueuedCommand& command) {
    std::lock_guard<std::mutex> lock(g_dataMutex);
    const bool matching = command.ownerRequestId == g_ownerObservation.requestId &&
        command.path == ui::OwnerObservationPath(g_ownerObservation);
    if (matching && g_visible.load() && !g_done.load()) return true;
    if (matching) g_ownerObservation.checking = false;
    return false;
}

// Apply a status GET only to its retained owner and original selection. A
// completed owner observation may still leave a distinct native CAS request.
static void ApplyOwnerObservation(const QueuedCommand& command, bool received, const std::string& body) {
    const auto receipt = ui::ParseObject(body);
    ui::Json result;
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if (command.ownerRequestId != g_ownerObservation.requestId) return;
    g_ownerObservation.checking = false;
    g_ownerObservation.lastReply = received ? receipt : ui::Json({{"ok",false},{"state","unknown"},
        {"request_id",command.ownerRequestId},{"message","Owner status check failed; the retained command remains unresolved."}});
    if (!received || ui::ReadOwnerCompletion(receipt, command.ownerRequestId, result) != ui::OwnerReply::Terminal) return;
    const bool current = command.generation == g_selectionGeneration && command.sim == g_selectedSim;
    const auto nativeId = g_ownerObservation.nativeRequestId;
    if (!nativeId.empty()) {
        if (result.contains("cas_request_id") && ui::Scalar(result, "cas_request_id") != nativeId) return;
        if (!result.contains("cas_request_id")) {
            result["cas_request_id"] = nativeId; result["ok"] = false; result["outcome"] = "unresolved";
            result["message"] = "Owner observation completed; the retained native CAS result remains unverified.";
        }
    }
    const auto recovered = result.dump();
    const auto& original = g_ownerOriginalCommand;
    if (result.contains("cas_request_id") && !ui::CasRequestIdentity(result["cas_request_id"])) return;
    if (current && result.contains("cas_request_id")) {
        g_ownerNativeDeliveryBusy = true;
        g_ownerDeliveredNativeReply = recovered;
    }
    if (!current) {
        // The GET resolves the historical command; its data cannot overwrite
        // a new selection. Queued work is cancelled before owner submission.
        g_ownerObservation.lastReply["message"] = "Owner command resolved for an earlier selection; its result was retained without replacing current data.";
    } else if (original.automaticStudioItems) {
        g_studioItemsReply = recovered; ++g_studioItemsReceipt;
    } else if (original.automaticCasReconcile) {
        g_casReconcileReply = recovered; g_casReconcileOk = true;
        g_casReconcileNativeId = original.casRequestId; g_casReconcileSim = original.sim;
        ++g_casReconcileReceipt;
    } else {
        if (!original.casBankAction.empty()) {
            ui::BankApply(g_casBank,original.sim,original.generation,original.casBankAction,result);
            g_casBankBusy=g_casBank.busy;
        }
        PublishCommandReply(recovered, g_ownerObservation.retainedAtMs);
        if (original.automaticCasRefresh) {
            if (original.path.find("action=cas_ui_diagnostics") != std::string::npos) {
                g_casDiagnosticReply = recovered; g_casDiagnosticMs = GetTickCount64();
            }
            // A recovered automatic acknowledgement is historical. Let the
            // native exact-ID reconciler release it before a new live read.
            g_casRefreshNativeId = result.contains("cas_request_id") && ui::CasRequestIdentity(result["cas_request_id"])
                ? ui::Scalar(result, "cas_request_id") : "";
            g_casRefreshFailed = false; g_casRefreshUnresolved = false;
            g_casRefreshMessage = "Retained owner command resolved; its original result is shown below.";
            ++g_casRefreshReceipt;
        }
    }
    g_ownerObservation.requestId.clear(); g_ownerBlocked = false; g_casSubmissionBusy = false;
    g_status = "Retained owner command resolved; see its original result";
}

static void WorkerLoop() {
    g_workerActive = true;
    while (!g_done) {
        QueuedCommand command;
        {
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if (!g_commands.empty()) { command = g_commands.front(); g_commands.pop_front(); }
        }
        if (command.resourceOperation) { RunResourceCommand(command); continue; }
            if (command.occultIcons) {
                if(g_ownerBlocked.load()||g_ownerNativeDeliveryBusy.load()||g_casBankBusy.load())continue;
                std::string body;
                if (HttpOwnedCommand(command.path,body)) {
                    RetainCommandOwner(command,body);
                    const auto reply=ui::ParseObject(body);
                    std::map<std::string,resource::Pixels> decoded;
                    const auto catalog=reply.value("occult_icons",ui::Json::object());
                    if(reply.value("ok",false)&&catalog.value("schema",0)==1&&
                        catalog.value("origin",std::string())=="installed-occult-trait-tuning"&&
                        catalog.contains("items")&&catalog["items"].is_array()&&catalog["items"].size()<=6) {
                        for(const auto& row:catalog["items"]) {
                            const auto name=ui::Scalar(row,"name");
                            if(name!="ALIEN"&&name!="VAMPIRE"&&name!="MERMAID"&&name!="WITCH"&&name!="WEREWOLF"&&name!="FAIRY")continue;
                            if(ui::Scalar(row,"status")!="resolved"||ui::Scalar(row,"image_base64").size()>175000)continue;
                            std::string png;
                            try{png=tray::Decode64(ui::Scalar(row,"image_base64"));}catch(const std::exception&){continue;}
                            resource::Pixels pixels;std::string reason;
                            if(resource::DecodeOccultImage(png,row,pixels,reason))decoded.emplace(name,std::move(pixels));
                        }
                    }
                    std::lock_guard<std::mutex> lock(g_dataMutex);g_occultIconPixels=std::move(decoded);
                }
                continue; // Artwork never replaces a user's action/result or changes a Sim.
            }
        if (command.simPreview) { RunSimPreview(command); continue; }
        if (command.trayClipboard) { RunTrayClipboard(command); continue; }
        if (!command.path.empty()) {
            if (command.ownerObservation) {
                if (!BeginOwnerObservation(command)) continue;
                std::string body;
                const bool ok = HttpGet(command.path, body, GetTickCount64() + 3000);
                ApplyOwnerObservation(command, ok, body);
                continue;
            }
            if ((g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() ||
                (g_casBankBusy.load() && command.casBankAction.empty())) && command.path.rfind("/api/command?", 0) == 0) {
                g_casSubmissionBusy = false;
                if (command.automaticStudioItems) g_studioItemsBusy = false;
                if (!command.casBankAction.empty()) {
                    std::lock_guard<std::mutex> lock(g_dataMutex);
                    g_casBank.busy=false; g_casBank.failed=true; g_casBankBusy=false;
                    g_casBank.message="CAS review was cancelled before submission because another owner is unresolved. Read status after resolving that owner.";
                }
                continue;
            }
            {
                std::lock_guard<std::mutex> lock(g_dataMutex);
                if (command.generation != g_selectionGeneration || command.sim != g_selectedSim) {
                    g_casSubmissionBusy = false;
                    if (command.automaticStudioItems) g_studioItemsBusy = false;
                    if (!command.casBankAction.empty() && ui::BankCurrent(g_casBank,command.sim,command.generation)) {
                        g_casBank.busy=false; g_casBank.failed=true; g_casBankBusy=false;
                        g_casBank.message="Selection changed before submission; no CAS review operation was sent.";
                    }
                    continue;
                }
                g_ownerSubmissionBusy = true;
            }
            struct OwnerSubmissionGuard { ~OwnerSubmissionGuard() { g_ownerSubmissionBusy = false; } } ownerSubmission;
            if (command.automaticStudioItems) {
                bool current;
                { std::lock_guard<std::mutex> lock(g_dataMutex); current = command.generation == g_selectionGeneration; }
                std::string result;
                if (current && g_visible.load()) HttpOwnedCommand(command.path, result);
                RetainCommandOwner(command, result);
                { std::lock_guard<std::mutex> lock(g_dataMutex);
                  g_studioItemsReply = current ? result : "{}"; ++g_studioItemsReceipt; }
                continue; // A metadata page cannot overwrite a user's command result.
            }
            bool automaticFailed = false, automaticUnresolved = false;
            std::string automaticMessage;
            if (command.automaticCasRefresh || command.automaticCasReconcile) {
                bool sameSelection;
                { std::lock_guard<std::mutex> lock(g_dataMutex); sameSelection = command.generation == g_selectionGeneration; }
                if (!AutomaticCasPaneVisible() || !g_casAutoRefreshEnabled.load() || !sameSelection) {
                    g_casSubmissionBusy = false;
                    continue; // Hidden/superseded auto work was never submitted.
                }
            }
            std::string body;
            bool ok = HttpOwnedCommand(command.path, body);
            if (command.automaticCasReconcile) {
                RetainCommandOwner(command, body);
                std::lock_guard<std::mutex> lock(g_dataMutex);
                if (command.generation == g_selectionGeneration) {
                    g_casReconcileReply = body; g_casReconcileOk = ok;
                    g_casReconcileNativeId = command.casRequestId; g_casReconcileSim = command.sim;
                    ++g_casReconcileReceipt;
                }
                g_casSubmissionBusy = false;
                continue; // Cached exact-ID result only; never render it as a new snapshot.
            }
            if (command.automaticCasRefresh) {
                const auto diagnosticMs = GetTickCount64();
                const auto diagnostic = ui::ParseObject(body);
                {
                    std::lock_guard<std::mutex> lock(g_dataMutex);
                    if (command.generation == g_selectionGeneration && ok) {
                        g_casDiagnosticReply = body; g_casDiagnosticMs = diagnosticMs;
                    }
                }
                const bool peerFresh = ok && ui::CasFreshNativePeer(diagnostic, command.sim, diagnosticMs, GetTickCount64());
                const bool transportIdle = peerFresh && ui::CasTransportIdle(diagnostic);
                bool sameSelection;
                { std::lock_guard<std::mutex> lock(g_dataMutex); sameSelection = command.generation == g_selectionGeneration; }
                if (peerFresh && transportIdle && sameSelection && AutomaticCasPaneVisible() && g_casAutoRefreshEnabled.load()) {
                    // This is one fresh read, after one exact-Sim heartbeat check.
                    // Preserve the existing native request/polling contract.
                    command.path = "/api/command?action=cas_ui_request&sim_id=" + UrlEncode(command.sim) +
                        "&value=" + UrlEncode("{\"operation\":\"status\"}");
                    ok = HttpOwnedCommand(command.path, body);
                    if (!ok || ui::OwnerCommandUnresolved(ui::ParseObject(body))) {
                        automaticFailed = true; automaticUnresolved = true;
                        automaticMessage = "Auto refresh paused: submission outcome is unverified. Inspect transport requests before another native read.";
                    }
                } else {
                    automaticFailed = !ok || !peerFresh || !transportIdle;
                    automaticMessage = !ok ? "Auto refresh backed off: transport diagnostics failed." :
                        (!peerFresh ? "Auto refresh waiting for a fresh native CAS peer for this exact Sim." :
                        (!transportIdle ? "Auto refresh waiting for the existing native request to resolve." : "Auto refresh canceled after leaving this view."));
                }
            }
            // HTTP submission is not a successful native CAS transition.
            // Poll the native acknowledgement once; never replay input.
            if (ok && command.path.find("action=cas_ui_request") != std::string::npos) {
                const auto pending = ui::ParseObject(body);
                const auto id = ui::Scalar(pending, "cas_request_id");
                if (ui::Scalar(pending, "outcome") == "pending-client" && id.size() == 32) {
                    command.casRequestId = id;
                    const auto query = "&sim_id=" + UrlEncode(command.sim);
                    const auto deadline = GetTickCount64() + 10000;
                    while (!g_done && GetTickCount64() < deadline) {
                        if (command.automaticCasRefresh && !AutomaticCasPaneVisible()) break;
                        std::string result;
                        if (!HttpOwnedCommand("/api/command?action=cas_ui_result" + query + "&value=" + UrlEncode(id), result)) break;
                        body = result;
                        if (ui::Scalar(ui::ReadObject(result), "outcome") != "pending-client") break;
                        Sleep(150);
                    }
                }
            }
            if (command.automaticCasRefresh && command.path.find("action=cas_ui_request") != std::string::npos && ok) {
                const auto data = ui::ParseObject(body);
                if (!data.contains("client") || !data.contains("ok") || data["ok"] != true || !ui::CasDocument(data["client"], command.sim)) {
                    automaticFailed = true;
                    automaticUnresolved = ui::OwnerCommandUnresolved(data) || (!ui::CasExplicitFailure(data) &&
                        (data.contains("cas_request_id") || ui::Scalar(data, "outcome") == "pending-client"));
                    automaticMessage = automaticUnresolved ? "Auto refresh paused; retain and inspect the native request ID. No read will be replayed." :
                        "Auto refresh backed off after a rejected or invalid native response.";
                } else automaticMessage = "Equipped inventory refreshed from the native CAS client.";
            }
            RetainCommandOwner(command, body);
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if (command.generation == g_selectionGeneration) {
                if (!command.casBankAction.empty()) {
                    ui::BankApply(g_casBank,command.sim,command.generation,command.casBankAction,ui::ParseObject(body));
                    g_casBankBusy=g_casBank.busy;
                }
                g_status = !ok ? "Command request failed; outcome unverified" :
                    (ExtractJsonValue(body, "outcome") == "pending-client" ? "Awaiting native CAS acknowledgement; request retained" :
                    (ExtractJsonValue(body, "ok") == "true" ? "Command completed; see its result" : "Command rejected; see its reason"));
                if (ok) PublishCommandReply(body, GetTickCount64());
                if (command.automaticCasRefresh) {
                    g_casRefreshFailed = automaticFailed; g_casRefreshUnresolved = automaticUnresolved;
                    g_casRefreshMessage = automaticMessage; ++g_casRefreshReceipt;
                    const auto data = ui::ParseObject(body);
                    g_casRefreshNativeId = automaticUnresolved && data.contains("cas_request_id") && ui::CasRequestIdentity(data["cas_request_id"])
                        ? ui::Scalar(data, "cas_request_id") : "";
                }
            }
            if (command.automaticCasRefresh || command.path.find("action=cas_ui_request") != std::string::npos) g_casSubmissionBusy = false;
            continue;
        }
        if (g_visible.load() && !g_nativeCasPaneVisible.load() && !g_ownerBlocked.load()) {
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

static void CleanupResourceTexture() {
    if (g_resourceTexture) { g_resourceTexture->Release(); g_resourceTexture = nullptr; }
    g_resourceTextureKey.clear(); g_resourceTextureReceipt = 0;
}

static void CleanupLibraryImages() {
    for(auto& item:g_libraryImageTextures)if(item.second)item.second->Release();
    g_libraryImageTextures.clear();g_libraryImageSizes.clear();g_libraryImageAttempted.clear();g_libraryImageContext.clear();
    ++g_libraryImageSerial;
    std::lock_guard<std::mutex> lock(g_dataMutex);g_libraryImagePixels.clear();g_libraryImageErrors.clear();g_thumbnailScene.reset();g_thumbnailBinding=ui::Json::object();
}

static void CleanupOccultIcons() {
    for(auto& item:g_occultIconTextures)if(item.second)item.second->Release();
    g_occultIconTextures.clear();g_occultIconsRequested=false;
    std::lock_guard<std::mutex> lock(g_dataMutex);g_occultIconPixels.clear();
}

static void SynchronizeOccultIcons() {
    std::map<std::string,resource::Pixels> received;
    {std::lock_guard<std::mutex> lock(g_dataMutex);received.swap(g_occultIconPixels);}
    for(auto& entry:received) {
        const auto& p=entry.second;
        if(!g_device||!p.width||!p.height||p.width>512||p.height>512||p.rgba.size()!=size_t(p.width)*p.height*4)continue;
        D3D11_TEXTURE2D_DESC desc{};desc.Width=p.width;desc.Height=p.height;desc.MipLevels=desc.ArraySize=desc.SampleDesc.Count=1;
        desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.Usage=D3D11_USAGE_IMMUTABLE;desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA data{};data.pSysMem=p.rgba.data();data.SysMemPitch=p.width*4;
        ID3D11Texture2D* texture=nullptr;ID3D11ShaderResourceView* view=nullptr;
        if(SUCCEEDED(g_device->CreateTexture2D(&desc,&data,&texture))&&texture){
            const auto result=g_device->CreateShaderResourceView(texture,nullptr,&view);texture->Release();
            if(SUCCEEDED(result)&&view){auto& old=g_occultIconTextures[entry.first];if(old)old->Release();old=view;}
        }
    }
#ifndef APEX_NATIVE_SMOKE
    if(!g_occultIconsRequested&&!g_ownerBlocked&&!g_ownerNativeDeliveryBusy&&!g_casBankBusy) {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if(!g_done&&g_commands.size()<48){QueuedCommand command{"/api/command?action=occult_icons",g_selectionGeneration};
            command.occultIcons=true;g_commands.push_back(std::move(command));g_occultIconsRequested=true;}
    }
#endif
}

static void SynchronizeLibraryImages(const ui::Json& page) {
    const auto context=ui::Scalar(page,"index_sha256")+page.value("query",ui::Json()).dump()+std::to_string(g_libraryImageGender);
    if(context!=g_libraryImageContext){CleanupLibraryImages();g_thumbnailAttempted.clear();g_libraryImageContext=context;}
    std::shared_ptr<td1::preview::Scene> thumbnail;ui::Json binding;
    {std::lock_guard<std::mutex> lock(g_dataMutex);thumbnail.swap(g_thumbnailScene);binding=g_thumbnailBinding;}
    if(thumbnail){try{
        td1::preview::Renderer renderer;renderer.Load(g_device,std::move(*thumbnail));
        const auto body=binding.at("body_type").get<int>();
        try{renderer.Preset(renderer.view,"selected",body);}catch(...){renderer.Preset(renderer.view,"face");}
        renderer.view.playing=false;renderer.Render(g_context,256,256,0);
        D3D11_TEXTURE2D_DESC d{};renderer.Target()->GetDesc(&d);d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        Microsoft::WRL::ComPtr<ID3D11Texture2D> staging;td1::preview::Check(g_device->CreateTexture2D(&d,nullptr,&staging),"Thumbnail readback allocation failed.");
        g_context->CopyResource(staging.Get(),renderer.Target());D3D11_MAPPED_SUBRESOURCE map{};
        td1::preview::Check(g_context->Map(staging.Get(),0,D3D11_MAP_READ,0,&map),"Thumbnail GPU readback failed.");
        resource::Pixels pixels;pixels.width=pixels.height=256;pixels.rgba.resize(256*256*4);
        for(size_t y=0;y<256;++y)std::memcpy(pixels.rgba.data()+y*256*4,static_cast<const unsigned char*>(map.pData)+y*map.RowPitch,256*4);
        g_context->Unmap(staging.Get(),0);
        const auto hash=resource::HashBytes(std::string(reinterpret_cast<const char*>(pixels.rgba.data()),pixels.rgba.size()));
        std::lock_guard<std::mutex> lock(g_dataMutex);g_libraryImagePixels[ui::Scalar(binding,"part_id")]=std::move(pixels);
        g_thumbnailReceipt["state"]="ready";g_thumbnailReceipt["rgba_sha256"]=hash;g_thumbnailReceipt["width"]=256;g_thumbnailReceipt["height"]=256;g_thumbnailReceipt["disk_assets_written"]=false;
    }catch(const std::exception& e){std::lock_guard<std::mutex> lock(g_dataMutex);g_thumbnailReceipt={{"ok",false},{"state","failed"},{"reason",e.what()}};}}
    std::map<std::string,resource::Pixels> received;
    {std::lock_guard<std::mutex> lock(g_dataMutex);received.swap(g_libraryImagePixels);}
    for(auto& entry:received) {
        const auto& pixels=entry.second;
        if(!g_device||!pixels.width||!pixels.height||pixels.width>512||pixels.height>512||
           pixels.rgba.size()!=size_t(pixels.width)*pixels.height*4||g_libraryImageTextures.size()>=60)continue;
        D3D11_TEXTURE2D_DESC description{};description.Width=pixels.width;description.Height=pixels.height;
        description.MipLevels=description.ArraySize=description.SampleDesc.Count=1;description.Format=DXGI_FORMAT_R8G8B8A8_UNORM;
        description.Usage=D3D11_USAGE_IMMUTABLE;description.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA data{};data.pSysMem=pixels.rgba.data();data.SysMemPitch=pixels.width*4;
        ID3D11Texture2D* texture=nullptr;ID3D11ShaderResourceView* view=nullptr;
        if(SUCCEEDED(g_device->CreateTexture2D(&description,&data,&texture))&&texture) {
            const auto result=g_device->CreateShaderResourceView(texture,nullptr,&view);texture->Release();
            if(SUCCEEDED(result)&&view){g_libraryImageTextures[entry.first]=view;g_libraryImageSizes[entry.first]=ImVec2(float(pixels.width),float(pixels.height));}
        }
    }
}

static bool ResourceTexture(const std::string& key) {
    resource::Pixels pixels; uint64_t receipt = 0;
    {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if (g_resourceImageKey != key || g_resourcePixels.rgba.empty()) return false;
        receipt = g_resourcePixelReceipt;
        if (g_resourceTexture && g_resourceTextureKey == key && receipt == g_resourceTextureReceipt) return true;
        pixels = g_resourcePixels;
    }
    CleanupResourceTexture();
    if (!g_device || !pixels.width || !pixels.height || pixels.width > 512 || pixels.height > 512 ||
        pixels.rgba.size() != static_cast<size_t>(pixels.width) * pixels.height * 4) return false;
    D3D11_TEXTURE2D_DESC description{};
    description.Width = pixels.width; description.Height = pixels.height;
    description.MipLevels = description.ArraySize = description.SampleDesc.Count = 1;
    description.Format = DXGI_FORMAT_R8G8B8A8_UNORM; description.Usage = D3D11_USAGE_IMMUTABLE;
    description.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    D3D11_SUBRESOURCE_DATA data{}; data.pSysMem = pixels.rgba.data(); data.SysMemPitch = pixels.width * 4;
    ID3D11Texture2D* texture = nullptr;
    if (FAILED(g_device->CreateTexture2D(&description, &data, &texture)) || !texture) return false;
    const HRESULT result = g_device->CreateShaderResourceView(texture, nullptr, &g_resourceTexture);
    texture->Release();
    if (FAILED(result) || !g_resourceTexture) return false;
    g_resourceTextureKey = key; g_resourceTextureReceipt = receipt;
    return true;
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

#ifdef APEX_NATIVE_SMOKE
static std::string g_smokeCapturePath;
#endif
static std::string TimestampName(const char* mode) {
#ifdef APEX_NATIVE_SMOKE
    if (!g_smokeCapturePath.empty()) return g_smokeCapturePath;
#endif
    std::time_t t = std::time(nullptr);
    std::tm tm{};
    localtime_s(&tm, &t);
    std::ostringstream ss;
    ss << ScreenshotFolder() << "\\TD1Apex_" << mode << "_" << std::put_time(&tm, "%Y%m%d_%H%M%S")
       << "_" << GetTickCount64() << ".bmp";
    return ss.str();
}

static bool SaveBackbufferBmp(IDXGISwapChain* sc, int mode) {
    // Plain capture belongs to DXGI, not F11 initialization or visibility.
    // Keep these references local so a cold Home/CAS capture installs no UI.
    struct CaptureDevice {
        ID3D11Device* device = nullptr; ID3D11DeviceContext* context = nullptr;
        ~CaptureDevice() { if (context) context->Release(); if (device) device->Release(); }
    } capture;
    if (!sc || FAILED(sc->GetDevice(__uuidof(ID3D11Device), reinterpret_cast<void**>(&capture.device))) || !capture.device) return false;
    capture.device->GetImmediateContext(&capture.context);
    if (!capture.context) return false;
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
        if (SUCCEEDED(capture.device->CreateTexture2D(&readableDesc, nullptr, &resolveTex)) && resolveTex) {
            capture.context->ResolveSubresource(resolveTex, 0, backBuffer, 0, desc.Format);
            sourceTex = resolveTex;
        }
    }
    D3D11_TEXTURE2D_DESC staging = readableDesc;
    staging.BindFlags = 0;
    staging.MiscFlags = 0;
    staging.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    staging.Usage = D3D11_USAGE_STAGING;
    ID3D11Texture2D* copyTex = nullptr;
    if (FAILED(capture.device->CreateTexture2D(&staging, nullptr, &copyTex)) || !copyTex) { if (resolveTex) resolveTex->Release(); backBuffer->Release(); return false; }
    capture.context->CopyResource(copyTex, sourceTex);
    D3D11_MAPPED_SUBRESOURCE mapped{};
    if (FAILED(capture.context->Map(copyTex, 0, D3D11_MAP_READ, 0, &mapped))) { copyTex->Release(); if (resolveTex) resolveTex->Release(); backBuffer->Release(); return false; }

    int w = static_cast<int>(readableDesc.Width);
    int h = static_cast<int>(readableDesc.Height);
    int x = 0, y = 0, cw = w, ch = h;
    const char* modeName = "full";
    if (mode == 1) { modeName = "face"; x = w / 4; y = h / 14; cw = w / 2; ch = h / 2; }
    else if (mode == 4) { modeName = "overlay"; }
    else if (mode == 2) { modeName = "body"; x = w / 5; y = h / 20; cw = (w * 3) / 5; ch = (h * 9) / 10; }
    if (x < 0) x = 0; if (y < 0) y = 0; if (x + cw > w) cw = w - x; if (y + ch > h) ch = h - y;
    int rowBytes = ((cw * 3 + 3) / 4) * 4;
    uint32_t pixelDataSize = static_cast<uint32_t>(rowBytes * ch);
    uint32_t fileSize = 14 + 40 + pixelDataSize;
    std::string path = TimestampName(modeName);
    std::ofstream f(path, std::ios::binary);
    if (!f) { capture.context->Unmap(copyTex, 0); copyTex->Release(); if (resolveTex) resolveTex->Release(); backBuffer->Release(); return false; }
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
    capture.context->Unmap(copyTex, 0);
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
        if (mouse) {
            POINT point{static_cast<short>(LOWORD(lParam)), static_cast<short>(HIWORD(lParam))};
            if (msg == WM_MOUSEWHEEL || msg == WM_MOUSEHWHEEL) ScreenToClient(hwnd, &point);
            const uint32_t down = msg == WM_LBUTTONDOWN || msg == WM_LBUTTONDBLCLK ? 1 : msg == WM_RBUTTONDOWN || msg == WM_RBUTTONDBLCLK ? 2 : msg == WM_MBUTTONDOWN || msg == WM_MBUTTONDBLCLK ? 4 : msg == WM_XBUTTONDOWN || msg == WM_XBUTTONDBLCLK ? 8 : 0;
            const uint32_t up = msg == WM_LBUTTONUP ? 1 : msg == WM_RBUTTONUP ? 2 : msg == WM_MBUTTONUP ? 4 : msg == WM_XBUTTONUP ? 8 : 0;
            if (g_pointerGate.Owns(point.x, point.y, down, up, io.WantCaptureMouse)) return TRUE;
        }
        if (key && io.WantCaptureKeyboard) return TRUE;
    } else {
        g_pointerGate.held = 0;
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
    style.Colors[ImGuiCol_WindowBg] = ImVec4(0.045f, 0.060f, 0.080f, 0.97f);
    style.Colors[ImGuiCol_ChildBg] = ImVec4(0.064f, 0.080f, 0.105f, 0.98f);
    style.Colors[ImGuiCol_Border] = ImVec4(0.16f, 0.21f, 0.27f, 0.65f);
    style.Colors[ImGuiCol_FrameBg] = ImVec4(0.095f, 0.13f, 0.17f, 1.0f);
    style.Colors[ImGuiCol_Header] = ImVec4(0.08f, 0.31f, 0.34f, 0.80f);
    style.Colors[ImGuiCol_HeaderHovered] = ImVec4(0.10f, 0.38f, 0.40f, 0.90f);
    style.Colors[ImGuiCol_HeaderActive] = ImVec4(0.12f, 0.46f, 0.45f, 1.0f);
    style.Colors[ImGuiCol_Button] = ImVec4(0.09f, 0.24f, 0.29f, 1.0f);
    style.Colors[ImGuiCol_ButtonHovered] = ImVec4(0.11f, 0.38f, 0.41f, 1.0f);
    style.Colors[ImGuiCol_ButtonActive] = ImVec4(0.12f, 0.46f, 0.45f, 1.0f);
    style.Colors[ImGuiCol_SliderGrab] = ImVec4(0.30f, 0.83f, 0.73f, 1.0f);
    style.ItemSpacing = ImVec2(9, 8);
    style.WindowRounding = 14.0f; style.FrameRounding = 9.0f; style.ScrollbarRounding = 9.0f; style.GrabRounding = 9.0f; style.WindowPadding = ImVec2(16, 14);
    if (!ImGui_ImplWin32_Init(g_hwnd) || !ImGui_ImplDX11_Init(g_device, g_context)) {
        Debug("ImGui backend initialization failed");
        if (ImGui::GetIO().BackendPlatformUserData) ImGui_ImplWin32_Shutdown();
        ImGui::DestroyContext();
        CleanupResourceTexture();
        CleanupLibraryImages();
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
    SynchronizeOccultIcons();
    const auto icon=g_occultIconTextures.find(ActiveOccultName());
    if(icon!=g_occultIconTextures.end()) {ImGui::Image(reinterpret_cast<ImTextureID>(icon->second),ImVec2(26,26));ImGui::SameLine();}
    ImGui::SetNextItemWidth(230);
    ImGui::Combo("Selected Occult", &g_selectedOccultIndex, kOccults, IM_ARRAYSIZE(kOccults));
}

static void DrawOccultCards(const char* action1, const char* label1, const char* action2, const char* label2, const char* action3 = nullptr, const char* label3 = nullptr, const char* action4 = nullptr, const char* label4 = nullptr) {
    SynchronizeOccultIcons();
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

static void DrawQuickAutonomy() {
    ui::Json state;
    { std::lock_guard<std::mutex> lock(g_dataMutex); state = g_qolReceipt; }
    if (!state.contains("autonomy") || !state["autonomy"].is_object()) {
        if (ImGui::SmallButton("Pause autonomy")) QueueAction("qol_autonomy_pause");
        ImGui::SameLine(); if (ImGui::SmallButton("Read safety")) QueueAction("qol_status");
        return;
    }
    bool paused = state["autonomy"].value("paused_by_apex", false);
    if (ImGui::Checkbox("Pause autonomy", &paused))
        QueueAction(paused ? "qol_autonomy_pause" : "qol_autonomy_resume");
    if (ImGui::IsItemHovered()) ImGui::SetTooltip("Stops new autonomous choices for the world this session. Resume restores the exact previous setting. Running actions continue; simulation stays independent.");
    ImGui::SameLine(); if (ImGui::SmallButton("Refresh safety")) QueueAction("qol_status");
}

static void DrawOccultSafety() {
    SynchronizeOccultIcons();
    ui::Json state;
    { std::lock_guard<std::mutex> lock(g_dataMutex); state = g_qolReceipt; }
    if (!state.contains("autonomy")) return;
    ImGui::SeparatorText("Occult safety");
    bool prevent = state.value("death", ui::Json::object()).value("prevented_by_apex", false);
    if (ImGui::Checkbox("Prevent deaths (world, this session)", &prevent))
        QueueAction(prevent ? "qol_death_prevent" : "qol_death_restore");
    if (ImGui::IsItemHovered()) ImGui::SetTooltip("Uses the game's death toggle and restores its prior setting. Does not revive a Sim already dying.");
    if (state.value("sim_id", std::string()) == g_selectedSim) {
        bool sun = state.value("sunlight_blocked", false), umbrella = state.value("automatic_umbrellas_blocked", false);
        const auto icon=g_occultIconTextures.find("VAMPIRE");
        if(icon!=g_occultIconTextures.end()){ImGui::Image(reinterpret_cast<ImTextureID>(icon->second),ImVec2(24,24));ImGui::SameLine();}
        if (ImGui::Checkbox("Disable vampire sunlight burning for this Sim", &sun)) QueueAction(sun ? "qol_sunlight_on" : "qol_sunlight_off");
        if (ImGui::Checkbox("Disable automatic umbrellas for this Sim", &umbrella)) QueueAction(umbrella ? "qol_umbrella_on" : "qol_umbrella_off");
        if (ImGui::IsItemHovered()) ImGui::SetTooltip("Prevents automatic umbrella opening; native put-away events remain available. This preference and sunlight protection are saved separately per Sim and save.");
    } else ImGui::TextDisabled("Refresh safety for the selected Sim to change its protection.");
    if (state.contains("household_safety") && state["household_safety"].is_array())
        for (const auto& member : state["household_safety"])
            if (member.value("is_dying", ui::Json()) == true || member.value("is_dead", ui::Json()) == true)
                ImGui::TextColored(ImVec4(1,0.45f,0.35f,1), "Sim %s: %s", ui::Scalar(member,"sim_id").c_str(), member.value("is_dying",ui::Json())==true?"dying; saving may be blocked":"dead");
}

static void DrawApexTab() {
    DrawOccultSafety();
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

static std::string CasBankFormLabel(const std::string& lane) {
    if (lane=="1") return "Human";
    if (lane=="2") return "Alien";
    if (lane=="4") return "Vampire";
    if (lane=="8") return "Mermaid";
    if (lane=="16") return "Spellcaster";
    if (lane=="32") return "Werewolf";
    if (lane=="64") return "Fairy";
    return "Native form "+lane;
}

static std::string CasBankFieldLabel(std::string name) {
    while (!name.empty() && name.front()=='_') name.erase(name.begin());
    while (!name.empty() && name.back()=='_') name.pop_back();
    std::replace(name.begin(),name.end(),'_',' ');
    if (!name.empty() && name.front()>='a' && name.front()<='z') name.front()-='a'-'A';
    return name;
}

static void DrawCasBankHash(const char* label, const std::string& hash) {
    if (hash.empty()) return;
    ImGui::TextDisabled("%s: %.12s...",label,hash.c_str());
    if (ImGui::IsItemHovered()) { ImGui::BeginTooltip(); ImGui::TextUnformatted(hash.c_str()); ImGui::EndTooltip(); }
}

// UI intent is independent of appearance authority. The canonical game owner
// captures, compares, prepares and verifies every native appearance owner.
static void DrawCasBankTransaction() {
    ui::CasBankView state;
    {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if (!ui::BankCurrent(g_casBank,g_selectedSim,g_selectionGeneration) && !g_casBankBusy.load()) {
            g_casBank={}; g_casBank.sim=g_selectedSim; g_casBank.generation=g_selectionGeneration;
        }
        state=g_casBank;
    }
    const bool requestBlocked=g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() || g_ownerSubmissionBusy.load() ||
        g_casSubmissionBusy.load() || g_casPendingId[0];
    ImGui::PushID("all-owner-cas-review");
    ImGui::SeparatorText("CAS form review");
    ImGui::TextWrapped("Retain originals before entering CAS. Return to Live through the semantic CLI, then run the verified Live review below. The game owner runs normal ticks, pauses, and observes every native form once. Choose which returned changes to keep.");
    ImGui::TextDisabled("1 Retain  /  2 Observe  /  3 Review each changed form  /  4 Prepare  /  5 Commit");
    const auto color=state.unresolved || state.failed ? ImVec4(1.0f,0.64f,0.34f,1) : ImVec4(0.35f,0.88f,0.77f,1);
    ImGui::TextColored(color,"%s",state.phase.empty() ? "Read transaction status to begin" : state.phase.c_str());
    if (!state.sim.empty()) ImGui::TextDisabled("Exact Sim: %s",state.sim.c_str());
    if (!state.message.empty()) ImGui::TextWrapped("%s",state.message.c_str());
    if (!state.ownerId.empty()) { ImGui::TextWrapped("Owner request: %s",state.ownerId.c_str()); }
    if (!state.reviewPhase.empty()) ImGui::TextWrapped("Live review: %s",state.reviewPhase.c_str());
    if (!state.reviewNonce.empty()) ImGui::TextDisabled("Review nonce: %.12s...",state.reviewNonce.c_str());
    if (state.clockProof) ImGui::TextColored(ImVec4(0.35f,0.88f,0.77f,1),"Exact Live context / positive normal ticks / Pause verified");
    const auto clockError=ui::Scalar(state.lastReply,"clock_proof_error");
    if (!state.clockProof && !clockError.empty() && !state.phase.empty()) ImGui::TextWrapped("Live proof: %s",clockError.c_str());
    DrawCasBankHash("Transaction",state.pendingHash); DrawCasBankHash("Raw return",state.rawHash); DrawCasBankHash("Prepared plan",state.planHash);

    ImGui::BeginDisabled(requestBlocked || state.busy || state.unresolved || !ui::ExactUint64Identity(ui::Json(state.sim)));
    if (ImGui::Button("Read transaction status")) QueueAction("cas_bank_status");
    ImGui::EndDisabled();
    ImGui::SameLine(); ImGui::BeginDisabled(requestBlocked || !ui::BankCanBegin(state));
    if (ImGui::Button("Before CAS: retain all originals")) QueueAction("cas_bank_begin");
    ImGui::EndDisabled();
    if (state.phase=="captured" || (state.phase=="observed" && !state.clockProof)) {
        ImGui::BeginDisabled(requestBlocked || !ui::BankCanObserve(state));
        if (ImGui::Button("After CAS: run, pause and review every form")) QueueAction("cas_bank_observe");
        ImGui::EndDisabled();
        ImGui::TextWrapped("The Source-owned review checks the exact Sim, household, save, zone and client. Existing raw observations are reused; no serializer or appearance observation is repeated.");
    }
    if (state.reviewPhase=="ready-status")
        ImGui::TextWrapped("Source retained a verified clock proof. Read transaction status for the actual returned-owner evidence; this acknowledgement supplies no appearance inventory.");
    else if (state.phase=="settling-live" || state.reviewPhase=="settling-live")
        ImGui::TextWrapped("Live review started; this acknowledgement is not an observed return. Read transaction status after the bounded normal-speed/Pause probe finishes. No mutation is retried.");
    if (!state.currentRuntime && !state.pendingHash.empty())
        ImGui::TextWrapped("This checkpoint belongs to another runtime. Inspect the retained history and use the pinned recovery CLI; old appearance will not be replayed here.");
    if (state.unresolved) {
        ImGui::TextWrapped("The existing owner request is unresolved. Use Check retained owner above. Only its exact result may release this review; no mutation is retried.");
    }
    if (ui::BankEvidence(state.evidence)) {
        const auto changed=state.evidence["changed_lanes"].size();
        ImGui::TextColored(ImVec4(0.35f,0.88f,0.77f,1),"%u changed / %u native forms observed",static_cast<unsigned>(changed),
            static_cast<unsigned>(state.evidence["lane_change_evidence"].size()));
        ImGui::TextWrapped("A difference does not establish edit intent. Review each changed form independently; unchanged owners retain their originals.");
        for (const auto& row:state.evidence["lane_change_evidence"]) {
            const auto lane=ui::Scalar(row,"lane"), label=CasBankFormLabel(lane);
            const bool changedOwner=row["changed"].get<bool>();
            ImGui::PushID(lane.c_str());
            const bool expanded=ImGui::CollapsingHeader((label+(changedOwner ? "  /  changed" : "  /  unchanged")).c_str(),
                changedOwner ? ImGuiTreeNodeFlags_DefaultOpen : ImGuiTreeNodeFlags_None);
            if (expanded) {
                if (changedOwner) {
                    int decision=0;
                    const auto found=state.choices.find(lane);
                    if (found!=state.choices.end()) decision=found->second=="accept-returned" ? 1 : found->second=="restore-original" ? 2 : 0;
                    ImGui::BeginDisabled(requestBlocked || !ui::BankIdle(state) || state.phase!="observed" || state.prepareAttempted || state.localPrepared);
                    ImGui::SetNextItemWidth(-1);
                    if (ImGui::Combo("##form-decision",&decision,"Choose explicitly...\0Keep returned CAS changes\0Restore original appearance\0")) {
                        std::lock_guard<std::mutex> lock(g_dataMutex);
                        if (ui::BankChoiceCurrent(g_casBank,state)) {
                            if (!decision) { g_casBank.choices.erase(lane); state.choices.erase(lane); }
                            else { const auto choice=decision==1 ? "accept-returned" : "restore-original";
                                g_casBank.choices[lane]=choice; state.choices[lane]=choice; }
                            if (decision!=1) { g_casBank.hairTargets.erase(lane); state.hairTargets.erase(lane); }
                        }
                    }
                    ImGui::EndDisabled();
                    if (state.hairEnabled && ui::BankHairInventory(state)) {
                        const auto& forms=state.hairInventory["forms"];
                        const auto form=std::find_if(forms.begin(),forms.end(),[&](const auto& item){ return item["lane"]==lane; });
                        if (form!=forms.end() && ImGui::TreeNode("Keep returned hair for specific outfits")) {
                            ImGui::TextWrapped("Check only the outfits whose returned hairstyle/color you want. Unchecked outfits keep their retained original hair; other accepted CAS edits are preserved.");
                            if ((*form)["wardrobe_unchanged"]!=true)
                                ImGui::TextWrapped("Outfits were added, removed or reordered. Hair acceptance is unavailable for this wardrobe; its originals and returned edit remain retained.");
                            ImGui::BeginDisabled(requestBlocked || decision!=1 || (*form)["wardrobe_unchanged"]!=true ||
                                !ui::BankChoiceCurrent(state,state));
                            if (ImGui::Button("Restore original hair for every outfit / keep none")) {
                                std::lock_guard<std::mutex> lock(g_dataMutex);
                                if (ui::BankSetHairNone(g_casBank,state,lane)) state.hairTargets=g_casBank.hairTargets;
                            }
                            ImGui::EndDisabled();
                            if (state.hairTargets.contains(lane) && state.hairTargets[lane].empty())
                                ImGui::TextDisabled("Explicit choice: keep no returned hairstyles; retain other accepted edits.");
                            const auto& outfits=(*form)["outfits"];
                            ImGui::Text("%u native outfits; no changes selected automatically",static_cast<unsigned>(outfits.size()));
                            if (ImGui::BeginChild("##hair-outfits",ImVec2(0,200),true)) {
                                ImGuiListClipper clipper; clipper.Begin(static_cast<int>(outfits.size()));
                                while (clipper.Step()) for (int index=clipper.DisplayStart;index<clipper.DisplayEnd;++index) {
                                    const auto& outfit=outfits[static_cast<size_t>(index)];
                                    const auto uid=ui::Scalar(outfit,"outfit_id");
                                    const auto outfitLabel=ui::Scalar(outfit,"category_name")+" "+std::to_string(outfit["ordinal"].get<uint32_t>()+1)+
                                        (outfit["hair_changed"]==true ? "  /  changed" : "  /  unchanged")+"##"+uid;
                                    bool selected=ui::BankHairSelected(state,lane,outfit);
                                    const bool selectable=decision==1 && outfit["selectable"]==true && !requestBlocked &&
                                        ui::BankIdle(state) && state.phase=="observed" && !state.prepareAttempted && !state.localPrepared;
                                    ImGui::BeginDisabled(!selectable);
                                    if (ImGui::Checkbox(outfitLabel.c_str(),&selected)) {
                                        std::lock_guard<std::mutex> lock(g_dataMutex);
                                        if (ui::BankSetHairTarget(g_casBank,state,lane,outfit,selected)) state.hairTargets=g_casBank.hairTargets;
                                    }
                                    ImGui::EndDisabled();
                                    if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled))
                                        ImGui::SetTooltip("Original outfit UID: %s\nReturned outfit UID: %s\nCategory: %s / number: %u\nChecked: keep returned hair. Unchecked: retain original hair.",
                                            ui::Scalar(outfit,"original_outfit_id").c_str(),ui::Scalar(outfit,"returned_outfit_id").c_str(),
                                            ui::Scalar(outfit,"category").c_str(),outfit["ordinal"].get<uint32_t>()+1);
                                }
                            }
                            ImGui::EndChild(); ImGui::TreePop();
                        }
                    }
                    const auto& before=row["before_fingerprint"]["field_sha256"], &after=row["returned_fingerprint"]["field_sha256"];
                    for (const auto& field:row["changed_fields"]) {
                        const auto name=field.get<std::string>();
                        ImGui::TextWrapped("%s",CasBankFieldLabel(name).c_str());
                        const auto oldHash=before.contains(name) ? before[name].get<std::string>() : "Unavailable before";
                        const auto newHash=after.contains(name) ? after[name].get<std::string>() : "Unavailable after";
                        DrawCasBankHash("Before",oldHash); DrawCasBankHash("Returned",newHash);
                    }
                }
                if (ImGui::TreeNode("All before / returned field fingerprints")) {
                    // Preserve returned future fields as well as known ones.
                    std::set<std::string> fields;
                    for (const auto* side:{"before_fingerprint","returned_fingerprint"})
                        for (auto it=row[side]["field_sha256"].begin();it!=row[side]["field_sha256"].end();++it) fields.insert(it.key());
                    for (const auto& name:fields) {
                        ImGui::TextWrapped("%s",name.c_str());
                        for (const auto* side:{"before_fingerprint","returned_fingerprint"}) {
                            const auto& fieldHashes=row[side]["field_sha256"];
                            const auto hash=fieldHashes.contains(name) ? fieldHashes[name].get<std::string>() : "Unavailable";
                            DrawCasBankHash(side==std::string("before_fingerprint") ? "Before" : "Returned",hash);
                        }
                    }
                    ImGui::TreePop();
                }
            }
            ImGui::PopID();
        }
        if (state.hairEnabled)
            ImGui::TextWrapped("Separate hair is enabled. For each kept form, expand its outfit picker and explicitly check which returned hairstyles/colors to keep. All other outfit hair stays original. Changed hair with no selected target keeps preparation disabled.");
        if (!state.hairError.empty()) ImGui::TextWrapped("Hair inventory unavailable: %s",state.hairError.c_str());
        if (!state.clockProof) ImGui::TextWrapped("Preparation and commit stay disabled until canonical status verifies the current Live clock proof and Pause.");
        ImGui::BeginDisabled(requestBlocked || !ui::BankCanPrepare(state));
        if (ImGui::Button("Prepare the explicit choices")) QueueAction("cas_bank_prepare");
        ImGui::EndDisabled();
        ImGui::SameLine(); ImGui::BeginDisabled(requestBlocked || !ui::BankCanCommit(state));
        if (ImGui::Button("Commit this exact reviewed plan once")) QueueAction("cas_bank_commit");
        ImGui::EndDisabled();
    } else if (state.phase=="observed" || state.phase=="planned") {
        ImGui::TextWrapped("Complete changed-owner evidence is unavailable. Mutations stay disabled; inspect the exact owner result.");
    }
    if (state.phase=="planned" && !state.localPrepared)
        ImGui::TextWrapped("This plan was prepared outside this F11 review. Complete it through the CLI that retained its exact request and plan hash.");
    if (state.phase=="completed")
        ImGui::TextWrapped("Native appearance owners and the form bank are committed. A certified game save and reload are still required to prove durability.");
    if (!state.lastReply.empty() && ImGui::TreeNode("Complete transaction receipt / raw review metadata")) {
        const auto receipt=state.lastReply.dump(2); ImGui::TextWrapped("%s",receipt.c_str());
        if (ImGui::SmallButton("Copy receipt")) ImGui::SetClipboardText(receipt.c_str());
        ImGui::TreePop();
    }
    if (!state.lastFailure.empty() && ImGui::TreeNode("Retained failure receipt")) {
        const auto failure=state.lastFailure.dump(2); ImGui::TextWrapped("%s",failure.c_str());
        if (ImGui::SmallButton("Copy failure")) ImGui::SetClipboardText(failure.c_str());
        ImGui::TreePop();
    }
    ImGui::PopID();
}

static void DrawFormsTab() {
    DrawCasBankTransaction();
    ImGui::Separator();
    DrawOccultSelector();
    ImGui::SameLine(); if (ImGui::Button("Switch Selected")) QueueAction("switch", ActiveOccultName());
    ImGui::SameLine(); if (ImGui::Button("Commit Current -> Selected Occult")) QueueAction("commit_current_to_occult", ActiveOccultName(), g_formLabel);
    ImGui::TextWrapped("Review CAS changes above before using direct form commands. The separate copy command applies the current visible appearance to one selected occult; it does not complete a CAS transaction.");
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

static void QueueStudioAction(const char* action, const char* occult = nullptr, const char* value = nullptr) {
    const auto forms = g_studioData.find("form_inventory");
    if (forms != g_studioData.end() && !forms->empty()) {
        g_studioFormIndex = std::clamp(g_studioFormIndex, 0, static_cast<int>(forms->size()) - 1);
        const auto& form = (*forms)[static_cast<size_t>(g_studioFormIndex)];
        const ui::Json envelope = {{"form", form["flags"]}, {"value", value && value[0] ? ui::Json(value) : ui::Json(nullptr)}};
        const auto payload = envelope.dump(); QueueAction(action, occult, payload.c_str());
    } else QueueAction(action, occult, value);
}

static void UpdateStudioData(const std::string& reply) {
    if (reply == g_studioLastReply) return;
    g_studioLastReply = reply;
    const auto& parsed = ui::ReadObject(reply);
    if (!ui::StudioDocument(parsed)) return;
    if(!ui::Scalar(parsed,"pending_preview").empty())g_trayPreviewActive=false;
    if(parsed.contains("appearance_clipboard")){
        const auto& clip=parsed["appearance_clipboard"];
        if(resource::Hex(ui::Scalar(clip,"id"),32)&&resource::Hash(clip,"sha256")){
            g_appearanceClipboard=clip;g_clipboardFields=parsed.value("clipboard_fields",ui::Json::array());
            g_clipboardOutfits=parsed.value("clipboard_outfits",ui::Json::array());g_pasteSourceOutfit=0;
        }
    }
    if (ui::StudioMetadataChanged(parsed, g_studioData))
        g_resourceInspections.clear();
    if (ui::Scalar(parsed, "history_lane") != ui::Scalar(g_studioData, "history_lane")) {
        g_studioData = ui::Json::object();
        g_historyId[0] = '\0';
        g_studioOutfitIndex = 0; g_studioPartIndex = 0;
    }
    for (auto item = parsed.begin(); item != parsed.end(); ++item) g_studioData[item.key()] = item.value();
    if (parsed.contains("part_editor")) {
        const auto& editor = parsed["part_editor"];
        if (resource::Hash(editor, "resource_sha256") && resource::Tgi(ui::Scalar(editor, "resource_tgi")) &&
            ui::Scalar(editor, "appearance_sha256") == ui::Scalar(g_studioData, "appearance_sha256")) {
            const auto key = ui::Scalar(g_studioData, "history_lane") + ":" + ui::Scalar(g_studioData, "appearance_sha256") + ":" +
                ui::Scalar(g_studioData, "inspected_form_flags") + ":" + ui::Scalar(editor, "target") + ":" + ui::Scalar(editor, "cas_part_id");
            if (g_resourceInspections.size() >= 1024) g_resourceInspections.clear();
            g_resourceInspections[key] = editor;
        }
    }
    // Successful Apply/Cancel replies include null; an old token must vanish.
    if (parsed.contains("pending_preview"))
        strncpy_s(g_previewId, ui::Scalar(parsed, "pending_preview").c_str(), _TRUNCATE);
    // Refresh the inventory explicitly after a write; never present pre-write
    // part metadata as current. History nodes remain useful after the change.
    const auto message = ui::Scalar(parsed, "message");
    if (message.find("Appearance write matches") == 0) {
        g_studioData.erase("outfit_inventory"); g_studioData.erase("color_editor"); g_studioData.erase("part_editor"); g_colorEditorKey.clear();
        QueueStudioAction("studio_status");
    }
    if (parsed.contains("form_inventory") && (!g_studioData.contains("form_selection_initialized"))) {
        // A new history lane may be an explicitly inspected inactive form.
        // Preserve that owner instead of snapping the selector back to Live.
        for (size_t i = 0; i < parsed["form_inventory"].size(); ++i)
            if (ui::Scalar(parsed["form_inventory"][i], "flags") == ui::Scalar(parsed, "inspected_form_flags"))
                g_studioFormIndex = static_cast<int>(i);
        g_studioData["form_selection_initialized"] = true;
    }
    if (parsed.contains("current_outfit_index") && parsed["current_outfit_index"].is_number_unsigned() &&
        (!g_studioData.contains("selection_initialized") || !g_studioData["selection_initialized"].get<bool>())) {
        g_studioOutfitIndex = parsed["current_outfit_index"].get<int>();
        g_studioData["selection_initialized"] = true;
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
    ImGui::SeparatorText("Part color / HSB shifts");
    const bool pending = !ui::Scalar(g_studioData, "pending_preview").empty();
    ImGui::BeginDisabled(pending);
    ImGui::Checkbox("Apply edits immediately", &g_livePartColor);
    ImGui::EndDisabled();
    bool released = false;
    ImGui::BeginDisabled(pending || g_ownerBlocked.load() || g_ownerSubmissionBusy.load() || g_ownerNativeDeliveryBusy.load());
    if (g_itemNameMode == 2) ImGui::TextUnformatted(ui::Scalar(editor, "part_name").c_str());
    color::Bounds bounds[4]; bool editable[4]{}; double lows[4]{}, highs[4]{};
    float wheel[4]{0.5f, 0.5f, 0.5f, 1.0f};
    for (unsigned index = 0; index < 4; ++index) {
        editable[index] = color::ReadBounds(editor, index, bounds[index]) && color::EditRange(bounds[index], lows[index], highs[index]);
        if (index < 3) wheel[index] = color::WheelPosition(bounds[index], g_colorValues[index]);
    }
    const float previousWheel[3]{wheel[0], wheel[1], wheel[2]};
    ImGui::TextDisabled("Shift wheel / selected CASP ranges");
    ImGui::SetNextItemWidth(std::min(250.0f, ImGui::GetContentRegionAvail().x));
    ImGui::BeginDisabled(!editable[0] && !editable[1] && !editable[2]);
    if (ImGui::ColorPicker4("##part-shift-wheel", wheel, ImGuiColorEditFlags_PickerHueWheel |
            ImGuiColorEditFlags_InputHSV | ImGuiColorEditFlags_DisplayHSV | ImGuiColorEditFlags_NoInputs |
            ImGuiColorEditFlags_NoAlpha | ImGuiColorEditFlags_NoSidePreview | ImGuiColorEditFlags_NoSmallPreview |
            ImGuiColorEditFlags_NoOptions)) {
        for (unsigned index = 0; index < 3; ++index) {
            double value;
            if (wheel[index] != previousWheel[index] && editable[index] && color::WheelValue(bounds[index], wheel[index], value)) {
                g_colorValues[index] = static_cast<float>(value); g_colorChanged[index] = true;
            }
        }
    }
    released = ImGui::IsItemDeactivatedAfterEdit();
    ImGui::EndDisabled();
    ImGui::TextWrapped("The wheel selects hue, saturation and brightness shifts within this part's ranges. Its colors are a control guide; the texture determines the final appearance.");
    const char* labels[]{"Hue shift", "Saturation shift", "Brightness shift", "Opacity"};
    bool changes = false;
    for (unsigned index = 0; index < 4; ++index) {
        const auto& channel = editor["channels"][names[index]];
        ImGui::PushID(static_cast<int>(index));
        ImGui::BeginDisabled(!editable[index]);
        const float low = editable[index] ? static_cast<float>(lows[index]) : g_colorValues[index];
        const float high = editable[index] ? static_cast<float>(highs[index]) : low;
        float controlValue = editable[index] ? std::clamp(g_colorValues[index], low, high) : g_colorValues[index];
        if (ImGui::SliderFloat(labels[index], &controlValue, low, high, "%.6f", ImGuiSliderFlags_AlwaysClamp)) {
            double value; int32_t lane;
            if (color::Quantize(bounds[index], controlValue, value, lane)) {
                g_colorValues[index] = static_cast<float>(value); g_colorChanged[index] = true;
            }
        }
        released = ImGui::IsItemDeactivatedAfterEdit() || released;
        ImGui::SameLine();
        if (ImGui::SmallButton("Reset")) {
            double value; int32_t lane;
            if (color::Quantize(bounds[index], index == 3 ? 1.0 : 0.0, value, lane)) {
                g_colorValues[index] = static_cast<float>(value); g_colorChanged[index] = true;
                released = true;
            }
        }
        ImGui::EndDisabled();
        ImGui::TextDisabled("%.6f | CASP %.6g to %.6g | CAS increment %.6g%s", g_colorValues[index],
            bounds[index].low, bounds[index].high, channel["step"].get<double>(), g_colorChanged[index] ? " | edited" : "");
        if (!editable[index]) ImGui::TextDisabled("This channel has no enabled representable editing range.");
        else if (g_colorValues[index] < low || g_colorValues[index] > high)
            ImGui::TextDisabled("Current raw value is outside the editing range; retained until explicitly changed.");
        changes = changes || g_colorChanged[index];
        ImGui::PopID();
    }
    ui::Json edits; std::string rawPreview;
    const bool validPreview = changes && color::Prepare(editor, g_colorValues, g_colorChanged, edits, rawPreview);
    ImGui::TextDisabled("Q14 resolution: 1 / 16384 (%.8f)", 1.0 / color::kQ14Scale);
    if (validPreview) ImGui::TextDisabled("Draft packed shift: %s", rawPreview.c_str());
    ImGui::BeginDisabled(!validPreview);
    const bool clicked = ImGui::Button(g_livePartColor ? "Apply part color now" : "Prepare part color preview");
    if (validPreview && (clicked || (g_livePartColor && released))) {
        const ui::Json request = {{"target", target}, {"lane", ui::Scalar(g_studioData, "history_lane")},
            {"cas_part_id", editor["cas_part_id"]}, {"color_hex", editor["color_hex"]},
            {"appearance_sha256", editor["appearance_sha256"]}, {"resource_sha256", editor["resource_sha256"]}, {"edits", edits}};
        const auto payload = request.dump(); QueueStudioAction(g_livePartColor ? "studio_color_live" : "studio_color_edit", nullptr, payload.c_str());
    }
    ImGui::EndDisabled();
    ImGui::TextWrapped("Live mode commits one undoable change when you release the wheel or slider. Unpause to let the game update visuals. Disable live mode to use Preview and Apply. Only edited channels change; the texture determines compatibility.");
    ImGui::EndDisabled();
}

static std::string OutfitCategory(const ui::Json& outfit) {
    const auto name = ui::Scalar(outfit, "category_name");
    return name.empty() ? "Category " + ui::Scalar(outfit, "category") : name;
}

static const ui::Json& ViewedStudioOutfits() {
    const auto forms = g_studioData.find("form_inventory");
    if (forms != g_studioData.end() && !forms->empty()) {
        g_studioFormIndex = std::clamp(g_studioFormIndex, 0, static_cast<int>(forms->size()) - 1);
        return (*forms)[static_cast<size_t>(g_studioFormIndex)]["outfit_inventory"];
    }
    static const auto empty = ui::Json::array();
    const auto outfits = g_studioData.find("outfit_inventory");
    return outfits == g_studioData.end() ? empty : *outfits;
}
static const ui::Json& ViewedPreviewOutfits() {
    const auto pending=g_studioData.find("preview_outfit_inventory");
    if(!ui::Scalar(g_studioData,"pending_preview").empty()&&pending!=g_studioData.end()&&pending->is_array())return *pending;
    return ViewedStudioOutfits();
}
static bool ViewedFormActive() {
    const auto forms = g_studioData.find("form_inventory");
    return forms == g_studioData.end() || forms->empty() || (*forms)[static_cast<size_t>(g_studioFormIndex)]["current"].get<bool>();
}
static const ui::Json* SelectedStudioPart() {
    const auto& outfits = ViewedStudioOutfits();
    if (outfits.empty()) return nullptr;
    g_studioOutfitIndex = std::clamp(g_studioOutfitIndex, 0, static_cast<int>(outfits.size()) - 1);
    const auto& parts = outfits[static_cast<size_t>(g_studioOutfitIndex)]["parts"];
    if (parts.empty()) return nullptr;
    g_studioPartIndex = std::clamp(g_studioPartIndex, 0, static_cast<int>(parts.size()) - 1);
    return &parts[static_cast<size_t>(g_studioPartIndex)];
}

static ui::Json ResourcePartEditor(const ui::Json& part) {
    const auto forms = g_studioData.find("form_inventory");
    if (forms != g_studioData.end() && !forms->empty() &&
        ui::Scalar((*forms)[static_cast<size_t>(g_studioFormIndex)], "flags") != ui::Scalar(g_studioData, "inspected_form_flags"))
        return ui::Json::object();
    const auto key = ui::Scalar(g_studioData, "history_lane") + ":" + ui::Scalar(g_studioData, "appearance_sha256") + ":" +
        ui::Scalar(g_studioData, "inspected_form_flags") + ":" + ui::Scalar(part, "target") + ":" + ui::Scalar(part, "cas_part_id");
    const auto cached = g_resourceInspections.find(key);
    return cached == g_resourceInspections.end() ? ui::Json::object() : cached->second;
}

static resource::ItemName StudioPartName(const ui::Json& part, const ui::Json& editor,
                                       const ui::Json& catalog, bool catalogValid) {
    const auto mode = static_cast<resource::NameMode>(std::clamp(g_itemNameMode, 0, 2));
    auto row = catalogValid ? resource::EquippedFromValidatedCatalog(catalog, part, editor,
        ui::Scalar(g_studioData, "appearance_sha256")) : ui::Json::object();
    auto name = resource::Name(row, mode);
    if (name.text.empty() && mode != resource::NameMode::Package) {
        name.text = ui::Scalar(editor, "part_name");
        if (!name.text.empty()) name.source = "casp-internal-name / native bytes";
    }
    return name;
}

static void RefreshStudioItems() {
    const auto& outfits = ViewedStudioOutfits();
    if (outfits.empty() || !g_studioData.contains("runtime_pid") ||
        !g_studioData.contains("inspected_form_flags")) return;
    g_studioOutfitIndex = std::clamp(g_studioOutfitIndex, 0, static_cast<int>(outfits.size()) - 1);
    const auto& outfit = outfits[static_cast<size_t>(g_studioOutfitIndex)];
    const auto forms = g_studioData.find("form_inventory");
    if (forms != g_studioData.end() && !forms->empty() &&
        (*forms)[static_cast<size_t>(g_studioFormIndex)]["flags"] != g_studioData["inspected_form_flags"]) return;
    const int form = g_studioData["inspected_form_flags"].get<int>();
    ui::Json request = {{"lane", g_studioData["history_lane"]}, {"appearance_sha256", g_studioData["appearance_sha256"]},
        {"runtime_pid", g_studioData["runtime_pid"]}, {"cursor", 0}, {"limit", 8}, {"outfit_index", outfit["index"]}};
    if (!ui::StudioItemRequest(request)) return;
    const auto context = request.dump();
    if (context != g_studioItemsContext) {
        g_studioItemsContext = context; g_studioItemsCursor = 0; g_studioItemsComplete = false;
        g_studioItemRows = ui::Json::object(); g_studioItemsMessage.clear();
    }
    std::string reply; uint64_t receipt;
    { std::lock_guard<std::mutex> lock(g_dataMutex); receipt = g_studioItemsReceipt; reply = g_studioItemsReply; }
    const auto now = GetTickCount64();
    if (receipt != g_studioItemsSeen) {
        g_studioItemsSeen = receipt; g_studioItemsBusy = false;
        const auto page = ui::ParseObject(reply);
        auto currentRequest = request; currentRequest["cursor"] = g_studioItemsCursor;
        if (g_studioItemRequest == currentRequest && ui::StudioItemPage(page, currentRequest, outfit, form)) {
            for (const auto& item : page["items"]) {
                const auto key = ui::Scalar(page, "history_lane") + ":" + ui::Scalar(page, "appearance_sha256") + ":" +
                    std::to_string(form) + ":" + ui::Scalar(item, "target") + ":" + ui::Scalar(item, "cas_part_id");
                g_studioItemRows[ui::Scalar(item, "target")] = item;
                if (item["part_editor"].is_object()) {
                    if (g_resourceInspections.size() >= 1024) g_resourceInspections.clear();
                    g_resourceInspections[key] = item["part_editor"];
                }
            }
            g_studioItemsComplete = page["complete"].get<bool>();
            g_studioItemsCursor += page["items"].size();
            g_studioItemsMessage = g_studioItemsComplete ? "All equipped rows inspected." : "Reading equipped item names...";
            g_studioItemsNextMs = now + 300;
        } else if (g_studioItemRequest != currentRequest) {
            g_studioItemsNextMs = now; // A prior outfit's response cannot stop the newly selected owner.
        } else {
            g_studioItemsMessage = "Item metadata changed or is unavailable. Refresh this Sim to retry.";
            g_studioItemsComplete = true; // Explicit refresh/context change, never an automatic retry loop.
        }
    }
    if (!g_studioItemsComplete && !g_studioItemsBusy.load() && now >= g_studioItemsNextMs) {
        request["cursor"] = g_studioItemsCursor;
        const ui::Json envelope = {{"form", form}, {"value", request.dump()}};
        const auto value = envelope.dump(); const auto path = BuildCommandPath("studio_items", nullptr, value.c_str());
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if (g_commands.empty() && !g_casSubmissionBusy.load() && !g_ownerBlocked.load() && !g_ownerNativeDeliveryBusy.load() && !g_casBankBusy.load()) {
            QueuedCommand command{path, g_selectionGeneration}; command.automaticStudioItems = true; command.sim = g_selectedSim;
            g_commands.push_back(std::move(command)); g_studioItemRequest = request; g_studioItemsBusy = true;
        }
    }
}

static void DrawResourcePart(const ui::Json& part, const ui::Json& editor) {
    const auto viewKey = ui::Scalar(g_studioData, "history_lane") + ":" + ui::Scalar(g_studioData, "appearance_sha256") + ":" +
        ui::Scalar(g_studioData, "inspected_form_flags") + ":" + ui::Scalar(part, "target") + ":" + ui::Scalar(part, "cas_part_id");
    if (g_resourceViewKey != viewKey) { g_resourceViewKey = viewKey; ++g_resourceSelectionSerial; g_resourceRequestedImage.clear(); }
    if (!g_resourceCatalogAttempted) { g_resourceCatalogAttempted = true; QueueResource(1); }
    ui::Json catalog; std::string catalogStatus;
    { std::lock_guard<std::mutex> lock(g_dataMutex); catalog = g_resourceCatalog; catalogStatus = g_resourceCatalogStatus; }
    const auto row = resource::Equipped(catalog, part, editor, ui::Scalar(g_studioData, "appearance_sha256"));
    ImGui::SeparatorText("Item / source package");
    ImGui::BeginDisabled(g_resourceCatalogBusy.load());
    if (ImGui::Button("Refresh resource cache")) QueueResource(1);
    ImGui::EndDisabled();
    if (row.empty()) {
        const auto internalName = ui::Scalar(editor, "part_name");
        if (g_itemNameMode != 1 && !internalName.empty()) { ImGui::TextWrapped("%s", internalName.c_str()); ImGui::TextDisabled("CASP internal name / effective native bytes"); }
        else if (g_itemNameMode == 1) ImGui::TextDisabled("Containing package filename unavailable without an exact cache match.");
        else ImGui::TextDisabled("Item name unavailable; inspect the exact equipped part.");
        ImGui::TextWrapped("Thumbnail unavailable: no pinned cache record matches this exact native resource TGI, body type and effective hash.");
        ImGui::TextWrapped("%s", catalogStatus.c_str());
        ImGui::BeginDisabled(); ImGui::Button("Open containing package in Sims 4 Studio"); ImGui::EndDisabled();
        return;
    }
    const auto name = resource::Name(row, static_cast<resource::NameMode>(std::clamp(g_itemNameMode, 0, 2)));
    if (!name.text.empty()) ImGui::TextWrapped("%s", name.text.c_str());
    else ImGui::TextDisabled("Item name unavailable in the verified package.");
    ImGui::TextDisabled("%s | %s", name.source.c_str(), ui::Scalar(row["provenance"], "origin").c_str());
    ImGui::TextDisabled("%s", ui::Scalar(row, "resource_tgi").c_str());
    const auto key = ResourceKey(row); const auto& thumbnail = row["thumbnail"];
    if (ui::Scalar(thumbnail, "status") == "resolved") {
        if (g_resourceRequestedImage != key && !g_resourceImageBusy.load() && QueueResource(2, row)) g_resourceRequestedImage = key;
        std::string imageStatus; unsigned width = 0, height = 0;
        {
            std::lock_guard<std::mutex> lock(g_dataMutex);
            if (g_resourceImageKey == key) { imageStatus = g_resourceImageStatus; width = g_resourcePixels.width; height = g_resourcePixels.height; }
        }
        if (ResourceTexture(key)) {
            const float scale = std::min(1.0f, 180.0f / static_cast<float>(std::max(width, height)));
            ImGui::Image(reinterpret_cast<ImTextureID>(g_resourceTexture), ImVec2(width * scale, height * scale));
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("Actual cached CAS thumbnail\nPNG SHA-256 %s\nResource %s", ui::Scalar(thumbnail, "sha256").c_str(), ui::Scalar(row, "resource_id").c_str());
        } else ImGui::TextDisabled("%s", g_resourceImageBusy.load() ? "Loading the pinned thumbnail..." : "Thumbnail not decoded/uploaded.");
        if (!imageStatus.empty()) ImGui::TextWrapped("%s", imageStatus.c_str());
    } else ImGui::TextWrapped("Thumbnail unavailable: %s", ui::Scalar(thumbnail, "reason").c_str());
    const bool ready = ui::Scalar(row["studio_open"], "status") == "ready";
    ImGui::BeginDisabled(!ready || g_resourceOpenBusy.load());
    if (ImGui::Button("Open containing package in Sims 4 Studio")) QueueResource(3, row);
    ImGui::EndDisabled();
    if (!ready) ImGui::TextWrapped("Studio unavailable: %s", ui::Scalar(row["studio_open"], "reason").c_str());
    else ImGui::TextWrapped("Opens an independent verified package copy. Automatic selection of this individual CASP inside Studio is unsupported.");
    std::string openStatus;
    { std::lock_guard<std::mutex> lock(g_dataMutex); if (g_resourceOpenKey == key) openStatus = g_resourceOpenStatus; }
    if (!openStatus.empty()) ImGui::TextWrapped("%s", openStatus.c_str());
    if (ImGui::TreeNode("Resource provenance")) { const auto raw = row.dump(2); ImGui::TextWrapped("%s", raw.c_str()); ImGui::TreePop(); }
}
static void DrawEquippedList() {
    ImGui::TextColored(ImVec4(0.35f, 0.88f, 0.77f, 1), "CAS / ALL CATEGORIES");
    const auto forms = g_studioData.find("form_inventory");
    if (forms != g_studioData.end() && !forms->empty()) {
        g_studioFormIndex = std::clamp(g_studioFormIndex, 0, static_cast<int>(forms->size()) - 1);
        const auto formName = ui::Scalar((*forms)[static_cast<size_t>(g_studioFormIndex)], "name");
        ImGui::SetNextItemWidth(-1);
        if (ImGui::BeginCombo("##form", formName.c_str())) {
            for (size_t i = 0; i < forms->size(); ++i) {
                const auto label = ui::Scalar((*forms)[i], "name") + ((*forms)[i]["current"].get<bool>() ? " / LIVE" : "");
                if (ImGui::Selectable(label.c_str(), g_studioFormIndex == static_cast<int>(i))) {
                    g_studioFormIndex = static_cast<int>(i); g_studioOutfitIndex = 0; g_studioPartIndex = 0; QueueStudioAction("studio_status");
                }
            }
            ImGui::EndCombo();
        }
        ImGui::TextDisabled("%s", ViewedFormActive() ? "Active form / editable" : "Stored form / direct editing");
    }
    const auto& outfits = ViewedStudioOutfits();
    if (outfits.empty()) { ImGui::TextWrapped("Inspect this Sim to read every form/outfit."); return; }
    g_studioOutfitIndex = std::clamp(g_studioOutfitIndex, 0, static_cast<int>(outfits.size()) - 1);
    const auto& outfit = outfits[static_cast<size_t>(g_studioOutfitIndex)];
    RefreshStudioItems();
    const auto label = OutfitCategory(outfit) + " / outfit " + ui::Scalar(outfit, "number");
    ImGui::SetNextItemWidth(-1);
    if (ImGui::BeginCombo("##wardrobe", label.c_str())) {
        for (size_t i = 0; i < outfits.size(); ++i) {
            const auto name = OutfitCategory(outfits[i]) + " / outfit " + ui::Scalar(outfits[i], "number");
            if (ImGui::Selectable(name.c_str(), g_studioOutfitIndex == static_cast<int>(i))) {
                g_studioOutfitIndex = static_cast<int>(i); g_studioPartIndex = 0;
            }
        }
        ImGui::EndCombo();
    }
    ImGui::SetNextItemWidth(-1); ImGui::InputTextWithHint("##parts-search", "Search skin details, jewelry...", g_partSearch, sizeof(g_partSearch));
    ImGui::SetNextItemWidth(-1); ImGui::Combo("Item names", &g_itemNameMode, "Preferred / friendly\0Package filename\0Internal code\0");
    if (!g_resourceCatalogAttempted) { g_resourceCatalogAttempted = true; QueueResource(1); }
    ui::Json resourceCatalog;
    { std::lock_guard<std::mutex> lock(g_dataMutex); resourceCatalog = g_resourceCatalog; }
    const bool resourceCatalogValid = resource::Catalog(resourceCatalog);
    ImGui::Checkbox("Show unequipped categories", &g_showEmptySlots);
    ImGui::SetNextItemWidth(-1); ImGui::Combo("##sort", &g_equippedSort, "Equipped first\0Category / alphabetical\0Serialized row order\0");
    const auto catalog = g_studioData.find("category_catalog");
    std::vector<std::string> groups{"All categories"};
    if (catalog != g_studioData.end()) for (const auto& category : *catalog) {
        const auto group = ui::Scalar(category, "group");
        if (std::find(groups.begin(), groups.end(), group) == groups.end()) groups.push_back(group);
    }
    g_casGroupIndex = std::clamp(g_casGroupIndex, 0, static_cast<int>(groups.size()) - 1);
    ImGui::SetNextItemWidth(-1);
    if (ImGui::BeginCombo("##cas-group", groups[static_cast<size_t>(g_casGroupIndex)].c_str())) {
        for (size_t i = 0; i < groups.size(); ++i) if (ImGui::Selectable(groups[i].c_str(), g_casGroupIndex == static_cast<int>(i))) g_casGroupIndex = static_cast<int>(i);
        ImGui::EndCombo();
    }
    const auto& parts = outfits[static_cast<size_t>(g_studioOutfitIndex)]["parts"];
    struct Row { int index; std::string label, group; };
    std::vector<Row> rows;
    auto categoryFor = [&](const ui::Json& part) -> const ui::Json* {
        if (catalog != g_studioData.end()) for (const auto& category : *catalog)
            if (ui::Scalar(category, "body_type") == ui::Scalar(part, "body_type")) return &category;
        return nullptr;
    };
    for (size_t i = 0; i < parts.size(); ++i) {
        const auto* category = categoryFor(parts[i]);
        const auto name = StudioPartName(parts[i], ResourcePartEditor(parts[i]), resourceCatalog, resourceCatalogValid);
        const auto fallback = g_itemNameMode == 1 ? "Package name unavailable" : "Name unavailable";
        const bool codeFallback = g_itemNameMode == 0 && name.source.find("casp-internal-name") == 0;
        rows.push_back({static_cast<int>(i), (name.text.empty() ? fallback : name.text) +
            (codeFallback ? " (internal code)" : "") + " / " + ui::Scalar(parts[i], "label"),
            category ? ui::Scalar(*category, "group") : "Runtime discovered"});
    }
    if (g_showEmptySlots && catalog != g_studioData.end()) for (const auto& category : *catalog) {
        bool equipped = false;
        for (const auto& part : parts) if (ui::Scalar(part, "body_type") == ui::Scalar(category, "body_type")) equipped = true;
        if (!equipped) rows.push_back({-1, ui::Scalar(category, "label"), ui::Scalar(category, "group")});
    }
    if (g_equippedSort != 2) std::stable_sort(rows.begin(), rows.end(), [](const Row& a, const Row& b) {
        if (g_equippedSort == 0 && (a.index >= 0) != (b.index >= 0)) return a.index >= 0;
        return a.group == b.group ? a.label < b.label : a.group < b.group;
    });
    ImGui::TextDisabled("%u equipped / %u categories", static_cast<unsigned>(parts.size()), static_cast<unsigned>(catalog == g_studioData.end() ? 0 : catalog->size()));
    if (!g_studioItemsMessage.empty()) ImGui::TextWrapped("%s", g_studioItemsMessage.c_str());
    ImGui::BeginChild("equipped-rows", ImVec2(0, 0), false);
    for (size_t i = 0; i < rows.size(); ++i) {
        const auto& row = rows[i];
        if (g_casGroupIndex && row.group != groups[static_cast<size_t>(g_casGroupIndex)]) continue;
        if (!TextContainsNoCase(row.label.c_str(), g_partSearch) && !TextContainsNoCase(row.group.c_str(), g_partSearch)) continue;
        ImGui::PushID(static_cast<int>(i));
        const auto label = row.label + (row.index < 0 ? " / empty" : "");
        if (row.index < 0) ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.44f, 0.51f, 0.60f, 1));
        if (ImGui::Selectable(label.c_str(), row.index >= 0 && g_studioPartIndex == row.index, 0, ImVec2(0, 30)) && row.index >= 0) {
            g_studioPartIndex = row.index; g_partReplacementIndex = 0; g_activeTab = 12;
            const auto target = ui::Scalar(parts[static_cast<size_t>(row.index)], "target"); QueueStudioAction("studio_part_inspect", nullptr, target.c_str());
        }
        if (row.index < 0) ImGui::PopStyleColor();
        if (ImGui::IsItemHovered()) {
            std::string reason;
            if (row.index >= 0) {
                const auto target = ui::Scalar(parts[static_cast<size_t>(row.index)], "target");
                const auto item = g_studioItemRows.find(target);
                if (item != g_studioItemRows.end()) reason = ui::Scalar(*item, "reason");
            }
            ImGui::SetTooltip("%s\n%s%s%s", row.group.c_str(), row.index < 0 ? "No part equipped in this outfit. Category is tracked without synthesizing a part." : "Exact equipped row / this form and outfit", reason.empty() ? "" : "\n", reason.c_str());
        }
        ImGui::PopID();
    }
    ImGui::EndChild();
}

static void DrawStudioParts() {
    const auto& outfits=ViewedStudioOutfits();
    if(!outfits.empty()) {
        const auto& parts=outfits[size_t(std::clamp(g_studioOutfitIndex,0,int(outfits.size())-1))]["parts"];
        const auto* current=SelectedStudioPart();
        ImGui::SetNextItemWidth(-1);
        if(ImGui::BeginCombo("Equipped item",current?ui::Scalar(*current,"label").c_str():"No equipped items")) {
            for(size_t i=0;i<parts.size();++i)if(ImGui::Selectable((ui::Scalar(parts[i],"label")+" / layer "+ui::Scalar(parts[i],"layer_id")+"##"+std::to_string(i)).c_str(),g_studioPartIndex==int(i))) {
                g_studioPartIndex=int(i);const auto target=ui::Scalar(parts[i],"target");QueueStudioAction("studio_part_inspect",nullptr,target.c_str());
            }
            ImGui::EndCombo();
        }
    }
    const auto* selected = SelectedStudioPart();
    if (!selected) { ImGui::TextWrapped("Choose an equipped part on the left."); return; }
    const auto& part = *selected;
    const auto target = ui::Scalar(part, "target");
    const auto color = ui::Scalar(part, "color_hex");
    ImGui::TextColored(ImVec4(0.35f, 0.88f, 0.77f, 1), "%s", ui::Scalar(part, "label").c_str());
    ImGui::TextDisabled("CASP %s | layer %s", ui::Scalar(part, "cas_part_hex").c_str(), ui::Scalar(part, "layer_id").c_str());
    DrawResourcePart(part, ResourcePartEditor(part));
    ImGui::SeparatorText("Replace equipped part");
    if (ImGui::Button("Inspect part / find compatible sources")) QueueStudioAction("studio_part_inspect", nullptr, target.c_str());
    const auto editor = g_studioData.find("part_editor");
    if (editor != g_studioData.end() && ui::Scalar(*editor, "target") == target &&
        ui::Scalar(*editor, "appearance_sha256") == ui::Scalar(g_studioData, "appearance_sha256")) {
        ImGui::TextWrapped("%s", ui::Scalar(*editor, "part_name").c_str());
        const auto& sources = (*editor)["candidates"];
        if (sources.empty()) ImGui::TextWrapped("No alternate part of this body type exists in this Sim's current-form wardrobe.");
        else {
            g_partReplacementIndex = std::clamp(g_partReplacementIndex, 0, static_cast<int>(sources.size()) - 1);
            auto name = [](const ui::Json& source) { return "Outfit " + ui::Scalar(source, "outfit_index") + " / " + ui::Scalar(source, "cas_part_hex"); };
            if (ImGui::BeginCombo("Source", name(sources[static_cast<size_t>(g_partReplacementIndex)]).c_str())) {
                for (size_t i = 0; i < sources.size(); ++i)
                    if (ImGui::Selectable((name(sources[i]) + "##" + std::to_string(i)).c_str(), g_partReplacementIndex == static_cast<int>(i))) g_partReplacementIndex = static_cast<int>(i);
                ImGui::EndCombo();
            }
            if (ImGui::Button("Preview replacement")) {
                const ui::Json request = {{"target", target}, {"source", sources[static_cast<size_t>(g_partReplacementIndex)]["target"]},
                    {"lane", g_studioData["history_lane"]}, {"appearance_sha256", g_studioData["appearance_sha256"]}};
                const auto payload = request.dump(); QueueStudioAction("studio_part_preview", nullptr, payload.c_str());
            }
        }
    }
    ImGui::SeparatorText("Exact part color");
    ImGui::TextDisabled("%s", color.empty() ? "No explicit color state" : color.c_str());
    const bool supported = part["target_supported"].get<bool>() && !color.empty();
    ImGui::BeginDisabled(!supported);
    if (ImGui::Button("Copy color")) QueueStudioAction("studio_color_copy", nullptr, target.c_str());
    ImGui::SameLine(); if (ImGui::Button("Preview paste")) QueueStudioAction("studio_color_preview", nullptr, target.c_str());
    if (ImGui::Button("Inspect slider bounds")) QueueStudioAction("studio_color_inspect", nullptr, target.c_str());
    ImGui::EndDisabled();
    if (supported) DrawNumericColor(target);
}

static ui::Json CurrentLibraryQuery() {
    return {{"text",g_librarySearch},{"body_type",g_libraryBody<0?ui::Json():ui::Json(g_libraryBody)},
        {"origin",g_libraryOrigin==0?ui::Json():ui::Json(g_libraryOrigin==1?"mod":"ea")},
        {"name_mode",std::array<const char*,3>{"preferred","package","code"}[std::clamp(g_itemNameMode,0,2)]},
        {"offset",g_libraryOffset},{"limit",60},
        {"view",std::array<const char*,3>{"all","favorites","recent"}[std::clamp(g_libraryView,0,2)]},
        {"author",g_libraryAuthor},{"sort",std::array<const char*,4>{"name","package","creator","id"}[std::clamp(g_librarySort,0,3)]},{"grouped",true}};
}

static void DrawLiveLibrary() {
    static const char* modes[] = {"Friendly / CC filename", "Package filename", "Internal code"};
    static const char* origins[] = {"All EA + CC", "Custom content", "EA content"};
    static const char* views[] = {"All items", "Favorites", "Recently inspected"};
    static const char* modeValues[] = {"preferred", "package", "code"};
    static const char* viewValues[] = {"all", "favorites", "recent"};
    ui::Json page, inspection; std::string status;
    { std::lock_guard<std::mutex> lock(g_dataMutex); page = g_libraryPage; inspection = g_libraryInspection; status = g_libraryStatus; }
    auto categoryName = [](int64_t body) {
        if (g_studioData.contains("category_catalog")) for (const auto& c : g_studioData["category_catalog"])
            if (c.contains("value") && c["value"] == body) return ui::Scalar(c, "label");
        for (const auto& c : kCasBodyTypes) if (c.fallbackValue == body) return std::string(c.label);
        return std::string("BodyType ") + std::to_string(body);
    };
    ImGui::TextColored(ImVec4(.35f, .88f, .77f, 1), "LIVE CAS LIBRARY");
    ImGui::TextDisabled("Every indexed part / independent form and outfit / no CAS room");
    ImGui::SetNextItemWidth(-1);
    if (ImGui::InputTextWithHint("##library-search", "Search CC names, filenames or internal codes", g_librarySearch, sizeof(g_librarySearch), ImGuiInputTextFlags_EnterReturnsTrue) || ImGui::IsItemDeactivatedAfterEdit()) {
        g_libraryOffset = 0; g_libraryQueryNeeded = true;
    }
    ImGui::SetNextItemWidth(220);
    if(ImGui::BeginCombo("Creator / filename tag",g_libraryAuthor.empty()?"All creators":g_libraryAuthor.c_str())) {
        if(ImGui::Selectable("All creators",g_libraryAuthor.empty())){g_libraryAuthor.clear();g_libraryOffset=0;g_libraryQueryNeeded=true;}
        if(page.contains("creators"))for(const auto& creator:page["creators"]){const auto label=ui::Scalar(creator,"name");if(ImGui::Selectable(label.c_str(),label==g_libraryAuthor)){g_libraryAuthor=label;g_libraryOffset=0;g_libraryQueryNeeded=true;}}
        ImGui::EndCombo();
    }
    if(ImGui::IsItemHovered())ImGui::SetTooltip("CC creator tags are inferred from package filenames; authorship is not verified.");
    ImGui::SetNextItemWidth(160);
    if(ImGui::Combo("Sort",&g_librarySort,"Item name\0Package name\0Creator tag\0Resource identity\0")){g_libraryOffset=0;g_libraryQueryNeeded=true;}
    const float filterWidth=std::max(90.f,(ImGui::GetContentRegionAvail().x-ImGui::GetStyle().ItemSpacing.x*2)/3);
    ImGui::SetNextItemWidth(filterWidth);
    if (ImGui::Combo("##library-names", &g_itemNameMode, modes, 3)) { g_libraryOffset = 0; g_libraryQueryNeeded = true; }
    ImGui::SameLine(); ImGui::SetNextItemWidth(filterWidth);
    if (ImGui::Combo("##library-origin", &g_libraryOrigin, origins, 3)) { g_libraryOffset = 0; g_libraryQueryNeeded = true; }
    ImGui::SameLine(); ImGui::SetNextItemWidth(filterWidth);
    if (ImGui::Combo("##library-view", &g_libraryView, views, 3)) { g_libraryOffset = 0; g_libraryQueryNeeded = true; }
    ImGui::SetNextItemWidth(-1);
    if (ImGui::BeginCombo("Category##library", g_libraryBody < 0 ? "All categories, including empty slots" : categoryName(g_libraryBody).c_str())) {
        if (ImGui::Selectable("All categories", g_libraryBody < 0)) { g_libraryBody = -1; g_libraryOffset = 0; g_libraryQueryNeeded = true; }
        if (page.contains("categories")) for (const auto& c : page["categories"]) {
            if (c["body_type"].is_null()) continue;
            const auto body = c["body_type"].get<int64_t>();
            const auto label = categoryName(body) + " (" + ui::Scalar(c, "count") + ")##" + std::to_string(body);
            if (ImGui::Selectable(label.c_str(), g_libraryBody == body)) { g_libraryBody = body; g_libraryOffset = 0; g_libraryQueryNeeded = true; }
        }
        ImGui::EndCombo();
    }
    ImGui::SetNextItemWidth(120); ImGui::SliderInt("Columns", &g_libraryColumns, 2, 8);
    const auto query = CurrentLibraryQuery();
    const auto queryKey = query.dump();
    if (g_libraryQueryNeeded && !g_libraryBusy.load() && QueueLibrary(4, query)) {
        g_libraryQueryKey = queryKey; g_libraryQueryNeeded = false;
    }
    ImGui::BeginDisabled(g_libraryBusy.load());
    if (ImGui::SmallButton("Refresh library")) g_libraryQueryNeeded = true;
    ImGui::EndDisabled(); ImGui::SameLine(); ImGui::TextWrapped("%s", status.c_str());
    if (page.empty() || page.value("query", ui::Json()) != query) { ImGui::TextDisabled("%s", g_libraryBusy.load() ? "Loading this catalog page..." : "No current page. Run live-cas-catalog serve with the verified index SHA256."); return; }
    ImGui::TextDisabled("%s CAS items / %s indexed resource candidates", ui::Scalar(page, "total").c_str(), ui::Scalar(page["snapshot"], "parts").c_str());
    if (!page["snapshot"].value("complete", false)) ImGui::TextWrapped("Some packages could not be indexed. Source errors remain visible in the CLI snapshot.");
    ImGui::BeginDisabled(g_libraryBusy.load() || g_libraryOffset == 0);
    if (ImGui::SmallButton("Previous page")) { g_libraryOffset = g_libraryOffset >= 60 ? g_libraryOffset - 60 : 0; g_libraryQueryNeeded = true; }
    ImGui::EndDisabled(); ImGui::SameLine();
    ImGui::BeginDisabled(g_libraryBusy.load() || page["next_offset"].is_null());
    if (ImGui::SmallButton("Next page")) { g_libraryOffset = page["next_offset"].get<size_t>(); g_libraryQueryNeeded = true; }
    ImGui::EndDisabled();
    SynchronizeLibraryImages(page);
    ImGui::Checkbox("Actual CAS thumbnails",&g_libraryShowImages);ImGui::SameLine();
    ImGui::Checkbox("Render missing images",&g_generateMissingThumbnails);ImGui::SameLine();
    ImGui::SetNextItemWidth(125);ImGui::Combo("##thumbnail-gender",&g_libraryImageGender,"Male preview\0Female preview\0");
    ImGui::SameLine();if(ImGui::SmallButton("Refresh images"))CleanupLibraryImages();
    ImGui::BeginChild("library-grid", ImVec2(0, std::clamp(ImGui::GetContentRegionAvail().y-235,160.f,600.f)), true);
    const int columns = std::clamp(g_libraryColumns, 2, 8);
    const float cardWidth = std::max(40.f, (ImGui::GetContentRegionAvail().x - ImGui::GetStyle().ItemSpacing.x * (columns - 1)) / columns);
    const float imageHeight=g_libraryShowImages?std::clamp(cardWidth,48.f,128.f):0.f,cardHeight=imageHeight+64.f;
    const auto& items = page["items"];ui::Json wanted=ui::Json::array();
    ImGuiListClipper clipper; clipper.Begin(static_cast<int>((items.size() + columns - 1) / columns), cardHeight + ImGui::GetStyle().ItemSpacing.y);
    while (clipper.Step()) for (int line = clipper.DisplayStart; line < clipper.DisplayEnd; ++line) {
        for (int column = 0; column < columns; ++column) {
            const size_t n = static_cast<size_t>(line * columns + column); if (n >= items.size()) break;
            if (column) ImGui::SameLine(); const auto& item = items[n]; const auto id = ui::Scalar(item, "part_id");
            ImGui::PushID(id.c_str()); const auto at = ImGui::GetCursorScreenPos();
            const bool available = item["status"] == "indexed";
            ImGui::BeginDisabled(!available || g_libraryBusy.load());
            if (ImGui::Selectable("##library-card", id == g_librarySelected, 0, ImVec2(cardWidth, cardHeight))) {
                g_librarySelected = id; g_libraryTargetRow = 0; ++g_resourceSelectionSerial; g_resourceRequestedImage.clear();
                QueueLibrary(5, {{"part_id", id}, {"index_sha256", page["index_sha256"]}});
            }
            ImGui::EndDisabled();auto* draw=ImGui::GetWindowDrawList();
            if(g_libraryShowImages) {
                const auto found=g_libraryImageTextures.find(id);
                if(found!=g_libraryImageTextures.end()) {
                    const auto size=g_libraryImageSizes.at(id);const float scale=std::min((cardWidth-8)/size.x,(imageHeight-4)/size.y);
                    const ImVec2 min(at.x+(cardWidth-size.x*scale)/2,at.y+2),max(min.x+size.x*scale,min.y+size.y*scale);
                    draw->AddImage(reinterpret_cast<ImTextureID>(found->second),min,max);
                }else {
                    const char* label=g_libraryImageAttempted.count(id)?"No image / inspect":"Loading image";
                    draw->AddText(ImVec2(at.x+4,at.y+imageHeight/2),IM_COL32(125,145,155,255),label);
                }
                if(available&&!g_libraryImageAttempted.count(id)&&wanted.size()<24)wanted.push_back(id);
                if(available&&g_generateMissingThumbnails&&g_libraryImageAttempted.count(id)&&!g_thumbnailAttempted.count(id)&&found==g_libraryImageTextures.end()) {
                    bool missing=false;{std::lock_guard<std::mutex> lock(g_dataMutex);missing=g_libraryImageErrors.count(id)!=0;}
                    if(missing)QueueThumbnail(item);
                }
            }
            const ImVec4 clip(at.x + 5, at.y + imageHeight+4, at.x + cardWidth - 5, at.y + cardHeight-20);
            const auto name = ui::Scalar(item, "name"); const auto display = name.empty() ? ui::Scalar(item, "package_name") : name;
            draw->AddText(ImGui::GetFont(), ImGui::GetFontSize(), ImVec2(at.x + 5, at.y + imageHeight+4), available ? IM_COL32(222, 232, 239, 255) : IM_COL32(127, 139, 152, 255), display.c_str(), nullptr, cardWidth - 10, &clip);
            const auto footer = (item["favorite"] == true ? std::string("Favorite") : item["body_type"].is_null() ? std::string("Unclassified") : categoryName(item["body_type"].get<int64_t>()))+
                (item.contains("swatch_count")?" / "+ui::Scalar(item,"swatch_count")+" swatches":"");
            const ImVec4 footerClip(at.x + 5, at.y + cardHeight-19, at.x + cardWidth - 5, at.y + cardHeight);
            draw->AddText(ImGui::GetFont(), ImGui::GetFontSize(), ImVec2(at.x + 5, at.y + cardHeight-18), IM_COL32(94, 195, 177, 255), footer.c_str(), nullptr, 0, &footerClip);
            if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                std::string imageReason;{std::lock_guard<std::mutex> lock(g_dataMutex);const auto found=g_libraryImageErrors.find(id);if(found!=g_libraryImageErrors.end())imageReason=found->second;}
                ImGui::SetTooltip("%s\nPackage: %s\nCode: %s\n%s\n%s\n%s", ui::Scalar(item, "preferred_name").c_str(), ui::Scalar(item, "package_name").c_str(), ui::Scalar(item, "code_name").c_str(), ui::Scalar(item, "resource_tgi").c_str(), available ? "Select to inspect and try on this actual item." : ui::Scalar(item, "reason").c_str(),imageReason.c_str());
            }
            ImGui::PopID();
        }
    }
    ImGui::EndChild();
    if(!wanted.empty()&&!g_libraryImagesBusy&&!g_libraryBusy) {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if(g_commands.size()<48) {
            QueuedCommand command{"",g_selectionGeneration};command.resourceOperation=7;command.resourceSelection=g_libraryImageSerial.load();
            command.resourceRow={{"part_ids",wanted},{"index_sha256",page["index_sha256"]},{"gender",g_libraryImageGender?"female":"male"}};
            if(library::ImagesRequest(command.resourceRow)){for(const auto& id:wanted)g_libraryImageAttempted.insert(id.get<std::string>());g_libraryImagesBusy=true;g_commands.push_back(std::move(command));}
        }
    }
    const ui::Json selection = {{"part_id", g_librarySelected}, {"index_sha256", page["index_sha256"]}};
    if (!library::Inspection(inspection, selection)) { ImGui::TextDisabled("Select an item to inspect its actual resource and compatibility."); return; }
    const auto& item = inspection["item"]; const auto& row = inspection["resource"];
    const auto name = resource::Name(row, static_cast<resource::NameMode>(std::clamp(g_itemNameMode, 0, 2)));
    ImGui::SeparatorText(name.text.empty() ? "Selected item" : name.text.c_str());
    if(inspection.contains("swatches")&&library::Swatches(inspection["swatches"],item)) {
        const auto& swatches=inspection["swatches"];
        ImGui::TextDisabled("%s swatches / choose a color variant",ui::Scalar(swatches,"total").c_str());
        ImGui::BeginChild("catalog-swatches",ImVec2(0,80),true);
        int n=0;const float width=std::max(1.f,ImGui::GetContentRegionAvail().x);
        for(const auto& variant:swatches["items"]) {
            const auto id=ui::Scalar(variant,"part_id");const auto& colors=variant["metadata"]["swatch_colors_argb"];
            if(n++&&ImGui::GetCursorPosX()+28<width)ImGui::SameLine();ImGui::PushID(id.c_str());
            const auto at=ImGui::GetCursorScreenPos();
            ImGui::BeginDisabled(g_libraryBusy.load());
            if(ImGui::Selectable("##swatch",id==g_librarySelected,0,ImVec2(24,24))) {
                g_librarySelected=id;++g_resourceSelectionSerial;g_resourceRequestedImage.clear();
                QueueLibrary(5,{{"part_id",id},{"index_sha256",page["index_sha256"]}});
            }
            ImGui::EndDisabled();
            auto* draw=ImGui::GetWindowDrawList();
            if(colors.empty())draw->AddText(ImVec2(at.x+6,at.y+3),IM_COL32(190,205,220,255),"?");
            else for(size_t c=0;c<colors.size();++c){const auto argb=colors[c].get<uint32_t>();
                const auto rgba=IM_COL32((argb>>16)&255,(argb>>8)&255,argb&255,(argb>>24)&255);
                draw->AddRectFilled(ImVec2(at.x+2+20.f*c/colors.size(),at.y+2),ImVec2(at.x+2+20.f*(c+1)/colors.size(),at.y+22),rgba);}
            if(ImGui::IsItemHovered())ImGui::SetTooltip("%s\n%s\nSwatch %s / %s source candidates",ui::Scalar(variant,"preferred_name").c_str(),ui::Scalar(variant,"package_name").c_str(),ui::Scalar(variant["metadata"],"swatch_order").c_str(),ui::Scalar(variant,"container_count").c_str());
            ImGui::PopID();
        }
        ImGui::EndChild();
        ImGui::BeginDisabled(g_libraryBusy.load());
        if(swatches["offset"]>0&&ImGui::SmallButton("Previous swatches"))QueueLibrary(5,{{"part_id",g_librarySelected},{"index_sha256",page["index_sha256"]},{"swatch_offset",std::max(0,swatches["offset"].get<int>()-120)}});
        if(!swatches["next_offset"].is_null()){ImGui::SameLine();if(ImGui::SmallButton("More swatches"))QueueLibrary(5,{{"part_id",g_librarySelected},{"index_sha256",page["index_sha256"]},{"swatch_offset",swatches["next_offset"]}});}
        ImGui::EndDisabled();
    }
    bool favorite = item.value("favorite",false);
    for (const auto& candidate : items) if (candidate["part_id"] == g_librarySelected) favorite = candidate["favorite"].get<bool>();
    ImGui::BeginDisabled(g_libraryBusy.load());
    if (ImGui::Checkbox("Favorite##selected-catalog", &favorite)) {
        QueueLibrary(6, {{"part_id", g_librarySelected}, {"index_sha256", page["index_sha256"]}, {"enabled", favorite}}); g_libraryQueryNeeded = true;
    }
    ImGui::EndDisabled();
    const auto key = ResourceKey(row);
    if (row["thumbnail"]["status"] == "resolved") {
        if (g_resourceRequestedImage != key && !g_resourceImageBusy.load() && QueueResource(2, row)) g_resourceRequestedImage = key;
        unsigned width = 0, height = 0;
        { std::lock_guard<std::mutex> lock(g_dataMutex); if (g_resourceImageKey == key) { width = g_resourcePixels.width; height = g_resourcePixels.height; } }
        if (ResourceTexture(key)) { const float scale = std::min(1.f, 128.f / static_cast<float>(std::max(width, height))); ImGui::Image(reinterpret_cast<ImTextureID>(g_resourceTexture), ImVec2(width * scale, height * scale)); }
        else ImGui::TextDisabled("Loading verified thumbnail...");
    } else {
        const auto found=g_libraryImageTextures.find(g_librarySelected);
        if(found!=g_libraryImageTextures.end()){ImGui::Image(reinterpret_cast<ImTextureID>(found->second),ImVec2(128,128));ImGui::TextDisabled("Rendered actual item / preview Sim");}
        else ImGui::TextWrapped("Thumbnail unavailable: %s", ui::Scalar(row["thumbnail"], "reason").c_str());
        ImGui::BeginDisabled(g_thumbnailBusy||g_simPreviewBusy||g_simPreview.scene.id.empty()||g_trayPreviewActive);
        if(ImGui::Button("Render this item's thumbnail"))QueueThumbnail(item);
        ImGui::EndDisabled();
    }
    ImGui::BeginDisabled(row["studio_open"]["status"] != "ready" || g_resourceOpenBusy.load());
    if (ImGui::Button("Open package copy in Sims 4 Studio##library")) QueueResource(3, row);
    ImGui::EndDisabled();
    const auto& outfits = ViewedStudioOutfits();
    if (outfits.empty() || !g_studioData.contains("history_lane") || !g_studioData.contains("appearance_sha256")) return;
    const auto& outfit = outfits[static_cast<size_t>(std::clamp(g_studioOutfitIndex, 0, static_cast<int>(outfits.size()) - 1))];
    std::vector<ui::Json> targets;
    for (const auto& part : outfit["parts"]) if (part["body_type"] == item["body_type"]) targets.push_back(part);
    ui::Json partIndex;
    if (!targets.empty()) {
        g_libraryTargetRow = std::clamp(g_libraryTargetRow, 0, static_cast<int>(targets.size()) - 1);
        if (ImGui::BeginCombo("Replace exact layer", ui::Scalar(targets[static_cast<size_t>(g_libraryTargetRow)], "target").c_str())) {
            for (size_t n = 0; n < targets.size(); ++n) if (ImGui::Selectable(ui::Scalar(targets[n], "target").c_str(), n == static_cast<size_t>(g_libraryTargetRow))) g_libraryTargetRow = static_cast<int>(n);
            ImGui::EndCombo();
        }
        partIndex = targets[static_cast<size_t>(g_libraryTargetRow)]["index"];
    } else ImGui::TextDisabled("Add to this empty category / selected form and outfit only.");
    ImGui::TextWrapped("Preview checks loaded CASP identity, age/species and fitting restrictions. Apply commits through full appearance history; other forms and outfits are retained.");
    ImGui::BeginDisabled(g_libraryBusy.load() || g_ownerBlocked.load() || g_ownerSubmissionBusy.load() || g_ownerNativeDeliveryBusy.load() || g_casBankBusy.load() || g_studioData.value("pending_preview", ui::Json()) != nullptr);
    if (ImGui::Button(g_livePartColor?"Apply selected item to this form / outfit":"Try on selected item / Preview")) {
        const auto tgi = ui::Scalar(item, "resource_tgi");
        const auto id = std::to_string(std::stoull(tgi.substr(18), nullptr, 16));
        const ui::Json request = {{"outfit_index", outfit["index"]}, {"outfit_id", outfit["outfit_id"]}, {"part_index", partIndex},
            {"body_type", item["body_type"]}, {"cas_part_id", id}, {"resource_tgi", item["resource_tgi"]},
            {"resource_sha256", item["resource_sha256"]}, {"lane", g_studioData["history_lane"]}, {"appearance_sha256", g_studioData["appearance_sha256"]}};
        const auto raw = request.dump(); QueueStudioAction(g_livePartColor?"studio_catalog_live":"studio_catalog_preview", nullptr, raw.c_str());
    }
    ImGui::EndDisabled();
}

static void DrawStudioTimeline() {
    ImGui::SetNextItemWidth(-1); ImGui::InputTextWithHint("##history-search", "Search checkpoints and operations", g_historySearch, sizeof(g_historySearch));
    const auto found = g_studioData.find("history_nodes");
    if (found == g_studioData.end() || found->empty()) { ImGui::TextDisabled("Inspect or capture a checkpoint to begin."); return; }
    ImGui::BeginChild("history-cards", ImVec2(0, 270), true);
    for (const auto& node : *found) {
        const auto id = ui::Scalar(node, "id"), label = ui::Scalar(node, "label");
        if (!TextContainsNoCase(label.c_str(), g_historySearch) && !TextContainsNoCase(id.c_str(), g_historySearch)) continue;
        const bool current = id == ui::Scalar(g_studioData, "history_cursor");
        const auto at = ImGui::GetCursorScreenPos();
        ImGui::PushID(id.c_str());
        if (ImGui::Selectable("##history-card", id == g_historyId, 0, ImVec2(0, 54))) strncpy_s(g_historyId, id.c_str(), _TRUNCATE);
        auto* draw = ImGui::GetWindowDrawList();
        const ImU32 accent = current ? IM_COL32(85, 220, 186, 255) : IM_COL32(109, 141, 179, 255);
        draw->AddLine(ImVec2(at.x + 9, at.y), ImVec2(at.x + 9, at.y + 54), IM_COL32(45, 72, 89, 255), 2);
        draw->AddCircleFilled(ImVec2(at.x + 9, at.y + 16), 4, accent);
        draw->AddText(ImVec2(at.x + 24, at.y + 4), accent, (label + (current ? "  / CURRENT" : "")).c_str());
        const auto delta = node.find("delta");
        const auto summary = delta != node.end() ? ui::Scalar(*delta, "summary") : "Retained checkpoint";
        draw->AddText(ImVec2(at.x + 24, at.y + 27), IM_COL32(145, 165, 184, 255), summary.c_str());
        if (ImGui::IsItemHovered()) {
            const auto parent = ui::Scalar(node, "parent");
            ImGui::SetTooltip("%s\nParent: %s\nComplete native Sim record retained: %s\nUTC epoch: %.0f", id.c_str(), parent.empty() ? "baseline" : parent.c_str(),
                node.value("complete_native_record_retained", false) ? "yes" : "no", node["time"].get<double>());
        }
        ImGui::PopID();
    }
    ImGui::EndChild();
}

static bool QueueCasAction(const ui::Json& request) {
    // Reserve before queueing so successive frames cannot stack native inputs
    // while the worker is waiting for the first request's identity.
    if (g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() || g_casPendingId[0] || g_casRefreshClock.unresolved) return false;
    bool idle = false;
    if (!g_casSubmissionBusy.compare_exchange_strong(idle, true)) return false;
    const auto value = request.dump();
    if (!QueueCommand(BuildCommandPath("cas_ui_request", nullptr, value.c_str()))) { g_casSubmissionBusy = false; return false; }
    return true;
}

static bool QueueAutomaticCasRefresh(const std::string& sim) {
    if (g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() || g_casBankBusy.load()) return false;
    bool idle = false;
    if (!g_casSubmissionBusy.compare_exchange_strong(idle, true)) return false;
    std::lock_guard<std::mutex> lock(g_dataMutex);
    // Automatic work cannot overtake a user's queued command or a changed
    // selection. The worker rechecks visibility before diagnostics and read.
    if (!g_commands.empty() || sim != g_selectedSim || g_done.load() || g_casBankBusy.load()) {
        g_casSubmissionBusy = false; return false;
    }
    g_commands.push_back({"/api/command?action=cas_ui_diagnostics&sim_id=" + UrlEncode(sim),
        g_selectionGeneration, true, sim});
    return true;
}

static bool QueueAutomaticCasReconcile(const std::string& sim, const std::string& requestId) {
    if (g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() || g_casBankBusy.load()) return false;
    bool idle = false;
    if (!g_casSubmissionBusy.compare_exchange_strong(idle, true)) return false;
    std::lock_guard<std::mutex> lock(g_dataMutex);
    if (!g_commands.empty() || sim != g_selectedSim || g_done.load() || g_casBankBusy.load()) {
        g_casSubmissionBusy = false; return false;
    }
    g_commands.push_back({"/api/command?action=cas_ui_result&sim_id=" + UrlEncode(sim) + "&value=" + UrlEncode(requestId),
        g_selectionGeneration, false, sim, true, requestId});
    return true;
}

static bool ReleaseAutomaticCasRead(const ui::Json& data, const std::string& sim) {
    if (g_casAutoRetainedId.empty() || g_casAutoRetainedId != g_casPendingId) return false;
    const auto state = ui::ResolveCasRead(data, g_casAutoRetainedId, sim);
    if (state != ui::CasReadResolution::Completed && state != ui::CasReadResolution::Failed && state != ui::CasReadResolution::Expired) return false;
    // This is the completion of an old read, not a newly captured inventory.
    // Keep snapshot data/age intact, release only our own status-read UUID,
    // then let the distinct fresh-status scheduler observe current CAS data.
    g_casPendingId[0] = '\0'; g_casAutoRetainedId.clear();
    g_casRefreshClock = {}; g_casReconcileClock = {};
    g_casAutoMessage = "Retained automatic read resolved. Refreshing the current native CAS inventory.";
    return true;
}


static void DrawNativeCas(const std::string& reply, ULONGLONG replyMs, bool history) {
    std::string sim;
    std::string observedReply = reply, deliveredReply;
    ULONGLONG observedReplyMs = replyMs;
    const auto now = GetTickCount64();
    g_nativeCasPaneVisible = true; g_nativeCasPaneMs = now;
    {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        sim = g_selectedSim;
        if (g_ownerNativeDeliveryBusy.load() && !g_ownerDeliveredNativeReply.empty()) {
            deliveredReply = g_ownerDeliveredNativeReply;
            observedReply = deliveredReply; observedReplyMs = g_commandReplyMs;
        }
        if (g_casDiagnosticMs != g_casDiagnosticsSeenMs) {
            g_casDiagnostics = ui::ParseObject(g_casDiagnosticReply);
            g_casDiagnosticsSeenMs = g_casDiagnosticMs;
        }
        if (g_casRefreshReceipt != g_casRefreshSeen) {
            g_casRefreshSeen = g_casRefreshReceipt; g_casAutoMessage = g_casRefreshMessage;
            g_casAutoRetainedId = g_casRefreshNativeId; g_casReconcileClock = {};
            if (g_casRefreshFailed) ui::CasRefreshFailed(g_casRefreshClock, now, g_casRefreshUnresolved);
            else if (!g_ownerBlocked.load()) g_casRefreshClock.unresolved = false;
        }
        if (g_casReconcileReceipt != g_casReconcileSeen) {
            g_casReconcileSeen = g_casReconcileReceipt;
            if (g_casReconcileNativeId == g_casAutoRetainedId && g_casReconcileSim == sim &&
                (!g_casReconcileOk || !ReleaseAutomaticCasRead(ui::ParseObject(g_casReconcileReply), sim))) {
                ui::CasRefreshFailed(g_casReconcileClock, now);
                g_casAutoMessage = "Retained automatic read is still unresolved; only its same result ID will be checked. No CAS operation is replayed.";
            }
            if (g_ownerNativeDeliveryBusy.load() && g_ownerOriginalCommand.automaticCasReconcile) {
                // The native exact-ID reconciler consumed this delivery above;
                // keep it out of the fresh inventory presentation path.
                g_ownerNativeDeliveryBusy = false; observedReply = reply; observedReplyMs = replyMs;
                deliveredReply.clear();
            }
        }
    }
    if (observedReply != g_casLastReply) {
        g_casLastReply = observedReply;
        const auto& data = ui::ReadObject(observedReply);
        if (data.contains("cas_request_id") && ui::CasRequestIdentity(data["cas_request_id"])) {
            strncpy_s(g_casPendingId, ui::Scalar(data, "cas_request_id").c_str(), _TRUNCATE);
            if (ui::Scalar(data, "cas_request_id") == g_casAutoRetainedId) {
                // Manual inspection of that same automatic UUID also releases
                // it without presenting its historical inventory as live.
                if (!ReleaseAutomaticCasRead(data, sim)) g_casRefreshClock.unresolved = true;
            } else if (data.contains("client") && ui::Scalar(data, "ok") == "true" && ui::CasDocument(data["client"], sim)) {
                g_casClientData = data["client"];
                g_casRoomData = data.value("cas_room", ui::Json::object());
                g_casSelectedItem = ui::RefreshCasSelection(g_casClientData, g_casSelectedPanel, g_casSelectedItem, g_casSelectedPreset);
                g_casSnapshotMs = observedReplyMs; // Receipt time survives hiding; showing never renews its age.
                g_casPendingId[0] = '\0';
                g_casRefreshClock.failures = 0; g_casRefreshClock.backoffUntilMs = 0; g_casRefreshClock.unresolved = false;
            } else if (ui::CasExplicitFailure(data)) {
                g_casClientData = ui::Json::object(); g_casSelectedItem = ui::Json::object();
                g_casPendingId[0] = '\0'; g_casSnapshotMs = 0;
                g_casRefreshClock.unresolved = false;
                if (g_casRefreshClock.backoffUntilMs <= now) ui::CasRefreshFailed(g_casRefreshClock, now);
            } else {
                // Pending, unknown, superseded, or malformed readback keeps its
                // exact native UUID; no fresh status request may hide it.
                g_casRefreshClock.unresolved = true;
            }
        }
        if (data.contains("native_initializer_observed") && data["native_initializer_observed"].is_boolean()) g_casDiagnostics = data;
    }
    // The render thread has now consumed the recovered result and retained
    // any native UUID before lifting the worker-to-render delivery barrier.
    if (!deliveredReply.empty()) {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if (g_ownerDeliveredNativeReply == deliveredReply) g_ownerNativeDeliveryBusy = false;
    }
    ImGui::TextColored(ImVec4(0.35f, 0.88f, 0.77f, 1), "CAS / ACKNOWLEDGED CLIENT SNAPSHOT");
    ImGui::BeginDisabled(g_casSubmissionBusy.load() || g_ownerBlocked.load() || g_casPendingId[0] || g_casRefreshClock.unresolved);
    if (ImGui::Button("Refresh equipped items")) QueueCasAction({{"operation", "status"}});
    ImGui::EndDisabled();
    ImGui::SameLine(); ImGui::BeginDisabled(g_casSubmissionBusy.load() || g_ownerBlocked.load());
    if (ImGui::Button("CAS transport diagnostics")) QueueAction("cas_ui_diagnostics");
    ImGui::EndDisabled();
    ImGui::SameLine(); ImGui::Checkbox("Show empty categories", &g_showEmptySlots);
    if (ImGui::Checkbox("Automatically refresh while this CAS view is open", &g_casAutoRefresh))
        g_casAutoRefreshEnabled = g_casAutoRefresh;
    ImGui::InputText("Search categories / exact item data", g_partSearch, sizeof(g_partSearch));
    if (g_casSubmissionBusy.load()) ImGui::TextWrapped("Native request submitted once; waiting for its result. No additional CAS input will be queued.");
    if (!g_casAutoMessage.empty()) ImGui::TextWrapped("%s", g_casAutoMessage.c_str());
    if (!g_casDiagnostics.empty() && ImGui::CollapsingHeader("Native CAS startup / transport")) {
        ImGui::TextWrapped("Initializer observed: %s / distributor client: %s / queued operations: %s",
            ui::Scalar(g_casDiagnostics, "native_initializer_observed").c_str(),
            ui::Scalar(g_casDiagnostics, "distributor_client_available").c_str(),
            ui::Scalar(g_casDiagnostics, "queued_operations").c_str());
        ImGui::TextWrapped("This read-only diagnostic does not prove an outfit or category transition.");
        if (ImGui::SmallButton("Copy complete transport diagnostic")) ImGui::SetClipboardText(g_casDiagnostics.dump(2).c_str());
        if (ImGui::TreeNode("Exact diagnostic fields")) { ImGui::TextWrapped("%s", g_casDiagnostics.dump(2).c_str()); ImGui::TreePop(); }
    }
    if (g_casPendingId[0]) {
        ImGui::TextWrapped("Awaiting native response: %s", g_casPendingId);
        ImGui::BeginDisabled(g_casSubmissionBusy.load() || g_ownerBlocked.load());
        if (ImGui::Button("Check retained request")) QueueAction("cas_ui_result", nullptr, g_casPendingId);
        ImGui::EndDisabled();
    }
    if (ui::CasReadReconcileDue(g_casReconcileClock, now, sim,
        ui::CasNativePaneVisible(g_visible.load(), g_nativeCasView, g_activeTab), g_casAutoRefresh,
        g_casSubmissionBusy.load(), g_casAutoRetainedId, g_casPendingId) && QueueAutomaticCasReconcile(sim, g_casAutoRetainedId))
        g_casReconcileClock.lastAttemptMs = now;
    if (ui::CasRefreshDue(g_casRefreshClock, now, g_casSnapshotMs, sim,
        ui::CasNativePaneVisible(g_visible.load(), g_nativeCasView, g_activeTab),
        g_casAutoRefresh, g_casSubmissionBusy.load(), g_casPendingId[0] != '\0') && QueueAutomaticCasRefresh(sim))
        g_casRefreshClock.lastAttemptMs = now;
    if (!ui::CasDocument(g_casClientData, sim)) {
        ImGui::TextWrapped("A fresh native CAS response for this Sim is required before equipped items can be shown.");
        return;
    }
    const auto& info = g_casClientData["sim"];
    ImGui::Text("%s %s / form %s / layer %s", ui::Scalar(info, "firstName").c_str(), ui::Scalar(info, "lastName").c_str(),
        ui::Scalar(info, "occultType").c_str(), ui::Scalar(info, "occultLayer").c_str());
    const auto& slot = g_casClientData["outfit"];
    ImGui::TextDisabled("Current outfit: category %s / index %s (zero based)", ui::Scalar(slot, "outfit_type").c_str(), ui::Scalar(slot, "outfit_index").c_str());
    const auto snapshotAge = (GetTickCount64() - g_casSnapshotMs) / 1000.0;
    ImGui::TextColored(snapshotAge > 2.5 ? ImVec4(1, 0.76f, 0.37f, 1) : ImVec4(0.55f, 0.76f, 0.71f, 1),
        "Last native acknowledgement: %.1f seconds ago", snapshotAge);
    ImGui::TextWrapped("Selected CAS form and outfit at that acknowledgement. Automatic refresh checks this exact Sim at most every two seconds while this view is open.");
    if (ImGui::SmallButton("Copy complete CAS snapshot")) ImGui::SetClipboardText(g_casClientData.dump(2).c_str());
    ImGui::SameLine(); ImGui::SetNextItemWidth(170);
    ImGui::Combo("Category order", &g_casCatalogSort, "Category name\0Equipped first\0Native menu state\0");
    const bool nativeActionPending = g_casSubmissionBusy.load() || g_ownerBlocked.load() || g_casPendingId[0] || g_casRefreshClock.unresolved;
    if (ui::CasRoomDocument(g_casRoomData,g_casClientData,sim)) {
        if (g_casRoomData.contains("native_layers")) {
            ImGui::SeparatorText("Native CAS layers");
            for (const auto& layer:g_casRoomData["native_layers"]) {
                if (layer["layer"]==1) ImGui::SameLine();
                const bool chosen=layer["selected"]==true;
                ImGui::PushID(1000+layer["layer"].get<int>());
                ImGui::BeginDisabled(nativeActionPending || snapshotAge>2.5 || chosen);
                if (ImGui::Button(ui::Scalar(layer,"label").c_str(),ImVec2(150,32)))
                    QueueCasAction({{"operation","layer-select"},{"household_id",ui::Scalar(g_casRoomData,"household_id")},
                        {"target_layer",layer["layer"]},{"expected_layer",g_casRoomData["selected_layer"]},
                        {"native_session",g_casRoomData["native_session"]}});
                ImGui::EndDisabled();
                ImGui::PopID();
            }
            ImGui::TextDisabled("Native primary/alternate navigation. Each retained occult keeps its own appearance.");
        }
        ImGui::SeparatorText("Apex CAS workspace / retained forms");
        int column=0;
        for (const auto& row:g_casRoomData["rows"]) {
            if (column++%4!=0) ImGui::SameLine();
            const bool chosen=row["selected"]==true;
            const bool available=row["navigation_supported"]==true;
            const auto form=row["form_flags"].get<int>();
            ImGui::PushID(form);
            if (chosen) ImGui::PushStyleColor(ImGuiCol_Button,ImVec4(0.36f,0.22f,0.54f,1.0f));
            ImGui::BeginDisabled(nativeActionPending || snapshotAge>2.5 || !available);
            if (ImGui::Button(ui::Scalar(row,"label").c_str(),ImVec2(125,32)) && !chosen)
                QueueCasAction({{"operation","form-select"},{"household_id",ui::Scalar(g_casRoomData,"household_id")},
                    {"form_flags",form},{"expected_layer",g_casRoomData["selected_layer"]},
                    {"native_session",g_casRoomData["native_session"]}});
            ImGui::EndDisabled();
            if (chosen) ImGui::PopStyleColor();
            if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled))
                ImGui::SetTooltip("%s\n%s",ui::Scalar(row,"label").c_str(),
                    available ? "Selects the observed native CAS layer. Edits are reviewed after returning to Live."
                              : "Original form retained. Editing this form requires a separate CAS visit with the current native transport.");
            ImGui::PopID();
        }
        ImGui::TextDisabled("Every captured form remains listed. Changing selection never removes an occult.");
    }
    if (history) {
        ImGui::BeginDisabled(nativeActionPending);
        if (ImGui::Button("Native CAS Undo")) QueueCasAction({{"operation", "undo"}});
        ImGui::SameLine(); if (ImGui::Button("Native CAS Redo")) QueueCasAction({{"operation", "redo"}});
        ImGui::EndDisabled();
    }
    ImGui::BeginChild("native-cas-equipped", ImVec2(std::min(420.0f, std::max(300.0f, ImGui::GetContentRegionAvail().x * 0.4f)), 0), true);
    std::vector<ui::Json> catalogs;
    for (const auto& item : g_casClientData["catalogs"]) catalogs.push_back(item);
    std::sort(catalogs.begin(), catalogs.end(), [](const auto& a, const auto& b) {
        if (g_casCatalogSort == 1) {
            const auto left = (a["supported"].get<bool>() ? a["items"].size() : 0) + (ui::CasHasPreset(a) ? 1 : 0);
            const auto right = (b["supported"].get<bool>() ? b["items"].size() : 0) + (ui::CasHasPreset(b) ? 1 : 0);
            if (left != right) return left > right;
        } else if (g_casCatalogSort == 2 && a["menu_state"] != b["menu_state"])
            return a["menu_state"].get<int64_t>() < b["menu_state"].get<int64_t>();
        return ui::Scalar(a, "panel") < ui::Scalar(b, "panel");
    });
    for (const auto& catalog : catalogs) {
        const auto name = ui::Scalar(catalog, "panel"), label = ui::CasPanelLabel(name);
        const bool supported = catalog["supported"].get<bool>();
        const auto& items = catalog["items"];
        const auto count = supported ? items.size() : 0;
        const auto presetQuery = ui::Scalar(catalog, "preset_query");
        const bool presetRecord = presetQuery == "returned-value";
        if (!g_showEmptySlots && ui::CasCatalogEmpty(catalog)) continue;
        const auto searchable = name + " " + catalog.dump();
        if (g_partSearch[0] && !TextContainsNoCase(searchable.c_str(), g_partSearch)) continue;
        ImGui::PushID(name.c_str());
        ImGui::BeginDisabled(nativeActionPending);
        if (ImGui::SmallButton("Edit")) QueueCasAction({{"operation", "panel"}, {"panel", name}});
        ImGui::EndDisabled();
        ImGui::SameLine();
        const bool equipped = count || ui::CasHasPreset(catalog);
        ImGui::PushStyleColor(ImGuiCol_Text, equipped ? ImVec4(0.45f, 0.93f, 0.81f, 1) :
            (!supported ? ImVec4(1, 0.76f, 0.37f, 1) : ImGui::GetStyleColorVec4(ImGuiCol_TextDisabled)));
        if (supported) ImGui::TextWrapped("%s / %u equipped%s", label.c_str(), static_cast<unsigned>(count),
            ui::CasHasPreset(catalog) ? " + preset" : "");
        else ImGui::TextWrapped("%s / unresolved", label.c_str());
        ImGui::PopStyleColor();
        if (supported) for (size_t i = 0; i < items.size(); ++i) {
            const auto id = ui::Scalar(items[i], "dataID");
            const auto annotation = ui::CasItemMetadata(g_casClientData, items[i]);
            const auto resolvedName = ui::Scalar(annotation, "name");
            const auto itemLabel = (resolvedName.empty() ? "Name unavailable" : resolvedName) + "##native-item";
            ImGui::PushID(static_cast<int>(i));
            ImGui::BeginDisabled(nativeActionPending);
            const bool selected = !g_casSelectedPreset && g_casSelectedPanel == name &&
                ((!id.empty() && id == ui::Scalar(g_casSelectedItem, "dataID")) || (id.empty() && g_casSelectedItem == items[i]));
            if (ImGui::Selectable(itemLabel.c_str(), selected)) {
                g_casSelectedItem = items[i]; g_casSelectedPanel = name; g_casSelectedPreset = false;
                QueueCasAction({{"operation", "panel"}, {"panel", name}});
            }
            if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                ImGui::BeginTooltip(); ImGui::PushTextWrapPos(440);
                ImGui::TextWrapped("%s\nCatalog identity: %s\nName source: %s\n%s", label.c_str(), id.c_str(),
                    annotation.empty() ? "Not fetched by this cached client" : ui::Scalar(annotation, "name_query").c_str(), items[i].dump(2).c_str());
                ImGui::PopTextWrapPos(); ImGui::EndTooltip();
            }
            ImGui::TextDisabled("Catalog %s", id.empty() ? "identity unavailable" : id.c_str());
            ImGui::EndDisabled(); ImGui::PopID();
        }
        if (presetRecord) {
            const auto& preset = catalog["preset"];
            const char* presetState = ui::CasPresetAbsent(preset) ? "No preset selected" :
                (ui::CasPresetSelected(preset) ? "Selected preset" : "Preset / inspect raw fields");
            const auto presetLabel = std::string(presetState) + (ui::CasPresetSelected(preset) ? " / " + ui::Scalar(preset, "presetId") : "");
            ImGui::BeginDisabled(nativeActionPending);
            if (ImGui::Selectable(presetLabel.c_str(), g_casSelectedPreset && g_casSelectedPanel == name)) {
                g_casSelectedItem = catalog["preset"]; g_casSelectedPanel = name; g_casSelectedPreset = true;
                QueueCasAction({{"operation", "panel"}, {"panel", name}});
            }
            if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                ImGui::BeginTooltip(); ImGui::PushTextWrapPos(440);
                ImGui::TextWrapped("%s\n%s", label.c_str(), preset.dump(2).c_str());
                ImGui::PopTextWrapPos(); ImGui::EndTooltip();
            }
            ImGui::EndDisabled();
        } else if (presetQuery == "failed") ImGui::TextDisabled("Preset query unresolved");
        ImGui::Separator(); ImGui::PopID();
    }
    ImGui::EndChild(); ImGui::SameLine();
    ImGui::BeginChild("native-cas-details", ImVec2(0, 0), true);
    ImGui::SeparatorText(g_casSelectedPreset ? "Native preset record / exact client fields" : "Selected item / exact client fields");
    if (g_casSelectedPreset && ui::CasPresetAbsent(g_casSelectedItem)) ImGui::TextDisabled("Native no-selection sentinel; every returned field is retained.");
    if (g_casSelectedItem.empty()) ImGui::TextWrapped("Choose an equipped item to open its native category and inspect its complete returned fields.");
    else {
        const auto annotation = g_casSelectedPreset ? ui::Json::object() : ui::CasItemMetadata(g_casClientData, g_casSelectedItem);
        const auto resolvedName = ui::Scalar(annotation, "name");
        if (!resolvedName.empty()) ImGui::TextColored(ImVec4(0.45f, 0.93f, 0.81f, 1), "%s", resolvedName.c_str());
        else ImGui::TextDisabled("Equipped item name unavailable");
        if (!annotation.empty()) {
            ImGui::TextDisabled("Name: %s / %s", ui::Scalar(annotation, "name_query").c_str(), ui::Scalar(annotation, "name_source").c_str());
            const auto virtualImage = ui::Scalar(annotation, "native_image_uri");
            ImGui::TextWrapped("Thumbnail unresolved: %s", virtualImage.empty() ? "the native catalog returned no image URI" : "native virtual image URI is retained; extracted pixels are not available");
            if (!virtualImage.empty() && ImGui::TreeNode("Native image provenance")) {
                ImGui::TextWrapped("%s", virtualImage.c_str()); ImGui::TreePop();
            }
            const auto metadataError = ui::Scalar(annotation, "error"), nameError = ui::Scalar(annotation, "name_error");
            if (!metadataError.empty()) ImGui::TextWrapped("Catalog query: %s", metadataError.c_str());
            if (!nameError.empty()) ImGui::TextWrapped("Name query: %s", nameError.c_str());
        } else ImGui::TextWrapped("Native CAS catalog names are unavailable while bulk lookup awaits a stable native contract. Accepted Live and stored-form views resolve exact CASP names. Preset metadata uses a separate native contract.");
        ImGui::BeginDisabled(true); ImGui::Button("Open containing package in Sims 4 Studio"); ImGui::EndDisabled();
        ImGui::TextWrapped("Studio access unresolved: this native catalog ID has no verified CASP resource binding.");
        ImGui::Separator();
        if (ImGui::Button("Copy complete item record")) ImGui::SetClipboardText(g_casSelectedItem.dump(2).c_str());
        for (auto field = g_casSelectedItem.begin(); field != g_casSelectedItem.end(); ++field)
            if (ImGui::TreeNode(field.key().c_str())) { ImGui::TextWrapped("%s", field.value().dump(2).c_str()); ImGui::TreePop(); }
    }
    if (ImGui::CollapsingHeader("Fields returned by CASGetSimInfo")) {
        if (ImGui::SmallButton("Copy exact CAS Sim record")) ImGui::SetClipboardText(info.dump(2).c_str());
        for (auto field = info.begin(); field != info.end(); ++field)
            if (ImGui::TreeNode(field.key().c_str())) { ImGui::TextWrapped("%s", field.value().dump(2).c_str()); ImGui::TreePop(); }
    }
    ImGui::EndChild();
}

static std::string SimPreviewContext() {
    const auto& outfits=ViewedPreviewOutfits();
    const auto forms=g_studioData.find("form_inventory");
    if(forms==g_studioData.end()||forms->empty()||g_studioFormIndex<0||g_studioFormIndex>=int(forms->size())||
       (*forms)[size_t(g_studioFormIndex)]["flags"]!=g_studioData.value("inspected_form_flags",ui::Json()))return {};
    if(outfits.empty()||g_studioOutfitIndex<0||g_studioOutfitIndex>=int(outfits.size()))return {};
    auto context=ui::Scalar(g_studioData,"history_lane")+":"+ui::Scalar(g_studioData,"appearance_sha256")+":"+
        ui::Scalar(g_studioData,"inspected_form_flags")+":"+ui::Scalar(outfits[size_t(g_studioOutfitIndex)],"outfit_id")+":"+
        ui::Scalar(outfits[size_t(g_studioOutfitIndex)],"index")+":"+ui::Scalar(g_studioData,"pending_preview")+":"+ui::Scalar(g_studioData,"visual_form");
    if(g_trayPreviewActive){try{const auto r=tray::Request(g_trayPreviewForms,g_trayPreviewFormIndex,g_trayPreviewOutfitIndex);
        context+=":tray:"+ui::Scalar(r,"sim_id")+":"+ui::Scalar(r,"form")+":"+ui::Scalar(r,"render_sha256")+":"+ui::Scalar(r,"outfit_id")+":"+ui::Scalar(r,"outfit_index");}catch(...){return {};}}
    return context;
}

static bool QueueTrayPreview(bool dataLocked=false) {
    const auto context=SimPreviewContext();if(context.empty())return false;
    const auto r=tray::Request(g_trayPreviewForms,g_trayPreviewFormIndex,g_trayPreviewOutfitIndex);
    std::unique_lock<std::mutex> lock(g_dataMutex,std::defer_lock);if(!dataLocked)lock.lock();if(g_simPreviewBusy||g_commands.size()>=48||context!=g_simPreviewContext)return false;
    QueuedCommand command{"",g_selectionGeneration};command.sim=g_selectedSim;command.simPreview=true;
    command.resourceRow={{"context",context},{"tray_request",r}};g_commands.push_back(std::move(command));
    g_simPreviewBusy=true;g_simPreviewAttemptedContext=context;g_simPreviewStatus="Assembling the exact Tray form in memory...";return true;
}

static bool QueueTrayClipboard() {
    if(!g_trayPreviewActive||g_trayClipboardBusy||g_ownerBlocked||g_ownerSubmissionBusy||g_simPreviewBusy)return false;
    const auto r=tray::Request(g_trayPreviewForms,g_trayPreviewFormIndex,g_trayPreviewOutfitIndex);
    auto label=ui::Scalar(g_trayPreviewForms[size_t(g_trayPreviewFormIndex)],"name")+" / Tray / "+tray::FormName(r["form"].get<unsigned>());
    if(label.size()>256)label=ui::Scalar(r,"sim_id")+" / Tray / "+tray::FormName(r["form"].get<unsigned>());
    std::lock_guard<std::mutex> lock(g_dataMutex);if(g_commands.size()>=48)return false;
    QueuedCommand command{"",g_selectionGeneration};command.sim=g_selectedSim;command.trayClipboard=true;
    command.resourceRow={{"tray_request",r},{"label",label},{"target_form",g_studioData.at("inspected_form_flags")}};g_commands.push_back(std::move(command));g_trayClipboardResult=ui::Json::object();g_trayClipboardBusy=true;return true;
}

// Process a completed scene even when its compact tab is not selected. GPU
// ownership stays on the game's render thread; the worker never touches D3D.
static void SynchronizeSimPreview() {
    const auto context=SimPreviewContext();
    std::shared_ptr<td1::preview::Scene> incoming;
    std::string status;bool changed=false;
    {std::lock_guard<std::mutex> lock(g_dataMutex);changed=context!=g_simPreviewContext;if(changed){g_simPreviewContext=context;g_simPreviewScene.reset();g_simPreviewStatus="Select a form and outfit, then refresh its 3D preview.";}incoming=g_simPreviewScene;status=g_simPreviewStatus;}
    if(changed){if(!g_simPreview.scene.id.empty()){g_simPreviewSavedView=g_simPreview.view;g_simPreviewSavedSim=g_simPreview.scene.sim;}g_simPreview.Reset();}
    if(incoming&&g_simPreview.scene.id!=incoming->id){try{const auto sim=incoming->sim;g_simPreview.Load(g_device,std::move(*incoming));
        if(g_simPreviewKeepCamera&&g_simPreviewSavedSim==sim){g_simPreview.view=g_simPreviewSavedView;auto& v=g_simPreview.view;v.clip=std::clamp(v.clip,-1,int(g_simPreview.scene.clips.size())-1);v.time=v.clip<0?0:std::clamp(v.time,0.f,g_simPreview.scene.clips[size_t(v.clip)].duration);}}
        catch(const std::exception& e){status=e.what();}
        std::lock_guard<std::mutex> lock(g_dataMutex);g_simPreviewScene.reset();g_simPreviewStatus=status;}
}

static void DrawIndependentSimPreview() {
    const auto& outfits=ViewedPreviewOutfits();
    const auto form=ui::Scalar(g_studioData,"inspected_form_flags");
    const auto lane=ui::Scalar(g_studioData,"history_lane"),appearance=ui::Scalar(g_studioData,"appearance_sha256");
    const auto context=SimPreviewContext();
    std::string status;
    {std::lock_guard<std::mutex> lock(g_dataMutex);status=g_simPreviewStatus;}
    ImGui::TextColored(ImVec4(.45f,.95f,.85f,1),"SIM / INDEPENDENT 3D");
    const bool blocked=g_simPreviewBusy||g_ownerBlocked||g_ownerNativeDeliveryBusy||g_ownerSubmissionBusy||g_casSubmissionBusy||g_casBankBusy||g_trayClipboardBusy;
    if(g_trayPreviewActive){
        ImGui::TextWrapped("TRAY SOURCE: %s. Destination stays the Sim / form selected above.",ui::Scalar(g_trayPreviewForms[size_t(g_trayPreviewFormIndex)],"name").c_str());
        ImGui::BeginDisabled(blocked);
        if(ImGui::Button("Return to destination")){g_trayPreviewActive=false;g_simPreviewAttemptedContext.clear();}
        if(g_trayPreviewActive){
            for(size_t i=0;i<g_trayPreviewForms.size();++i){if(i)ImGui::SameLine();const auto label=tray::FormName(g_trayPreviewForms[i]["request"]["form"].get<unsigned>())+"##tray-form"+std::to_string(i);
                if(ImGui::Button(label.c_str())){g_trayPreviewFormIndex=int(i);g_trayPreviewOutfitIndex=0;}}
            const auto& sourceOutfits=g_trayPreviewForms[size_t(g_trayPreviewFormIndex)]["outfits"];
            const auto outfitLabel="Category "+ui::Scalar(sourceOutfits[size_t(g_trayPreviewOutfitIndex)],"category")+" / "+ui::Scalar(sourceOutfits[size_t(g_trayPreviewOutfitIndex)],"number");
            if(ImGui::BeginCombo("Tray source outfit",outfitLabel.c_str())){for(size_t i=0;i<sourceOutfits.size();++i){const auto text="Category "+ui::Scalar(sourceOutfits[i],"category")+" / "+ui::Scalar(sourceOutfits[i],"number")+"##tray-outfit"+std::to_string(i);
                if(ImGui::Selectable(text.c_str(),int(i)==g_trayPreviewOutfitIndex))g_trayPreviewOutfitIndex=int(i);}ImGui::EndCombo();}
            if(ImGui::Button("Copy displayed Tray form"))QueueTrayClipboard();
        }ImGui::EndDisabled();
    }
    ImGui::BeginDisabled(context.empty()||blocked);
    const bool refresh=ImGui::Button("Refresh 3D preview");
    ImGui::EndDisabled();ImGui::SameLine();ImGui::Checkbox("Auto",&g_simPreviewAutomatic);
    if(!context.empty()&&!blocked&&(refresh||(context!=g_simPreviewAttemptedContext&&g_simPreviewAutomatic))){
        if(g_trayPreviewActive)QueueTrayPreview();else{
        const auto& outfit=outfits[size_t(g_studioOutfitIndex)];
        ui::Json value={{"lane",lane},{"appearance_sha256",appearance},{"outfit_index",outfit["index"]},{"outfit_id",outfit["outfit_id"]}};
        const auto pending=ui::Scalar(g_studioData,"pending_preview");if(!pending.empty())value["preview_id"]=pending;
        const ui::Json envelope={{"form",std::stoul(form)},{"value",value.dump()}};
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if(g_commands.size()<48){QueuedCommand command{"/api/command?action=studio_preview_snapshot&sim_id="+UrlEncode(g_selectedSim)+"&value="+UrlEncode(envelope.dump()),g_selectionGeneration};
            command.sim=g_selectedSim;command.simPreview=true;command.resourceRow={{"context",context}};g_commands.push_back(std::move(command));g_simPreviewBusy=true;g_simPreviewAttemptedContext=context;g_simPreviewStatus="Reading the exact selected appearance...";}
        }
    }
    if(!g_simPreview.Texture()&&g_simPreview.scene.id.empty()){ImGui::TextWrapped("%s",status.c_str());return;}
    auto& view=g_simPreview.view;
    if(ImGui::Button("Face"))g_simPreview.Preset(view,"face");
    ImGui::SameLine();if(ImGui::Button("Body"))g_simPreview.Preset(view,"body");
    const auto* selected=SelectedStudioPart();
    ImGui::SameLine();ImGui::BeginDisabled(!selected);
    if(ImGui::Button("Frame item")){try{g_simPreview.Preset(view,"selected",(*selected)["body_type"].get<int>());}catch(const std::exception& e){g_status=e.what();}}
    ImGui::EndDisabled();
    int projection=view.orthographic?1:0;ImGui::SetNextItemWidth(135);
    if(ImGui::Combo("##projection",&projection,"Perspective\0Orthographic\0"))view.orthographic=projection==1;
    ImGui::SameLine();int controls=view.blenderControls?0:1;ImGui::SetNextItemWidth(135);
    if(ImGui::Combo("##camera-controls",&controls,"Blender controls\0Simple controls\0"))view.blenderControls=controls==0;
    if(ImGui::CollapsingHeader("Camera / pose / lighting")) {
      static const char* presets[]={"front","back","left","right","top","reset"};
      for(int i=0;i<6;++i){if(i%3)ImGui::SameLine();if(ImGui::Button(presets[i]))g_simPreview.Preset(view,presets[i]);}
      ImGui::Checkbox("Turntable",&view.autoRotate);
      ImGui::Checkbox("Keep camera across outfits / forms",&g_simPreviewKeepCamera);
      ImGui::SetNextItemWidth(-1);ImGui::SliderFloat("Lens / field of view",&view.fov,10,90,"%.0f degrees");
      ImGui::SetNextItemWidth(-1);ImGui::SliderAngle("Camera roll",&view.roll,-180,180);
      if(!g_simPreview.scene.clips.empty()){
        std::string name=view.clip>=0&&view.clip<int(g_simPreview.scene.clips.size())?g_simPreview.scene.clips[size_t(view.clip)].name:"Bind pose";
        ImGui::SetNextItemWidth(-1);if(ImGui::BeginCombo("##preview-pose",name.c_str())){if(ImGui::Selectable("Bind pose",view.clip<0)){view.clip=-1;view.time=0;}
            for(size_t i=0;i<g_simPreview.scene.clips.size();i++)if(ImGui::Selectable(g_simPreview.scene.clips[i].name.c_str(),view.clip==int(i))){view.clip=int(i);view.time=0;}ImGui::EndCombo();}
        if(view.clip>=0){ImGui::Checkbox("Play animation",&view.playing);ImGui::SameLine();ImGui::SetNextItemWidth(100);ImGui::SliderFloat("Speed",&view.speed,.1f,2.f,"%.1fx");
            ImGui::SetNextItemWidth(-1);if(ImGui::SliderFloat("##preview-time",&view.time,0,g_simPreview.scene.clips[size_t(view.clip)].duration,"%.2fs"))view.playing=false;}
      }
      ImGui::SetNextItemWidth(-1);ImGui::SliderFloat("Light",&view.exposure,.5f,1.8f);
    }
    const float width=std::clamp(ImGui::GetContentRegionAvail().x,64.f,1024.f),height=std::clamp(ImGui::GetContentRegionAvail().y-65,120.f,1024.f);
    try {g_simPreview.Render(g_context,unsigned(width),unsigned(height),ImGui::GetIO().DeltaTime);
        ImGui::Image(reinterpret_cast<ImTextureID>(g_simPreview.Texture()),ImVec2(width,height));
        if(ImGui::IsItemHovered()){auto& io=ImGui::GetIO();
            float zoom=io.MouseWheel;
            const bool middle=ImGui::IsMouseDragging(ImGuiMouseButton_Middle);
            if(view.blenderControls&&middle&&io.KeyCtrl)zoom-=io.MouseDelta.y*.05f;
            view.distance=std::clamp(view.distance*std::exp(-zoom*.12f),.1f,30.f);view.orthoScale=std::clamp(view.orthoScale*std::exp(-zoom*.12f),.05f,30.f);
            if(view.blenderControls?middle&&!io.KeyShift&&!io.KeyCtrl:ImGui::IsMouseDragging(ImGuiMouseButton_Left)){view.yaw-=io.MouseDelta.x*.008f;view.pitch=std::clamp(view.pitch+io.MouseDelta.y*.008f,-1.55f,1.55f);view.autoRotate=false;}
            if(view.blenderControls?middle&&io.KeyShift&&!io.KeyCtrl:ImGui::IsMouseDragging(ImGuiMouseButton_Right)){
                const float scale=(view.orthographic?view.orthoScale:2*view.distance*std::tan(DirectX::XMConvertToRadians(view.fov)*.5f))/height;
                g_simPreview.Pan(-io.MouseDelta.x*scale,io.MouseDelta.y*scale);
            }}
    }catch(const std::exception& e){ImGui::TextWrapped("%s",e.what());}
    ImGui::TextDisabled("%s",view.blenderControls?"MMB orbit | Shift+MMB pan | Ctrl+MMB / wheel zoom":"Left-drag orbit | right-drag pan | wheel zoom");
    ImGui::TextDisabled("Form %u / outfit %s",g_simPreview.scene.form,g_simPreview.scene.outfit.c_str());
    if(!ui::Scalar(g_studioData,"pending_preview").empty())ImGui::TextColored(ImVec4(.95f,.8f,.3f,1),"TRY-ON / Apply to keep, Cancel to discard");
    if(!g_simPreview.scene.warnings.empty()&&ImGui::CollapsingHeader("Preview resource issues"))ImGui::TextWrapped("%s",g_simPreview.scene.warnings.c_str());
}

static void DrawStudioFormStrip() {
    SynchronizeOccultIcons();
    const auto forms=g_studioData.find("form_inventory");if(forms==g_studioData.end()||forms->empty())return;
    ImGui::SeparatorText("APPEARANCE OWNERS / each form keeps its own edits");
    ImGui::BeginDisabled(g_simPreviewBusy||g_ownerBlocked||g_ownerNativeDeliveryBusy||g_ownerSubmissionBusy||g_casSubmissionBusy||g_casBankBusy||g_previewId[0]);
    float remaining=ImGui::GetContentRegionAvail().x;
    for(size_t i=0;i<forms->size();++i){const auto& form=(*forms)[i];const auto label=ui::Scalar(form,"name")+(form.value("current",false)?" / LIVE":"");
        static const std::map<std::string,const char*> names={{"2","ALIEN"},{"4","VAMPIRE"},{"8","MERMAID"},{"16","WITCH"},{"32","WEREWOLF"},{"64","FAIRY"}};
        const auto name=names.find(ui::Scalar(form,"flags"));const char* occult=name==names.end()?nullptr:name->second;
        const float width=ImGui::CalcTextSize(label.c_str()).x+ImGui::GetStyle().FramePadding.x*2+
            (occult&&g_occultIconTextures.count(occult)?ImGui::CalcTextSize("      ").x:0);
        if(i&&remaining>width+ImGui::GetStyle().ItemSpacing.x){ImGui::SameLine();remaining-=ImGui::GetStyle().ItemSpacing.x;}
        else remaining=ImGui::GetContentRegionAvail().x;
        const bool selected=int(i)==g_studioFormIndex;
        ImGui::PushID(int(i));if(selected)ImGui::PushStyleColor(ImGuiCol_Button,ImVec4(.14f,.42f,.39f,1));
        if(OccultButton(label.c_str(),occult)){g_studioFormIndex=int(i);g_studioOutfitIndex=0;g_studioPartIndex=0;QueueStudioAction("studio_status");}
        if(selected)ImGui::PopStyleColor();
        if(ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled))ImGui::SetTooltip("Inspect and edit this stored appearance. The Live Sim does not transform.\nApply or Cancel a pending try-on before choosing another owner.");
        ImGui::PopID();remaining-=width;
    }
    ImGui::EndDisabled();
    const auto& outfits=ViewedStudioOutfits();if(outfits.empty())return;
    g_studioOutfitIndex=std::clamp(g_studioOutfitIndex,0,int(outfits.size())-1);
    ImGui::BeginDisabled(g_previewId[0]||g_simPreviewBusy);
    ImGui::SetNextItemWidth(240);const auto& outfit=outfits[size_t(g_studioOutfitIndex)];
    if(ImGui::BeginCombo("Outfit / exact owner",(OutfitCategory(outfit)+" "+ui::Scalar(outfit,"number")).c_str())) {
        for(size_t i=0;i<outfits.size();++i)if(ImGui::Selectable((OutfitCategory(outfits[i])+" "+ui::Scalar(outfits[i],"number")+"##"+std::to_string(i)).c_str(),g_studioOutfitIndex==int(i))){g_studioOutfitIndex=int(i);g_studioPartIndex=0;}
        ImGui::EndCombo();
    }
    ImGui::EndDisabled();
    ImGui::BeginDisabled(g_previewId[0]);
    ImGui::Checkbox("Apply edits immediately",&g_livePartColor);ImGui::EndDisabled();
    ImGui::SameLine();ImGui::TextDisabled("%s",g_livePartColor?"Undoable on release / unpause for Live visuals":"Try-on only / Apply keeps changes");
    if(g_previewId[0]) {
        ImGui::TextColored(ImVec4(.95f,.8f,.3f,1),"Uncommitted try-on / selected form and outfit");
        if(ImGui::Button("Apply this try-on",ImVec2(155,30)))QueueStudioAction("studio_apply",nullptr,g_previewId);
        ImGui::SameLine();if(ImGui::Button("Discard this try-on",ImVec2(155,30)))QueueStudioAction("studio_cancel",nullptr,g_previewId);
    }
}

static void DrawAppearanceSliders() {
    ImGui::TextWrapped("Face and body controls belong to the selected appearance owner. Preset sculpt bytes and other modifier groups are retained.");
    if(ImGui::CollapsingHeader("All EA / CC modifiers · package conflicts and duplicate definitions")) {
        static char librarySearch[201]="";static bool conflictsOnly=false;static int kind=0,offset=0,group=0;
        const char* kinds[]={"modifier","hotspot","preset","sculpt","all"};
        ImGui::SetNextItemWidth(-1);ImGui::InputTextWithHint("##slider-library-search","Package name, region, modifier key or hotspot",librarySearch,sizeof(librarySearch));
        ImGui::Combo("Resource type",&kind,kinds,5);ImGui::Checkbox("Conflicts / identical CC definitions only",&conflictsOnly);
        const auto query=[&](int next){
            if(g_sliderLibraryBusy)return;offset=std::max(0,next);g_sliderLibraryBusy=true;
            QueuedCommand command{"",g_selectionGeneration};command.resourceOperation=12;
            command.resourceRow={{"search",librarySearch},{"offset",offset},{"limit",25},{"kind",kinds[kind]},{"conflicts_only",conflictsOnly}};
            g_commands.push_back(std::move(command));g_sliderLibraryStatus="Reading immutable slider catalog...";
        };
        ImGui::BeginDisabled(g_sliderLibraryBusy);if(ImGui::Button("Search definitions"))query(0);
        ImGui::SameLine();if(ImGui::Button("Previous definitions"))query(std::max(0,offset-25));
        ImGui::SameLine();if(ImGui::Button("Next definitions"))query(offset+25);ImGui::EndDisabled();
        ImGui::TextWrapped("%s",g_sliderLibraryStatus.c_str());
        ImGui::TextWrapped("Distinct modifier IDs can be edited independently even if a CAS hotspot hides their gesture. Competing bytes at the same modifier ID share one native control. Identical resource bytes are duplicate definitions, not proof a whole package is redundant.");
        const char* groups[]={"Face","Body","Aged face","Aged body"};ImGui::Combo("New modifier storage group",&group,groups,4);
        if(g_sliderLibraryPage.contains("items"))for(const auto& row:g_sliderLibraryPage["items"]) {
            const auto tgi=ui::Scalar(row,"resource_tgi");ImGui::PushID(tgi.c_str());
            const auto conflict=ui::Scalar(row,"conflict");
            const bool collision=conflict=="conflicting-mod-definitions";
            ImGui::TextColored(collision?ImVec4(1,.45f,.25f,1):ImVec4(.65f,.85f,1,1),"%s / %s",ui::Scalar(row,"kind").c_str(),tgi.c_str());
            ImGui::TextWrapped("%s",conflict.c_str());
            if(row.value("unusable_zero_identifier",false))ImGui::TextColored(ImVec4(1,.45f,.25f,1),"Unusable ID zero / cannot be stored on a Sim");
            if(row.contains("hotspot_bindings"))ImGui::TextDisabled("%zu hotspot direction bindings",row["hotspot_bindings"].size());
            bool stored=false;const auto currentRows=g_studioData.find("shape_editor");
            if(currentRows!=g_studioData.end()&&currentRows->is_array())for(const auto& item:*currentRows)
                if(item.value("key",ui::Json())==row["instance"]&&item.value("group",ui::Json())==group+2)stored=true;
            static std::map<std::string,float> initialValues;auto& initial=initialValues[tgi+":"+std::to_string(group)];
            if(row["kind"]=="modifier"){ImGui::SetNextItemWidth(130);ImGui::InputFloat("Initial amount",&initial,0,0,"%.6f");}
            size_t ordinal=0;
            for(const auto& provider:row["providers"]) {
                ImGui::PushID(static_cast<int>(ordinal++));ImGui::TextWrapped("%s · %s",ui::Scalar(provider,"package_name").c_str(),ui::Scalar(provider,"origin").c_str());
                if(ImGui::IsItemHovered())ImGui::SetTooltip("Resource SHA256: %s",ui::Scalar(provider,"resource_sha256").c_str());
                if(row["kind"]=="modifier") {
                    ImGui::BeginDisabled(row["instance"]=="0"||stored||!g_studioData.contains("appearance_sha256")||!g_studioData.contains("history_lane")||!std::isfinite(initial)||g_previewId[0]||g_ownerBlocked||g_ownerSubmissionBusy||g_ownerNativeDeliveryBusy||g_casBankBusy||g_simPreviewBusy);
                    if(ImGui::Button(stored?"Stored: edit value below":"Try this modifier definition")) {
                        ui::Json request={{"group",group+2},{"value",initial},{"resource_tgi",tgi},{"resource_sha256",provider["resource_sha256"]},
                            {"lane",g_studioData["history_lane"]},{"appearance_sha256",g_studioData["appearance_sha256"]}};
                        const auto raw=request.dump();QueueStudioAction(g_livePartColor?"studio_shape_add_live":"studio_shape_add_preview",nullptr,raw.c_str());
                    }ImGui::EndDisabled();
                }
                ImGui::PopID();
            }
            ImGui::Separator();ImGui::PopID();
        }
    }
    if(ImGui::Button("Read this form's sliders"))QueueStudioAction("studio_shape_inspect");
    const auto editor=g_studioData.find("shape_editor");if(editor==g_studioData.end()||!editor->is_array()){ImGui::TextDisabled("Inspect to read every existing face/body modifier and physique component.");return;}
    static std::string context;static std::map<std::string,float> values;
    const auto current=ui::Scalar(g_studioData,"history_lane")+":"+ui::Scalar(g_studioData,"appearance_sha256")+":"+editor->dump();
    if(context!=current){context=current;values.clear();}
    static char search[201]="";static float low=-1,high=1;
    ImGui::SetNextItemWidth(-1);ImGui::InputTextWithHint("##shape-search","Filter region, package or modifier key",search,sizeof(search));
    if(ImGui::CollapsingHeader("Slider display range")){ImGui::SetNextItemWidth(110);ImGui::InputFloat("Low",&low);ImGui::SetNextItemWidth(110);ImGui::InputFloat("High",&high);ImGui::TextWrapped("Display range controls this editor; it is not a verified native or CC limit. Existing values are never clamped.");}
    ImGui::BeginDisabled(g_previewId[0]||g_ownerBlocked||g_ownerSubmissionBusy||g_ownerNativeDeliveryBusy||g_casBankBusy||!std::isfinite(low)||!std::isfinite(high)||low>=high);
    for(const auto& row:*editor) {
        if(!row.is_object()||!row.contains("value")||!row["value"].is_number())continue;
        auto label=ui::Scalar(row,"label");std::string package;
        if(ui::Scalar(row,"field")=="facial_attributes")for(const auto& metadata:g_simPreview.scene.modifiers)
            if(metadata["group"]==row["group"]&&metadata["index"]==row["index"]&&metadata["key"]==row["key"]){label=ui::Scalar(metadata,"label");package=ui::Scalar(metadata,"package");break;}
        if(!TextContainsNoCase(label.c_str(),search)&&!TextContainsNoCase(package.c_str(),search))continue;
        const auto key=ui::Scalar(row,"field")+":"+ui::Scalar(row,"group")+":"+ui::Scalar(row,"index")+":"+ui::Scalar(row,"key");
        const auto inserted=values.emplace(key,row["value"].get<float>());auto& value=inserted.first->second;
        ImGui::PushID(key.c_str());ImGui::TextWrapped("%s",label.c_str());
        if(!package.empty())ImGui::TextDisabled("Source package: %s",package.c_str());
        ImGui::TextDisabled("%s / group %s / row %s",ui::Scalar(row,"field").c_str(),ui::Scalar(row,"group").c_str(),ui::Scalar(row,"index").c_str());
        ImGui::SetNextItemWidth(-1);ImGui::SliderFloat("##amount",&value,std::min(low,row["value"].get<float>()),std::max(high,row["value"].get<float>()),"%.6f");
        const bool released=ImGui::IsItemDeactivatedAfterEdit();
        ImGui::SetNextItemWidth(150);ImGui::InputFloat("Exact value",&value,0,0,"%.9g");
        const bool typed=ImGui::IsItemDeactivatedAfterEdit();
        if(std::isfinite(value)&&value!=row["value"].get<float>()&&((g_livePartColor&&(released||typed))||ImGui::Button("Try on slider change"))) {
            ui::Json request={{"field",row["field"]},{"group",row["group"]},{"index",row["index"]},{"key",row["key"]},{"before",row["value"]},{"value",value},{"lane",g_studioData["history_lane"]},{"appearance_sha256",g_studioData["appearance_sha256"]}};
            const auto raw=request.dump();QueueStudioAction(g_livePartColor?"studio_shape_live":"studio_shape_preview",nullptr,raw.c_str());
        }
        ImGui::Separator();ImGui::PopID();
    }
    ImGui::EndDisabled();
}

static void DrawAppearanceTransfer() {
    if(!ImGui::CollapsingHeader("Copy / paste appearance · any Sim / any form"))return;
    const bool pending=!ui::Scalar(g_studioData,"pending_preview").empty();
    ImGui::BeginDisabled(g_ownerBlocked||g_ownerSubmissionBusy||g_casSubmissionBusy||g_simPreviewBusy);
    if(ImGui::Button("Copy this form appearance"))QueueStudioAction("studio_copy_appearance");
    ImGui::EndDisabled();
    if(g_appearanceClipboard.empty()){ImGui::TextDisabled("Copy a form, or import a Tray appearance through the CLI.");return;}
    const auto& source=g_appearanceClipboard.at("source");
    ImGui::TextWrapped("Source: %s / form %s. Paste affects only the selected destination form.",ui::Scalar(source,"label").c_str(),ui::Scalar(source,"form").c_str());
    static int preset=1;const char* presets[]={"Whole appearance","One outfit","Skin details","Tattoos","Choose fields / categories"};
    if(ImGui::Combo("Paste selection",&preset,presets,5)){
        g_pasteFields.clear();g_pasteBodies.clear();g_pasteScope=preset==0?2:1;
        if(preset==0)for(const auto& name:g_clipboardFields)if(name!="__outfits__")g_pasteFields.insert(name.get<std::string>());
        if(preset==2){g_pasteFields={"skin_tone","skin_tone_val_shift"};}
        if(preset==3){g_pasteFields={"parts_custom_tattoos"};}
        if(preset==2||preset==3)for(const auto& row:g_studioData.value("category_catalog",ui::Json::array())){
            const auto key=ui::Scalar(row,"key");if(key.find(preset==2?"SKINDETAIL":"TATTOO")!=std::string::npos)g_pasteBodies.insert(row["body_type"].get<int>());
        }
    }
    const char* scopes[]={"No outfit parts","One numbered outfit","All source outfits / preserve destination extras"};
    ImGui::Combo("Outfit scope",&g_pasteScope,scopes,3);if(g_pasteScope!=1)g_pasteBodies.clear();
    if(g_pasteScope==1&&!g_clipboardOutfits.empty()){
        g_pasteSourceOutfit=std::clamp(g_pasteSourceOutfit,0,int(g_clipboardOutfits.size())-1);
        const auto& selected=g_clipboardOutfits[size_t(g_pasteSourceOutfit)];
        const auto label=ui::Scalar(selected,"category_name")+" "+ui::Scalar(selected,"number");
        if(ImGui::BeginCombo("Source outfit",label.c_str())){for(size_t i=0;i<g_clipboardOutfits.size();i++){
            const auto& row=g_clipboardOutfits[i];const auto text=ui::Scalar(row,"category_name")+" "+ui::Scalar(row,"number")+"##"+std::to_string(i);
            if(ImGui::Selectable(text.c_str(),int(i)==g_pasteSourceOutfit))g_pasteSourceOutfit=int(i);
        }ImGui::EndCombo();}
        ImGui::TextDisabled("Destination: the form/outfit selected above. Empty selected source categories remove only those slots.");
    }
    if(ImGui::TreeNode("Choose captured appearance fields")){
        for(const auto& field:g_clipboardFields){const auto name=field.get<std::string>();if(name=="__outfits__")continue;
            bool selected=g_pasteFields.count(name)>0;auto label=name;std::replace(label.begin(),label.end(),'_',' ');
            if(ImGui::Checkbox(label.c_str(),&selected)){if(selected)g_pasteFields.insert(name);else g_pasteFields.erase(name);}
        }ImGui::TreePop();
    }
    if(g_pasteScope==1&&ImGui::TreeNode("Choose any CAS categories · empty selection means whole outfit")){
        for(const auto& row:g_studioData.value("category_catalog",ui::Json::array())){
            const int body=row["body_type"].get<int>();bool selected=g_pasteBodies.count(body)>0;
            const auto label=ui::Scalar(row,"label")+"##paste-body-"+std::to_string(body);
            if(ImGui::Checkbox(label.c_str(),&selected)){if(selected)g_pasteBodies.insert(body);else g_pasteBodies.erase(body);}
        }ImGui::TreePop();
    }
    ImGui::BeginDisabled(pending||g_ownerBlocked||g_ownerSubmissionBusy||g_casSubmissionBusy||g_simPreviewBusy||(g_pasteScope==0&&g_pasteFields.empty()));
    if(ImGui::Button(g_livePartColor?"Paste selected fields now":"Try on selected fields")){
        ui::Json selection={{"fields",g_pasteFields},{"outfits",g_pasteScope==0?"none":g_pasteScope==1?"one":"all"},
            {"source_outfit",g_pasteSourceOutfit},{"target_outfit",g_studioOutfitIndex},{"body_types",g_pasteBodies}};
        ui::Json request={{"clipboard_id",g_appearanceClipboard["id"]},{"clipboard_sha256",g_appearanceClipboard["sha256"]},
            {"selection",selection},{"lane",g_studioData["history_lane"]},{"appearance_sha256",g_studioData["appearance_sha256"]}};
        const auto raw=request.dump();QueueStudioAction(g_livePartColor?"studio_paste_live":"studio_paste_preview",nullptr,raw.c_str());
    }
    ImGui::EndDisabled();
    ImGui::TextDisabled("Identity, household, traits, occult powers and progression are preserved. Journal Apply / Discard / Undo retain the destination preimage.");
}

static void DrawTrayGallery() {
    ui::Json page,inspection;std::string status;
    {std::lock_guard<std::mutex> lock(g_dataMutex);page=g_galleryPage;inspection=g_galleryInspection;status=g_galleryStatus;}
    ImGui::SetNextItemWidth(-1);
    if(ImGui::InputTextWithHint("##tray-search","Search household / lot / room names and creators",g_gallerySearch,sizeof(g_gallerySearch),ImGuiInputTextFlags_EnterReturnsTrue)||ImGui::IsItemDeactivatedAfterEdit()){g_galleryOffset=0;g_galleryQueryNeeded=true;}
    ImGui::SetNextItemWidth(150);if(ImGui::Combo("Type##tray",&g_galleryKind,"All items\0Households\0Lots\0Rooms\0")){g_galleryOffset=0;g_galleryQueryNeeded=true;}
    ImGui::SameLine();if(ImGui::SmallButton("Refresh Tray"))g_galleryQueryNeeded=true;
    const ui::Json query={{"text",g_gallerySearch},{"kind",std::array<const char*,4>{"all","household","lot","room"}[std::clamp(g_galleryKind,0,3)]},{"offset",g_galleryOffset},{"limit",60}};
    if(g_galleryQueryNeeded&&!g_galleryBusy&&QueueGallery(8,query))g_galleryQueryNeeded=false;
    ImGui::TextWrapped("%s",status.c_str());
    if(!tray::Page(page,query)){ImGui::TextDisabled("Start live-cas-catalog serve with --tray-root pointing to your Tray library.");return;}
    ImGui::TextDisabled("%s native library items / files read in place",ui::Scalar(page,"total").c_str());
    ImGui::BeginDisabled(g_galleryBusy);
    if(g_galleryOffset&&ImGui::SmallButton("Previous##tray")){g_galleryOffset=g_galleryOffset>=60?g_galleryOffset-60:0;g_galleryQueryNeeded=true;}
    if(!page["next_offset"].is_null()){ImGui::SameLine();if(ImGui::SmallButton("Next##tray")){g_galleryOffset=page["next_offset"].get<size_t>();g_galleryQueryNeeded=true;}}
    ImGui::EndDisabled();
    const auto context=ui::Scalar(page,"library_sha256")+query.dump();
    if(context!=g_galleryImageContext){g_galleryTextures.clear();g_gallerySizes.clear();g_galleryImageAttempted.clear();g_galleryImageContext=context;}
    std::map<std::string,resource::Pixels> pixels;{std::lock_guard<std::mutex> lock(g_dataMutex);pixels.swap(g_galleryPixels);}
    for(const auto& entry:pixels){const auto& p=entry.second;if(!g_device||!p.width||p.rgba.size()!=size_t(p.width)*p.height*4||g_galleryTextures.size()>=60)continue;
        D3D11_TEXTURE2D_DESC d{};d.Width=p.width;d.Height=p.height;d.MipLevels=d.ArraySize=d.SampleDesc.Count=1;d.Format=DXGI_FORMAT_R8G8B8A8_UNORM;d.Usage=D3D11_USAGE_IMMUTABLE;d.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA data{p.rgba.data(),p.width*4,0};Microsoft::WRL::ComPtr<ID3D11Texture2D> texture;Microsoft::WRL::ComPtr<ID3D11ShaderResourceView> view;
        if(SUCCEEDED(g_device->CreateTexture2D(&d,&data,&texture))&&SUCCEEDED(g_device->CreateShaderResourceView(texture.Get(),nullptr,&view))){g_galleryTextures[entry.first]=view;g_gallerySizes[entry.first]=ImVec2(float(p.width),float(p.height));}}
    ImGui::BeginChild("tray-gallery-cards",ImVec2(0,260),true);
    const float width=std::max(70.f,(ImGui::GetContentRegionAvail().x-16)/3),height=width*.67f+60;
    ImGuiListClipper clipper;clipper.Begin(int((page["items"].size()+2)/3),height+ImGui::GetStyle().ItemSpacing.y);
    while(clipper.Step())for(int line=clipper.DisplayStart;line<clipper.DisplayEnd;++line)for(int column=0;column<3;++column){const auto n=size_t(line*3+column);if(n>=page["items"].size())break;
        if(column)ImGui::SameLine();const auto& item=page["items"][n];const auto id=ui::Scalar(item,"item_id");ImGui::PushID(id.c_str());const auto at=ImGui::GetCursorScreenPos();
        ImGui::BeginDisabled(g_galleryBusy||item["status"]!="ready"||item["kind"]!="household"||!ui::Scalar(g_studioData,"pending_preview").empty());
        if(ImGui::Selectable("##tray-card",id==g_gallerySelected,0,ImVec2(width,height))){
            g_gallerySelected=id;g_gallerySimIndex=0;
            QueueGallery(9,{{"item_id",id},{"library_sha256",page["library_sha256"]},{"context",{{"runtime_pid",GetCurrentProcessId()},{"history_lane",g_studioData["history_lane"]}}}});}
        ImGui::EndDisabled();auto* draw=ImGui::GetWindowDrawList();const auto found=g_galleryTextures.find(id);
        if(found!=g_galleryTextures.end()){const auto size=g_gallerySizes.at(id);const float scale=std::min((width-8)/size.x,(height-60)/size.y);draw->AddImage(reinterpret_cast<ImTextureID>(found->second.Get()),ImVec2(at.x+4,at.y+4),ImVec2(at.x+4+size.x*scale,at.y+4+size.y*scale));}
        else draw->AddText(ImVec2(at.x+6,at.y+15),IM_COL32(135,157,180,255),"Native Tray portrait");
        const auto label=ui::Scalar(item,"name"),creator=ui::Scalar(item,"creator");draw->PushClipRect(at,ImVec2(at.x+width,at.y+height),true);draw->AddText(ImVec2(at.x+5,at.y+height-52),IM_COL32(225,236,246,255),label.c_str());
        draw->AddText(ImVec2(at.x+5,at.y+height-31),IM_COL32(135,174,195,255),(creator+" / "+ui::Scalar(item,"kind")).c_str());draw->PopClipRect();
        if(ImGui::IsItemHovered())ImGui::SetTooltip("%s\n%s\n%s files / %s Sims\n%s",label.c_str(),creator.c_str(),ui::Scalar(item,"file_count").c_str(),ui::Scalar(item,"sim_count").c_str(),ui::Scalar(item,"description").c_str());
        if(item["image_count"]>0&&!g_galleryImageAttempted.count(id)&&!g_galleryImageBusy&&!g_galleryBusy&&QueueGallery(10,{{"item_id",id},{"library_sha256",page["library_sha256"]},{"image_index",0}}))g_galleryImageAttempted.insert(id);
        ImGui::PopID();}
    ImGui::EndChild();
    if(inspection.value("item_id",ui::Json())!=g_gallerySelected||inspection.value("library_sha256",ui::Json())!=page["library_sha256"]||!inspection.contains("preview_sims"))return;
    const auto& sims=inspection["preview_sims"];g_gallerySimIndex=std::clamp(g_gallerySimIndex,0,int(sims.size())-1);
    if(ImGui::BeginCombo("Source Sim",ui::Scalar(sims[size_t(g_gallerySimIndex)],"name").c_str())){for(size_t i=0;i<sims.size();++i)if(ImGui::Selectable((ui::Scalar(sims[i],"name")+"##"+ui::Scalar(sims[i],"sim_id")).c_str(),i==size_t(g_gallerySimIndex)))g_gallerySimIndex=int(i);ImGui::EndCombo();}
    const auto& sim=sims[size_t(g_gallerySimIndex)];
    ImGui::BeginDisabled(g_simPreviewBusy||g_ownerBlocked||g_ownerSubmissionBusy||g_casSubmissionBusy||g_casBankBusy||!ui::Scalar(g_studioData,"pending_preview").empty());
    if(ImGui::Button("View this Tray Sim in 3D")){const auto lane=ui::Scalar(g_studioData,"history_lane");
        if(tray::Forms(sim["forms"],GetCurrentProcessId(),lane.substr(0,lane.find(':')))){
            g_previewId[0]=0;g_trayPreviewForms=sim["forms"];g_trayPreviewFormIndex=g_trayPreviewOutfitIndex=0;g_trayPreviewActive=true;g_trayClipboardResult=ui::Json::object();
            g_simPreviewAutomatic=true;g_simPreviewFocusRequested=true;g_simPreviewContext=SimPreviewContext();g_simPreviewAttemptedContext.clear();QueueTrayPreview();}}
    ImGui::EndDisabled();
    ImGui::TextWrapped("Preview switches only the library source. Copy displayed form, then choose the destination occult and selected paste fields below. Native group import/export is available through the Tray CLI.");
}

static void DrawStudioTab(const std::string& reply, ULONGLONG replyMs, bool history) {
    ImGui::BeginDisabled(g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() || g_ownerSubmissionBusy.load() || g_casSubmissionBusy.load() || g_casPendingId[0] || g_casBankBusy.load());
    bool requestedNativeView = g_nativeCasView;
    if (ImGui::Checkbox("Editing in native CAS", &requestedNativeView) && !g_ownerBlocked.load() &&
        !g_ownerNativeDeliveryBusy.load() && !g_ownerSubmissionBusy.load() && !g_casSubmissionBusy.load() && !g_casPendingId[0] && !g_casBankBusy.load()) {
        g_nativeCasView = requestedNativeView;
        g_casClientData = ui::Json::object(); g_casSelectedItem = ui::Json::object();
        if (g_nativeCasView) QueueCasAction({{"operation", "status"}});
    }
    ImGui::EndDisabled();
    if (g_nativeCasView) { DrawNativeCas(reply, replyMs, history); return; }
    UpdateStudioData(reply);
    SynchronizeSimPreview();
    ImGui::TextColored(ImVec4(0.35f, 0.88f, 0.77f, 1), history ? "CAS HISTORY" : "EQUIPPED PART INSPECTOR");
    ImGui::TextDisabled("Current form / exact targets / retained branches");
    if (g_studioData.value("history_runtime_only", ui::Json(false)) == true)
        ImGui::TextDisabled("Session history: this view is tied to the current game session.");
    if (ImGui::Button("Inspect / refresh", ImVec2(160, 0))) { g_studioItemsContext.clear(); QueueStudioAction("studio_status"); }
    ImGui::SameLine(); ImGui::TextDisabled("%u checkpoints", static_cast<unsigned>(g_studioData.value("history_nodes", ui::Json::array()).size()));
    if(!history){
        ImGui::SetNextItemWidth(150);
        if(ImGui::Combo("Layout",&g_studioLayout,"Balanced\0Character\0Catalog\0Custom\0")) {
            if(g_studioLayout<3){g_studioPreviewShare=g_studioLayout==1?.55f:g_studioLayout==2?.30f:.38f;g_libraryColumns=g_studioLayout==2?6:g_studioLayout==1?3:4;g_studioEquippedSidebar=false;}
        }
        ImGui::SameLine();ImGui::SetNextItemWidth(140);if(ImGui::SliderFloat("3D width",&g_studioPreviewShare,.25f,.65f,"%.2f"))g_studioLayout=3;
        DrawStudioFormStrip();ImGui::Checkbox("Equipped sidebar",&g_studioEquippedSidebar);
    }
    if(history||g_studioEquippedSidebar){ImGui::BeginChild("studio-equipped", ImVec2(history?270:230, 0), true); DrawEquippedList(); ImGui::EndChild(); ImGui::SameLine();}
    const float roomWidth=ImGui::GetContentRegionAvail().x;
    const bool previewColumn=!history&&roomWidth>=570;
    if(previewColumn){g_simPreviewFocusRequested=false;ImGui::BeginChild("independent-sim-preview",ImVec2(std::clamp(roomWidth*g_studioPreviewShare,230.f,std::max(230.f,roomWidth-290.f)),0),true);DrawIndependentSimPreview();ImGui::EndChild();ImGui::SameLine();}
    ImGui::BeginChild("studio-workspace", ImVec2(0, 0), true);
    if (ImGui::CollapsingHeader("CAS form acceptance / review",history?ImGuiTreeNodeFlags_DefaultOpen:ImGuiTreeNodeFlags_None)) DrawCasBankTransaction();
    const auto& viewedOutfits = ViewedStudioOutfits();
    const bool wardrobeOpen=ImGui::CollapsingHeader("Wardrobe / independent hair");
    if (wardrobeOpen && !viewedOutfits.empty() && ImGui::Button("Duplicate selected outfit / preview")) {
        const auto& outfit = viewedOutfits[static_cast<size_t>(g_studioOutfitIndex)];
        const ui::Json request = {{"source", outfit["index"]}, {"category", outfit["category"]},
            {"lane", ui::Scalar(g_studioData, "history_lane")}, {"appearance_sha256", ui::Scalar(g_studioData, "appearance_sha256")}};
        const auto value = request.dump(); QueueStudioAction("studio_outfit_duplicate", nullptr, value.c_str());
    }
    const auto hairPolicy = g_studioData.find("hair_policy");
    if (wardrobeOpen && hairPolicy != g_studioData.end()) {
        bool enabled = (*hairPolicy)["enabled"].get<bool>();
        if (ImGui::Checkbox("Keep hairstyles / colors independent per outfit", &enabled))
            QueueStudioAction(enabled ? "studio_hair_enable" : "studio_hair_disable");
        if (enabled) {
            ImGui::TextDisabled("Every category and outfit number / each form / event driven");
            ImGui::TextWrapped("Retain all owners before CAS using the review above. After verified Live return, hair choices require original outfit UID, category and ordinal through the typed CLI. The obsolete pre-entry hair-target buttons are removed; F11 does not infer which hairstyle change was intended.");
            const auto error = ui::Scalar(*hairPolicy, "last_error");
            if (!error.empty()) ImGui::TextWrapped("Retained protection issue: %s", error.c_str());
        }
        ImGui::Separator();
    }
    if (history) {
        ImGui::SetNextItemWidth(-1); ImGui::InputTextWithHint("##checkpoint-label", "Name a checkpoint", g_checkpointLabel, sizeof(g_checkpointLabel));
        if (ImGui::Button("Capture checkpoint")) QueueStudioAction("studio_checkpoint", nullptr, g_checkpointLabel);
        DrawStudioTimeline();
        if (ImGui::Button("Preview Undo")) QueueStudioAction("studio_undo");
        ImGui::SameLine(); if (ImGui::Button("Preview Redo")) QueueStudioAction("studio_redo", nullptr, g_historyId);
        ImGui::SameLine(); ImGui::BeginDisabled(!g_historyId[0]);
        if (ImGui::Button("Preview Jump")) QueueStudioAction("studio_jump", nullptr, g_historyId);
        ImGui::EndDisabled();
        if (g_studioData.value("legacy_outfit_history_retained", false)) ImGui::TextDisabled("Earlier outfit-only history retained separately.");
        ImGui::TextWrapped("Full native Sim records and their runtime schemas are retained at checkpoints. Undo restores captured appearance; gameplay records remain available for inspection.");
    } else if (ImGui::BeginTabBar("live-cas-workspace")) {
        if (ImGui::BeginTabItem("Equipped / colors",nullptr,g_workspaceFocusRequested==0?ImGuiTabItemFlags_SetSelected:ImGuiTabItemFlags_None)) {if(g_workspaceFocusRequested==0)g_workspaceFocusRequested=-1; DrawStudioParts(); ImGui::EndTabItem(); }
        if(!previewColumn&&ImGui::BeginTabItem("3D Sim",nullptr,g_simPreviewFocusRequested?ImGuiTabItemFlags_SetSelected:ImGuiTabItemFlags_None)){
            g_simPreviewFocusRequested=false;DrawIndependentSimPreview();ImGui::EndTabItem();}
        if (ImGui::BeginTabItem("EA + CC library", nullptr, (g_libraryFocusRequested||g_workspaceFocusRequested==1) ? ImGuiTabItemFlags_SetSelected : ImGuiTabItemFlags_None)) {
            g_libraryFocusRequested = false;if(g_workspaceFocusRequested==1)g_workspaceFocusRequested=-1; DrawLiveLibrary(); ImGui::EndTabItem();
        }
        if(ImGui::BeginTabItem("Tray gallery",nullptr,g_workspaceFocusRequested==3?ImGuiTabItemFlags_SetSelected:ImGuiTabItemFlags_None)){if(g_workspaceFocusRequested==3)g_workspaceFocusRequested=-1;DrawTrayGallery();ImGui::EndTabItem();}
        if(ImGui::BeginTabItem("Face / body sliders",nullptr,g_workspaceFocusRequested==2?ImGuiTabItemFlags_SetSelected:ImGuiTabItemFlags_None)){if(g_workspaceFocusRequested==2)g_workspaceFocusRequested=-1;DrawAppearanceSliders();ImGui::EndTabItem();}
        ImGui::EndTabBar();
    }
    const auto forms = g_studioData.find("form_inventory");
    if(!history){
        if(ui::Scalar(g_studioData,"inspected_form_flags")=="32"&&ImGui::CollapsingHeader("Werewolf appearance · EA or Human / CC")){
            bool human=g_studioData.value("werewolf_appearance_style",std::string("ea"))=="human_cc";
            ImGui::BeginDisabled(!ui::Scalar(g_studioData,"pending_preview").empty()||g_ownerBlocked||g_ownerSubmissionBusy||g_casSubmissionBusy||g_simPreviewBusy);
            if(ImGui::Checkbox("Human / personal CC look",&human)){QueueAction(human?"werewolf_human_on":"werewolf_human_off");QueueStudioAction("studio_status");}
            ImGui::BeginDisabled(human);
            if(ImGui::Button("Try EA-generated Werewolf defaults"))QueueStudioAction("studio_werewolf_ea_preview");
            ImGui::EndDisabled();ImGui::EndDisabled();
            ImGui::TextWrapped("Both looks retain their own edits. EA defaults are a try-on with Apply / Discard / Undo. Werewolf membership and progression stay intact.");
        }
        DrawAppearanceTransfer();
    }
    if (forms != g_studioData.end() && !forms->empty() && ImGui::CollapsingHeader("All captured appearance fields / preset results")) {
        const auto& form = (*forms)[static_cast<size_t>(g_studioFormIndex)];
        for (const auto& field : form["appearance_fields"]) {
            const auto label = ui::Scalar(field, "name");
            if (ImGui::TreeNode(label.c_str())) {
                const auto value = field["value"].dump();
                ImGui::TextDisabled("Type: %s / full value retained", ui::Scalar(field, "kind").c_str());
                if (ImGui::SmallButton("Copy exact field value")) ImGui::SetClipboardText(value.c_str());
                ImGui::TextWrapped("%s", value.substr(0, 1024).c_str());
                if (value.size() > 1024) ImGui::TextDisabled("Long value: copy/export for the complete record.");
                ImGui::TreePop();
            }
        }
    }
    ImGui::SeparatorText("Accepted preview");
    const auto delta = g_studioData.find("preview_delta");
    if (g_previewId[0] && delta != g_studioData.end()) {
        ImGui::TextWrapped("Changes: %s", ui::Scalar(*delta, "summary").c_str());
        if (delta->contains("part_changes")) for (const auto& row : (*delta)["part_changes"]) {
            const auto& before = row["before"]; const auto& after = row["after"];
            ImGui::TextWrapped("%s / category %s / outfit %s: %s -> %s", ui::Scalar(row, "label").c_str(),
                ui::Scalar(row, "category").c_str(), ui::Scalar(row, "outfit_ordinal").c_str(),
                before.is_object() ? ui::Scalar(before, "id").c_str() : "absent",
                after.is_object() ? ui::Scalar(after, "id").c_str() : "absent");
        }
    } else ImGui::TextDisabled("No pending preview");
    ImGui::BeginDisabled(!g_previewId[0]);
    if (ImGui::Button("Apply preview", ImVec2(150, 34))) QueueStudioAction("studio_apply", nullptr, g_previewId);
    ImGui::SameLine(); if (ImGui::Button("Cancel", ImVec2(90, 34))) QueueStudioAction("studio_cancel", nullptr, g_previewId);
    ImGui::EndDisabled();
    if (ImGui::CollapsingHeader("Recovery / exact identities")) {
        ImGui::TextWrapped("%s", ui::Scalar(g_studioData, "history_lane").c_str());
        ImGui::InputText("History node", g_historyId, sizeof(g_historyId));
        ImGui::InputText("Preview ID", g_previewId, sizeof(g_previewId));
        if (ImGui::Button("Resolve interrupted transaction")) QueueStudioAction("studio_recover");
    }
    ImGui::EndChild();
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
    g_nativeCasPaneVisible = ui::CasNativePaneVisible(g_visible.load(), g_nativeCasView, g_activeTab);
    g_nativeCasPaneMs = GetTickCount64();
    const auto display = ImGui::GetIO().DisplaySize;
    ImGui::SetNextWindowSize(ImVec2(std::max(400.0f, std::min(1180.0f, display.x - 40)), std::max(400.0f, std::min(920.0f, display.y - 60))), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImVec2(20, 30), ImGuiCond_FirstUseEver);
    ImGui::Begin("APEX / Occult Hybrid Studio", nullptr, ImGuiWindowFlags_NoCollapse);
    const auto windowPos = ImGui::GetWindowPos(), windowSize = ImGui::GetWindowSize();
    g_pointerGate.left = static_cast<int>(windowPos.x); g_pointerGate.top = static_cast<int>(windowPos.y);
    g_pointerGate.right = static_cast<int>(windowPos.x + windowSize.x); g_pointerGate.bottom = static_cast<int>(windowPos.y + windowSize.y);
    std::string status, json, sim, reply;
    ULONGLONG replyMs = 0;
    std::vector<std::string> logs;
    { std::lock_guard<std::mutex> lock(g_dataMutex); status = g_status; json = g_json; logs = g_logLines; sim = g_selectedSim; reply = g_commandReply; replyMs = g_commandReplyMs; }

    ImGui::TextColored(ImVec4(0.45f, 0.95f, 1.0f, 1.0f), "%s", status.c_str());
    ImGui::SameLine(); ImGui::TextDisabled("F%u toggle | hidden: no HTTP polling", g_toggleKey - VK_F1 + 1);
    std::string commandMessage = ExtractJsonValue(reply, "message");
    if (!commandMessage.empty()) ImGui::TextWrapped("Last command: %s", commandMessage.c_str());
    ui::OwnerObservation owner;
    { std::lock_guard<std::mutex> lock(g_dataMutex); owner = g_ownerObservation; }
    if (!owner.lastReply.empty()) {
        ImGui::TextWrapped("Owner result: %s / %s", ui::Scalar(owner.lastReply, "request_id").c_str(),
            (g_ownerBlocked.load() ? "unresolved; commands paused" : "resolved"));
        const auto ownerMessage = ui::Scalar(owner.lastReply, "message");
        if (!ownerMessage.empty()) ImGui::TextWrapped("Last owner check: %s", ownerMessage.c_str());
        if (g_ownerBlocked.load()) {
            ImGui::BeginDisabled(!ui::OwnerObservationDue(owner, GetTickCount64(), true, true));
            if (ImGui::Button("Check retained owner")) QueueOwnerObservation(true);
            ImGui::EndDisabled();
            if (owner.checking) { ImGui::SameLine(); ImGui::TextDisabled("Checking the same owner ID..."); }
            QueueOwnerObservation(false);
        }
        if (ImGui::TreeNode("Last owner status result")) { ImGui::TextWrapped("%s", owner.lastReply.dump(2).c_str()); ImGui::TreePop(); }
    }
    char simBuf[64] = {};
    strncpy_s(simBuf, sim.c_str(), _TRUNCATE);
    ImGui::SetNextItemWidth(260);
    ImGui::BeginDisabled(g_casSubmissionBusy.load() || g_ownerBlocked.load() || g_ownerNativeDeliveryBusy.load() ||
        g_ownerSubmissionBusy.load() || g_casBankBusy.load() || g_casPendingId[0] || g_casRefreshClock.unresolved);
    if (ImGui::InputText("Target Sim ID", simBuf, sizeof(simBuf))) {
        std::lock_guard<std::mutex> lock(g_dataMutex);
        if (!g_ownerSubmissionBusy.load() && !g_ownerBlocked.load() && !g_ownerNativeDeliveryBusy.load() &&
            !g_casSubmissionBusy.load() && !g_casBankBusy.load() && !g_casPendingId[0] && !g_casRefreshClock.unresolved) {
        g_selectedSim = simBuf;
        ++g_selectionGeneration;
        g_json = "{}";
        g_commandReply = "{}";
        g_commandReplyMs = 0;
        g_previewId[0] = '\0'; g_historyId[0] = '\0';
        g_studioData = ui::Json::object(); g_studioLastReply.clear();
        g_casClientData = ui::Json::object(); g_casSelectedItem = ui::Json::object(); g_casLastReply.clear(); g_casPendingId[0] = '\0'; g_casSnapshotMs = 0; g_casDiagnostics = ui::Json::object();
        g_casRefreshClock = {}; g_casDiagnosticReply.clear(); g_casDiagnosticMs = 0; g_casDiagnosticsSeenMs = 0;
        g_casAutoRetainedId.clear(); g_casReconcileClock = {}; g_casReconcileSeen = g_casReconcileReceipt;
        g_casRefreshSeen = g_casRefreshReceipt; g_casAutoMessage.clear();
        g_studioOutfitIndex = 0; g_studioPartIndex = 0;
        g_status = "Selection changed; waiting for current data";
        g_lastStatusMs = 0;
        }
    }
    ImGui::EndDisabled();
    ImGui::SameLine(); ActionButton("Refresh", "status", nullptr, nullptr, ImVec2(86,0));
    ImGui::SameLine(); ActionButton("Health", "health", nullptr, nullptr, ImVec2(86,0));
    if (ImGui::CollapsingHeader("Diagnostics")) {
        ActionButton("Diagnostics", "diagnostics", nullptr, nullptr, ImVec2(112,0));
        ImGui::SameLine(); ActionButton("QA Self-Test", "qa_self_test", nullptr, nullptr, ImVec2(128,0));
        ImGui::SameLine(); ActionButton("Code Audit", "code_audit", nullptr, nullptr, ImVec2(112,0));
        ImGui::SameLine(); ActionButton("Research Audit", "research_audit", nullptr, nullptr, ImVec2(136,0));
        ImGui::SameLine(); ActionButton("Final Audit", "final_audit", nullptr, nullptr, ImVec2(116,0));
    }
    std::string warn = ui::StatusScalar(ui::ReadObject(json), "drift_warning_count");
    if (!warn.empty() && warn != "0") {
        ImGui::Separator();
        ImGui::TextColored(ImVec4(1.0f, 0.35f, 0.40f, 1.0f), "DRIFT WARNING: %s issue(s) found. Open Drift Guard or press Fix.", warn.c_str());
        ImGui::SameLine(); if (ImGui::Button("Fix Selected")) QueueAction("fix_occult_drift", ActiveOccultName());
        ImGui::SameLine(); if (ImGui::Button("Scan Again")) QueueAction("scan_occult_drift");
    }
    ImGui::Separator();

    DrawQuickAutonomy();
    const char* tabs[] = {"Apex", "Forms", "Saved Forms", "Drift Guard", "Reference Shots", "CAS Tools", "CAS Categories", "MCCC Shield", "Raw Flags", "Sims/API", "Log", "CAS History", "Equipped CAS"};
    ImGui::BeginChild("navigation", ImVec2(160, 0), true);
    for (int i = 0; i < IM_ARRAYSIZE(tabs); ++i) {
        if (ImGui::Selectable(tabs[i], g_activeTab == i)) g_activeTab = i;
    }
    ImGui::EndChild();
    ImGui::SameLine();

    ImGui::BeginChild("main_left", ImVec2(g_activeTab >= 11 ? 0 : ImGui::GetContentRegionAvail().x * 0.65f, 0), false);
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
    else if (g_activeTab == 11) DrawStudioTab(reply, replyMs, true);
    else if (g_activeTab == 12) DrawStudioTab(reply, replyMs, false);
    ImGui::EndChild();
    if (g_activeTab < 11) {
        ImGui::SameLine(); ImGui::BeginChild("right_dock", ImVec2(0, 0), true);
        DrawLogDock(logs); ImGui::EndChild();
    }
    DrawConfirmation();
    g_nativeCasPaneVisible = ui::CasNativePaneVisible(g_visible.load(), g_nativeCasView, g_activeTab);
    g_nativeCasPaneMs = GetTickCount64();
    ImGui::End();
}

static void ResetRenderer() {
    g_visible = false;
    g_nativeCasPaneVisible = false;
    CleanupRenderTarget();
    CleanupResourceTexture();
    CleanupLibraryImages();
    CleanupOccultIcons();
    g_simPreview.Reset();
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

static bool IsGameCanvas(HWND window) {
    DWORD process = 0; RECT client{}; wchar_t windowClass[256]{};
    if (!IsWindow(window) || !GetClientRect(window, &client) ||
        !GetClassNameW(window, windowClass, 256)) return false;
    GetWindowThreadProcessId(window, &process);
    return GameCanvas(process, GetCurrentProcessId(), IsWindowVisible(window) != 0,
        IsIconic(window) != 0, GetAncestor(window, GA_ROOT) == window,
        client.right - client.left, client.bottom - client.top, windowClass);
}

static BOOL CALLBACK CountGameCanvas(HWND window, LPARAM result) {
    if (IsGameCanvas(window)) ++*reinterpret_cast<unsigned*>(result);
    return TRUE;
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
    unsigned matchingWindows = 0;
    if (!IsGameCanvas(desc.OutputWindow) || !EnumWindows(CountGameCanvas,
        reinterpret_cast<LPARAM>(&matchingWindows)) ||
        !UniqueGameCanvas(true, matchingWindows)) return false;
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
    const int capture = g_loaderStatus.load() >= 2 ? g_captureRequest.exchange(0) : 0;
    if (capture && capture != 4) SaveBackbufferBmp(sc, capture);
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
                if (capture == 4) SaveBackbufferBmp(sc, 4);
            }
        }
    } else g_nativeCasPaneVisible = false;
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
    if (!td1::CaptureReady(td1::g_hooked.load(), td1::g_loaderStatus.load(), false, td1::g_visible.load())) return -1;
    int idle = 0;
    return td1::g_captureRequest.compare_exchange_strong(idle, 3) ? 0 : -2;
}
// Disposable-profile CLI input runs inside the already-authorized game. It
// cannot address EA/UAC/another process, and stale viewport coordinates fail.
// Thread-local DPI scope: never change the game's process DPI configuration.
struct ApexInputDpi {
    using SetContext = HANDLE (WINAPI *)(HANDLE);
    SetContext set = reinterpret_cast<SetContext>(GetProcAddress(GetModuleHandleW(L"user32.dll"), "SetThreadDpiAwarenessContext"));
    HANDLE previous = set ? set(reinterpret_cast<HANDLE>(static_cast<INT_PTR>(-4))) : nullptr; // PER_MONITOR_AWARE_V2
    ~ApexInputDpi() { if (set && previous) set(previous); }
};
extern "C" __declspec(dllexport) int WINAPI ApexGameInputVersion() { return 2; }
extern "C" __declspec(dllexport) int WINAPI ApexGameInputState() { return td1::g_inputState.load(); }
extern "C" __declspec(dllexport) int WINAPI ApexGameCursorX() { return td1::g_cursorX.load(); }
extern "C" __declspec(dllexport) int WINAPI ApexGameCursorY() { return td1::g_cursorY.load(); }
// Observational diagnostics only. Input Version 2 and every ownership/focus
// guard remain unchanged. HWNDs use signed int32 ABI bits, not decimal casts.
extern "C" __declspec(dllexport) int WINAPI ApexGameInputMetric(int index) {
    std::lock_guard<std::recursive_mutex> renderLock(td1::g_renderMutex);
    ApexInputDpi dpi;
    const HWND expected = td1::g_hwnd, foreground = GetForegroundWindow();
    DWORD expectedPid = 0, foregroundPid = 0;
    if (expected) GetWindowThreadProcessId(expected, &expectedPid);
    if (foreground) GetWindowThreadProcessId(foreground, &foregroundPid);
    switch (index) {
    case 0: case 1: {
        RECT client{};
        if (!expected || !GetClientRect(expected, &client)) return -1;
        return index == 0 ? client.right - client.left : client.bottom - client.top;
    }
    case 2: case 3: {
        POINT origin{};
        if (!expected || !ClientToScreen(expected, &origin)) return -1;
        return index == 2 ? origin.x : origin.y;
    }
    case 4: return td1::ui::MetricHandleBits(foregroundPid);
    case 5: return td1::ui::MetricHandleBits(expectedPid);
    case 6: return td1::ui::MetricHandleBits(reinterpret_cast<uintptr_t>(expected));
    case 7: return td1::ui::MetricHandleBits(reinterpret_cast<uintptr_t>(foreground));
    case 8: {
        const HWND expectedRoot = expected ? GetAncestor(expected, GA_ROOT) : nullptr;
        const HWND foregroundRoot = foreground ? GetAncestor(foreground, GA_ROOT) : nullptr;
        return expectedRoot && foregroundRoot && expectedRoot == foregroundRoot ? 1 : 0;
    }
    default: return -1;
    }
}
extern "C" __declspec(dllexport) int WINAPI ApexCaptureOverlay() {
    if (!td1::CaptureReady(td1::g_hooked.load(), td1::g_loaderStatus.load(), true, td1::g_visible.load())) return -1;
    int idle = 0;
    return td1::g_captureRequest.compare_exchange_strong(idle, 4) ? 0 : -2;
}
extern "C" __declspec(dllexport) int WINAPI ApexOverlayStudio(unsigned long long sim, int tab) {
    const auto activeTab = td1::ui::StudioOverlayTab(tab);
    const bool nativeCas = tab == 13 || tab == 14;
    if (!sim || activeTab < 0 || !td1::g_hooked.load()) return -1;
    std::lock_guard<std::recursive_mutex> lock(td1::g_renderMutex);
    if (td1::g_ownerBlocked.load() || td1::g_ownerNativeDeliveryBusy.load() || td1::g_ownerSubmissionBusy.load() ||
        td1::g_casSubmissionBusy.load() || td1::g_casBankBusy.load() || td1::g_casPendingId[0] || td1::g_casRefreshClock.unresolved) return -2;
    {
        std::lock_guard<std::mutex> data(td1::g_dataMutex);
        if (td1::g_ownerBlocked.load() || td1::g_ownerNativeDeliveryBusy.load() || td1::g_ownerSubmissionBusy.load() || td1::g_casBankBusy.load()) return -2;
        td1::g_selectedSim = std::to_string(sim); ++td1::g_selectionGeneration;
        td1::g_commandReply = "{}"; td1::g_studioLastReply.clear();
        td1::g_commandReplyMs = 0;
        td1::g_studioData = td1::ui::Json::object();
        td1::g_casClientData = td1::ui::Json::object(); td1::g_casSelectedItem = td1::ui::Json::object();
        td1::g_casLastReply.clear(); td1::g_casPendingId[0] = '\0'; td1::g_casSnapshotMs = 0;
        td1::g_casRefreshClock = {}; td1::g_casDiagnosticReply.clear(); td1::g_casDiagnosticMs = 0;
        td1::g_casAutoRetainedId.clear(); td1::g_casReconcileClock = {}; td1::g_casReconcileSeen = td1::g_casReconcileReceipt;
        td1::g_casDiagnosticsSeenMs = 0; td1::g_casRefreshSeen = td1::g_casRefreshReceipt; td1::g_casAutoMessage.clear();
        td1::g_historyId[0] = '\0'; td1::g_previewId[0] = '\0';
    }
    td1::g_activeTab = activeTab; td1::g_visible = true; td1::g_nativeCasView = nativeCas;
    td1::g_libraryFocusRequested = tab == 15;
    td1::g_nativeCasPaneVisible = nativeCas; td1::g_nativeCasPaneMs = GetTickCount64();
    if (nativeCas) {
        if (!td1::QueueCasAction({{"operation", "status"}})) return -3;
    } else td1::QueueAction("studio_status"); // The canonical game owner supplies accepted Live/bank data.
    return 0;
}
// Typed preview/review controls: no OS input or foreground changes. Review
// actions use the same once-only Source queue as the F11 transaction drawer.
extern "C" __declspec(dllexport) const char* WINAPI ApexSimPreviewControl(const char* raw) {
    static std::string reply;
    std::lock_guard<std::recursive_mutex> renderLock(td1::g_renderMutex);
    std::lock_guard<std::mutex> data(td1::g_dataMutex);
    using namespace td1;
    try{
        if(!raw||strnlen_s(raw,ui::kMaxOwnerJsonBytes+1)>ui::kMaxOwnerJsonBytes)throw std::runtime_error("Bounded preview control required.");
        const auto request=ui::ParseObject(raw);const auto operation=ui::Scalar(request,"operation");
        if(operation=="cas-review"){
            const auto action=ui::Scalar(request,"action"); std::string queued;
            if (action=="status") {
                if (request.size()!=2) throw std::runtime_error("CAS review status accepts no intent fields.");
                if (!ui::BankCurrent(g_casBank,g_selectedSim,g_selectionGeneration) && !g_casBankBusy &&
                    !g_casBank.busy && !g_casBank.unresolved) {
                    g_casBank={}; g_casBank.sim=g_selectedSim; g_casBank.generation=g_selectionGeneration;
                }
            } else {
                if (!g_hooked || g_done || g_ownerBlocked || g_ownerNativeDeliveryBusy || g_ownerSubmissionBusy ||
                    g_casSubmissionBusy || g_casBankBusy || g_casBank.busy || g_casBank.unresolved ||
                    g_casPendingId[0] || g_casRefreshClock.unresolved || !g_commands.empty())
                    throw std::runtime_error("Resolve the existing native owner before changing the CAS review model.");
                if (action=="select") {
                    const auto sim=ui::Scalar(request,"sim_id");
                    if (request.size()!=5 || !ui::BankControlExpected(g_casBank,request.at("expected")) ||
                        !ui::BankControlRoster(request.at("roster"),sim) ||
                        (g_casBank.sim!=sim && (g_casBank.localPrepared ||
                            (g_casBank.prepareAttempted && g_casBank.phase!="completed"))))
                        throw std::runtime_error("Select requires the exact current view and a completed Source Sim roster; resolve any prepared plan first.");
                    if (g_selectedSim!=sim || !ui::BankCurrent(g_casBank,g_selectedSim,g_selectionGeneration)) {
                        g_selectedSim=sim; ++g_selectionGeneration;
                        g_casBank={}; g_casBank.sim=sim; g_casBank.generation=g_selectionGeneration;
                    }
                    g_commandReply="{}"; g_commandReplyMs=0; g_studioLastReply.clear(); g_studioData=ui::Json::object();
                    g_casClientData=ui::Json::object(); g_casSelectedItem=ui::Json::object();
                    g_previewId[0]=0; g_historyId[0]=0; g_nativeCasView=false; g_activeTab=1; g_visible=true;
                    queued="cas_bank_status";
                } else {
                    if (!ui::BankCurrent(g_casBank,g_selectedSim,g_selectionGeneration) ||
                        !ui::BankControlIntent(g_casBank,request,queued))
                        throw std::runtime_error("CAS review view, nonce, form decision or exact outfit target is stale or unavailable.");
                }
                if (!queued.empty() && !QueueCasBankActionLocked(queued))
                    throw std::runtime_error("CAS review queue refused the action; inspect its retained model before another operation.");
            }
            reply=ui::Json{{"ok",true},{"operation","cas-review"},{"action",action},{"view",ui::BankControlView(g_casBank)},
                {"queued_action",queued},{"source_receipt",g_casBank.lastReply},{"source_failure",g_casBank.lastFailure},
                {"message",g_casBank.message},{"runtime_pid",GetCurrentProcessId()},{"foreground_required",false},
                {"game_appearance_written",false},{"native_model_control",true},{"physical_imgui_click_proven",false},
                {"automatic_replay_allowed",false}}.dump();
            return reply.c_str();
        } else if(operation=="tray"){
            if(request.size()!=5||!g_hooked||g_simPreviewBusy||g_trayClipboardBusy||g_ownerBlocked||g_ownerNativeDeliveryBusy||g_ownerSubmissionBusy||g_casSubmissionBusy||g_casBankBusy||g_casPendingId[0]||g_commands.size()>=48)throw std::runtime_error("Resolve the current owner before previewing a Tray source.");
            const auto& selection=request.at("selection");
            if(!ui::StudioDocument(selection)||!ui::Scalar(selection,"pending_preview").empty()||selection.at("runtime_pid")!=GetCurrentProcessId())throw std::runtime_error("Fresh idle destination selection required.");
            const auto lane=ui::Scalar(selection,"history_lane"),guid=lane.substr(0,lane.find(':'));
            const auto sim=tray::DestinationSim(selection);
            if(!ui::ExactUint64Identity(ui::Json(sim))||!tray::Forms(request.at("forms"),GetCurrentProcessId(),guid)||!ui::CasInt(request.at("form"),1,64)||!ui::CasInt(request.at("outfit_index"),0,1023))throw std::runtime_error("Exact represented Tray source and destination required.");
            int formIndex=-1,targetIndex=-1;const auto& rows=request.at("forms");
            for(size_t i=0;i<rows.size();++i)if(rows[i]["request"]["form"]==request["form"])formIndex=int(i);
            const int outfitIndex=request["outfit_index"].get<int>();const auto source=tray::Request(rows,formIndex,outfitIndex);
            const auto& targetForms=selection["form_inventory"];
            for(size_t i=0;i<targetForms.size();++i)if(targetForms[i]["flags"]==selection["inspected_form_flags"])targetIndex=int(i);
            if(targetIndex<0||targetForms[size_t(targetIndex)]["outfit_inventory"].empty())throw std::runtime_error("Destination appearance owner has no outfit.");
            g_selectedSim=sim;++g_selectionGeneration;g_studioData=selection;g_studioFormIndex=targetIndex;g_studioOutfitIndex=0;g_studioPartIndex=0;
            g_trayPreviewForms=rows;g_trayPreviewFormIndex=formIndex;g_trayPreviewOutfitIndex=outfitIndex;g_trayPreviewActive=true;
            g_previewId[0]=0;
            g_trayClipboardResult=ui::Json::object();
            g_studioLastReply.clear();g_commandReply="{}";g_commandReplyMs=0;g_nativeCasView=false;g_activeTab=12;g_visible=true;g_simPreviewAutomatic=true;
            g_simPreviewContext=SimPreviewContext();g_simPreviewAttemptedContext=g_simPreviewContext;
            if(!g_simPreview.scene.id.empty()){g_simPreviewSavedView=g_simPreview.view;g_simPreviewSavedSim=g_simPreview.scene.sim;}
            g_simPreview.Reset();g_simPreviewScene.reset();g_simPreviewFocusRequested=true;
            QueuedCommand command{"",g_selectionGeneration};command.sim=sim;command.simPreview=true;command.resourceRow={{"context",g_simPreviewContext},{"tray_request",source}};
            g_commands.push_back(std::move(command));g_simPreviewBusy=true;g_simPreviewStatus="Loading the selected Tray form without importing a Sim...";
        }else if(operation=="tray-copy"){
            if(request.size()!=3||!g_trayPreviewActive||g_simPreviewBusy||g_trayClipboardBusy||g_ownerSubmissionBusy||g_ownerBlocked||g_casSubmissionBusy||g_casBankBusy||g_commands.size()>=48)throw std::runtime_error("Resolve the current preview/owner before copying its exact Tray form.");
            const auto r=tray::Request(g_trayPreviewForms,g_trayPreviewFormIndex,g_trayPreviewOutfitIndex);
            if(request.at("form")!=r.at("form")||request.at("native_sha256")!=r.at("native_sha256"))throw std::runtime_error("Displayed Tray form differs from copy intent.");
            QueuedCommand command{"",g_selectionGeneration};command.sim=g_selectedSim;command.trayClipboard=true;command.resourceRow={{"tray_request",r},{"label",ui::Scalar(r,"sim_id")+" / Tray / "+tray::FormName(r["form"].get<unsigned>())},{"target_form",g_studioData.at("inspected_form_flags")}};
            g_commands.push_back(std::move(command));g_trayClipboardResult=ui::Json::object();g_trayClipboardBusy=true;
        }else if(operation=="load"){
            if(request.size()!=4||g_simPreviewBusy||g_ownerBlocked||g_ownerNativeDeliveryBusy||g_ownerSubmissionBusy||g_casSubmissionBusy||g_casBankBusy||g_casPendingId[0])throw std::runtime_error("Another owner operation is unresolved or preview fields differ.");
            const auto& job=request.at("job");const auto& selection=request.at("selection");
            if(!g_hooked||!job.value("ok",false)||ui::Scalar(job,"state")!="ready"||!resource::Hex(ui::Scalar(job,"request_id"),64)||
               !resource::Hex(ui::Scalar(job,"scene_id"),64)||!ui::ExactUint64Identity(job.at("sim_id"))||
               !(job.at("outfit_id")=="0"||ui::ExactUint64Identity(job.at("outfit_id")))||!ui::CasInt(job.at("outfit_index"),0,1023)||!ui::StudioDocument(selection)||
               job.at("runtime_pid")!=GetCurrentProcessId()||job.at("appearance_sha256")!=selection.at("appearance_sha256")||
               job.at("form")!=selection.at("inspected_form_flags")||job.at("lane")!=selection.at("history_lane")||
               job.at("preview_id")!=selection.at("pending_preview"))throw std::runtime_error("Preview selection differs from its completed owner job.");
            const auto sim=ui::Scalar(job,"sim_id");const auto lane=ui::Scalar(job,"lane");
            if(lane.find(":"+sim+":"+ui::Scalar(job,"form")+":")==std::string::npos)throw std::runtime_error("Preview lane belongs to another Sim.");
            int formIndex=-1,outfitIndex=-1;const auto& forms=selection.at("form_inventory");
            for(size_t i=0;i<forms.size();i++)if(forms[i].at("flags")==job.at("form")){
                formIndex=int(i);const auto& outfits=!ui::Scalar(selection,"pending_preview").empty()&&selection.contains("preview_outfit_inventory")&&selection["preview_outfit_inventory"].is_array()?selection.at("preview_outfit_inventory"):forms[i].at("outfit_inventory");
                for(size_t k=0;k<outfits.size();k++)if(outfits[k].at("outfit_id")==job.at("outfit_id")&&outfits[k].at("index")==job.at("outfit_index"))outfitIndex=int(k);
            }
            if(formIndex<0||outfitIndex<0||g_commands.size()>=48)throw std::runtime_error("Exact preview form/outfit is unavailable.");
            if(!request.at("automatic").is_boolean())throw std::runtime_error("Boolean automatic preview flag required.");
            g_trayPreviewActive=false;
            g_selectedSim=sim;++g_selectionGeneration;g_studioData=selection;g_studioFormIndex=formIndex;g_studioOutfitIndex=outfitIndex;g_studioPartIndex=0;
            strncpy_s(g_previewId,ui::Scalar(selection,"pending_preview").c_str(),_TRUNCATE);
            g_studioLastReply.clear();g_commandReply="{}";g_commandReplyMs=0;g_nativeCasView=false;g_activeTab=12;g_visible=true;
            g_simPreviewContext=SimPreviewContext();g_simPreviewAttemptedContext=g_simPreviewContext;g_simPreviewAutomatic=request.at("automatic").get<bool>();
            if(!g_simPreview.scene.id.empty()){g_simPreviewSavedView=g_simPreview.view;g_simPreviewSavedSim=g_simPreview.scene.sim;}
            g_simPreview.Reset();g_simPreviewScene.reset();g_simPreviewFocusRequested=true;
            QueuedCommand command{"",g_selectionGeneration};command.sim=sim;command.simPreview=true;command.resourceRow={{"context",g_simPreviewContext},{"job",job}};
            g_commands.push_back(std::move(command));g_simPreviewBusy=true;g_simPreviewStatus="Loading the exact memory-only preview...";
        }else if(operation=="mode"){
            if(request.size()!=2||!request.contains("apply_mode")||(request["apply_mode"]!="live"&&request["apply_mode"]!="preview")||g_previewId[0])throw std::runtime_error("Resolve the current try-on before selecting a typed apply mode.");
            g_livePartColor=request["apply_mode"]=="live";
        }else if(operation=="library-select"){
            auto selection=request;selection.erase("operation");
            if(g_libraryPage.value("query",ui::Json())!=CurrentLibraryQuery()||!library::VisibleSelection(g_libraryPage,g_libraryInspection,selection)||!QueueLibrary(5,selection,true))throw std::runtime_error("Select an exact visible item or its currently inspected swatch; wait for the current library request.");
            g_workspaceFocusRequested=1;g_activeTab=12;g_visible=true;
        }else if(operation=="thumbnail"){
            if(request.size()!=3||!resource::Hash(request,"part_id")||request.value("index_sha256",ui::Json())!=g_libraryPage.value("index_sha256",ui::Json()))throw std::runtime_error("Exact current catalog thumbnail selection required.");
            ui::Json item;if(g_libraryInspection.value("index_sha256",ui::Json())==request["index_sha256"]&&g_libraryInspection.contains("item")&&g_libraryInspection["item"].value("part_id",ui::Json())==request["part_id"])item=g_libraryInspection["item"];
            else if(g_libraryPage.contains("items"))for(const auto& row:g_libraryPage["items"])if(row["part_id"]==request["part_id"])item=row;
            if(item.empty()||!QueueThumbnail(item,true))throw std::runtime_error("Thumbnail is unresolved or its exact candidate is unavailable.");
            g_workspaceFocusRequested=1;g_activeTab=12;g_visible=true;
        }else if(operation=="gallery-query"){
            if(request.size()!=2||!request.contains("query")||!tray::Query(request["query"]))throw std::runtime_error("Typed Tray gallery page required.");
            const auto& q=request["query"];strcpy_s(g_gallerySearch,sizeof(g_gallerySearch),q["text"].get<std::string>().c_str());g_galleryOffset=q["offset"].get<size_t>();g_galleryKind=q["kind"]=="household"?1:q["kind"]=="lot"?2:q["kind"]=="room"?3:0;
            if(q["limit"]!=60||!QueueGallery(8,q,true))throw std::runtime_error("Gallery query is busy or page size differs.");g_galleryQueryNeeded=false;g_workspaceFocusRequested=3;
            g_activeTab=12;g_visible=true;
        }else if(operation=="gallery-select"){
            auto selection=request;selection.erase("operation");if(!tray::Selection(selection)||selection.size()!=2||selection.value("library_sha256",ui::Json())!=g_galleryPage.value("library_sha256",ui::Json())||!ui::StudioDocument(g_studioData)||!ui::Scalar(g_studioData,"pending_preview").empty())throw std::runtime_error("Exact current Tray item and idle destination required.");
            bool present=false;for(const auto& item:g_galleryPage["items"])if(item["item_id"]==selection["item_id"]&&item["kind"]=="household"&&item["status"]=="ready")present=true;
            selection["context"]={{"runtime_pid",GetCurrentProcessId()},{"history_lane",g_studioData["history_lane"]}};
            if(!present||!QueueGallery(9,selection,true))throw std::runtime_error("Household source absent or gallery busy.");g_gallerySelected=ui::Scalar(selection,"item_id");g_gallerySimIndex=0;
        }else if(operation=="gallery-view"){
            if(request.size()!=2||!ui::ExactUint64Identity(request.at("sim_id"))||g_galleryBusy||g_simPreviewBusy||g_ownerBlocked||g_ownerSubmissionBusy||g_casBankBusy||!ui::Scalar(g_studioData,"pending_preview").empty()||g_galleryInspection.value("item_id",ui::Json())!=g_gallerySelected)throw std::runtime_error("Exact ready Tray source Sim and idle destination required.");
            ui::Json forms;for(const auto& sim:g_galleryInspection.at("preview_sims"))if(sim["sim_id"]==request["sim_id"])forms=sim["forms"];
            const auto lane=ui::Scalar(g_studioData,"history_lane");if(!tray::Forms(forms,GetCurrentProcessId(),lane.substr(0,lane.find(':'))))throw std::runtime_error("Represented Tray forms differ.");
            g_previewId[0]=0;g_trayPreviewForms=forms;g_trayPreviewFormIndex=g_trayPreviewOutfitIndex=0;g_trayPreviewActive=true;g_simPreviewAutomatic=true;g_simPreviewFocusRequested=true;g_simPreviewContext=SimPreviewContext();g_simPreviewAttemptedContext.clear();if(!QueueTrayPreview(true))throw std::runtime_error("Tray preview was not queued.");
        }else if(operation=="workspace"){
            if(request.size()!=2||!request.contains("values")||!library::Workspace(request["values"]))throw std::runtime_error("Typed layout, columns and catalog filters required.");
            const auto& values=request["values"];
            if(values.contains("layout")) {
                const auto layout=values["layout"];
                g_studioLayout=layout=="balanced"?0:layout=="character"?1:layout=="catalog"?2:3;
                if(g_studioLayout<3){g_studioPreviewShare=g_studioLayout==1?.55f:g_studioLayout==2?.30f:.38f;g_libraryColumns=g_studioLayout==2?6:g_studioLayout==1?3:4;g_studioEquippedSidebar=false;}
            }
            if(values.contains("preview_share")){g_studioPreviewShare=values["preview_share"].get<float>();g_studioLayout=3;}
            if(values.contains("columns"))g_libraryColumns=values["columns"].get<int>();
            if(values.contains("sidebar"))g_studioEquippedSidebar=values["sidebar"].get<bool>();
            if(values.contains("thumbnails"))g_libraryShowImages=values["thumbnails"].get<bool>();
            if(values.contains("generate_thumbnails"))g_generateMissingThumbnails=values["generate_thumbnails"].get<bool>();
            if(values.contains("gender"))g_libraryImageGender=values["gender"]=="male"?0:1;
            if(values.contains("query")) {
                const auto& q=values["query"];const auto text=q["text"].get<std::string>();strcpy_s(g_librarySearch,sizeof(g_librarySearch),text.c_str());
                g_libraryBody=q["body_type"].is_null()?-1:q["body_type"].get<int64_t>();
                g_libraryOrigin=q["origin"].is_null()?0:q["origin"]=="mod"?1:2;
                g_itemNameMode=q["name_mode"]=="preferred"?0:q["name_mode"]=="package"?1:2;
                g_libraryView=q["view"]=="all"?0:q["view"]=="favorites"?1:2;
                g_libraryOffset=q["offset"].get<size_t>();g_libraryAuthor=q.value("author",std::string());
                const auto sort=q.value("sort",std::string("name"));g_librarySort=sort=="name"?0:sort=="package"?1:sort=="creator"?2:3;
                g_libraryQueryNeeded=true;
            }
            if(values.contains("tab")){g_workspaceFocusRequested=values["tab"]=="equipped"?0:values["tab"]=="library"?1:values["tab"]=="tray"?3:2;g_libraryFocusRequested=false;}
            g_activeTab=12;g_visible=true;
        }else if(operation=="view"){
            if(request.size()!=3||ui::Scalar(request,"scene_id")!=g_simPreview.scene.id||g_simPreview.scene.id.empty()||g_simPreviewBusy)throw std::runtime_error("Exact loaded preview scene required.");
            g_simPreview.Control(request.at("values"));
        }else if(operation=="clear"){
            if(request.size()!=1||g_simPreviewBusy)throw std::runtime_error("Preview is still assembling.");
            g_trayPreviewActive=false;g_trayPreviewForms=ui::Json::array();g_simPreview.Reset();g_simPreviewScene.reset();g_simPreviewSavedSim.clear();g_simPreviewAutomatic=false;g_simPreviewStatus="Preview released.";
        }else if(operation!="status"||request.size()!=1)throw std::runtime_error("Unknown typed preview operation.");
        const auto& v=g_simPreview.view;
        reply=ui::Json({{"ok",true},{"busy",g_simPreviewBusy.load()},{"staged",bool(g_simPreviewScene)},
            {"ready",!g_simPreview.scene.id.empty()&&g_simPreview.frames>0},
            {"scene_id",g_simPreview.scene.id},{"sim_id",g_simPreview.scene.sim},{"form",g_simPreview.scene.form},{"outfit_id",g_simPreview.scene.outfit},{"outfit_index",g_simPreview.scene.outfitIndex},
            {"frames",g_simPreview.frames},{"meshes",g_simPreview.scene.meshes.size()},{"clips",g_simPreview.scene.clips.size()},
            {"status",g_simPreviewStatus},{"warnings",g_simPreview.scene.warnings},{"apply_mode",g_livePartColor?"live":"preview"},{"foreground_required",false},{"game_appearance_written",false},
            {"tray_source",g_trayPreviewActive},{"destination_sim_id",g_selectedSim},{"clipboard_busy",g_trayClipboardBusy.load()},{"appearance_clipboard",g_appearanceClipboard},
            {"clipboard_result",g_trayClipboardResult},
            {"thumbnail",g_thumbnailReceipt},{"thumbnail_busy",g_thumbnailBusy.load()},
            {"library_selection",{{"busy",g_libraryBusy.load()},{"part_id",g_libraryInspection.value("item",ui::Json::object()).value("part_id",ui::Json())},{"index_sha256",g_libraryInspection.value("index_sha256",ui::Json())},
                {"resource_tgi",g_libraryInspection.value("item",ui::Json::object()).value("resource_tgi",ui::Json())},{"resource_sha256",g_libraryInspection.value("item",ui::Json::object()).value("resource_sha256",ui::Json())},
                {"swatch_count",g_libraryInspection.value("swatches",ui::Json::object()).value("total",ui::Json())},{"swatch_offset",g_libraryInspection.value("swatches",ui::Json::object()).value("offset",ui::Json())},
                {"swatch_colors_argb",g_libraryInspection.value("item",ui::Json::object()).value("metadata",ui::Json::object()).value("swatch_colors_argb",ui::Json::array())}}},
            {"gallery",{{"busy",g_galleryBusy.load()},{"ready",!g_galleryPage.empty()},{"library_sha256",g_galleryPage.value("library_sha256",ui::Json())},{"total",g_galleryPage.value("total",ui::Json())},{"selected_item",g_gallerySelected},{"source_ready",g_galleryInspection.value("item_id",ui::Json())==g_gallerySelected},{"source_sim_count",g_galleryInspection.value("preview_sims",ui::Json::array()).size()},{"image_count",g_galleryTextures.size()},{"status",g_galleryStatus}}},
            {"workspace",{{"layout",std::array<const char*,4>{"balanced","character","catalog","custom"}[std::clamp(g_studioLayout,0,3)]},{"preview_share",g_studioPreviewShare},{"columns",g_libraryColumns},{"sidebar",g_studioEquippedSidebar},{"thumbnails",g_libraryShowImages},{"gender",g_libraryImageGender==0?"male":"female"},{"query",CurrentLibraryQuery()},
                {"catalog_ready",!g_libraryPage.empty()&&g_libraryPage.value("query",ui::Json())==CurrentLibraryQuery()}, {"catalog_total",g_libraryPage.value("total",ui::Json())},{"catalog_index_sha256",g_libraryPage.value("index_sha256",ui::Json())},{"thumbnail_ready_count",g_libraryImageTextures.size()},{"catalog_status",g_libraryStatus}}},
            {"view",{{"yaw",v.yaw},{"pitch",v.pitch},{"distance",v.distance},{"height",v.height},{"pan",v.pan},{"pan_depth",v.panDepth},{"roll",v.roll},{"fov",v.fov},{"ortho_scale",v.orthoScale},{"projection",v.orthographic?"orthographic":"perspective"},{"controls",v.blenderControls?"blender":"simple"},{"time",v.time},
              {"clip",v.clip},{"speed",v.speed},{"exposure",v.exposure},{"playing",v.playing},{"turntable",v.autoRotate},{"body_type",v.body}}}}).dump();
    }catch(const std::exception& e){reply=ui::Json({{"ok",false},{"reason",e.what()},{"foreground_required",false},{"game_appearance_written",false}}).dump();}
    return reply.c_str();
}

extern "C" __declspec(dllexport) int WINAPI ApexGameInput(int command, int x, int y, int width, int height) {
    std::lock_guard<std::recursive_mutex> renderLock(td1::g_renderMutex);
    ApexInputDpi dpi;
    HWND hwnd = td1::g_hwnd;
    DWORD owner = 0;
    RECT rect{};
    if (!td1::g_hooked.load() || !hwnd || !IsWindow(hwnd) || !IsWindowVisible(hwnd)) return -1;
    GetWindowThreadProcessId(hwnd, &owner);
    if (owner != GetCurrentProcessId()) return -2;
    if (command != 4 && GetAncestor(GetForegroundWindow(), GA_ROOT) != GetAncestor(hwnd, GA_ROOT)) return -2;
    if (!GetClientRect(hwnd, &rect) || rect.right != width || rect.bottom != height) return -3;
    if (command == 2) {
        if (x != VK_F11 && x != VK_ESCAPE && x != VK_RETURN && x != VK_TAB && x != VK_SPACE) return -4;
    } else if ((command != 1 && command != 3 && command != 4) || x < 0 || y < 0 || x >= width || y >= height) return -4;
    bool idle = false;
    if (!td1::g_inputBusy.compare_exchange_strong(idle, true)) return -6;
    td1::g_inputState = 1; td1::g_cursorX = -1; td1::g_cursorY = -1;
    if (command == 4) {
        // Address the verified game's event queue only. No SetForegroundWindow,
        // physical cursor movement or SendInput; acceptance is not UI proof.
        const LPARAM position = MAKELPARAM(x, y);
        const bool moved = PostMessageW(hwnd, WM_MOUSEMOVE, 0, position) != 0;
        const bool down = moved && PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, position) != 0;
        const bool up = down && PostMessageW(hwnd, WM_LBUTTONUP, 0, position) != 0;
        td1::g_inputState = moved && down && up ? 4 : -5;
        td1::g_inputBusy = false;
        return 0;
    }
    // Move is delivered on a game-owned worker, then allowed to traverse the
    // real event/render loop BEFORE down. Same-batch move/down used stale CAS
    // hit-testing. Every click checks the exact physical cursor and ownership.
    std::thread([hwnd, command, x, y, width, height] {
        ApexInputDpi workerDpi;
        auto valid = [&] {
            RECT current{}; DWORD pid = 0;
            GetWindowThreadProcessId(hwnd, &pid);
            return IsWindow(hwnd) && pid == GetCurrentProcessId() &&
                GetAncestor(GetForegroundWindow(), GA_ROOT) == GetAncestor(hwnd, GA_ROOT) &&
                GetClientRect(hwnd, &current) && current.right == width && current.bottom == height;
        };
        int outcome = -8;
        if (valid()) {
            if (command != 2) {
                POINT screen{x, y};
                const int left = GetSystemMetrics(SM_XVIRTUALSCREEN), top = GetSystemMetrics(SM_YVIRTUALSCREEN);
                const int sw = GetSystemMetrics(SM_CXVIRTUALSCREEN), sh = GetSystemMetrics(SM_CYVIRTUALSCREEN);
                if (ClientToScreen(hwnd, &screen) && sw > 1 && sh > 1 && screen.x >= left && screen.y >= top && screen.x < left + sw && screen.y < top + sh) {
                    INPUT move{}; move.type = INPUT_MOUSE;
                    move.mi.dx = static_cast<LONG>((2LL * (screen.x - left) + 1) * 65536 / (2LL * sw));
                    move.mi.dy = static_cast<LONG>((2LL * (screen.y - top) + 1) * 65536 / (2LL * sh));
                    move.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
                    outcome = SendInput(1, &move, sizeof(INPUT)) == 1 ? -7 : -5;
                    Sleep(120);
                    POINT actual{};
                    if (GetCursorPos(&actual) && ScreenToClient(hwnd, &actual)) {
                        td1::g_cursorX = actual.x; td1::g_cursorY = actual.y;
                        if (actual.x == x && actual.y == y && valid()) outcome = 2;
                    }
                } else outcome = -3;
            } else outcome = 2;
            if (outcome == 2 && command != 3 && valid()) {
                INPUT down{}; down.type = command == 2 ? INPUT_KEYBOARD : INPUT_MOUSE;
                if (command == 2) down.ki.wVk = static_cast<WORD>(x);
                else down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
                if (SendInput(1, &down, sizeof(INPUT)) == 1) {
                    td1::g_inputState = 3; Sleep(100);
                    INPUT up{}; up.type = down.type;
                    if (command == 2) { up.ki.wVk = static_cast<WORD>(x); up.ki.dwFlags = KEYEVENTF_KEYUP; }
                    else up.mi.dwFlags = MOUSEEVENTF_LEFTUP;
                    outcome = SendInput(1, &up, sizeof(INPUT)) == 1 ? 4 : -5;
                } else outcome = -5;
            } else if (outcome == 2 && command == 3) outcome = 4;
        }
        td1::g_inputState = outcome; td1::g_inputBusy = false;
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
    // Exercise the actual owner recovery and queue guards with deterministic
    // receipts. This test never starts HTTP or repeats a command submission.
    const std::string ownerId(32, 'a'), nativeId(32, 'b');
    const auto uncertain = ui::Json({{"ok",false},{"outcome","unresolved"},
        {"request_id",ownerId},{"request_state","unknown"}}).dump();
    g_selectedSim = "22"; g_selectionGeneration = 2; g_visible = true;
    g_commandReply = "{\"message\":\"current selection\"}";
    QueuedCommand historical{"/api/command?action=studio_status&sim_id=11", 1}; historical.sim = "11";
    if (!RetainCommandOwner(historical, uncertain)) return 35;
    g_ownerObservation.lastCheckMs = 0;
    if (!QueueOwnerObservation(true) || g_commands.size() != 1 ||
        g_commands.front().path != "/api/requests/status?request_id=" + ownerId ||
        !g_commands.front().ownerObservation || g_commands.front().sim != "11") return 36;
    const auto historicalCheck = g_commands.front(); g_commands.pop_front();
    g_visible = false;
    if (BeginOwnerObservation(historicalCheck) || g_ownerObservation.checking) return 46;
    g_visible = true; g_ownerObservation.lastCheckMs = 0;
    if (!QueueOwnerObservation(true) || g_commands.size() != 1) return 47;
    const auto resumedCheck = g_commands.front(); g_commands.pop_front();
    if (!BeginOwnerObservation(resumedCheck)) return 48;
    ApplyOwnerObservation(resumedCheck, true, ui::Json({{"request_id",ownerId},{"state","completed"},
        {"result",{{"ok",true},{"message","historical result"}}}}).dump());
    if (g_ownerBlocked.load() || !g_ownerObservation.requestId.empty() ||
        ui::Scalar(ui::ParseObject(g_commandReply),"message") != "current selection") return 37;
    g_ownerObservation = {}; g_ownerOriginalCommand = {}; g_selectedSim.clear(); g_selectionGeneration = 0;
    g_commandReply = "{}";
    // Exercise the production typed bank queue and same-UUID completion
    // without any HTTP submission or native Sim access.
    g_selectedSim="11"; g_selectionGeneration=3;
    if (!QueueCasBankAction("cas_bank_status") || g_commands.size()!=1 || !g_casBankBusy.load() ||
        g_commands.front().path!="/api/command?action=cas_bank_ui_status&sim_id=11" ||
        QueueCommand("/api/command?action=status") || QueueCasBankAction("cas_bank_begin")) return 49;
    const auto bankCommand=g_commands.front(); g_commands.pop_front();
    ui::BankApply(g_casBank,"11",3,"cas_bank_status",ui::Json{{"ok",false},{"request_id",ownerId},{"request_state","unknown"}});
    if (!RetainCommandOwner(bankCommand,uncertain)) return 50;
    g_ownerObservation.lastCheckMs=0;
    if (!QueueOwnerObservation(true) || g_commands.size()!=1) return 51;
    const auto bankCheck=g_commands.front(); g_commands.pop_front();
    ApplyOwnerObservation(bankCheck,true,ui::Json{{"request_id",ownerId},{"state","completed"},
        {"result",{{"ok",true},{"blocked",false},{"legacy_pending_not_converted",false},
            {"clock_proof_validated",false},{"review_nonce",nativeId},{"review_state","idle"}}}}.dump());
    if (g_casBankBusy.load() || g_ownerBlocked.load() || !ui::BankCanBegin(g_casBank) ||
        !QueueCasBankAction("cas_bank_begin") || g_commands.size()!=1 ||
        g_commands.front().path!="/api/command?action=cas_bank_begin&sim_id=11") return 52;
    g_commands.clear(); g_casBank={}; g_casBankBusy=false;
    g_selectedSim.clear(); g_selectionGeneration=0; g_commandReply="{}";
    std::string preSubmitRefusal;
    if (!HttpOwnedCommand("/api/command?action=status&request_id=forbidden",preSubmitRefusal) ||
        ui::Scalar(ui::ParseObject(preSubmitRefusal),"state")!="rejected" ||
        ui::ParseObject(preSubmitRefusal).contains("request_id")) return 53;
    if (!LoadRealD3D11()) return 10;
    HWND window = CreateDummyWindow();
    if (!window) return 11;
    // A 64-pixel helper clips the workspace before nested tab content can be
    // laid out. Exercise the actual workstation at a realistic hidden-window
    // client size; this never activates or displays the helper window.
    if (!SetWindowPos(window, nullptr, 0, 0, 1280, 1024, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)) return 56;
    DXGI_SWAP_CHAIN_DESC desc{};
    desc.BufferCount = 1; desc.BufferDesc.Width = desc.BufferDesc.Height = 64;
    desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.OutputWindow = window; desc.SampleDesc.Count = 1; desc.Windowed = TRUE;
    IDXGISwapChain* swap = nullptr; ID3D11Device* device = nullptr; ID3D11DeviceContext* context = nullptr;
    HRESULT hr = g_realCreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, 0,
        nullptr, 0, D3D11_SDK_VERSION, &desc, &swap, &device, nullptr, &context);
    if (FAILED(hr)) return 12;
    // Capture the actual WARP chain before ImGui/device globals exist. The
    // temporary output is independent of every Sims profile and deleted here.
    char temporary[MAX_PATH]{}, captureFile[MAX_PATH]{};
    if (!swap || !device || !context || !GetTempPathA(MAX_PATH, temporary) ||
        !GetTempFileNameA(temporary, "APX", 0, captureFile)) return 60;
    const bool previousVisibility = g_visible.exchange(false);
    g_smokeCapturePath = captureFile;
    ID3D11Texture2D* plainBuffer = nullptr; ID3D11RenderTargetView* plainView = nullptr;
    const float plainColor[] = {1.0f,0.0f,0.0f,1.0f};
    bool plainReady = SUCCEEDED(swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void**>(&plainBuffer))) &&
        plainBuffer && SUCCEEDED(device->CreateRenderTargetView(plainBuffer,nullptr,&plainView)) && plainView;
    if (plainReady) context->ClearRenderTargetView(plainView,plainColor);
    const bool copied = plainReady && SaveBackbufferBmp(swap,3);
    if (plainView) plainView->Release(); if (plainBuffer) plainBuffer->Release();
    std::ifstream plainFile(captureFile,std::ios::binary);
    const std::string plain((std::istreambuf_iterator<char>(plainFile)),std::istreambuf_iterator<char>());
    plainFile.close(); DeleteFileA(captureFile); g_smokeCapturePath.clear();
    if (!copied || plain.size()!=54+64*64*3 || plain.substr(0,2)!="BM" ||
        static_cast<unsigned char>(plain[54])!=0 || static_cast<unsigned char>(plain[55])!=0 ||
        static_cast<unsigned char>(plain[56])!=255 || g_device || g_context ||
        ImGui::GetCurrentContext() || g_renderedFrames.load()!=0 || g_visible.load()) return 61;
    g_captureCompleted=0; g_visible=previousVisibility;
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
    g_selectedSim = "11"; g_selectionGeneration = 3; g_casAutoRefresh = false;
    QueuedCommand nativeCommand{"/api/command?action=cas_ui_request&sim_id=11", 3};
    nativeCommand.sim = "11"; nativeCommand.casRequestId = nativeId;
    if (!RetainCommandOwner(nativeCommand, uncertain)) return 38;
    g_ownerObservation.lastCheckMs = 0;
    if (!QueueOwnerObservation(true) || g_commands.size() != 1) return 39;
    const auto ownerCheck = g_commands.front(); g_commands.pop_front();
    const auto pendingNative = ui::Json({{"ok",false},{"outcome","pending-client"},{"cas_request_id",nativeId}});
    ApplyOwnerObservation(ownerCheck, true, ui::Json({{"request_id",ownerId},{"state","failed"},{"result",pendingNative}}).dump());
    if (g_ownerBlocked.load() || !g_ownerNativeDeliveryBusy.load() ||
        QueueCasAction({{"operation","status"}}) || QueueAutomaticCasRefresh("11") ||
        QueueCommand("/api/command?action=cas_ui_request&sim_id=11")) return 40;
    auto drawNativeReceipt = [&](const std::string& staleSnapshot) {
        ImGui_ImplDX11_NewFrame(); ImGui_ImplWin32_NewFrame(); ImGui::NewFrame();
        ImGui::Begin("owner recovery smoke"); DrawNativeCas(staleSnapshot, 0, false); ImGui::End(); ImGui::Render();
    };
    drawNativeReceipt("{}"); // Deliberately predates worker publication.
    if (g_ownerNativeDeliveryBusy.load() || std::string(g_casPendingId) != nativeId ||
        std::string(g_casPendingId) == ownerId || QueueCasAction({{"operation","undo"}}) ||
        ApexOverlayStudio(22, 11) != -2 || g_selectedSim != "11") return 41;
    const auto failedNative = ui::Json({{"ok",false},{"cas_request_id",nativeId},{"cas_request_state","failed"},
        {"message","Native action refused."}}).dump();
    { std::lock_guard<std::mutex> lock(g_dataMutex); PublishCommandReply(failedNative, GetTickCount64()); }
    if (!g_ownerNativeDeliveryBusy.load() || QueueCommand("/api/command?action=status")) return 42;
    drawNativeReceipt("{}");
    if (g_ownerNativeDeliveryBusy.load() || g_casPendingId[0] || g_casRefreshClock.unresolved) return 43;
    // The same reservation is required for ordinary pending-client replies,
    // before the render thread has copied their native UUID.
    { std::lock_guard<std::mutex> lock(g_dataMutex); PublishCommandReply(pendingNative.dump(), GetTickCount64()); }
    if (!g_ownerNativeDeliveryBusy.load() || QueueCasAction({{"operation","status"}})) return 44;
    drawNativeReceipt(failedNative);
    if (g_ownerNativeDeliveryBusy.load() || std::string(g_casPendingId) != nativeId) return 45;
    g_ownerObservation = {}; g_ownerOriginalCommand = {}; g_ownerDeliveredNativeReply.clear();
    g_selectedSim.clear(); g_selectionGeneration = 0; g_commandReply = g_json = "{}";
    g_casPendingId[0] = '\0'; g_casRefreshClock = {}; g_casLastReply.clear(); g_casAutoRefresh = true;
    g_nativeCasPaneVisible = false;
    // Upload actual owned RGBA pixels, then read back the GPU resource. This
    // isolates texture ownership/device cleanup from broker HTTP and CAS.
    const auto thumbnailKey = std::string(64, 'e') + ":" + std::string(64, 'f');
    g_resourceImageKey = thumbnailKey; g_resourcePixels = {1, 1, {17, 34, 51, 255}}; ++g_resourcePixelReceipt;
    if (!ResourceTexture(thumbnailKey) || !g_resourceTexture) return 30;
    ID3D11Resource* thumbnailResource = nullptr; g_resourceTexture->GetResource(&thumbnailResource);
    ID3D11Texture2D* thumbnailTexture = nullptr;
    if (!thumbnailResource || FAILED(thumbnailResource->QueryInterface(__uuidof(ID3D11Texture2D), reinterpret_cast<void**>(&thumbnailTexture)))) return 31;
    thumbnailResource->Release();
    D3D11_TEXTURE2D_DESC thumbnailDescription{}; thumbnailTexture->GetDesc(&thumbnailDescription);
    thumbnailDescription.Usage = D3D11_USAGE_STAGING; thumbnailDescription.BindFlags = 0; thumbnailDescription.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    ID3D11Texture2D* thumbnailReadback = nullptr;
    if (FAILED(g_device->CreateTexture2D(&thumbnailDescription, nullptr, &thumbnailReadback))) return 32;
    g_context->CopyResource(thumbnailReadback, thumbnailTexture); thumbnailTexture->Release();
    D3D11_MAPPED_SUBRESOURCE mappedThumbnail{};
    if (FAILED(g_context->Map(thumbnailReadback, 0, D3D11_MAP_READ, 0, &mappedThumbnail))) return 33;
    const unsigned char expectedThumbnail[] = {17, 34, 51, 255};
    const bool exactThumbnail = !std::memcmp(mappedThumbnail.pData, expectedThumbnail, sizeof(expectedThumbnail));
    g_context->Unmap(thumbnailReadback, 0); thumbnailReadback->Release();
    if (!exactThumbnail || ResourceTexture("foreign-resource")) return 34;
    // Render the new virtualized library using synthetic protocol data. No
    // HTTP, native CAS input, desktop activation or household is involved.
    g_libraryBusy=true;
    const ui::Json libraryQuery={{"text",""},{"body_type",nullptr},{"origin",nullptr},{"name_mode","preferred"},
        {"offset",0},{"limit",60},{"view","all"},{"author",""},{"sort","name"}};
    ui::Json libraryItems=ui::Json::array();
    for (int i=0;i<60;++i) {
        std::ostringstream identity; identity << std::hex << std::setw(64) << std::setfill('0') << i+1;
        libraryItems.push_back({{"part_id",identity.str()},{"resource_sha256",std::string(64,'b')},{"package_sha256",std::string(64,'c')},
            {"resource_tgi","034AEECB:80000000:0000000000000001"},{"package_name","Synthetic CC.package"},
            {"preferred_name","Synthetic CC"},{"code_name","synthetic_code"},{"body_type",35},{"favorite",false},
            {"name","Synthetic catalog item " + std::to_string(i)},{"status","indexed"},{"origin","mod"}});
    }
    g_libraryPage={{"ok",true},{"index_sha256",std::string(64,'d')},{"query",libraryQuery},{"items",libraryItems},
        {"categories",ui::Json::array({{{"body_type",35},{"count",60}}})},{"total",60},{"offset",0},{"next_offset",nullptr},
        {"snapshot",{{"parts",60},{"complete",true}}}};
    if (!library::Page(g_libraryPage,libraryQuery)) return 54;
    SynchronizeLibraryImages(g_libraryPage);
    const auto columnId=ui::Scalar(libraryItems[0],"part_id");
    {std::lock_guard<std::mutex> lock(g_dataMutex);g_libraryImagePixels[columnId]=g_resourcePixels;}
    SynchronizeLibraryImages(g_libraryPage);
    if(g_libraryImageTextures.count(columnId)!=1||g_libraryImageSizes.at(columnId).x!=1)return 56;
    ID3D11Resource* columnResource=nullptr;g_libraryImageTextures.at(columnId)->GetResource(&columnResource);
    ID3D11Texture2D* columnTexture=nullptr;
    if(!columnResource||FAILED(columnResource->QueryInterface(__uuidof(ID3D11Texture2D),reinterpret_cast<void**>(&columnTexture))))return 57;
    columnResource->Release();D3D11_TEXTURE2D_DESC columnDescription{};columnTexture->GetDesc(&columnDescription);
    columnDescription.Usage=D3D11_USAGE_STAGING;columnDescription.BindFlags=0;columnDescription.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ID3D11Texture2D* columnReadback=nullptr;
    if(FAILED(g_device->CreateTexture2D(&columnDescription,nullptr,&columnReadback)))return 58;
    g_context->CopyResource(columnReadback,columnTexture);columnTexture->Release();D3D11_MAPPED_SUBRESOURCE columnPixels{};
    if(FAILED(g_context->Map(columnReadback,0,D3D11_MAP_READ,0,&columnPixels)))return 59;
    const bool exactColumnPixels=!std::memcmp(columnPixels.pData,expectedThumbnail,sizeof(expectedThumbnail));
    g_context->Unmap(columnReadback,0);columnReadback->Release();if(!exactColumnPixels)return 61;
    const auto queuedBeforeLibrary=g_commands.size();
    ImGui_ImplDX11_NewFrame(); ImGui_ImplWin32_NewFrame(); ImGui::NewFrame();
    ImGui::SetNextWindowSize(ImVec2(700,800),ImGuiCond_Always);
    ImGui::Begin("Live catalog render smoke"); DrawLiveLibrary(); ImGui::End(); ImGui::Render();
    if (!ImGui::GetDrawData() || ImGui::GetDrawData()->TotalVtxCount <= 0 || g_commands.size()!=queuedBeforeLibrary) return 55;
    ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
    g_libraryBusy=false; g_libraryPage=ui::Json::object();CleanupLibraryImages();
    // Query real native window metrics without activating it or submitting
    // input. This exercises the diagnostic export against the selected WARP
    // swapchain and catches pointer/sign truncation or stale-window reads.
    RECT observedClient{}; POINT observedOrigin{};
    if (!GetClientRect(window, &observedClient) || !ClientToScreen(window, &observedOrigin)) return 27;
    if (ApexGameInputMetric(0) != observedClient.right - observedClient.left ||
        ApexGameInputMetric(1) != observedClient.bottom - observedClient.top ||
        ApexGameInputMetric(2) != observedOrigin.x || ApexGameInputMetric(3) != observedOrigin.y ||
        static_cast<uint32_t>(ApexGameInputMetric(5)) != GetCurrentProcessId() ||
        static_cast<uint32_t>(ApexGameInputMetric(6)) != static_cast<uint32_t>(reinterpret_cast<uintptr_t>(window)) ||
        ApexGameInputMetric(9) != -1 || ApexGameInputVersion() != 2) return 28;
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
    if (g_device || g_context || g_hwnd || g_resourceTexture || !g_resourceTextureKey.empty() || ImGui::GetCurrentContext() || g_loaderStatus != 1) return 23;
    if (ApexGameInputMetric(0) != -1 || ApexGameInputMetric(5) != 0 || ApexGameInputMetric(6) != 0 || ApexGameInputMetric(8) != 0) return 29;
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
    printf("DX11 WARP: visible owner same-ID recovery/hidden cancellation/stale-selection refusal, recovered and ordinary native UUID delivery/mutation guards, actual Present detour/menu + numeric color render, exact thumbnail GPU upload/readback/foreign-key refusal, native HWND/PID/geometry diagnostics, 8 RTVs+depth restored, ResizeBuffers, renderer teardown/reinit, hidden zero worker, first keypress/held/focus edges passed\n");
    // COM/UI cleanup while the hidden test window still exists.
    CleanupRenderTarget();
    CleanupResourceTexture();
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
