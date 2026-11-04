# CAS UI interaction research: November 2026

**Repository documentation mirror.** This research was prepared for the existing [live research wiki](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/wiki/External-Sims-4-Research-%E2%80%90-2026%E2%80%9011). Browser timeouts prevented editing that page; live-wiki synchronization is pending. This additive file does not replace the wiki's existing research or current project requirements.


## Dynamic CAS and Styled Looks public interaction checks

**Checked 2026-11-04.** This supplements the [owner's updated-package inventory and UI priorities](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/wiki/Apex-Owner-Requirements-Checklist#updated-dynamic-cas-and-ui) and [earlier community regressions](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/wiki/Research-Proposals#dynamic-cas--apex-community-evidence-and-merge-safeguards), rather than repeating their feature lists. Public descriptions are not proof that the owner's supplied package, Apex's current merge, or the running game implements them. No game files or active project tasks were accessed.

### New public Dynamic CAS details

The [author's current description and dated update notes](https://www.curseforge.com/sims4/mods/dynamic-cas-columns) advertise **maru_Dynamic_CAS_Companion261104.zip** for **1.129.39**. The linked file page was unavailable to this research tool; its binary, hash and separate changelog were not inspected.

- **Search:** requires names embedded by CAS Tooltip Studio. November 3 adds comma-separated terms; November 4 adds Eye Preview tooltip/search support and adds Cheek subcategories. The documented text does not define AND/OR matching.
- **Presets:** November 2 adds favorites, hiding and thumbnail scaling. October 30 documents individual outfit-slot copying and a Styled Looks search fix.
- **Styled Looks:** an upper-right icon toggles thumbnail view; the CC filter restricts custom looks. This is distinct from the ordinary clothing catalog.
- **Input:** left/right navigate items; A/D change selected-item swatches. History, Swatch Preview and Current Outfit share `dynamic_cas_history.columns#number` and `dynamic_cas_history.thumbnail_scale#number`; the main catalog uses the corresponding `dynamic_cas_columns` keys.
- **CC List:** select items, commit with Done, click the adjacent count to filter the selection. Settings clear the list; a separate CC List Mover consumes its `UserSetting.ini` entries. The mover's post was unavailable, so its matching/move/rollback semantics are unverified.

The [CAS Tooltip Studio author post](https://www.patreon.com/marumaruSIMSMOD/posts/cas-tooltip-174022486) clarifies that naming rewrites package descriptions: automatic naming preserves valid existing text, custom naming replaces it, and a name applies to all swatches in a selected package. Separate-output and backup/replace modes exist. A blank existing description can suppress naming; older CASP support requires a conversion option, while unsupported files remain unchanged. The public page lists a v2.4.0 source ZIP, but its contents and license were not retrieved. This is a comparison route, **not a reason to make package rewriting a prerequisite for Apex's existing shared-index search**.

### SimMattically's exact reference and reuse boundary

The [owner-specified Styled Looks UI Makeover post](https://www.patreon.com/SimMattically/posts/styled-looks-ui-173991211) publicly describes an adjustable grid, right-click favoriting, custom looks before ordinary looks, and a functioning custom-content filter. It claims compatibility with weerbesu's More Columns in CAS, but explicitly identifies **`casfeaturedlooks.gfx`** as the resource that conflicts with other Styled Looks UI replacements. That statement does not establish compatibility with Dynamic CAS's own Styled Looks replacement or Apex.

The post labels the download **Early Access, public release TBA**. No version number or public changelog was verified. The [creator's patch-status page](https://www.simmattically.com/mods-patch-status/) is dated October 28 for game 1.129 and has no Styled Looks UI row, so it is not a current compatibility result for this mod.

**Visible versus unavailable:** public feature text was readable; no static preview image or video was successfully inspected. Do not attribute an exact drag gesture, heart-button action, bottom-slider placement, easing, frame cadence or persistence behavior to unseen footage. Smooth integrated expansion, the heart Favorites filter and retained bottom size/column sliders remain the owner's explicit Apex priorities.

**Rights:** maru's [CurseForge license](https://www.curseforge.com/sims4/mods/dynamic-cas-columns/license) is CC BY 4.0; preserve attribution, license and modification notices, and check individual bundled components. SimMattically's [creator-wide terms](https://www.patreon.com/SimMattically/posts/simmattically-of-100418776), displayed March 15, 2024, prohibit mod modification/reupload and reuse/modification of its code. No applicable exception was verified. Use independent interaction design, not copied SimMattically code or assets, unless separate permission is established. Do not extend maru's DCC license automatically to separate helper programs.

### Focused integration tests to add, not claimed passes

1. **One Styled Looks owner:** enumerate exact resource keys, hashes and winning providers for the supplied donor, Apex and any comparator. Exercise the real preview/page/variant widget and its grid toggle. A successful clothing-catalog resize must not count as Styled Looks qualification.
2. **Continuous layout input:** capture uninterrupted edge drags, reversal and pointer release outside the panel while changing bottom column/card sliders. Check synchronized values, selection/scroll retention, reachable controls and no detached replacement panel. Measure rendered cadence rather than declaring an animation smooth from endpoint screenshots.
3. **Favorite and hidden state:** include ordinary CAS parts, Presets, eye previews and Styled Looks as separate surfaces. Verify the heart filter, empty results, removal of the last visible favorite, hidden-plus-favorite combinations, category/form changes and restart without changing worn parts. Distinguish user-required heart presentation from a donor's star control.
4. **Search semantics:** compare named/unnamed CC, blank descriptions, same-name different packages, multiple swatches, comma terms and empty terms. Record actual union/intersection behavior rather than guessing it. Verify Eye Preview, Styled Looks and Cheek subcategories separately; preserve exact identity when labels collide. No package mutation is needed to test Apex's indexed metadata path.
5. **Keyboard and shared layout:** press A/D and arrows with a selected item, an open swatch popup and focused search/naming/numeric fields. Check that typing never equips an unintended swatch. Change one auxiliary panel's dimensions and verify intentional shared-layout behavior without accidentally overwriting the main catalog or saved favorites.
6. **CC-list boundary:** select across categories, commit/cancel, filter by count, remove one entry and reopen. Export exact identifiers with unresolved or duplicate providers visible. Test any external mover separately on disposable fixtures with the game closed; never infer that deselecting/hiding an item authorizes moving or deleting its package.
