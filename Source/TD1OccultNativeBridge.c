// TD1OccultNativeBridge.c
// Native x64 helper DLL for TD1 Occult Hybrid Apex ImGui overlay build v6.
// Freestanding, no CRT dependency, loaded by Sims 4 Python through ctypes.

typedef unsigned long long u64;
typedef long long i64;
typedef unsigned int u32;

static u64 td1_lowest_bit(u64 mask) { return mask & (~mask + 1ULL); }
static u32 td1_popcount64(u64 mask) { u32 count = 0U; while (mask != 0ULL) { mask &= (mask - 1ULL); ++count; } return count; }

__declspec(dllexport) u64 TD1OccultNativeVersion(void) { return 2026052806ULL; }
__declspec(dllexport) u64 TD1OccultMaskAdd(u64 mask, u64 value) { return mask | value; }
__declspec(dllexport) u64 TD1OccultMaskRemove(u64 mask, u64 value) { return mask & (~value); }
__declspec(dllexport) int TD1OccultMaskHas(u64 mask, u64 value) { if (value == 0ULL) return mask == 0ULL; return ((mask & value) == value) ? 1 : 0; }
__declspec(dllexport) u64 TD1OccultMaskToggle(u64 mask, u64 value) { return mask ^ value; }
__declspec(dllexport) u64 TD1OccultNormalizeCurrent(u64 available, u64 current) { if (current == 0ULL) return 0ULL; return current & available; }
__declspec(dllexport) u64 TD1OccultLowestBit(u64 mask) { return td1_lowest_bit(mask); }
__declspec(dllexport) u64 TD1OccultChooseSafeForm(u64 available, u64 current, u64 requested) { u64 chosen = requested & available; if (chosen != 0ULL) return td1_lowest_bit(chosen); chosen = current & available; if (chosen != 0ULL) return td1_lowest_bit(chosen); return 0ULL; }
__declspec(dllexport) int TD1OccultSimIdLooksValid(i64 sim_id) { return sim_id > 0 ? 1 : 0; }
__declspec(dllexport) u64 TD1OccultFnv1a64(const char *data, u32 length) { u64 hash = 1469598103934665603ULL; u32 i; if (data == 0) return hash; for (i = 0; i < length; ++i) { hash ^= (unsigned char)data[i]; hash *= 1099511628211ULL; } return hash; }
__declspec(dllexport) u64 TD1OccultMaskNormalizeSupported(u64 mask, u64 supported) { return mask & supported; }
__declspec(dllexport) u32 TD1OccultMaskCount(u64 mask) { return td1_popcount64(mask); }
__declspec(dllexport) int TD1OccultIsPowerOfTwo(u64 mask) { return (mask != 0ULL && (mask & (mask - 1ULL)) == 0ULL) ? 1 : 0; }
__declspec(dllexport) u64 TD1OccultChooseNext(u64 available, u64 current) { u64 candidates; if (available == 0ULL) return 0ULL; if (current == 0ULL) return td1_lowest_bit(available); candidates = available & (~((current << 1ULL) - 1ULL)); if (candidates != 0ULL) return td1_lowest_bit(candidates); return td1_lowest_bit(available); }
__declspec(dllexport) int TD1OccultStateScore(u64 available, u64 current, u64 supported) { int score = 100; if ((available & ~supported) != 0ULL) score -= 35; if (available == 0ULL) score += 5; if (current == 0ULL) score += 5; else if ((current & available) != 0ULL && TD1OccultIsPowerOfTwo(current)) score += 10; else score -= 35; if (td1_popcount64(available & supported) > 1U) score += 5; if (score < 0) return 0; if (score > 100) return 100; return score; }
__declspec(dllexport) u64 TD1OccultClampCurrent(u64 available, u64 current) { current &= available; if (current == 0ULL) return 0ULL; if (TD1OccultIsPowerOfTwo(current)) return current; return td1_lowest_bit(current); }
__declspec(dllexport) u64 TD1OccultRepairMask(u64 flag_mask, u64 trait_mask, u64 supported) { return (flag_mask | trait_mask) & supported; }
__declspec(dllexport) u64 TD1OccultMaskMissing(u64 expected, u64 actual) { return expected & (~actual); }
__declspec(dllexport) u64 TD1OccultMaskExtra(u64 expected, u64 actual) { return actual & (~expected); }
__declspec(dllexport) int TD1OccultNeedsRepair(u64 available, u64 current, u64 supported) { if ((available & ~supported) != 0ULL) return 1; if (current != 0ULL && ((current & available) == 0ULL || !TD1OccultIsPowerOfTwo(current))) return 1; return 0; }
__declspec(dllexport) u64 TD1OccultCommandHash(u64 action_hash, u64 sim_id, u64 occult_mask) { u64 hash = 1469598103934665603ULL; hash ^= action_hash; hash *= 1099511628211ULL; hash ^= sim_id; hash *= 1099511628211ULL; hash ^= occult_mask; hash *= 1099511628211ULL; return hash; }

// Overlay-specific helpers are intentionally tiny and deterministic. The actual ImGui renderer lives in the separate d3d11 proxy source kit.
__declspec(dllexport) u64 TD1OverlayNativeVersion(void) { return 2026052806ULL; }
__declspec(dllexport) u32 TD1OverlayProtocolVersion(void) { return 6U; }
__declspec(dllexport) u32 TD1OverlayVirtualKeyF11(void) { return 0x7AU; }
__declspec(dllexport) u32 TD1OverlayMaxLogLines(void) { return 600U; }
__declspec(dllexport) u32 TD1OverlayHiddenMode(void) { return 0U; }
__declspec(dllexport) u32 TD1OverlayClampPollMs(u32 requested, u32 min_ms, u32 max_ms) { if (requested < min_ms) return min_ms; if (requested > max_ms) return max_ms; return requested; }
__declspec(dllexport) int TD1OverlayShouldPoll(u64 now_ms, u64 last_ms, u32 visible, u32 interval_ms) { if (!visible) return 0; if (interval_ms < 100U) interval_ms = 100U; return (now_ms >= last_ms && (now_ms - last_ms) >= (u64)interval_ms) ? 1 : 0; }
__declspec(dllexport) u32 TD1OverlayPerfLevel(u32 last_frame_us) { if (last_frame_us <= 250U) return 0U; if (last_frame_us <= 1000U) return 1U; if (last_frame_us <= 2500U) return 2U; return 3U; }
__declspec(dllexport) u64 TD1OverlayProtocolHash(void) { return TD1OccultFnv1a64("TD1_APEX_IMGUI_OVERLAY_V6", 25U); }
__declspec(dllexport) int TD1OverlayCommandSafeToPoll(u32 visible, u32 pending_count) { if (!visible) return 0; return pending_count < 16U ? 1 : 0; }

__declspec(dllexport) u64 TD1SavedFormHash(const char *data, u32 length) { return TD1OccultFnv1a64(data, length); }

int __stdcall TD1DllMain(void *hinst, unsigned long reason, void *reserved) { return 1; }
