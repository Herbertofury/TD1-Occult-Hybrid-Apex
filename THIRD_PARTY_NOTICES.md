# Third-party / research provenance

Apex Occult Hybrid uses recovered/historical hybrid projects as research and regression references while converging production runtime ownership on first-party Apex artifacts.

## Occult Hybrid lineage

- TD1 / TwelfthDoctor1 / L-P-TD1 — original Occult Hybrid source lineage: https://github.com/L-P-TD1/ts4-occulthybrid
- IcedCream — original Hybrid work incorporated in the TD1/LordPercival lineage.
- LordPercivalXII — current distributed Occult Hybrid Unlocker & Stabilizer releases and maintenance lineage.

Apex must preserve upstream credits and applicable licenses/notices for any code or packaged content actually reused. Do not imply upstream endorsement.

**Production dependency rule:** the release must not require separately installed TD1/TwelfthDoctor1/IcedCream/LordPercival files. The owner's later explicit authorization permits incorporating covered code/resources into Apex-owned artifacts, with exact provenance. The candidate adapts the actual 1.13.7 implementation into `apex_hybrid`; it does not require the original archive installed alongside it.

## Dear ImGui

The recovered native overlay source kit vendors Dear ImGui source. Upstream: https://github.com/ocornut/imgui

The recovered V9.5 tree includes an ImGui license file with SHA-256:
`173506a2d6f7fb67990d257fb2507f188690eca39060c39469ae7bef43aae2a3`

Before shipping a rebuilt overlay, preserve the complete upstream license text from the vendored/retrieved ImGui version.

## Optional interoperability

Lot51 Core, XML Injector and other Sims utilities remain optional interoperability targets. MCCC's covered CAS/Dresser/shared material is now also an explicitly authorized implementation base. Only the documented Dresser helper port is included in this candidate; MCCC's unrelated gameplay automation is not bundled.


## Owner-provided author permissions

The project owner states they have full permission from the relevant authors of:
- the current TD1/LordPercival occult-hybrid baseline; and
- Crilender CASUnlocks; and
- MC Command Center (MCCC), specifically the relevant CAS/Dresser/shared CAS-related material covered by the author's permission; and
- thepancake1 Color Sliders, specifically relevant thepancake1-owned UI/package/conversion material covered by the author's permission.

to use their material in Apex.

For project execution, permissioned material may be inspected, reused, ported, adapted, merged and incorporated into Apex with attribution/provenance. Public license labels should not be treated as overriding a direct author permission for the material actually covered by that permission.

This permission record does not automatically extend to unrelated third-party components bundled inside an archive; preserve those components' separate provenance/terms where applicable.


## MCCC CAS/Dresser authorized baseline

The owner-provided permission allows Apex development to inspect, reuse, port, adapt and merge authorized MCCC MC CAS / MC Dresser / shared CAS-related implementation material.

Current public compatibility baseline verified for research: MCCC 2026.5.0, documented for Sims 4 PC 1.128.90.1030.

The final Apex release does not require MCCC; MCCC is a development/implementation baseline for Apex Live CAS Studio. `Source/apex_core/dresser_parts.py` ports Deaderpool's four `DresserOutfitObject` part/color helpers from the pinned 2026.5.0 `mc_utils.pyc`, adding strict integer/alignment checks. `manifests/mccc-dresser-port.json` records module/instruction identities and nine matching pure-helper cases. This is not full MC CAS/Dresser parity.

## Crilender CASUnlocks

Crilender is credited for the actual v1.9h main, Archetypes, Fairy, Gloves Below Tops, Horse, Mermaid and Werewolf resources incorporated into the candidate `ApexCASUnlocks.package`. Resource bytes and IDs are preserved. The Fairy addon explicitly owns two overlapping SIMDATA keys; manifests record every input and selected owner.

## Preserved embedded notices

The mod-folder F11 sidecar uses Tsuda Kageyu's [MinHook v1.3.4](https://github.com/TsudaKageyu/minhook/releases/tag/v1.3.4), pinned at `c3fcafdc10146beb5919319d0683e44e3c30d537`. The x64 source is vendored unchanged. Its complete BSD notice and Vyacheslav Patkov HDE notices are preserved in `NativeOverlay/third_party/minhook/LICENSE.txt` and distributed in the candidate's `Licenses` directory.

CAS color packing and CASP field layouts were researched against the maintained [CmarNYC-Tools/TS4SimRipper](https://github.com/CmarNYC-Tools/TS4SimRipper) and [CmarNYC CAS Tools](https://github.com/Oops19/cmarNYC_CASTools) repositories. The format reader/codec in `apex_core` is an independent implementation of those data-format facts. No GPL parser source, tool binary or private EA resource/code is bundled. SimRipper's original C# parser was compiled privately as an independent comparison oracle; hashes and matching fields are recorded in `manifests/cas-color-format.json`. JPEXS FFDec 26.3.0 was used privately to inspect the authorized UI and is not distributed.

The overlay uses Niels Lohmann's MIT-licensed [JSON for Modern C++ v3.12.0](https://github.com/nlohmann/json/releases/tag/v3.12.0) for typed transport data, Unicode labels and exact integer identities. The vendored single header matches the official release SHA-256 `aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63`. Its complete `LICENSE.MIT` is shipped alongside the ImGui license. Native protocol fixtures cover the production reader; this dependency does not establish game-hook compatibility.

Authorized hybrid modules retain their embedded source-lineage notices, including `(C) Copyright TD1 & TWoCC 2020 - 2021` and the stated CC-BY-NC-ND 4.0 label where present. Adaptation relies on the owner's recorded direct author permission for covered material; this record does not relicense independently owned components or assert upstream endorsement. ImGui's complete MIT license is included in the bundle. Private xdis/uncompyle6 inspection tools and the Python compiler are not bundled, and private EA Python code is not published.


## thepancake1 Color Sliders authorized baseline

The owner-provided permission allows Apex development to inspect, reuse, port, adapt and merge relevant thepancake1-owned Color Sliders material.

Current public baseline verified for research: Color Sliders v4f, UI checked/updated through Sims 4 patch 1.127.41 on 2026-08-26. Apex targets the newer 1.128.90.1030 build and must port/revalidate the baseline forward.

The final Apex release does not require the original Color Sliders mod. Preserve attribution/provenance for authorized material that survives into Apex, and preserve separate terms for any MizoreYukii/CmarNYC/other independently owned lineage material not covered by thepancake1 permission.
