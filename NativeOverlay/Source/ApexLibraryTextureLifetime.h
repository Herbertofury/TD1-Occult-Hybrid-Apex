#pragma once
#include <cstddef>
#include <type_traits>
#include <utility>

// Render-thread-only: caller owns candidate until Detach succeeds.
namespace td1 { namespace library_texture {
template<class TextureMap, class SizeMap, class Key, class Holder, class Size>
bool Install(TextureMap& textures, SizeMap& sizes, const Key& key, Holder& candidate,
             const Size& dimensions, std::size_t limit) {
    static_assert(std::is_nothrow_copy_assignable<Size>::value,
                  "Existing texture dimensions must be nonthrowing to update.");
    auto existing = textures.find(key);
    if (!candidate.Get() || (existing == textures.end() && textures.size() >= limit)) return false;
    auto previousSize = sizes.find(key);
    if (existing != textures.end()) {
        if (previousSize == sizes.end()) sizes.emplace(key, dimensions);
        else previousSize->second = dimensions;
        auto* previous = existing->second;
        existing->second = candidate.Detach();
        if (previous) previous->Release();
        return true;
    }
    // Add the raw pointer while the holder retains ownership; roll back if
    // the second map allocation fails or its key already exists.
    auto inserted = textures.emplace(key, candidate.Get());
    if (!inserted.second) return false;
    try {
        if (!sizes.emplace(key, dimensions).second) {
            textures.erase(inserted.first);
            return false;
        }
    } catch (...) {
        textures.erase(inserted.first);
        throw;
    }
    candidate.Detach();
    return true;
}
} }
