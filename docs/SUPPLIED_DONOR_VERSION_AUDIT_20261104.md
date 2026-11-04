# Supplied Dynamic CAS donor version: audit-only pipeline

This adds a separate exact-version recognition and collision report. It does
not alter `maru_companion.read_package`, the existing 66-resource donor gate,
any historical proof, the builder, a package or a game installation. Recognition
is not permission to merge. Both donor variants must remain supported once a
separate new-version proof exists.

The user-supplied package SHA-256 is
`66ab31072bfe3d7e9fe4b9954d3e7bb7c5409ece01190db8c82349a1bc7acda5`.
It has 88 DBPF resources, with exact TGI/SHA-256 identities recorded in the
hash-only `tools/maru_companion_supplied_inventory.json`. The package bytes
themselves have not established a release/version string. The previously
reviewed package SHA is
`054ca6a189a587063290df004a42072c5381e59404d33e58ddb737ab821cf9c3`.
All 66 old TGIs are present in the supplied file: 40 have identical content,
26 differ and 22 are newly present. No old TGI is absent.

Against the retained disposable bridge SHA
`c3f70eeef33114b705e8247c6af2bd1f23a51ba9b6e48b40ec95d9b6be6a5a3f`, and
independently against the historical V356 bridge SHA
`21297bbe456957dae60e9565b5a0d02ec5a0b7ec780f813eb55894084fb0eb78`,
67 supplied TGIs overlap. These are retained test/build artifacts, not
evidence of the user's current effective game resources.

Three differing GFX overlaps require new, resource-specific proofs before any
precedence decision:

1. `62ECC59A:00000000:DF09D526F4C77B95`, the customizer Main: retain the new
   donor's actual classes and callbacks and the full Apex native/owned method
   adaptation chain; independently verify bytecode, bindings and rollback.
2. `62ECC59A:00000000:89D13757C58C2E05`, the donor grid provider: retain the
   new donor provider and every Apex grid continuation. Prove the distinct
   canonical provider and shared class bindings as well as this resource;
   historical donor hashes and method counts cannot authenticate new bytes.
3. `62ECC59A:00000000:3E752EBCB41E7298`, the Plan Outfit header: newly
   present in the supplied donor but already present with different bytes in
   Apex. Retain the donor behavior and the existing Apex width/attachment
   adaptation. It is not covered by the old donor's overlap allowance.

The supplied `casfeaturedlooks.gfx`
`62ECC59A:00000000:DBEC8F675D3E53B2` is new and did not overlap those two
historical Apex bridges. It needs its own exact source/adapter and runtime
proof, and conflicts with other mods replacing the same resource. This is not
a guarantee about any other installed mod set. Changed non-GFX resources also
need provenance and dependency review; no blanket choice of donor or Apex wins.

The module accepts either the exact historical donor or the exact supplied
package for **inspection**. It validates the complete 88-resource inventory
for the latter, rejects unknown bytes and duplicate inventory keys, binds an
Apex comparison to a caller-supplied artifact SHA, enumerates overlaps and
required roles, and never selects precedence or reports a merge as authorized.
Missing roles are explicit. It cannot be used to bypass the existing merger.

The owner explicitly requires retaining both bottom sliders: size and column
count. The integrated panel-edge grip and interactive favorites/filter hearts
are additional controls. The audit marks all five controls unverified; it must
not treat source presence, donor identity or a compiled package as proof. The
existing 2–32 column target, requested 20–160% card sizing, spacing and viewport
fit remain required, with no panel covering the Sim or native controls.

After placing the exact private donor and reviewed Apex artifact locally, the
read-only audit can write a new hash-only report beneath this checkout's
existing `.work` directory:

```powershell
python tools/maru_companion_versions.py --donor <exact-private-package> --apex <private-apex-package> --apex-sha256 <reviewed-sha256> --output .work/<new-report>.json
```

This audit does not require, produce, or install an altered package. Do not
use its report as a bytecode-retention or package-merger approval.
The focused tests use `APEX_PRIVATE_MARU_DONOR` and `APEX_PRIVATE_CAS_BRIDGE`
for the optional, hash-checked private package fixtures; missing fixtures are
reported as explicit skips. The module and committed tests contain no local
machine-specific package paths.

The [creator's current license page](https://www.curseforge.com/sims4/mods/dynamic-cas-columns/license)
identifies maru's Dynamic CAS Companion as CC BY 4.0. Any reused covered code
or assets require attribution, license information and a clear modification
notice. The creator's current license page does not identify these exact
supplied bytes as a particular release. No donor package, compiled donor code,
extracted donor image or third-party asset is included in this audit. The TGI
and SHA-256 metadata are evidence, not a copy of the protected resource bytes.

The actual migration still needs independent new-version compiled and rollback
proofs, full resource ownership, a new build/recovery epoch compatible with the
preserved dirty v358 state, and matched no-Apex/staged in-game testing. The
separate Styled Looks prototype is not part of this version audit. No parity,
smooth motion, frame-time gain or release readiness is asserted here.
