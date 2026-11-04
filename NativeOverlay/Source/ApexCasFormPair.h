// Portrait placement is independent of appearance identity and native genus.
#pragma once
#include "ApexCasOwnerGraph.h"

namespace td1::nativecas::engine {
struct FormPair {
    std::string base,alternate;
    std::uint8_t layer=0;
};
inline FormPair SelectFormPair(const std::string& human,const std::string& selected,
        std::uint32_t selectedKind,const FormPair& previous) {
    if(!FormOwnerId(human) || !FormOwnerId(selected) || !Kind(selectedKind))
        throw std::runtime_error("Portraits require exact shared Human and selected form identities.");
    if(selected==human) {
        // Selecting Human retains the currently chosen occult and its own
        // native arrangement, rather than manufacturing another Human.
        if(previous.base==human && FormOwnerId(previous.alternate) && previous.alternate!=human)
            return {previous.base,previous.alternate,0};
        if(previous.alternate==human && FormOwnerId(previous.base) && previous.base!=human)
            return {previous.base,previous.alternate,1};
        return {human,human,0}; // An ordinary Human has no invented occult.
    }
    // EA Alien uses base Alien / alternate disguise. Keep that arrangement.
    if(selectedKind==2) return {selected,human,0};
    // Ghost, Servo, etc. may use genus Human. Identity, not genus, decides
    // whether this is the shared Human or a distinct upper portrait.
    return {human,selected,1};
}
}
