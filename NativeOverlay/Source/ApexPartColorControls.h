// CASP-bounded shift controls. The wheel is a range selector, not texture RGB.
#pragma once
#include "ApexUiData.h"
#include <iomanip>
#include <sstream>

namespace td1::color {
using Json = ui::Json;
inline constexpr double kQ14Scale = 16384.0;
inline constexpr double kQ14Low = -2.0;
inline constexpr double kQ14High = 32767.0 / kQ14Scale;
inline constexpr std::array<const char*, 4> kChannels{"hue", "saturation", "brightness", "opacity"};
inline constexpr std::array<unsigned, 4> kLaneBits{32, 16, 0, 48};
struct Bounds { double low{}, high{}, step{}; bool enabled{}; };
inline bool ReadBounds(const Json& editor, unsigned index, Bounds& bounds) {
    if (index >= kChannels.size() || !editor.is_object() || !editor.contains("channels") ||
        !editor["channels"].is_object() || !editor["channels"].contains(kChannels[index])) return false;
    const auto& value = editor["channels"][kChannels[index]];
    if (!value.is_object() || !value.contains("enabled") || !value["enabled"].is_boolean()) return false;
    for (const auto* field : {"value", "min", "max", "step"})
        if (!value.contains(field) || !value[field].is_number() || !std::isfinite(value[field].get<double>())) return false;
    bounds = {value["min"].get<double>(), value["max"].get<double>(), value["step"].get<double>(), value["enabled"].get<bool>()};
    return bounds.low <= bounds.high && bounds.step >= 0;
}
inline bool EditRange(const Bounds& bounds, double& low, double& high) {
    low = std::max(bounds.low, kQ14Low); high = std::min(bounds.high, kQ14High);
    return bounds.enabled && bounds.step > 0 && low < high;
}
inline bool Quantize(const Bounds& bounds, double requested, double& quantized, int32_t& lane) {
    if (!bounds.enabled || bounds.step <= 0 || !std::isfinite(requested) || requested < bounds.low || requested > bounds.high) return false;
    const auto rounded = std::round(requested * kQ14Scale); // Native Python rounds halves away from zero.
    if (!std::isfinite(rounded) || rounded < -32768 || rounded > 32767) return false;
    lane = static_cast<int32_t>(rounded); quantized = lane / kQ14Scale;
    return quantized >= bounds.low - 0.5 / kQ14Scale && quantized <= bounds.high + 0.5 / kQ14Scale;
}
inline float WheelPosition(const Bounds& bounds, double value) {
    double low, high;
    return EditRange(bounds, low, high) ? static_cast<float>(std::clamp((value - low) / (high - low), 0.0, 1.0)) : 0.5f;
}
inline bool WheelValue(const Bounds& bounds, double position, double& value) {
    double low, high; int32_t lane;
    return std::isfinite(position) && position >= 0 && position <= 1 && EditRange(bounds, low, high) &&
        Quantize(bounds, low + position * (high - low), value, lane);
}
inline bool Raw(const std::string& text, uint64_t& raw) {
    if (text.size() != 16) return false;
    raw = 0;
    for (const char c : text) {
        const int digit = c >= '0' && c <= '9' ? c - '0' : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
        if (digit < 0) return false;
        raw = (raw << 4) | static_cast<uint64_t>(digit);
    }
    return true;
}
inline std::string RawHex(uint64_t raw) {
    std::ostringstream text; text << std::uppercase << std::hex << std::setw(16) << std::setfill('0') << raw;
    return text.str();
}
inline bool Prepare(const Json& editor, const float values[4], const bool changed[4], Json& edits, std::string& rawHex) {
    edits = Json::object(); rawHex.clear(); uint64_t raw;
    if (!Raw(ui::Scalar(editor, "color_hex"), raw)) return false;
    for (unsigned index = 0; index < 4; ++index) {
        if (!changed[index]) continue;
        Bounds bounds; double quantized; int32_t lane;
        if (!ReadBounds(editor, index, bounds) || !Quantize(bounds, values[index], quantized, lane)) return false;
        edits[kChannels[index]] = quantized;
        const uint64_t mask = uint64_t{65535} << kLaneBits[index];
        raw = (raw & ~mask) | (static_cast<uint64_t>(static_cast<uint16_t>(lane)) << kLaneBits[index]);
    }
    if (edits.empty()) return false;
    rawHex = RawHex(raw); return true;
}
} // namespace td1::color
