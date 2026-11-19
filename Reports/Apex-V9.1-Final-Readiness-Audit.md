# TD1 Occult Hybrid Apex V9.1 - Final Readiness Audit

Date: 2026-05-28
Build: 2026.05.28-v9.1-ready-overlay-safe

## Result

Offline readiness audit passed after a final overlay API hardening fix.

## Issue Found and Fixed

During the final double-check, `/api/overlay/capabilities` and `/api/overlay/state` returned HTTP 500 outside the Sims runtime. Root cause: layered V6/V8/V9 compatibility code redefined `_load_saved_forms()` with a boolean-returning loader, while an older overlay capabilities function still expected a dictionary return value.

V9.1 appends a final readiness shim that:

- Replaces `_overlay_capabilities()` with a JSON-safe capability payload that does not depend on shadowed legacy loaders.
- Replaces `_logs_payload()` with a safe log payload.
- Replaces `_overlay_state_payload()` with a fail-closed state payload for the F11 ImGui overlay.
- Keeps saved-form rows/counts functional through `_list_saved_forms()` first, then dictionary fallback.
- Keeps command execution routed through `/api/command` and the Sims action queue.

## Endpoint Smoke Test

Validated outside the game runtime:

- `/` returned HTTP 200 and loaded the local browser panel.
- `/api/overlay/capabilities` returned HTTP 200 and valid JSON.
- `/api/overlay/state?count=40` returned HTTP 200 and valid JSON.
- `/api/command?action=qa_self_test` returned HTTP 200 and valid JSON. It correctly reported missing Sims runtime modules in the sandbox.
- `/api/command?action=cas_category_status` returned HTTP 200 and reported 116 CAS category buttons.
- `/api/command?action=list_saved_forms` returned HTTP 200 and reported an empty saved-form catalog.

## Static Validation

- Final ZIP integrity: pass.
- Apex `.ts4script` integrity: pass.
- Embedded `td1_occult_hybrid_apex.py` matches `Source/td1_occult_hybrid_apex.py`.
- Python 3.7 AST parse: pass.
- Native helper DLL type: PE32+ x64 Windows DLL.
- Native helper export count: 32.
- F11 overlay source includes command buttons, toggles, running log, QA self-test, MCCC shield, Drift Guard, Reference Shots, CAS Tools, and CAS Categories.
- CAS BodyType table contains 116 rows and the critical categories are present.
- No `__pycache__` or `.pyc` files added by Apex packaging.

## Notes

The sandbox cannot launch The Sims 4, load a real save, or compile/run the Windows DirectX 11 proxy DLL. Windows Visual Studio build and in-game smoke testing are still required for the native overlay DLL.

The QA self-test intentionally reports fatal runtime-import errors outside the game because Sims modules such as `protocolbuffers.Outfits_pb2`, `services`, `alarms`, and `sims.outfits.outfit_enums.BodyType` are not available in this Linux sandbox. That is expected and is not an archive/package failure.
