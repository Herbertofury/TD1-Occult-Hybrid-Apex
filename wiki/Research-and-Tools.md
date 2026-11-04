# Research & Tools

## Occult/Sims references

- L-P-TD1/ts4-occulthybrid — upstream source lineage.
- Oops19/TS4-XmlInjector — tuning/XML injection patterns.
- stark-studio-labs/sims4-stark-devkit — Sims development reference.

## Overlay / profiling

- ocornut/imgui — Dear ImGui.
- TsudaKageyu/minhook — narrow hook reference.
- microsoft/Detours — mature Windows instrumentation reference.
- GameTechDev/PresentMon — frame/present telemetry.
- WPR/WPA — thread, CPU and I/O proof.

Codex should record a disposition for every challenger: adopt, adapt, reference, or reject; include the reason and provenance.

### Frame-time investigation references

These are measurement references, not evidence that a tool or change improves Apex. Validate availability, compatibility and overhead on the target machine before use.

- [PresentMon console documentation](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md): process-targeted CSV capture can record per-frame timing, CPU and GPU metrics. Some metrics require additional instrumentation or options; check the actual CSV columns and dropped-event diagnostics before interpreting them. Preserve raw captures alongside tool version and settings.
- [Microsoft WPR introduction](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/introduction-to-wpr) and [GPUView guide](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/using-gpuview): ETW recordings can help correlate frame stalls with CPU scheduling, file activity and GPU events. Check trace requirements and collection overhead; a correlation is a lead to investigate, not proof of causation.
- [AMD Radeon GPU Profiler compatibility](https://gpuopen.com/manuals/rgp_manual/): RGP supports explicit graphics APIs such as DirectX 12 and Vulkan; its manual says it does not work with DirectX 11 or OpenGL. Check the running game's actual graphics API and GPU before choosing it; do not assume it can profile an older API.

For each repeatable gameplay or CAS scenario, compare equivalent unmodded and modded captures under the same game version, save, graphics settings, frame cap and workload. Include frame-time distributions and worst stalls, not average FPS alone. Mark loading or other deliberate transitions, retain the raw files, and repeat after a targeted change. Any claim of improvement requires an actual comparison on the target game with required functionality intact.
