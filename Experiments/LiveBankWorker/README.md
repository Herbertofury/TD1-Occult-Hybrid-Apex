# Experimental Live bank byte worker

Not wired into Sims, the Apex DLL, Python, F11, the command queue, or any game
profile. All tests use new temporary directories. A receipt proves durable
metadata bytes only and always says `native_call_authorized: false`.

This versioned experiment is deliberately separate from production packages
and startup. It installs no service, starts no background process by default,
and is not a qualified many-thousand-Sim release component. Its Rust source,
tests and pinned dependency lock match the frozen private prototype.

## Purpose and boundary

The current synchronous `form_bank.switch` performs two full bank reads before
three ordered durable writes. That cost runs inside the owner-thread command;
the queue's one-millisecond budget cannot preempt an individual command.
This prototype proves the disk/JSON work can run behind nonblocking submit/poll
without moving a Sim, tracker, wrapper, game API, Python mapping, GFx object,
callable, or borrowed native pointer to another thread.

The owner of a `Request` moves its immutable, independently owned byte buffers
into a worker. Submit inspects only bounded primitive context and lengths. It
does not parse JSON, hash a large patch, wait for disk, join a thread, or encode
a Python mapping. Two bounded Rayon workers perform the pure work; a separate
single writer lane serializes this bank's filesystem transactions. All status
receipts contain copied primitives and bounded strings.

This Rust API is a prototype library, not a C ABI yet. A production FFI must
copy exactly bounded input bytes before returning and use fixed exports, with
an authenticated profile/root capability. Merely creating a Python thread
around `json.dumps` would still contend on the game interpreter's GIL and is
not the implementation proposed here.

## Exact JSON and edits

The strict scanner validates the complete input document and every patch:

- decoded duplicate keys are rejected at any depth;
- malformed UTF-8, malformed JSON, trailing input and nonfinite floats fail;
- arbitrary-size integers never pass through floating-point conversion;
- float spelling, negative zero, whitespace, escaped Unicode and accepted
  escaped lone surrogates are retained byte-for-byte where untouched;
- literal astral Unicode and its escaped surrogate pair compare as the same
  key, so differently encoded duplicates cannot pass.

There is no appearance-protobuf projection and no full `serde_json::Value`
reserialization. Only reviewed top-level value spans in one existing selected
record can change. Every other bank byte—including every other Sim's record
and unknown metadata—remains exact. New reviewed keys are inserted inside the
selected record only. A targeted value such as `bank` is an explicit complete
caller-supplied value; the worker cannot infer appearance authority or preserve
unknown subfields that the caller incorrectly omitted from that replacement.
The future owner-thread receiver must verify the complete replacement plan.

An existing foreign switch WAL, a legacy pending WAL, an absent selected
record, an unknown patched key, a mismatching WAL UUID, and a skipped phase
are refused. The prototype does not replace the full current Python `_blocked`
contract for every CAS journal variant. That remains a required owner-thread
admission gate in an eventual integration.

## Three ordered durability barriers

For one exact UUID/save/Sim context:

1. `Captured`: retain complete originals in `switch_pending` before any native
   mutation. An existing switch/legacy WAL cannot be overwritten.
2. `Issued`: require the preceding acknowledged whole-file SHA and captured
   witness, then persist `native-operation-issued` before native execution.
3. `Complete`: require the preceding issued witness, a completed history row
   with both stored and active full-owner verification flags, and clear the
   pending marker in the same atomic metadata replacement.

Each phase acquires the same exclusive cooperative lock filename as Python,
reads and strictly validates the complete bank, checks its expected SHA,
writes a new `.pending` file with `create_new`, syncs it, verifies its lease,
rechecks current complete bank bytes, atomically renames, and reads back and
compares the entire resulting file before publishing Ready. SHA/revision
advances only on that Ready receipt. Unknown/existing leases and pending files
are never stolen or overwritten.

A fault before replacement leaves the original bank. A post-replacement fault
retains the potentially durable bank and its lease, publishes Failed with
`outcome_may_be_durable: true`, and never retries the phase. No automatic
rollback or native replay is authorized. Like the existing Python protocol,
this is a cooperative writer contract, not an atomic compare-and-swap against
an external writer that ignores the lease. Windows power-loss/directory
durability semantics require additional qualification; successful byte
readback alone does not establish power-loss persistence.

## Idempotency, bounds, and lifecycle

Only one phase of a context may be in flight. Later phases must present the
prior exact acknowledged SHA. A reused UUID for another save/Sim is refused.
Any duplicate UUID/phase returns only its original ticket with the explicit
`input_not_adopted: true` flag. It does not compare, accept, or apply the newly
supplied replacement bytes. The caller must poll that original ticket.

Limits are explicit: two workers, four in-flight jobs, 48 MiB per complete
document, depth 128, two million JSON nodes, and 256 retained phase receipts.
The byte reservation budget is reported. Capacity exhaustion returns Busy or
an explicit refusal; there is no silent clipping, eviction, dropped form,
history truncation, or fallback. The retained-receipt budget and conservative
reservation model are prototype limits, not a qualified many-thousand-Sim
production design. A durable receipt-retirement/idempotency ledger is still
needed before long-running release use.

## Remaining production integration

The future game-thread state machine must capture native bytes at bounded
owner boundaries, revalidate the complete before-image after each yield,
respect owner/save/generation changes, perform native mutation exactly once,
preserve the permanent native guard, and capture/verify every owner after the
last reconciliation write. Worker completion cannot authorize these steps by
itself. No unrelated interaction, Gallery control, or save navigation should
be disabled while a job waits; only the target's conflicting appearance writes
need an exact pending fence. Existing saves must continue to use their actual
serialization preservation boundary.

`CommandQueue.drain` currently completes any `{ok: true}` result. It needs an
explicit internal waiting-continuation state, not a JSON `pending` object
passed off as a completed mutation. The original UUID must remain pollable;
transport timeouts after issuance must never resubmit the native operation.

## Validation

Run:

    $env:CARGO_TARGET_DIR = "$PWD/.work/live-bank-worker-prototype/target"
    cargo test --offline --manifest-path Experiments/LiveBankWorker/Cargo.toml

Fourteen tests pass: thirteen integration tests plus one scheduling test. The
durability test exercises eight injected faults at each of three phases
(24 combinations). A held disk lane leaves four submitted jobs pending while
the caller performs thousands of nonblocking polls and receives explicit Busy
for a fifth job. No actual game latency, CPU utilization, universal hitch-free
behavior, production readiness, or performance improvement is claimed.
