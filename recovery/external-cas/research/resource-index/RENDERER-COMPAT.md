# Renderer contract and source-specific rig investigation

This is bounded offline research, not evidence of native-game CAS parity. The
renderer behavior below was inspected at recovery branch commit
`e0282ea1c43fb3e22b8cc377a27feb4653b8ca79`. No assets, resource identifiers,
package fingerprints, game/profile data or derived image bytes are published.

## Rig selection and APXMESH1

The earlier 384-rig sample was not representative of human rigs. A filter using
the minimum encoded size for 165 v3.1 bones found five candidates in the selected
base full package. All five have the sampled GEOM's three palette hashes, and
all have the same 165 ordered hashes and parent hierarchy as independently
provided adult, child, toddler and infant TS4CAS Tools rig fixtures. Thus neither
bone count, palette coverage, order nor hierarchy alone identifies the correct
age-specific bind transforms. In the selected full package, two candidate
payloads are byte-identical to the adult fixture and one to the child fixture;
none matches the supplied toddler or infant fixtures. All five have matching
keys in the selected delta package, but **every** paired delta payload differs
from its full counterpart and none is byte-identical to any of the four fixtures.
All ten candidates matched TS4CAS Tools' reader on compared bone fields. The
fixture matching and the selected package set do not establish which source the
game loads, nor cover every installed package or CC source. Do not force a rig
based on the palette; establish the Sim's species and age, exact selected source,
and actual game load precedence first.

`projectApxCandidate` in `renderer-compat.mjs` is an in-memory diagnostic
adapter, not an integrated loader. It requires a 165-bone binary rig and text
rig whose ordered hashes, parents and float32 transform fields match; callers
must authenticate both sources themselves. It maps each nonzero GEOM palette
lane by hash to the rig order, assigns a safe zero index to zero-weight lanes,
normalizes raw byte weights only in the APXMESH projection, and retains raw
positions, normals, first UVs and triangle indices. The generated text used for
the following check was derived from the explicit fixture locally; the other
worker's current configured text rig was not available for comparison.

For the sampled installed GEOM, all 66 vertices' raw weight sums were 255.
With the explicit adult fixture, its in-memory APXMESH1 candidate passed the
existing renderer's `SceneBudget` validator: 66 vertices and 216 indices. The
renderer checks all four joint lanes, including zero-weight lanes, and accepts
normalized weights; it rejects invalid indices and weights. These checks prove
the interface shape for this sample, not rig selection or visual correctness.

`computeBindMatrices` preserves exact unit-scale behavior by default. Its
explicit near-unit option labels its result approximate. The adult fixture has
36 bones with non-unit scale, all within 5.365e-7 of one; snapping these to one
gave a maximum local/global matrix-component difference of approximately
1.070e-6 compared with TS4CAS Tools. Its scale formula and game conventions are
not independently established. `deriveSkinMatrices` requires caller-supplied
posed global matrices in the same coordinate system and forms
`posedGlobal * inverseBind`; it rejects non-rigid results as the renderer does.
With explicitly approximate rest matrices, the renderer's existing rigid skin
diagnostic accepted the sample; maximum position change was zero and normal
change 5.365e-7. A synthetic whole-rig translation produced the expected
0.05 maximum displacement. This is not a real pose, a game-space validation,
or proof that the scale approximation is suitable for animation.

The parser and APXMESH candidate retain raw GEOM coordinates and UVs. The
independent Blender importer converts position and normal `(x,y,z)` to
`(x,-z,y)` and flips V for Blender's conventions; that does not by itself prove
the renderer's Y-up coordinate system or texture row origin is wrong. Any basis
conversion must also be applied consistently to rig transforms and animation;
do not flip geometry or UVs merely because Blender does. Compare against a
coordinated in-game reference before claiming orientation parity.

## Texture and alpha

The sampled diffuse's first RLE2 mip was independently compared with the
Blender converter and Pillow. Of 2,097,152 decoded RGBA pixels, 1,882,712 have
zero alpha, 3,339 partial alpha and 211,101 full alpha. All zero-alpha pixels
retain nonzero RGB in the decoder result. `OpaqueTexture` in the inspected
renderer rejects any alpha below 255; its optional `AlphaMask` is a separate
bilinearly sampled threshold test and does not implement translucent blending.
Flattening alpha to satisfy the opaque input would discard coverage, and
filtering hidden RGB separately can affect cutout edges. The source alpha's
association and game material role, mask usage, cutoff and blending remain
unestablished.

The inspected renderer interpolates RGB byte values directly and applies a
diagnostic light multiplier; the RLE payload and decoder do not establish a
texture transfer function or native color-management path. No sRGB/linear or
premultiplication conversion is selected on this evidence. RLES has additional
uninterpreted bytes, so its BC3 candidate is not a complete material decode.

## Repeating checks

Run `renderer-compat.test.mjs` and `rig.test.mjs`. Set `APX_VALIDATOR_BIN` and
`APX_SKIN_VALIDATOR_BIN` to locally compiled copies of `apx-validator.rs` and
`apx-skin-validator.rs` to exercise the retained renderer's reader and rigid
skin code; the executables are built privately and are not included here. The
full set of reference-reader environment variables is documented in README.
`compare-renderer-private.mjs`, `compare-rig-private.mjs`, and
`compare-rig-fixtures-private.mjs` accept explicit private source paths and emit
aggregate evidence only. Run them on stable inputs at low priority; do not
publish asset data or assume index-only scans establish payload identity.
