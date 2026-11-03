//! Read-only appearance-owner inventory using installed descriptor field tags.
//! Root and stored forms stay separate. Missing stored values never silently
//! fall back to root values. Opaque facial/outfit payloads are not certified here.
use crate::{Result, fields, sim_id, var};
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OwnerKey {
    Root,
    Stored(u32),
}
#[derive(Debug)]
pub struct Owner<'a> {
    pub key: OwnerKey,
    pub raw: &'a [u8],
    pub facial: Option<&'a [u8]>,
    pub outfits: Option<&'a [u8]>,
    pub known_form: bool,
}
#[derive(Debug)]
pub struct OwnerCatalog<'a> {
    pub sim_id: u64,
    pub current_flags: Option<u32>,
    pub pending_flags: Option<u32>,
    pub membership_flags: Option<u32>,
    pub owners: Vec<Owner<'a>>,
    pub root_type_also_stored: bool,
}
fn optional_bytes(raw: &[u8], tag: u32) -> Result<Option<&[u8]>> {
    let f: Vec<_> = fields(raw)?
        .into_iter()
        .filter(|f| f.number == tag)
        .collect();
    if f.is_empty() {
        return Ok(None);
    }
    if f.len() != 1 || f[0].kind != 2 {
        return Err("ambiguous owner bytes");
    }
    Ok(Some(&raw[f[0].value..f[0].end]))
}
fn optional_u32(raw: &[u8], tag: u32) -> Result<Option<u32>> {
    let f: Vec<_> = fields(raw)?
        .into_iter()
        .filter(|f| f.number == tag)
        .collect();
    if f.is_empty() {
        return Ok(None);
    }
    if f.len() != 1 || f[0].kind != 0 {
        return Err("ambiguous owner flags");
    }
    let mut at = f[0].value;
    let value = var(raw, &mut at)?;
    Ok(Some(
        u32::try_from(value).map_err(|_| "owner flags exceed uint32")?,
    ))
}
fn known(form: u32) -> bool {
    matches!(form, 1 | 2 | 4 | 8 | 16 | 32 | 64)
}
pub fn inspect_owners(raw: &[u8], expected_id: u64) -> Result<OwnerCatalog<'_>> {
    let id = sim_id(raw)?;
    if id != expected_id {
        return Err("owner Sim identity changed");
    }
    let mut catalog = OwnerCatalog {
        sim_id: id,
        current_flags: None,
        pending_flags: None,
        membership_flags: None,
        owners: vec![Owner {
            key: OwnerKey::Root,
            raw,
            facial: optional_bytes(raw, 18)?,
            outfits: optional_bytes(raw, 21)?,
            known_form: false,
        }],
        root_type_also_stored: false,
    };
    let Some(attributes) = optional_bytes(raw, 30)? else {
        return Ok(catalog);
    };
    let Some(tracker) = optional_bytes(attributes, 17)? else {
        return Ok(catalog);
    };
    catalog.current_flags = optional_u32(tracker, 2)?;
    catalog.pending_flags = optional_u32(tracker, 4)?;
    catalog.membership_flags = optional_u32(tracker, 1)?;
    catalog.owners[0].known_form = catalog.current_flags.is_some_and(known);
    let mut seen = std::collections::HashSet::new();
    for f in fields(tracker)?.into_iter().filter(|f| f.number == 3) {
        if catalog.owners.len() >= 129 {
            return Err("stored appearance count bound");
        }
        if f.kind != 2 {
            return Err("stored appearance wrong wire type");
        }
        let form_raw = &tracker[f.value..f.end];
        let form = optional_u32(form_raw, 1)?.ok_or("stored appearance lacks type")?;
        if !seen.insert(form) {
            return Err("duplicate stored appearance type");
        }
        catalog.root_type_also_stored |= catalog.current_flags == Some(form);
        catalog.owners.push(Owner {
            key: OwnerKey::Stored(form),
            raw: form_raw,
            facial: optional_bytes(form_raw, 12)?,
            outfits: optional_bytes(form_raw, 21)?,
            known_form: known(form),
        });
    }
    Ok(catalog)
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::put;
    fn field(tag: u32, payload: &[u8]) -> Vec<u8> {
        let mut b = vec![];
        put((tag as u64) << 3 | 2, &mut b);
        put(payload.len() as u64, &mut b);
        b.extend(payload);
        b
    }
    fn number(tag: u32, value: u64) -> Vec<u8> {
        let mut b = vec![];
        put((tag as u64) << 3, &mut b);
        put(value, &mut b);
        b
    }
    fn sim(tracker: &[u8]) -> Vec<u8> {
        let mut b = vec![9];
        b.extend(42u64.to_le_bytes());
        b.extend(field(18, b"root facial"));
        b.extend(field(21, b"root outfits"));
        b.extend(field(30, &field(17, tracker)));
        b
    }
    #[test]
    fn root_and_stored_do_not_merge() {
        let mut form = number(1, 2);
        form.extend(field(12, b"stored facial"));
        let mut tracker = number(2, 2);
        tracker.extend(field(3, &form));
        let raw = sim(&tracker);
        let copy = raw.clone();
        let c = inspect_owners(&raw, 42).unwrap();
        assert_eq!(c.owners.len(), 2);
        assert_eq!(c.owners[0].facial, Some(&b"root facial"[..]));
        assert_eq!(c.owners[1].facial, Some(&b"stored facial"[..]));
        assert_eq!(c.owners[1].outfits, None);
        assert!(c.root_type_also_stored);
        assert_eq!(raw, copy);
        assert_eq!(c.owners[1].raw, form);
    }
    #[test]
    fn absent_current_is_unknown_not_human() {
        let raw = sim(&[]);
        let c = inspect_owners(&raw, 42).unwrap();
        assert_eq!(c.current_flags, None);
        assert!(!c.owners[0].known_form);
    }
    #[test]
    fn combined_and_future_types_are_retained_unqualified() {
        let mut t = number(2, 3);
        t.extend(field(3, &number(1, 128)));
        let raw = sim(&t);
        let c = inspect_owners(&raw, 42).unwrap();
        assert_eq!(c.current_flags, Some(3));
        assert!(!c.owners[0].known_form);
        assert_eq!(c.owners[1].key, OwnerKey::Stored(128));
        assert!(!c.owners[1].known_form);
    }
    #[test]
    fn duplicate_form_and_flags_refuse() {
        let a = field(3, &number(1, 2));
        let raw = sim(&[a.clone(), a].concat());
        assert!(inspect_owners(&raw, 42).is_err());
        let raw = sim(&[number(2, 1), number(2, 2)].concat());
        assert!(inspect_owners(&raw, 42).is_err());
    }
    #[test]
    fn flags_and_unknown_owner_data_stay_exact() {
        let mut form = number(1, 4);
        form.extend(field(500, b"unknown future"));
        let mut t = number(1, 7);
        t.extend(number(2, 2));
        t.extend(number(4, 4));
        t.extend(field(3, &form));
        let raw = sim(&t);
        let c = inspect_owners(&raw, 42).unwrap();
        assert_eq!(c.membership_flags, Some(7));
        assert_eq!(c.pending_flags, Some(4));
        assert_eq!(c.owners[1].raw, form);
    }
    #[test]
    fn wrong_identity_missing_type_and_wrong_wire_refuse() {
        let raw = sim(&[]);
        assert!(inspect_owners(&raw, 43).is_err());
        assert!(inspect_owners(&sim(&field(3, &[])), 42).is_err());
        assert!(inspect_owners(&sim(&number(3, 1)), 42).is_err());
    }
    #[test]
    fn count_bound() {
        let mut t = vec![];
        for i in 0..129 {
            t.extend(field(3, &number(1, i)));
        }
        assert_eq!(
            inspect_owners(&sim(&t), 42).unwrap_err(),
            "stored appearance count bound"
        );
    }
}
