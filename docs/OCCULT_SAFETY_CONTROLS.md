# Autonomy and occult safety

F11 has a **Pause autonomy** control above the navigation. It stops new world
autonomy decisions for the default native settings group without pausing time
or cancelling user-directed interactions. Turning it off restores the exact
previous override, including an inherited or already-disabled setting.
Readback determines the displayed state. A conflicting change from another
mod is retained and reported rather than overwritten.

The Apex tab also contains three controls:

- **Prevent deaths (world, this session)** uses the native death-enable switch
  and restores its previous value. It does not revive a Sim already dying.
- **Disable vampire sunlight burning for this Sim** filters only the exact
  sunlight buffs supplied by installed vampire trait tuning. Day/night effects
  and other Sims retain their native behavior. Existing matching sunlight buffs
  are removed and checked when enabling this preference.
- **Disable automatic umbrellas for this Sim** prevents native routing from
  adding the umbrella-opening event. Put-away events remain native; an already
  open umbrella can still be put away normally.

Sunlight and umbrella preferences are stored by save GUID and Sim ID, independently
of appearance, traits, perks and occult membership. Autonomy/death overrides last
for the session. These features add no recurring scan or polling timer, and their
callbacks perform no file access. Disabled wrappers delegate the original call
with its original arguments and optional defaults.

The equivalent commands in the disposable testing CLI are:

```powershell
python tools/apex_cli.py qol autonomy-pause --state .work/reusable-profile-session.json --sim-id SIM_ID
python tools/apex_cli.py qol autonomy-resume --state .work/reusable-profile-session.json --sim-id SIM_ID
python tools/apex_cli.py qol death-prevent --state .work/reusable-profile-session.json --sim-id SIM_ID
python tools/apex_cli.py qol sunlight-on --state .work/reusable-profile-session.json --sim-id SIM_ID
python tools/apex_cli.py qol umbrella-on --state .work/reusable-profile-session.json --sim-id SIM_ID
python tools/apex_cli.py qol status --state .work/reusable-profile-session.json --sim-id SIM_ID
```

`sunlight-off`, `umbrella-off` and `death-restore` reverse the corresponding
controls. `qol status` reports each loaded household member's dying/dead state
and effective autonomy setting. Saving during a death restriction remains an
unverified operation; it is never force-saved or replayed automatically.

With the disposable game closed, `qol arm-test-safety --state STATE` explicitly
arms next-load autonomy pause, death prevention and a paused clock for that one
marked test profile. `disarm-test-safety` removes this startup choice. Production
profiles are not armed by this command.

## Special-form qualification

Installed game 1.128.90 exposes Human, Alien, Vampire, Mermaid, Witch, Werewolf
and Fairy in `OccultType`. Ghost, PlantSim, Servo and temporary transformations
use other state owners. They must be tested and represented through their actual
traits, buffs, species/mechanical state and complete save-model fields rather
than invented occult bit values. T132 remains open: independent appearance edits,
CAS/Live transitions, death/revival overlays and save/Tray round trips for those
states have not been qualified by the seven-form household tests.
