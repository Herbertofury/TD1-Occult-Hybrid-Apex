# Special appearances and native occult forms

This is the implementation/acceptance plan for T132. It is not a completed
special-form stability claim.

Read-only inspection of installed game 1.128.90's `simulation.zip` establishes
that `OccultType` contains Human, Alien, Vampire, Mermaid, Witch, Werewolf and
Fairy. The existing seven appearance owners correspond to those native types.

Ghost behavior belongs to other owners. `SimInfo.is_ghost` delegates to its
death tracker; that tracker tests actual ghost traits from
`DEATH_TYPE_GHOST_TRAIT_MAP`. A detached `SimInfoBaseWrapper.is_ghost` returns
false. Ghost base/edge colors also belong to `SimInfo`, with a native
`set_ghost_color`/distributor path. Treating a stored occult wrapper as a complete
Ghost would therefore lose its overlay state. The complete native save-model
export already retains ghost colors, death state, traits and unknown fields,
but export alone is not independent editing or round-trip qualification.

Special-form implementation must:

- Identify capabilities through actual native traits, buffs, robot/mechanical
  state and death state. Preserve every unknown state in the complete native
  record; do not invent new `OccultType` bits.
- Keep native appearance ownership separate from state activation. Editing an
  appearance must not recreate a Sim, change household identity or reload an
  unvalidated whole Sim save record.
- Namespace special looks by Sim, save, native occult owner and explicit special
  profile. Capture the base appearance before a temporary overlay and retain
  its independent edits when entering/leaving that overlay.
- Preserve Ghost colors and temporary visual/voice effects separately from the
  permanent Alien/Vampire/etc. appearance. Test that a transient effect is not
  committed implicitly to another stored form.
- Expose native availability/activation and unsupported operations explicitly
  in F11/CLI. Restore only through a validated owner-specific native path.

Acceptance remains open for Ghost, PlantSim, Servo, Skeleton, Scarecrow and other
available temporary/custom states. Each needs full CAS and Live editing,
single-member and whole-household transitions, independent outfits/skin details/
sliders, positive unpaused ticks, normal save/cold reload and Tray import/export.
The Vampire/Alien five-member test is the priority before adding another state
to its disposable household.
