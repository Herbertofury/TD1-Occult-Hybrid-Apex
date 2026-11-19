// Worker-owned immutable pixels only; D3D objects belong to the render thread.
// Microsoft WIC stream decoder and D3D immutable texture contracts:
// https://learn.microsoft.com/windows/win32/api/wincodec/nf-wincodec-iwicimagingfactory-createdecoderfromstream
// https://learn.microsoft.com/windows/win32/direct3d11/overviews-direct3d-11-resources-textures-how-to
#pragma once
#include <windows.h>
#include <wincodec.h>
#include <bcrypt.h>
#include "ApexResourceData.h"

namespace td1::resource {
inline std::string HashBytes(const std::string& bytes) {
    BCRYPT_ALG_HANDLE algorithm = nullptr; BCRYPT_HASH_HANDLE hash = nullptr;
    DWORD length = 0, written = 0; std::string result;
    std::vector<unsigned char> work, digest(32);
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) return result;
    if (BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&length), sizeof(length), &written, 0) >= 0 &&
        written == sizeof(length) && length > 0 && length <= 65536) {
        work.resize(length);
        if (BCryptCreateHash(algorithm, &hash, work.data(), length, nullptr, 0, 0) >= 0 &&
            BCryptHashData(hash, reinterpret_cast<PUCHAR>(const_cast<char*>(bytes.data())), static_cast<ULONG>(bytes.size()), 0) >= 0 &&
            BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) >= 0) {
            static const char hex[] = "0123456789abcdef";
            for (auto byte : digest) { result.push_back(hex[byte >> 4]); result.push_back(hex[byte & 15]); }
        }
    }
    if (hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return result;
}
inline bool CatalogIdentities(const Json& catalog) {
    if (!Catalog(catalog)) return false;
    for (const auto& row : catalog["items"])
        if (HashBytes(ui::Scalar(row, "resource_tgi") + "\n" + ui::Scalar(row, "effective_resource_sha256")) !=
            ui::Scalar(row, "resource_id")) return false;
    return true;
}
template<class T> struct ComObject {
    T* ptr = nullptr;
    ~ComObject() { if (ptr) ptr->Release(); }
    T** out() { return &ptr; }
};
struct Pixels { unsigned width = 0, height = 0; std::vector<unsigned char> rgba; };
inline bool DecodeThumbnail(const std::string& bytes, const Json& row, Pixels& pixels, std::string& reason) {
    pixels = {}; reason.clear();
    static const unsigned char png[] = {137, 80, 78, 71, 13, 10, 26, 10};
    if (!row.is_object() || !row.contains("thumbnail") || !row["thumbnail"].is_object() ||
        ui::Scalar(row["thumbnail"], "status") != "resolved" || !Hash(row["thumbnail"], "sha256") ||
        bytes.size() < sizeof(png) || bytes.size() > 8 * 1024 * 1024 ||
        std::memcmp(bytes.data(), png, sizeof(png)) != 0 ||
        HashBytes(bytes) != ui::Scalar(row["thumbnail"], "sha256")) {
        reason = "Thumbnail bytes do not match the pinned PNG hash."; return false;
    }
    const auto& thumbnail = row["thumbnail"];
    if (!thumbnail.contains("width") || !thumbnail["width"].is_number_integer() ||
        !thumbnail.contains("height") || !thumbnail["height"].is_number_integer() ||
        thumbnail["width"] <= 0 || thumbnail["width"] > 512 || thumbnail["height"] <= 0 || thumbnail["height"] > 512) {
        reason = "Pinned thumbnail dimensions are invalid."; return false;
    }
    const HRESULT initialized = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    bool decoded = false;
    {
        // Declare bytes first so they outlive all stream/decoder COM objects.
        std::vector<unsigned char> owned(bytes.begin(), bytes.end());
        ComObject<IWICImagingFactory> factory; ComObject<IWICStream> stream;
        ComObject<IWICBitmapDecoder> decoder; ComObject<IWICBitmapFrameDecode> frame;
        ComObject<IWICFormatConverter> converter;
        UINT count = 0, width = 0, height = 0; GUID container{};
        // Stream retains this owned buffer only until the decoder is released.
        if ((SUCCEEDED(initialized) || initialized == RPC_E_CHANGED_MODE) &&
            SUCCEEDED(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER,
                IID_PPV_ARGS(factory.out()))) &&
            SUCCEEDED(factory.ptr->CreateStream(stream.out())) &&
            SUCCEEDED(stream.ptr->InitializeFromMemory(owned.data(), static_cast<DWORD>(owned.size()))) &&
            SUCCEEDED(factory.ptr->CreateDecoderFromStream(stream.ptr, nullptr, WICDecodeMetadataCacheOnLoad, decoder.out())) &&
            SUCCEEDED(decoder.ptr->GetContainerFormat(&container)) && IsEqualGUID(container, GUID_ContainerFormatPng) &&
            SUCCEEDED(decoder.ptr->GetFrameCount(&count)) && count == 1 &&
            SUCCEEDED(decoder.ptr->GetFrame(0, frame.out())) && SUCCEEDED(frame.ptr->GetSize(&width, &height)) &&
            width > 0 && width <= 512 && height > 0 && height <= 512 &&
            width == thumbnail["width"].get<unsigned>() && height == thumbnail["height"].get<unsigned>() &&
            SUCCEEDED(factory.ptr->CreateFormatConverter(converter.out())) &&
            SUCCEEDED(converter.ptr->Initialize(frame.ptr, GUID_WICPixelFormat32bppRGBA,
                WICBitmapDitherTypeNone, nullptr, 0, WICBitmapPaletteTypeCustom))) {
            pixels.rgba.resize(static_cast<size_t>(width) * height * 4);
            decoded = SUCCEEDED(converter.ptr->CopyPixels(nullptr, width * 4,
                static_cast<UINT>(pixels.rgba.size()), pixels.rgba.data()));
            if (decoded) { pixels.width = width; pixels.height = height; }
        }
    }
    if (SUCCEEDED(initialized)) CoUninitialize();
    if (!decoded) { pixels = {}; reason = "WIC could not verify/decode the pinned PNG dimensions."; }
    return decoded;
}
} // namespace td1::resource
