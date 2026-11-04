# Post-v138 CAS diagnostic status

The five-slot private preview remains experimental. Native Tray save, real-game write/readback, native material fidelity, complete editing, independent top/bottom selection, durable integrated session restore, and current five-slot browser acceptance remain unverified. No creator assets or private configuration are included here.

A solid-color foreground coverage diagnostic compared the paired-face candidate against the default renderer. In one private top/bottom scene, 23 poses across nine yaw angles produced 207 frames with zero foreground coverage pixels lost or gained. A second legacy scene produced zero differences over 69 frames. This resolves an earlier inconclusive background-color heuristic for those tested scenes only, not native fidelity or broad compatibility. The diagnostic remains opt-in and is not recommended as a production default.

On one local run of 69 frames, median renderer timings were 34.59 ms default, 59.92 ms recomputing pairs, and 32.68 ms using cached pairs. Dynamic and cached pair-frame hashes matched. These are local measurements, not a general performance guarantee. Separately, a copy-on-write staging experiment cloned no files on this filesystem and was slower than the retained original; it was not adopted.

A 10-source private catalog contained 236 CASPs, including 10 tops and 10 bottoms, with source bytes unchanged. This does not demonstrate independent selection or compatibility. Existing archive-level README and qualification files describe v71 and should not be interpreted as current completion evidence.
