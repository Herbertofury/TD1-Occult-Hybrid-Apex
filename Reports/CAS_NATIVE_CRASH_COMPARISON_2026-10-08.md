# Native CAS crash comparison — 2026-10-08

The preserved Fairy CAS failure repeats the native null-read signature from five earlier CAS failures. Its cause remains unverified. This comparison does not close alternate-form return, acceptance, appearance persistence or stability gates.

The bounded offline comparison covered nine unique crash XML reports from the same game build, `1.128.90.1030`. Six reports have native PC `0x14112c645`, exception code `0xc0000005`, inaccessible read address `0x8`, and a null pointer register. Their first three reported stack addresses match; later callers differ. The exception flag and inaccessible address were decoded according to Microsoft's [MINIDUMP_EXCEPTION structure](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception). The dump's exception, module and memory stream types follow the documented [MINIDUMP_STREAM_TYPE values](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ne-minidumpapiset-minidump_stream_type).

| Preserved event | Time | Exact null-read signature |
| --- | --- | --- |
| Prologue | 06:02:49 | Yes |
| Native edit | 06:19:02 | Yes |
| No-overlay edit | 06:30:43 | Yes |
| Timer entry | 06:59:16 | Yes |
| Serialization-guard Human entry | 17:59:40 | Yes |
| v2 Fairy entry; Cancel dialog observed | 21:00:40 | Yes |

The earlier no-overlay capture has a module-list stream with no Apex module, and its host evidence records the sidecar absent. The matching failure therefore predates the newest selector observer and also occurred in an observed run without a loaded Apex overlay. This does not identify the CAS bridge, patched UI, native engine or original save as the cause.

The latest entry successfully recorded the raw Human/Fairy pair. A later first Cancel input opened the native confirmation dialog; no confirmation input was submitted before the bridge disappeared. The preserved bound-crash proof retains `causality_verified=false` and `report_pid_attribution_verified=false`. The dialog warning alone does not supersede the independently observed native existing-Sim CAS mode.

A separate source review found that the existing socket CONNECT callback queried native Sim identity outside the owned Timer. The form-selection work is addressing that execution-phase issue separately. The crash evidence does not establish that this callback was executing when the native failure occurred.

Private evidence is preserved in ignored `.work/research/owner-v2-cas-crash-comparison.json` and `.work/research/owner-v2-cas-crash-investigation.md`. The comparison records input hashes, bounded parsing, diagnostic registers and inspected-source hashes. Executable bytes, proprietary decompilation and user appearance/bank data are excluded from this public report. Missing native symbols and caller code prevent causal attribution. No game input, process-memory access, profile writes or protected-original changes were made by the investigation.
