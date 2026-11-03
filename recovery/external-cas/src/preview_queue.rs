//! Bounded latest-request-wins PREVIEW queue. Never use for durable edit commands.
//! At most one render in flight and one desired request. Stale completion cannot
//! reopen a closed view or replace a newer scene. Failed frames retain last-good.
use crate::preview::Frame;
use std::sync::Arc;
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Ticket {
    pub epoch: u64,
    pub sequence: u64,
    pub pose_revision: u64,
}
#[derive(Debug, Clone, Copy)]
pub struct Request {
    pub ticket: Ticket,
    pub yaw: f32,
}
#[derive(Default)]
pub struct PreviewQueue {
    epoch: u64,
    sequence: u64,
    open: bool,
    desired: Option<Request>,
    running: Option<Request>,
    displayed: Option<(Ticket, Arc<Frame>)>,
    failure: Option<(Ticket, &'static str)>,
}
impl PreviewQueue {
    pub fn open(&mut self) -> Result<(), &'static str> {
        let next = self.epoch.checked_add(1).ok_or("preview epoch overflow")?;
        self.epoch = next;
        self.open = true;
        self.desired = None;
        self.displayed = None;
        self.failure = None;
        Ok(())
    }
    pub fn close(&mut self) {
        self.open = false;
        self.desired = None;
        self.displayed = None;
        self.failure = None;
    }
    pub fn request(&mut self, yaw: f32, pose_revision: u64) -> Result<Ticket, &'static str> {
        if !self.open || !yaw.is_finite() {
            return Err("closed/invalid preview request");
        }
        let sequence = self
            .sequence
            .checked_add(1)
            .ok_or("preview sequence overflow")?;
        self.sequence = sequence;
        let ticket = Ticket {
            epoch: self.epoch,
            sequence,
            pose_revision,
        };
        self.desired = Some(Request { ticket, yaw });
        self.failure = None;
        Ok(ticket)
    }
    pub fn take_work(&mut self) -> Option<Request> {
        if !self.open || self.running.is_some() {
            return None;
        }
        let desired = self.desired?;
        if self
            .displayed
            .as_ref()
            .is_some_and(|x| x.0 == desired.ticket)
            || self.failure.is_some_and(|x| x.0 == desired.ticket)
        {
            return None;
        }
        self.running = Some(desired);
        Some(desired)
    }
    pub fn complete(&mut self, ticket: Ticket, result: Result<Frame, &'static str>) -> bool {
        if !self.running.is_some_and(|r| r.ticket == ticket) {
            return false;
        }
        self.running = None;
        if !self.open || !self.desired.is_some_and(|r| r.ticket == ticket) {
            return false;
        }
        match result {
            Ok(frame) => {
                if !(16..=1024).contains(&frame.width)
                    || !(16..=1024).contains(&frame.height)
                    || frame.rgb.len() != frame.width * frame.height * 3
                    || frame.covered_pixels > frame.width * frame.height
                    || frame.triangles > 2_000_000
                {
                    self.failure = Some((ticket, "invalid completed frame"));
                    return false;
                }
                self.displayed = Some((ticket, Arc::new(frame)));
                self.failure = None;
                true
            }
            Err(error) => {
                self.failure = Some((ticket, error));
                false
            }
        }
    }
    pub fn displayed(&self) -> Option<&Arc<Frame>> {
        self.displayed.as_ref().map(|x| &x.1)
    }
    pub fn is_stale(&self) -> bool {
        self.displayed
            .as_ref()
            .is_some_and(|x| !self.desired.is_some_and(|r| r.ticket == x.0))
    }
    pub fn failure(&self) -> Option<&'static str> {
        self.failure.map(|x| x.1)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn frame() -> Frame {
        Frame {
            width: 16,
            height: 16,
            rgb: vec![0; 768],
            covered_pixels: 0,
            triangles: 0,
            stage_ms: None,
        }
    }
    #[test]
    fn late_completion_never_replaces_newer_request() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let old = q.take_work().unwrap();
        let latest = q.request(1., 2).unwrap();
        assert!(!q.complete(old.ticket, Ok(frame())));
        assert!(q.displayed().is_none());
        assert_eq!(q.take_work().unwrap().ticket, latest);
        assert!(q.complete(latest, Ok(frame())));
    }
    #[test]
    fn close_and_reopen_do_not_accept_old_scene() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let old = q.take_work().unwrap();
        q.close();
        assert!(!q.complete(old.ticket, Ok(frame())));
        assert!(q.displayed().is_none());
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let new = q.take_work().unwrap();
        assert_ne!(old.ticket.epoch, new.ticket.epoch);
        assert!(!q.complete(old.ticket, Ok(frame())));
        assert!(q.complete(new.ticket, Ok(frame())));
    }
    #[test]
    fn coalesces_ten_thousand_requests_not_edits() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let old = q.take_work().unwrap();
        let mut last = old.ticket;
        for i in 0..10000 {
            last = q.request(i as f32, 1).unwrap();
            assert!(q.take_work().is_none());
        }
        assert!(!q.complete(old.ticket, Ok(frame())));
        assert_eq!(q.take_work().unwrap().ticket, last);
        assert!(q.complete(last, Ok(frame())));
        assert!(q.take_work().is_none());
    }
    #[test]
    fn failure_retains_last_good_marks_stale_and_no_retry_loop() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let a = q.take_work().unwrap();
        q.complete(a.ticket, Ok(frame()));
        let saved = Arc::clone(q.displayed().unwrap());
        q.request(1., 2).unwrap();
        let b = q.take_work().unwrap();
        assert!(q.is_stale());
        assert!(!q.complete(b.ticket, Err("render failed")));
        assert_eq!(q.failure(), Some("render failed"));
        assert!(Arc::ptr_eq(&saved, q.displayed().unwrap()));
        assert!(q.take_work().is_none());
        q.request(1., 2).unwrap();
        assert!(q.take_work().is_some());
    }
    #[test]
    fn duplicate_completion_does_not_unlock_active_worker() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let a = q.take_work().unwrap();
        q.complete(a.ticket, Ok(frame()));
        q.request(1., 1).unwrap();
        let b = q.take_work().unwrap();
        q.request(2., 1).unwrap();
        assert!(!q.complete(a.ticket, Ok(frame())));
        assert!(q.take_work().is_none());
        q.complete(b.ticket, Ok(frame()));
        assert!(q.take_work().is_some());
    }
    #[test]
    fn closed_and_nonfinite_requests_refuse() {
        let mut q = PreviewQueue::default();
        assert!(q.request(0., 1).is_err());
        q.open().unwrap();
        assert!(q.request(f32::NAN, 1).is_err());
        assert!(q.take_work().is_none());
    }
    #[test]
    fn malformed_frame_preserves_last_good() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let a = q.take_work().unwrap();
        q.complete(a.ticket, Ok(frame()));
        let saved = Arc::clone(q.displayed().unwrap());
        q.request(1., 1).unwrap();
        let b = q.take_work().unwrap();
        let mut bad = frame();
        bad.width = usize::MAX;
        assert!(!q.complete(b.ticket, Ok(bad)));
        assert!(Arc::ptr_eq(&saved, q.displayed().unwrap()));
        assert_eq!(q.failure(), Some("invalid completed frame"));
    }
    #[test]
    fn reopening_while_old_work_runs_remains_bounded() {
        let mut q = PreviewQueue::default();
        q.open().unwrap();
        q.request(0., 1).unwrap();
        let old = q.take_work().unwrap();
        q.close();
        q.open().unwrap();
        let new = q.request(1., 1).unwrap();
        assert!(q.take_work().is_none());
        assert!(!q.complete(old.ticket, Ok(frame())));
        assert!(q.displayed().is_none());
        assert_eq!(q.take_work().unwrap().ticket, new);
    }
}
