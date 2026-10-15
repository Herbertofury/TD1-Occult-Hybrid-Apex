# Native CAS hybrid membership, October 15

The requirement is a modded native CAS room in which every owned occult remains
selectable, with independent appearances, and additional occults can be added
without replacing existing ones. Native limitations are implementation targets,
not the intended product behavior. The permanent appearance guard remains on.

## V134 actual-game evidence

- [x] Install the matching candidate only in the single reusable disposable
  profile. The protected original is read/copy only.
- [x] Complete normal Save and Exit before installation. The manual Slot 2
  checkpoint is `7f20b6298cfd72aae9639dab37b4408233d87cae0d626b568350fda844cca771`.
- [x] Diagnose one EA launch failure before Sims initializes: the elevated EA
  helper times out. A subsequent launch succeeds; the existing CLI acknowledges
  the exact EA permission dialog on both attempts. No account bypass is used.
- [x] Load the exact indexed manual save, select the played apartment building
  and occupied unit through addressed background game input, then enter Live.
  No foreground handoff or OS cursor movement is used.
- [x] Compare all 35 stored and five active appearance owners before CAS. Every
  owner matches the pre-install baseline. Proof
  `native-cas-v134-cold-current-all40.json`, SHA-256
  `ba927de3464616e5b7912b5081cb451c36864bec2dad441bb79378e2b2185863`.
- [x] Enter the actual full existing-household editor and retain native status.
  The selected Alien reports `allOccultTypes=3`, `occultType=2`, layer `0`,
  native session `1`. Proof `native-cas-v134-full-household-cas-entry.json`,
  SHA-256 `c05e2937f48381e5ceef380fb7436aa2dc326c185013068723941a0179d08bde`.
  **This fails complete membership exposure.** No cross-occult setter is sent
  against that pair-only mask, and no cross-occult editing success is claimed.
- [x] Identify Apex's own entry narrowing in `cas_entry_context.prepare`:
  it explicitly requests `1 | current` for every household hybrid, even though
  all independently captured owners remain present. Changing only the serialized
  export in V134 cannot remove that earlier restriction.
- [x] Return the unedited visit through semantic native acceptance, advance
  actual simulation ticks, and commit all five independent return transactions.
  Every member commit verifies, then all 40 appearance owners match exactly.
  Household commit proof SHA-256:
  `806876156146cf21157349f19942526348f45504064d82140750cbccb883932c`.
- [x] Exit normally without saving. Native process exit and unchanged complete
  disposable save/backup inventory are verified. No forced game termination is
  used for this installation.

## V135 implementation and component checks

- [x] Replace the entry pair request with the complete membership set from the
  actual tracker query and existing native flags. Stored appearance memory alone
  never adds membership. Preserve the selected kind and unknown existing flags.
- [x] Preflight the whole household before native writes. Every advertised
  registered membership requires an already captured appearance owner. Missing
  owners block entry instead of generating replacement appearances.
- [x] Refuse a native setter result that loses any non-Human membership. Retain
  complete durable appearance/trait/context originals and the unresolved intent;
  never proceed with a pair-only result or replay a failed write.
- [x] Keep exact native owner identities, current kind, appearances and gameplay
  traits unchanged by preparation. Each member still has its independent CAS
  return transaction and permanent guard.
- [x] Pass 14 entry tests, including complete memberships, removed-membership
  memory, missing-owner refusal, native pair-only normalization, rejected setters,
  appearance side effects and interrupted preparation. All 15 existing native
  frontdoor tests also pass.
- [x] Pass all 801 CAS tests and 26 upgrade/migration tests against frozen V135
  source. An earlier broad V134 run overlaps the V135 source edit: its 18
  failure/error results all involve changed source-pin authority. That mixed
  run is retained and is not reported as a clean full-suite result. The fresh
  V135 migration run passes; no source-integrity check is removed or relaxed.
- [x] Build the immutable candidate with 93 Python 3.7 modules and seven packages.
  Bundle SHA-256:
  `efab888c8b0b59dc22d974329e55d8c63004c8626389dabc2bcb0a4bc44ff5ee`.
  The build manifest honestly records that its optional Rust verifier was not
  supplied to that build invocation. A separate verification then validates all
  seven indexes and byte-compares all 207 independently Rust-extracted resources.
  Separate receipt SHA-256:
  `17446fa6207e1b623c75a7b1523bc50d317cfa775b9fc79b3c3ff415cf014b69`.
- [x] Install the matching V135 bundle in the same disposable profile after
  verified normal process exit. No alternate test profile is created.
- [x] Cold-load the same unchanged manual save under V135, pause it, and compare
  all 40 appearance owners exactly. Proof SHA-256:
  `1ef895fc990845a95ad01f36133d8df609948cd81905e6641d86d60bc53c8314`.
- [x] Test V135's real full-household CAS entry. All five native preparation
  results retain every non-Human bit (`126`) and their original current kinds,
  appearances and traits. The raw selector packet, captured **before** EA's
  ActionScript handler, nevertheless contains only one pair per member: masks
  `3`, `33`, `9`, `65`, `3`. The selected Alien reports mask `3`.
  Entry proof SHA-256:
  `f664975886e4ce1900c01bf17bdb74d20b73132aad781eb7a398dd5deafabb4b`.
  **The raw native CAS view still exposes one pair.** V135 removes Apex's
  own restriction but does not fix this presentation/selection limit. The
  packet alone does not establish deletion of persistent membership.
- [x] Run the separate native-view probe against that exact session. It records
  one read-only status and refuses to send any cross-occult setter because the
  full mask is absent. Probe SHA-256:
  `e69ff2d1c2505aa99eb92d3ec16ac78325ec60897f56678f0ba91586635befb2`.
  No Alien/Vampire round trip is claimed for this visit.

Passive native-code inspection also finds that EA's selector computes the
non-Human membership mask and tests whether the entire mask belongs to its
alternate-form set. A Spellcaster-containing full hybrid does not satisfy that
single-form presentation check. The planned UI correction must distinguish
the currently displayed kind from complete membership; altering UI labels
alone cannot repair the already narrowed raw native packet. External read-only
process access is denied by Windows (error 5), so deeper runtime inspection
requires an explicit read-only diagnostic inside the authorized game mod.
The [subsequent native-code inspection](NATIVE_CAS_CODE_INSPECTION_2026-10-15.md)
implements that diagnostic and finds the real live service references.

## Remaining runtime gates

- [ ] Verify V135 exposes all six memberships in actual native CAS.
- [ ] Navigate actual Alien alternate → Vampire alternate → Alien alternate
  inside one visit without membership loss, then edit and retain their distinct
  appearances through Live switching and reload.
- [ ] Add a new occult inside ordinary/full/MCCC CAS without replacing existing
  memberships or appearances. `occult-view` only selects an already-owned kind;
  it is not an additive membership implementation.
- [ ] Qualify every other member, occult, alternate and editable category.
- [ ] Complete named special-state gameplay, cross-session variants and native
  whole-household Tray/Library import acceptance. See the life-state report.

No component check, menu input acknowledgement or selected native occult value
establishes appearance persistence. Production-save acceptance remains open.
