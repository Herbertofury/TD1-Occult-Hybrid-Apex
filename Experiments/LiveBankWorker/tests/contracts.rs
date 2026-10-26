use apex_live_bank_worker_prototype::*;
use std::{
    fs, thread,
    time::{Duration, Instant},
};

fn context() -> Context {
    Context {
        uuid: "a".repeat(32),
        save: "10".into(),
        sim: "20".into(),
    }
}
fn original() -> Vec<u8> {
    br#" {"schema":1,"future":{"number":184467440737095516151234567890,"decimal":1.2300e+03,"surrogate":"\ud800","escaped":"\uD83E\uDDD9"},"records":{"10:20":{"bank":{"1":{"unknown":"retained"}},"alien_unknown":[7,8],"switch_pending":null,"switch_history":[]},"10:21":{"untouched_number":-0.00e-03}}} "#.to_vec()
}
fn updates(phase: Phase) -> Vec<Update> {
    let ctx = context();
    if phase == Phase::Complete {
        vec![
        Update{key:"switch_pending".into(),raw:b"null".to_vec()},
        Update{key:"switch_history".into(),raw:format!(r#"[{{"request_id":"{}","state":"immediate-native-readback-verified","all_stored_owners_verified":true,"active_owner_verified":true,"unknown":"history-opaque"}}]"#,ctx.uuid).into_bytes()},
        Update{key:"active_lane".into(),raw:b"4".to_vec()}
    ]
    } else {
        vec![Update {
            key: "switch_pending".into(),
            raw: format!(
                r#"{{"request_id":"{}","state":"{}","originals":{{"unknown_future":"retained"}}}}"#,
                ctx.uuid,
                if phase == Phase::Captured {
                    "captured"
                } else {
                    "native-operation-issued"
                }
            )
            .into_bytes(),
        }]
    }
}
fn request(phase: Phase, before: &[u8]) -> Request {
    Request {
        context: context(),
        phase,
        expected_sha: sha(before),
        updates: updates(phase),
        fault: Fault::None,
    }
}
fn ticket(worker: &Worker, req: Request) -> u64 {
    match worker.submit(req) {
        Submit::Accepted(ticket) => ticket,
        other => panic!("Unexpected submit: {other:?}"),
    }
}
fn done(worker: &Worker, ctx: &Context, ticket: u64) -> Poll {
    let start = Instant::now();
    loop {
        let value = worker.poll(ctx, ticket);
        if !matches!(value, Poll::Pending) {
            return value;
        }
        assert!(start.elapsed() < Duration::from_secs(5));
        thread::sleep(Duration::from_millis(1));
    }
}
fn ready(worker: &Worker, ctx: &Context, ticket: u64) -> Receipt {
    match done(worker, ctx, ticket) {
        Poll::Ready(r) => r,
        other => panic!("Expected Ready: {other:?}"),
    }
}

#[test]
fn strict_validator_rejects_duplicate_nonfinite_invalid_number_unicode_and_trailing_data() {
    for raw in [
        br#"{"x":1,"x":2}"#.as_slice(),
        br#"{"a":1,"\u0061":2}"#,
        br#"{"x":{"a":1,"\u0061":2}}"#,
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e999",
        b"-1e999",
        b"01",
        b"1.",
        b"1e",
        b"1e+",
        b"[1,]",
        b"{\"a\":1,}",
        b"{}{}",
        b"\xff",
        br#""\uqqqq""#,
    ] {
        assert!(
            validate_json(raw).is_err(),
            "Accepted {}",
            String::from_utf8_lossy(raw)
        );
    }
}

#[test]
fn strict_validator_preserves_large_integers_numeric_spelling_and_python_lone_surrogates() {
    for raw in [
        b"1844674407370955161512345678901234567890".as_slice(),
        b"-0",
        b"-0.00e-03",
        b"1.2300E+2",
        br#""\ud800""#,
        br#"{"\ud800":"unpaired"}"#,
    ] {
        assert!(validate_json(raw).is_ok());
    }
    let literal = "{\"🧙\":1,\"\\uD83E\\uDDD9\":2}".as_bytes().to_vec();
    assert!(validate_json(&literal).unwrap_err().contains("Duplicate"));
}

#[test]
fn raw_patch_changes_only_one_reviewed_value_and_preserves_every_other_byte() {
    let before = original();
    let req = request(Phase::Captured, &before);
    let after = patch_document(&before, &req).unwrap();
    let old = b"\"switch_pending\":null";
    let replacement = [
        b"\"switch_pending\":".as_slice(),
        req.updates[0].raw.as_slice(),
    ]
    .concat();
    let at = before.windows(old.len()).position(|w| w == old).unwrap();
    let expected = [
        &before[..at],
        replacement.as_slice(),
        &before[at + old.len()..],
    ]
    .concat();
    assert_eq!(after, expected);
    assert!(
        after
            .windows(b"184467440737095516151234567890".len())
            .any(|w| w == b"184467440737095516151234567890")
    );
    assert!(
        after
            .windows(b"\"10:21\":{\"untouched_number\":-0.00e-03}".len())
            .any(|w| w == b"\"10:21\":{\"untouched_number\":-0.00e-03}")
    );
}

#[test]
fn three_ordered_durable_barriers_have_exact_complete_readbacks_and_no_native_authority() {
    let dir = tempfile::tempdir().unwrap();
    let file = dir.path().join("form_bank.json");
    fs::write(&file, original()).unwrap();
    let worker = Worker::open(dir.path()).unwrap();
    assert_eq!(
        worker.limits(),
        (2, MAX_JOBS, MAX_DOCUMENT, MAX_DOCUMENT * 5 * MAX_JOBS)
    );
    let mut before = original();
    for phase in [Phase::Captured, Phase::Issued, Phase::Complete] {
        let req = request(phase, &before);
        let expected = patch_document(&before, &req).unwrap();
        let t = ticket(&worker, req);
        let receipt = ready(&worker, &context(), t);
        assert_eq!(receipt.before_sha, sha(&before));
        assert_eq!(receipt.file_sha, sha(&expected));
        assert_eq!(receipt.before_bytes, before.len());
        assert_eq!(receipt.after_bytes, expected.len());
        assert!(receipt.durable);
        assert!(!receipt.native_call_authorized);
        assert_eq!(fs::read(&file).unwrap(), expected);
        assert!(!dir.path().join(".form_bank.json.cas-writer.lock").exists());
        assert!(!dir.path().join("form_bank.json.pending").exists());
        before = expected;
    }
}

#[test]
fn issued_or_complete_cannot_jump_a_durable_barrier_or_use_stale_sha() {
    let dir = tempfile::tempdir().unwrap();
    fs::write(dir.path().join("form_bank.json"), original()).unwrap();
    let worker = Worker::open(dir.path()).unwrap();
    assert!(matches!(
        worker.submit(request(Phase::Issued, &original())),
        Submit::Refused(_)
    ));
    assert!(matches!(
        worker.submit(request(Phase::Complete, &original())),
        Submit::Refused(_)
    ));
    let t = ticket(&worker, request(Phase::Captured, &original()));
    let receipt = ready(&worker, &context(), t);
    assert_ne!(receipt.file_sha, sha(&original()));
    assert!(matches!(
        worker.submit(request(Phase::Issued, &original())),
        Submit::Refused(_)
    ));
}

#[test]
fn repeated_uuid_adopts_no_new_input_and_only_exposes_its_original_ticket() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("form_bank.json");
    fs::write(&path, original()).unwrap();
    let worker = Worker::open(dir.path()).unwrap();
    let req = request(Phase::Captured, &original());
    let t = ticket(&worker, req.clone());
    let first = ready(&worker, &context(), t);
    let durable = fs::read(&path).unwrap();
    let mut changed = req;
    changed.updates[0].raw = b"BAD NEW INPUT MUST NOT BE ADOPTED".to_vec();
    assert_eq!(
        worker.submit(changed),
        Submit::OriginalOnly {
            ticket: t,
            input_not_adopted: true
        }
    );
    assert_eq!(fs::read(&path).unwrap(), durable);
    assert_eq!(ready(&worker, &context(), t).file_sha, first.file_sha);
}

#[test]
fn ownership_is_bound_across_phases_and_poll_context_is_exact() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("form_bank.json");
    fs::write(&path, original()).unwrap();
    let worker = Worker::open(dir.path()).unwrap();
    let t = ticket(&worker, request(Phase::Captured, &original()));
    let first = ready(&worker, &context(), t);
    let mut wrong = context();
    wrong.sim = "21".into();
    assert!(matches!(worker.poll(&wrong, t), Poll::ContextMismatch));
    let mut req = request(Phase::Issued, &fs::read(&path).unwrap());
    req.context = wrong;
    req.expected_sha = first.file_sha;
    assert!(matches!(worker.submit(req), Submit::Refused(_)));
    assert!(matches!(worker.poll(&context(), u64::MAX), Poll::Unknown));
}

#[test]
fn external_revision_change_is_not_overwritten() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("form_bank.json");
    let changed = b"{\"schema\":1,\"records\":{\"10:20\":{\"external\":true}}}";
    fs::write(&path, changed).unwrap();
    let worker = Worker::open(dir.path()).unwrap();
    let t = ticket(&worker, request(Phase::Captured, &original()));
    assert!(matches!(
        done(&worker, &context(), t),
        Poll::Failed {
            outcome_may_be_durable: false,
            ..
        }
    ));
    assert_eq!(fs::read(&path).unwrap(), changed);
}

#[test]
fn foreign_or_stale_writer_lease_is_never_stolen() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("form_bank.json");
    fs::write(&path, original()).unwrap();
    let lock = dir.path().join(".form_bank.json.cas-writer.lock");
    fs::write(&lock, b"foreign").unwrap();
    let worker = Worker::open(dir.path()).unwrap();
    let t = ticket(&worker, request(Phase::Captured, &original()));
    assert!(matches!(done(&worker, &context(), t), Poll::Failed { .. }));
    assert_eq!(fs::read(&lock).unwrap(), b"foreign");
    assert_eq!(fs::read(&path).unwrap(), original());
}

#[test]
fn unknown_fields_or_records_cannot_be_selected_for_patching() {
    let before = original();
    let mut req = request(Phase::Captured, &before);
    req.updates.push(Update {
        key: "alien_unknown".into(),
        raw: b"[]".to_vec(),
    });
    assert!(patch_document(&before, &req).is_err());
    req = request(Phase::Captured, &before);
    req.context.sim = "22".into();
    assert!(patch_document(&before, &req).is_err());
    req = request(Phase::Captured, &before);
    req.updates[0].raw = br#"{"request_id":"other","state":"captured"}"#.to_vec();
    assert!(patch_document(&before, &req).is_err());
}

#[test]
fn duplicate_patch_key_and_malformed_phase_witness_are_refused() {
    let before = original();
    let mut req = request(Phase::Captured, &before);
    req.updates.push(req.updates[0].clone());
    assert!(patch_document(&before, &req).is_err());
    let mut req = request(Phase::Complete, &before);
    req.updates[1].raw=format!(r#"[{{"request_id":"{}","state":"immediate-native-readback-verified","all_stored_owners_verified":1,"active_owner_verified":true}}]"#,context().uuid).into_bytes();
    assert!(patch_document(&before, &req).is_err());
}

#[test]
fn existing_foreign_or_legacy_wal_cannot_be_overwritten_and_next_phase_requires_prior_witness() {
    let before = original();
    let captured = patch_document(&before, &request(Phase::Captured, &before)).unwrap();
    assert!(
        patch_document(&captured, &request(Phase::Captured, &captured))
            .unwrap_err()
            .contains("retained")
    );
    assert!(patch_document(&before, &request(Phase::Issued, &before)).is_err());
    assert!(patch_document(&captured, &request(Phase::Complete, &captured)).is_err());
    let legacy = String::from_utf8(before.clone())
        .unwrap()
        .replace(
            "\"switch_pending\":null",
            "\"switch_pending\":null,\"pending\":{\"state\":\"captured\"}",
        )
        .into_bytes();
    assert!(
        patch_document(&legacy, &request(Phase::Captured, &legacy))
            .unwrap_err()
            .contains("legacy")
    );
}

#[test]
fn every_durability_fault_retains_originals_or_ambiguous_durable_evidence_without_replay() {
    for phase in [Phase::Captured, Phase::Issued, Phase::Complete] {
        for fault in [
            Fault::BeforeRead,
            Fault::BeforeWrite,
            Fault::AfterTempSync,
            Fault::BeforeReplace,
            Fault::AfterReplace,
            Fault::AfterReadback,
            Fault::WrongReadback,
            Fault::LostReceipt,
        ] {
            let dir = tempfile::tempdir().unwrap();
            let path = dir.path().join("form_bank.json");
            fs::write(&path, original()).unwrap();
            let worker = Worker::open(dir.path()).unwrap();
            let mut before = original();
            for prior in [Phase::Captured, Phase::Issued] {
                if prior >= phase {
                    break;
                }
                let t = ticket(&worker, request(prior, &before));
                ready(&worker, &context(), t);
                before = fs::read(&path).unwrap();
            }
            let mut req = request(phase, &before);
            req.fault = fault;
            let expected = patch_document(&before, &req).unwrap();
            let t = ticket(&worker, req.clone());
            let result = done(&worker, &context(), t);
            let replaced = matches!(
                fault,
                Fault::AfterReplace
                    | Fault::AfterReadback
                    | Fault::WrongReadback
                    | Fault::LostReceipt
            );
            assert!(
                matches!(result,Poll::Failed{outcome_may_be_durable,..} if outcome_may_be_durable==replaced),
                "Wrong outcome for {phase:?}/{fault:?}: {result:?}"
            );
            assert_eq!(
                fs::read(&path).unwrap(),
                if replaced { expected } else { before }
            );
            assert_eq!(
                dir.path().join(".form_bank.json.cas-writer.lock").exists(),
                replaced
            );
            assert_eq!(
                worker.submit(req),
                Submit::OriginalOnly {
                    ticket: t,
                    input_not_adopted: true
                }
            );
        }
    }
}
