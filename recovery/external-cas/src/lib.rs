//! Isolated external-CAS draft foundation. No game, disk, network or unsafe code.
//! Wire scanning adapts Apex Metadata/src/appearance_worker.rs; unknown bytes stay exact.
use std::sync::Arc;
type Result<T> = std::result::Result<T, &'static str>;
const MAX_RECORD: usize = 8 * 1024 * 1024;
const MAX_FIELDS: usize = 65536;
const MAX_HISTORY: usize = 16;
const MAX_SNAPSHOT_BYTES: usize = 32 * 1024 * 1024;
#[derive(Clone, Copy)]
struct Field {
    number: u32,
    kind: u8,
    start: usize,
    value: usize,
    end: usize,
}
fn var(raw: &[u8], at: &mut usize) -> Result<u64> {
    let mut v = 0u64;
    for shift in (0..70).step_by(7) {
        let b = *raw.get(*at).ok_or("truncated varint")?;
        *at += 1;
        if shift == 63 && b > 1 {
            return Err("varint overflow");
        }
        v |= u64::from(b & 127) << shift;
        if b & 128 == 0 {
            return Ok(v);
        }
    }
    Err("unbounded varint")
}
fn put(mut v: u64, out: &mut Vec<u8>) {
    while v > 127 {
        out.push((v as u8 & 127) | 128);
        v >>= 7
    }
    out.push(v as u8)
}
fn skip(raw: &[u8], at: &mut usize, kind: u8, tag: u32, depth: u32) -> Result<()> {
    if depth > 32 {
        return Err("group depth");
    }
    if kind == 0 {
        var(raw, at)?;
        return Ok(());
    }
    if kind == 3 {
        while *at < raw.len() {
            let key = var(raw, at)?;
            let n = key >> 3;
            let k = (key & 7) as u8;
            if n == 0 || n > 536870911 {
                return Err("invalid group tag");
            }
            if k == 4 {
                return if n == u64::from(tag) {
                    Ok(())
                } else {
                    Err("mismatched group end")
                };
            }
            skip(raw, at, k, n as u32, depth + 1)?;
        }
        return Err("unterminated group");
    }
    let size = match kind {
        1 => 8,
        5 => 4,
        2 => var(raw, at)?,
        _ => return Err("invalid wire kind"),
    };
    if size > raw.len().saturating_sub(*at) as u64 {
        return Err("truncated field");
    }
    *at += size as usize;
    Ok(())
}
fn fields(raw: &[u8]) -> Result<Vec<Field>> {
    if raw.len() > MAX_RECORD {
        return Err("record limit");
    }
    let (mut at, mut rows) = (0, Vec::new());
    while at < raw.len() {
        if rows.len() >= MAX_FIELDS {
            return Err("field limit");
        }
        let start = at;
        let key = var(raw, &mut at)?;
        let n = key >> 3;
        let k = (key & 7) as u8;
        if n == 0 || n > 536870911 || k == 4 {
            return Err("invalid field tag");
        }
        let value;
        if k == 2 {
            let size = var(raw, &mut at)?;
            value = at;
            if size > raw.len().saturating_sub(at) as u64 {
                return Err("truncated bytes");
            }
            at += size as usize;
        } else {
            value = at;
            skip(raw, &mut at, k, n as u32, 0)?;
        }
        rows.push(Field {
            number: n as u32,
            kind: k,
            start,
            value,
            end: at,
        });
    }
    Ok(rows)
}
fn sim_id(raw: &[u8]) -> Result<u64> {
    let ids: Vec<_> = fields(raw)?.into_iter().filter(|f| f.number == 1).collect();
    if ids.len() != 1 || ids[0].kind != 1 {
        return Err("ambiguous Sim identity");
    }
    let f = ids[0];
    let id = u64::from_le_bytes(
        raw[f.value..f.end]
            .try_into()
            .map_err(|_| "identity extent")?,
    );
    if id == 0 {
        return Err("zero Sim identity");
    }
    Ok(id)
}
fn one(raw: &[u8], tag: u32, kind: u8) -> Result<Field> {
    let rows: Vec<_> = fields(raw)?
        .into_iter()
        .filter(|f| f.number == tag)
        .collect();
    if rows.len() != 1 || rows[0].kind != kind {
        return Err("required singular field absent or ambiguous");
    }
    Ok(rows[0])
}
fn splice_bytes(raw: &[u8], field: Field, payload: &[u8]) -> Result<Vec<u8>> {
    if field.kind != 2 {
        return Err("not a message/bytes span");
    }
    let mut encoded = Vec::new();
    put((u64::from(field.number) << 3) | 2, &mut encoded);
    put(payload.len() as u64, &mut encoded);
    encoded.extend(payload);
    let size = raw.len() - (field.end - field.start) + encoded.len();
    if size > MAX_RECORD {
        return Err("record limit");
    }
    let mut out = Vec::with_capacity(size);
    out.extend_from_slice(&raw[..field.start]);
    out.extend(encoded);
    out.extend_from_slice(&raw[field.end..]);
    Ok(out)
}
fn array_values(raw: &[u8], fixed: bool) -> Result<Vec<u64>> {
    let mut values = Vec::new();
    for f in fields(raw)? {
        if f.number != 1 {
            return Err("unknown parallel-array field; edit refused");
        }
        let b = &raw[f.value..f.end];
        match (fixed, f.kind) {
            (false, 0) => {
                let mut at = 0;
                values.push(var(b, &mut at)?);
            }
            (false, 2) => {
                let mut at = 0;
                while at < b.len() {
                    values.push(var(b, &mut at)?);
                    if values.len() > 4096 {
                        return Err("array limit");
                    }
                }
            }
            (true, 1) => values.push(u64::from_le_bytes(
                b.try_into().map_err(|_| "fixed64 extent")?,
            )),
            (true, 2) => {
                if !b.len().is_multiple_of(8) {
                    return Err("fixed64 packed alignment");
                }
                for chunk in b.as_chunks::<8>().0 {
                    values.push(u64::from_le_bytes(*chunk));
                    if values.len() > 4096 {
                        return Err("array limit");
                    }
                }
            }
            _ => return Err("array encoding"),
        }
        if values.len() > 4096 {
            return Err("array limit");
        }
    }
    Ok(values)
}
fn patch_color_array(raw: &[u8], index: usize, color: u64) -> Result<Vec<u8>> {
    let mut values = array_values(raw, false)?;
    if index >= values.len() {
        return Err("color index");
    }
    if values[index] == color {
        return Ok(raw.to_vec());
    }
    values[index] = color;
    let mut packed = Vec::new();
    for v in values {
        put(v, &mut packed)
    }
    let mut encoded = vec![10];
    put(packed.len() as u64, &mut encoded);
    encoded.extend(packed);
    let mut out = Vec::new();
    let mut written = false;
    for f in fields(raw)? {
        if f.number == 1 {
            if !written {
                out.extend_from_slice(&encoded);
                written = true
            }
        } else {
            out.extend_from_slice(&raw[f.start..f.end])
        }
    }
    if !written {
        return Err("missing color entries");
    }
    Ok(out)
}
#[derive(Clone, Copy, Debug)]
pub enum NameField {
    First,
    Last,
}
impl NameField {
    fn tag(self) -> u32 {
        match self {
            Self::First => 5,
            Self::Last => 6,
        }
    }
}
/// The tags above are checked against the privately recovered installed SimData descriptor.
/// This initial slice edits names only; native name rules and full CAS remain unqualified.
pub struct CheckpointParts<'a> {
    pub header: [u8; 36],
    pub records: Vec<&'a [u8]>,
}
pub struct Draft {
    id: u64,
    revision: u64,
    original: Arc<[u8]>,
    current: Arc<[u8]>,
    undo: Vec<Arc<[u8]>>,
    redo: Vec<Arc<[u8]>>,
}
pub struct ExportPlan {
    pub sim_id: u64,
    pub revision: u64,
    original: Arc<[u8]>,
    proposed: Arc<[u8]>,
}
impl ExportPlan {
    pub fn proposed_bytes(&self) -> &[u8] {
        &self.proposed
    }
    pub fn matches_original(&self, current: &[u8]) -> bool {
        current == self.original.as_ref()
    }
}
impl Draft {
    pub fn new(expected_sim: u64, bytes: Vec<u8>) -> Result<Self> {
        let id = sim_id(&bytes)?;
        if id != expected_sim {
            return Err("wrong Sim");
        }
        let data: Arc<[u8]> = bytes.into();
        Ok(Self {
            id,
            revision: 0,
            original: data.clone(),
            current: data,
            undo: vec![],
            redo: vec![],
        })
    }
    pub fn sim_identity(&self) -> u64 {
        self.id
    }
    pub fn original_bytes(&self) -> &[u8] {
        &self.original
    }
    /// App-owned draft checkpoint, not a Sims save/Tray format or authorization grant.
    pub fn checkpoint_parts(&self) -> Result<CheckpointParts<'_>> {
        let records: Vec<&[u8]> = std::iter::once(self.original.as_ref())
            .chain(std::iter::once(self.current.as_ref()))
            .chain(self.undo.iter().map(|b| b.as_ref()))
            .chain(self.redo.iter().map(|b| b.as_ref()))
            .collect();
        let bytes: usize = records.iter().map(|r| r.len()).sum();
        if self.undo.len() + self.redo.len() > MAX_HISTORY || bytes > MAX_SNAPSHOT_BYTES {
            return Err("checkpoint history bounds");
        }
        let mut out = b"APXDRFT1".to_vec();
        out.extend(1u32.to_le_bytes());
        out.extend(self.id.to_le_bytes());
        out.extend(self.revision.to_le_bytes());
        out.extend((self.undo.len() as u32).to_le_bytes());
        out.extend((self.redo.len() as u32).to_le_bytes());
        let header: [u8; 36] = out.try_into().map_err(|_| "checkpoint header length")?;
        Ok(CheckpointParts { header, records })
    }
    pub fn encode_checkpoint(&self) -> Result<Vec<u8>> {
        let parts = self.checkpoint_parts()?;
        let mut out = parts.header.to_vec();
        for raw in parts.records {
            out.extend((raw.len() as u32).to_le_bytes());
            out.extend(raw)
        }
        Ok(out)
    }
    pub fn decode_checkpoint(expected_sim: u64, raw: &[u8]) -> Result<Self> {
        if raw.len() < 36 || raw.len() > MAX_SNAPSHOT_BYTES + 1024 || &raw[..8] != b"APXDRFT1" {
            return Err("checkpoint header/bound");
        }
        fn number(raw: &[u8], at: &mut usize, n: usize) -> Result<u64> {
            let end = at.checked_add(n).ok_or("checkpoint overflow")?;
            let b = raw.get(*at..end).ok_or("truncated checkpoint")?;
            *at = end;
            let mut wide = [0u8; 8];
            wide[..n].copy_from_slice(b);
            Ok(u64::from_le_bytes(wide))
        }
        let mut at = 8;
        if number(raw, &mut at, 4)? != 1 {
            return Err("unsupported checkpoint version");
        }
        let id = number(raw, &mut at, 8)?;
        let revision = number(raw, &mut at, 8)?;
        let un = number(raw, &mut at, 4)? as usize;
        let re = number(raw, &mut at, 4)? as usize;
        if id != expected_sim
            || id == 0
            || un > MAX_HISTORY
            || re > MAX_HISTORY
            || un + re > MAX_HISTORY
        {
            return Err("checkpoint identity/history");
        }
        let mut records = Vec::new();
        let mut bytes = 0usize;
        for _ in 0..2 + un + re {
            let len = number(raw, &mut at, 4)? as usize;
            if len == 0 || len > MAX_RECORD {
                return Err("checkpoint record bound");
            }
            bytes = bytes.checked_add(len).ok_or("checkpoint overflow")?;
            if bytes > MAX_SNAPSHOT_BYTES {
                return Err("checkpoint byte budget");
            }
            let end = at.checked_add(len).ok_or("checkpoint overflow")?;
            let value = raw.get(at..end).ok_or("truncated checkpoint record")?;
            at = end;
            if sim_id(value)? != id {
                return Err("checkpoint mixes Sim identities");
            }
            records.push(Arc::<[u8]>::from(value));
        }
        if at != raw.len() {
            return Err("checkpoint trailing bytes");
        }
        let mut all = records.into_iter();
        let original = all.next().unwrap();
        let current = all.next().unwrap();
        let undo = all.by_ref().take(un).collect();
        let redo = all.collect();
        Ok(Self {
            id,
            revision,
            original,
            current,
            undo,
            redo,
        })
    }
    pub fn revision(&self) -> u64 {
        self.revision
    }
    pub fn bytes(&self) -> &[u8] {
        &self.current
    }
    fn next(&self, expected: u64) -> Result<u64> {
        if expected != self.revision {
            return Err("stale draft revision");
        }
        self.revision.checked_add(1).ok_or("revision overflow")
    }
    fn budget(&self, new_size: usize) -> Result<()> {
        let bytes = self.original.len()
            + self.current.len()
            + new_size
            + self.undo.iter().map(|b| b.len()).sum::<usize>();
        if self.undo.len() >= MAX_HISTORY || bytes > MAX_SNAPSHOT_BYTES {
            return Err("history budget; explicit checkpoint required");
        }
        Ok(())
    }
    pub fn edit_name(&mut self, expected: u64, field: NameField, text: &str) -> Result<u64> {
        let next = self.next(expected)?;
        if text.len() > 1024 || text.chars().any(char::is_control) {
            return Err("name bounds");
        }
        let tag = field.tag();
        let rows = fields(&self.current)?;
        let matches: Vec<_> = rows.iter().filter(|f| f.number == tag).collect();
        if matches.len() > 1 || matches.first().is_some_and(|f| f.kind != 2) {
            return Err("ambiguous name field");
        }
        let mut replacement = Vec::new();
        put((u64::from(tag) << 3) | 2, &mut replacement);
        put(text.len() as u64, &mut replacement);
        replacement.extend_from_slice(text.as_bytes());
        let removed = matches.first().map_or(0, |f| f.end - f.start);
        let found = !matches.is_empty();
        drop(matches);
        let size = self.current.len() - removed + replacement.len();
        if size > MAX_RECORD {
            return Err("record limit");
        }
        let mut result = Vec::with_capacity(size);
        for f in rows {
            if f.number == tag {
                result.extend_from_slice(&replacement)
            } else {
                result.extend_from_slice(&self.current[f.start..f.end])
            }
        }
        if !found {
            result.extend_from_slice(&replacement)
        }
        if result.as_slice() == self.current.as_ref() {
            return Ok(self.revision);
        }
        self.budget(result.len())?;
        if sim_id(&result)? != self.id {
            return Err("identity changed");
        }
        self.undo.push(self.current.clone());
        self.current = result.into();
        self.redo.clear();
        self.revision = next;
        Ok(next)
    }
    /// Offline root-active outfit bytes only. No occult-lane or native apply authority.
    pub fn edit_outfit_color(
        &mut self,
        expected: u64,
        outfit_id: u64,
        index: usize,
        color: u64,
    ) -> Result<u64> {
        let next = self.next(expected)?;
        if outfit_id == 0 {
            return Err("zero outfit identity");
        }
        let root = one(&self.current, 21, 2)?;
        let list = &self.current[root.value..root.end];
        let mut chosen = None;
        let mut seen = std::collections::BTreeSet::new();
        let mut count = 0;
        for f in fields(list)? {
            if f.number != 1 {
                continue;
            }
            count += 1;
            if count > 1024 || f.kind != 2 {
                return Err("outfit list shape");
            }
            let outfit = &list[f.value..f.end];
            let id_field = one(outfit, 1, 0)?;
            let mut at = 0;
            let id = var(&outfit[id_field.value..id_field.end], &mut at)?;
            if !seen.insert(id) {
                return Err("duplicate outfit identity");
            }
            if id == outfit_id {
                chosen = Some(f)
            }
        }
        let selected = chosen.ok_or("outfit identity absent")?;
        let outfit = &list[selected.value..selected.end];
        let parts_field = one(outfit, 5, 2)?;
        let types_field = one(outfit, 7, 2)?;
        let colors_field = one(outfit, 12, 2)?;
        let parts = array_values(&outfit[parts_field.value..parts_field.end], true)?;
        let types = array_values(&outfit[types_field.value..types_field.end], false)?;
        let colors = &outfit[colors_field.value..colors_field.end];
        let values = array_values(colors, false)?;
        if parts.is_empty()
            || parts.len() != types.len()
            || parts.len() != values.len()
            || index >= parts.len()
            || types.iter().any(|v| *v > u32::MAX as u64)
        {
            return Err("parallel outfit arrays differ");
        }
        let edited_colors = patch_color_array(colors, index, color)?;
        if edited_colors.as_slice() == colors {
            return Ok(self.revision);
        }
        let edited_outfit = splice_bytes(outfit, colors_field, &edited_colors)?;
        let edited_list = splice_bytes(list, selected, &edited_outfit)?;
        let result = splice_bytes(&self.current, root, &edited_list)?;
        self.budget(result.len())?;
        if sim_id(&result)? != self.id {
            return Err("identity changed");
        }
        self.undo.push(self.current.clone());
        self.current = result.into();
        self.redo.clear();
        self.revision = next;
        Ok(next)
    }
    pub fn undo(&mut self, expected: u64) -> Result<u64> {
        let next = self.next(expected)?;
        let previous = self.undo.pop().ok_or("no undo")?;
        self.redo.push(self.current.clone());
        self.current = previous;
        self.revision = next;
        Ok(next)
    }
    pub fn redo(&mut self, expected: u64) -> Result<u64> {
        let next = self.next(expected)?;
        let later = self.redo.pop().ok_or("no redo")?;
        self.undo.push(self.current.clone());
        self.current = later;
        self.revision = next;
        Ok(next)
    }
    /// Produces owned bytes, never writes them. Not a native CAS/Live authorization grant.
    pub fn prepare_export(&self, expected: u64, current_source: &[u8]) -> Result<ExportPlan> {
        if expected != self.revision {
            return Err("stale draft revision");
        }
        if current_source != self.original.as_ref() {
            return Err("source changed; rebase required");
        }
        Ok(ExportPlan {
            sim_id: self.id,
            revision: self.revision,
            original: self.original.clone(),
            proposed: self.current.clone(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn bytes(tag: u32, value: &[u8]) -> Vec<u8> {
        let mut r = vec![];
        put((u64::from(tag) << 3) | 2, &mut r);
        put(value.len() as u64, &mut r);
        r.extend(value);
        r
    }
    fn integer(tag: u32, value: u64) -> Vec<u8> {
        let mut r = vec![];
        put(u64::from(tag) << 3, &mut r);
        put(value, &mut r);
        r
    }
    fn identity(id: u64) -> Vec<u8> {
        let mut r = vec![9];
        r.extend(id.to_le_bytes());
        r
    }
    fn sample() -> Vec<u8> {
        let mut r = identity(42);
        r.extend(bytes(600, b"future-root"));
        r.extend(bytes(5, b"Old"));
        let mut outfit = integer(1, 77);
        outfit.extend(integer(2, 0));
        let mut flags = vec![];
        put(u64::MAX, &mut flags);
        put(1u64 << 63, &mut flags);
        outfit.extend(bytes(16, &flags));
        outfit.extend(bytes(777, b"future-outfit"));
        r.extend(bytes(21, &bytes(1, &outfit)));
        r.extend(bytes(6, b"Family"));
        r
    }
    fn untouched(raw: &[u8], tag: u32) -> Vec<u8> {
        fields(raw)
            .unwrap()
            .iter()
            .filter(|f| f.number != tag)
            .flat_map(|f| raw[f.start..f.end].iter().copied())
            .collect()
    }
    #[test]
    fn edit_retains_unknown_root_and_outfit_field16_exactly() {
        let raw = sample();
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert_eq!(d.edit_name(0, NameField::First, "New 🐾").unwrap(), 1);
        assert_eq!(untouched(&raw, 5), untouched(d.bytes(), 5));
        assert_eq!(sim_id(d.bytes()).unwrap(), 42);
    }
    #[test]
    fn undo_redo_and_export_preserve_exact_bytes() {
        let raw = sample();
        let mut d = Draft::new(42, raw.clone()).unwrap();
        d.edit_name(0, NameField::First, "New").unwrap();
        let changed = d.bytes().to_vec();
        d.undo(1).unwrap();
        assert_eq!(d.bytes(), raw);
        d.redo(2).unwrap();
        assert_eq!(d.bytes(), changed);
        let p = d.prepare_export(3, &raw).unwrap();
        assert_eq!(p.proposed_bytes(), changed);
        assert!(p.matches_original(&raw));
        assert!(!p.matches_original(&changed));
    }
    #[test]
    fn stale_revision_and_changed_source_refuse_without_mutation() {
        let raw = sample();
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_name(1, NameField::First, "Bad").is_err());
        assert_eq!(d.bytes(), raw);
        assert_eq!(d.revision(), 0);
        assert!(d.prepare_export(0, b"different").is_err());
        assert!(d.prepare_export(99, &raw).is_err());
    }
    #[test]
    fn missing_optional_presence_restores_on_undo() {
        let raw = identity(42);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        d.edit_name(0, NameField::First, "").unwrap();
        assert_ne!(d.bytes(), raw);
        d.undo(1).unwrap();
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn identical_edit_does_not_dirty_history() {
        let raw = sample();
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert_eq!(d.edit_name(0, NameField::First, "Old").unwrap(), 0);
        assert!(d.undo(0).is_err());
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn identity_refuses_zero_wrong_duplicate_and_wrong_wire() {
        assert!(Draft::new(42, identity(0)).is_err());
        assert!(Draft::new(99, identity(42)).is_err());
        let mut b = identity(42);
        b.extend(identity(42));
        assert!(Draft::new(42, b).is_err());
        assert!(Draft::new(42, integer(1, 42)).is_err());
    }
    #[test]
    fn ambiguous_name_refuses_without_mutation() {
        let mut raw = sample();
        raw.extend(bytes(5, b"other"));
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_name(0, NameField::First, "x").is_err());
        assert_eq!(d.bytes(), raw);
        let mut raw = identity(42);
        raw.extend(integer(5, 7));
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_name(0, NameField::First, "x").is_err());
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn malformed_wire_refuses_boundedly() {
        for bad in [
            vec![0],
            vec![0x80; 10],
            vec![10, 127, 1],
            vec![12],
            vec![11, 20],
            vec![15],
        ] {
            let mut raw = identity(42);
            raw.extend(bad);
            assert!(Draft::new(42, raw).is_err());
        }
        let mut raw = identity(42);
        for _ in 0..35 {
            raw.push(19)
        }
        for _ in 0..35 {
            raw.push(20)
        }
        assert!(Draft::new(42, raw).is_err());
    }
    #[test]
    fn unknown_group_kept_byte_exact() {
        let mut raw = sample();
        put((777 << 3) | 3, &mut raw);
        raw.extend(integer(1, u64::MAX));
        put((777 << 3) | 4, &mut raw);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        d.edit_name(0, NameField::Last, "Other").unwrap();
        assert_eq!(untouched(&raw, 6), untouched(d.bytes(), 6));
    }
    #[test]
    fn bounds_refuse_without_mutation() {
        let raw = sample();
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_name(0, NameField::First, &"x".repeat(1025)).is_err());
        assert!(d.edit_name(0, NameField::First, "a\0b").is_err());
        assert_eq!(d.bytes(), raw);
        assert!(Draft::new(42, vec![0; MAX_RECORD + 1]).is_err());
    }
    #[test]
    fn history_limit_does_not_silently_evict_or_mutate() {
        let mut d = Draft::new(42, sample()).unwrap();
        for i in 0..MAX_HISTORY {
            d.edit_name(i as u64, NameField::First, &format!("N{i}"))
                .unwrap();
        }
        let raw = d.bytes().to_vec();
        assert!(
            d.edit_name(MAX_HISTORY as u64, NameField::Last, "too far")
                .is_err()
        );
        assert_eq!(d.bytes(), raw);
        assert_eq!(d.revision(), MAX_HISTORY as u64);
    }
    #[test]
    fn divergent_edit_clears_redo_only_after_success() {
        let mut d = Draft::new(42, sample()).unwrap();
        d.edit_name(0, NameField::First, "A").unwrap();
        d.undo(1).unwrap();
        assert!(d.edit_name(2, NameField::Last, "bad\n").is_err());
        d.redo(2).unwrap();
        d.undo(3).unwrap();
        d.edit_name(4, NameField::Last, "B").unwrap();
        assert!(d.redo(5).is_err());
    }
    #[test]
    fn snapshot_is_owned_and_send_sync() {
        fn check<T: Send + Sync>() {}
        check::<Draft>();
        check::<ExportPlan>();
        let source = sample();
        let mut d = Draft::new(42, source.clone()).unwrap();
        let p = d.prepare_export(0, &source).unwrap();
        d.edit_name(0, NameField::First, "later").unwrap();
        assert_eq!(p.proposed_bytes(), source);
    }
    #[test]
    fn deterministic_unknown_field_stress() {
        let mut seed = 17u64;
        for i in 0..1000 {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            let mut raw = sample();
            raw.extend(integer(500 + (i % 200) as u32, seed));
            raw.extend(bytes(900, &seed.to_le_bytes()));
            let mut d = Draft::new(42, raw.clone()).unwrap();
            d.edit_name(0, NameField::First, &format!("Case{i}"))
                .unwrap();
            assert_eq!(untouched(&raw, 5), untouched(d.bytes(), 5));
            d.undo(1).unwrap();
            assert_eq!(d.bytes(), raw);
        }
    }
}

#[cfg(test)]
mod outfit_tests {
    use super::*;
    fn b(tag: u32, value: &[u8]) -> Vec<u8> {
        let mut r = vec![];
        put((u64::from(tag) << 3) | 2, &mut r);
        put(value.len() as u64, &mut r);
        r.extend(value);
        r
    }
    fn v(tag: u32, value: u64) -> Vec<u8> {
        let mut r = vec![];
        put(u64::from(tag) << 3, &mut r);
        put(value, &mut r);
        r
    }
    fn outfit(id: u64, packed: bool) -> Vec<u8> {
        let mut r = v(1, id);
        r.extend(v(2, 0));
        let mut parts = vec![];
        if packed {
            let mut data = vec![];
            data.extend(111u64.to_le_bytes());
            data.extend(222u64.to_le_bytes());
            parts.extend(b(1, &data));
        } else {
            for id in [111u64, 222] {
                parts.push(9);
                parts.extend(id.to_le_bytes());
            }
        }
        r.extend(b(5, &parts));
        let mut types = v(1, 2);
        types.extend(v(1, 8));
        r.extend(b(7, &types));
        let mut colors = vec![];
        if packed {
            let mut data = vec![];
            put(7, &mut data);
            put(u64::MAX, &mut data);
            colors.extend(b(1, &data));
        } else {
            colors.extend(v(1, 7));
            colors.extend(v(1, u64::MAX));
        }
        r.extend(b(12, &colors));
        r.extend(v(16, 1u64 << 63));
        r.extend(b(777, b"future-outfit"));
        r
    }
    fn record(a: &[u8], other: bool) -> Vec<u8> {
        let mut r = vec![9];
        r.extend(42u64.to_le_bytes());
        let mut list = b(1, a);
        list.extend(b(700, b"future-list"));
        if other {
            list.extend(b(1, &outfit(78, true)))
        }
        r.extend(b(21, &list));
        r.extend(b(600, b"future-root"));
        r
    }
    fn get_outfit(raw: &[u8], wanted: u64) -> Vec<u8> {
        let f = one(raw, 21, 2).unwrap();
        let list = &raw[f.value..f.end];
        for f in fields(list).unwrap() {
            if f.number == 1 {
                let body = &list[f.value..f.end];
                let id = one(body, 1, 0).unwrap();
                let mut at = 0;
                if var(&body[id.value..id.end], &mut at).unwrap() == wanted {
                    return body.to_vec();
                }
            }
        }
        panic!("outfit missing")
    }
    fn outside(raw: &[u8], tag: u32) -> Vec<u8> {
        fields(raw)
            .unwrap()
            .into_iter()
            .filter(|f| f.number != tag)
            .flat_map(|f| raw[f.start..f.end].to_vec())
            .collect()
    }
    #[test]
    fn actual_color_slice_changes_only_one_value_and_preserves_unknowns() {
        for packed in [false, true] {
            let a = outfit(77, packed);
            let raw = record(&a, true);
            let mut d = Draft::new(42, raw.clone()).unwrap();
            d.edit_outfit_color(0, 77, 1, 1u64 << 63).unwrap();
            let changed = get_outfit(d.bytes(), 77);
            assert_eq!(outside(&a, 12), outside(&changed, 12));
            assert_eq!(get_outfit(d.bytes(), 78), get_outfit(&raw, 78));
            assert_eq!(outside(&raw, 21), outside(d.bytes(), 21));
            let c = one(&changed, 12, 2).unwrap();
            let colors = &changed[c.value..c.end];
            assert_eq!(array_values(colors, false).unwrap(), vec![7, 1u64 << 63]);
            let old = one(&a, 12, 2).unwrap();
            assert_eq!(outside(&a[old.value..old.end], 1), outside(colors, 1));
        }
    }
    #[test]
    fn no_op_keeps_original_encoding_and_revision() {
        for packed in [false, true] {
            let raw = record(&outfit(77, packed), false);
            let mut d = Draft::new(42, raw.clone()).unwrap();
            assert_eq!(d.edit_outfit_color(0, 77, 1, u64::MAX).unwrap(), 0);
            assert_eq!(d.bytes(), raw);
            assert!(d.undo(0).is_err());
        }
    }
    #[test]
    fn undo_redo_restores_full_original_outfit() {
        let raw = record(&outfit(77, true), true);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        d.edit_outfit_color(0, 77, 0, u64::MAX).unwrap();
        let next = d.bytes().to_vec();
        d.undo(1).unwrap();
        assert_eq!(d.bytes(), raw);
        d.redo(2).unwrap();
        assert_eq!(d.bytes(), next);
    }
    #[test]
    fn wrong_id_slot_and_revision_refuse_unchanged() {
        let raw = record(&outfit(77, true), true);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        for args in [(0, 99, 0), (0, 0, 0), (0, 77, 2), (1, 77, 0)] {
            assert!(d.edit_outfit_color(args.0, args.1, args.2, 3).is_err());
            assert_eq!(d.bytes(), raw);
            assert_eq!(d.revision(), 0);
        }
    }
    #[test]
    fn duplicate_outfit_ids_refuse() {
        let a = outfit(78, true);
        let raw = record(&a, true);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_outfit_color(0, 78, 0, 3).is_err());
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn misaligned_fixed64_and_parallel_length_refuse() {
        for which in [5, 7, 12] {
            let a = outfit(77, true);
            let f = one(&a, which, 2).unwrap();
            let broken = if which == 5 {
                b(1, &[1, 2, 3])
            } else {
                v(1, 7)
            };
            let a = splice_bytes(&a, f, &broken).unwrap();
            let raw = record(&a, false);
            let mut d = Draft::new(42, raw.clone()).unwrap();
            assert!(d.edit_outfit_color(0, 77, 0, 3).is_err());
            assert_eq!(d.bytes(), raw);
        }
    }
    #[test]
    fn duplicate_parallel_message_refuses() {
        let mut a = outfit(77, true);
        a.extend(b(12, &v(1, 7)));
        let raw = record(&a, false);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_outfit_color(0, 77, 0, 3).is_err());
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn invalid_body_type_uint32_refuses() {
        let a = outfit(77, true);
        let f = one(&a, 7, 2).unwrap();
        let mut types = v(1, u64::MAX);
        types.extend(v(1, 8));
        let a = splice_bytes(&a, f, &types).unwrap();
        let raw = record(&a, false);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        assert!(d.edit_outfit_color(0, 77, 0, 3).is_err());
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn color_stress_retains_other_outfit_and_unknown_flags() {
        for i in 0..512u64 {
            let a = outfit(77, i % 2 == 0);
            let raw = record(&a, true);
            let mut d = Draft::new(42, raw.clone()).unwrap();
            d.edit_outfit_color(0, 77, (i % 2) as usize, i.wrapping_mul(0x9e3779b97f4a7c15))
                .unwrap();
            let changed = get_outfit(d.bytes(), 77);
            assert_eq!(outside(&a, 12), outside(&changed, 12));
            assert_eq!(get_outfit(d.bytes(), 78), get_outfit(&raw, 78));
        }
    }
    #[test]
    fn unknown_parallel_array_data_refuses_edit_but_is_not_lost() {
        for tag in [5, 7, 12] {
            let a = outfit(77, true);
            let f = one(&a, tag, 2).unwrap();
            let mut array = a[f.value..f.end].to_vec();
            array.extend(b(900, b"future-array-semantics"));
            let a = splice_bytes(&a, f, &array).unwrap();
            let raw = record(&a, true);
            let mut d = Draft::new(42, raw.clone()).unwrap();
            assert!(d.edit_outfit_color(0, 77, 0, 3).is_err());
            assert_eq!(d.bytes(), raw);
            d.edit_name(0, NameField::First, "Unrelated").unwrap();
            assert_eq!(get_outfit(d.bytes(), 77), a);
        }
    }
}

pub mod mesh;

#[cfg(test)]
mod checkpoint_tests {
    use super::*;
    fn record() -> Vec<u8> {
        let mut r = vec![9];
        r.extend(42u64.to_le_bytes());
        r.extend([42, 3, b'O', b'l', b'd']);
        r
    }
    #[test]
    fn checkpoint_restores_full_undo_redo_branch() {
        let original = record();
        let mut d = Draft::new(42, original.clone()).unwrap();
        d.edit_name(0, NameField::First, "A").unwrap();
        let a = d.bytes().to_vec();
        d.edit_name(1, NameField::Last, "B").unwrap();
        let b = d.bytes().to_vec();
        d.undo(2).unwrap();
        let wire = d.encode_checkpoint().unwrap();
        let mut restored = Draft::decode_checkpoint(42, &wire).unwrap();
        assert_eq!(restored.revision(), 3);
        assert_eq!(restored.bytes(), a);
        restored.redo(3).unwrap();
        assert_eq!(restored.bytes(), b);
        restored.undo(4).unwrap();
        restored.undo(5).unwrap();
        assert_eq!(restored.bytes(), original);
    }
    #[test]
    fn checkpoint_truncations_trailing_and_wrong_version_refuse() {
        let d = Draft::new(42, record()).unwrap();
        let raw = d.encode_checkpoint().unwrap();
        for n in 0..raw.len() {
            assert!(Draft::decode_checkpoint(42, &raw[..n]).is_err())
        }
        let mut bad = raw.clone();
        bad.push(0);
        assert!(Draft::decode_checkpoint(42, &bad).is_err());
        let mut bad = raw;
        bad[8] = 2;
        assert!(Draft::decode_checkpoint(42, &bad).is_err());
    }
    #[test]
    fn checkpoint_wrong_identity_and_excess_counts_refuse() {
        let d = Draft::new(42, record()).unwrap();
        let raw = d.encode_checkpoint().unwrap();
        assert!(Draft::decode_checkpoint(43, &raw).is_err());
        for offset in [28, 32] {
            let mut bad = raw.clone();
            bad[offset..offset + 4].copy_from_slice(&u32::MAX.to_le_bytes());
            assert!(Draft::decode_checkpoint(42, &bad).is_err());
        }
    }
    #[test]
    fn malformed_history_record_refuses() {
        let mut d = Draft::new(42, record()).unwrap();
        d.edit_name(0, NameField::First, "A").unwrap();
        let mut raw = d.encode_checkpoint().unwrap();
        let first_len = u32::from_le_bytes(raw[36..40].try_into().unwrap()) as usize;
        let second_len_at = 40 + first_len;
        let second_len =
            u32::from_le_bytes(raw[second_len_at..second_len_at + 4].try_into().unwrap()) as usize;
        let history = second_len_at + 4 + second_len + 4;
        raw[history + 1] = 43;
        assert!(Draft::decode_checkpoint(42, &raw).is_err());
    }
}

pub mod modifier;

pub mod preview;

pub mod skin;

pub mod preview_queue;

pub mod morph_preview;

pub mod appearance_owners;
