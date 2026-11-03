//! Existing modifier edits in the root-active facial-attribute blob.
//! Layer tags come from the installed descriptor; aged-over-base precedence
//! follows the existing Apex preview adapter. No native slider-range or apply authority.
use super::{Draft, Field, Result, fields, one, put, sim_id, splice_bytes};
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Layer {
    Face,
    Body,
    AgedFace,
    AgedBody,
}
impl Layer {
    fn tag(self) -> u32 {
        match self {
            Self::Face => 2,
            Self::Body => 3,
            Self::AgedFace => 4,
            Self::AgedBody => 5,
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Selection {
    pub layer: Layer,
    pub ordinal: usize,
    pub key: u64,
    pub expected_amount_bits: Option<u32>,
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Entry {
    pub ordinal: usize,
    pub key: Option<u64>,
    pub amount: Option<f32>,
}
impl Entry {
    pub fn selection(self, layer: Layer) -> Result<Selection> {
        Ok(Selection {
            layer,
            ordinal: self.ordinal,
            key: self.key.ok_or("modifier key absent")?,
            expected_amount_bits: self.amount.map(f32::to_bits),
        })
    }
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Effective {
    pub selection: Selection,
    pub amount: f32,
}
fn optional(raw: &[u8], tag: u32, kind: u8) -> Result<Option<Field>> {
    let rows: Vec<_> = fields(raw)?
        .into_iter()
        .filter(|f| f.number == tag)
        .collect();
    if rows.len() > 1 || rows.first().is_some_and(|f| f.kind != kind) {
        return Err("ambiguous modifier member");
    }
    Ok(rows.first().copied())
}
fn entry(raw: &[u8], ordinal: usize) -> Result<Entry> {
    let key = match optional(raw, 1, 0)? {
        Some(f) => {
            let mut at = 0;
            Some(super::var(&raw[f.value..f.end], &mut at)?)
        }
        None => None,
    };
    let amount = match optional(raw, 2, 5)? {
        Some(f) => {
            let a = f32::from_le_bytes(
                raw[f.value..f.end]
                    .try_into()
                    .map_err(|_| "modifier amount extent")?,
            );
            if !a.is_finite() {
                return Err("non-finite modifier amount");
            }
            Some(a)
        }
        None => None,
    };
    Ok(Entry {
        ordinal,
        key,
        amount,
    })
}
fn rows(raw: &[u8], layer: Layer) -> Result<Vec<Field>> {
    let rows: Vec<_> = fields(raw)?
        .into_iter()
        .filter(|f| f.number == layer.tag())
        .collect();
    if rows.len() > 4096 || rows.iter().any(|f| f.kind != 2) {
        return Err("modifier layer shape/bound");
    }
    Ok(rows)
}
impl Draft {
    pub fn modifiers(&self, layer: Layer) -> Result<Vec<Entry>> {
        let Some(root) = optional(&self.current, 18, 2)? else {
            return Ok(vec![]);
        };
        let morph = &self.current[root.value..root.end];
        rows(morph, layer)?
            .into_iter()
            .enumerate()
            .map(|(i, f)| entry(&morph[f.value..f.end], i))
            .collect()
    }
    pub fn effective_modifier(&self, face: bool, key: u64) -> Result<Option<Effective>> {
        if key == 0 {
            return Err("zero modifier resource key unsupported");
        }
        let layers = if face {
            [Layer::Face, Layer::AgedFace]
        } else {
            [Layer::Body, Layer::AgedBody]
        };
        let mut selected = None;
        for layer in layers {
            for e in self.modifiers(layer)? {
                if e.key == Some(key) {
                    selected = Some(Effective {
                        selection: e.selection(layer)?,
                        amount: e.amount.unwrap_or(0.0),
                    })
                }
            }
        }
        Ok(selected)
    }
    pub fn edit_modifier(
        &mut self,
        expected: u64,
        selection: Selection,
        amount: f32,
    ) -> Result<u64> {
        let next = self.next(expected)?;
        if !amount.is_finite() {
            return Err("non-finite proposed modifier");
        }
        let root = one(&self.current, 18, 2)?;
        let morph = &self.current[root.value..root.end];
        let layer = rows(morph, selection.layer)?;
        let selected = *layer
            .get(selection.ordinal)
            .ok_or("modifier ordinal absent")?;
        let old = &morph[selected.value..selected.end];
        let current = entry(old, selection.ordinal)?;
        if current.key != Some(selection.key)
            || current.amount.map(f32::to_bits) != selection.expected_amount_bits
        {
            return Err("stale modifier selection");
        }
        let old_bits = current.amount.map(f32::to_bits);
        let new_bits = amount.to_bits();
        if old_bits == Some(new_bits) || (old_bits.is_none() && new_bits == 0) {
            return Ok(self.revision);
        }
        let mut replacement = vec![];
        put((2 << 3) | 5, &mut replacement);
        replacement.extend(new_bits.to_le_bytes());
        let old_amount = optional(old, 2, 5)?;
        let mut modified = vec![];
        if let Some(f) = old_amount {
            modified.extend_from_slice(&old[..f.start]);
            modified.extend(replacement);
            modified.extend_from_slice(&old[f.end..]);
        } else {
            modified.extend_from_slice(old);
            modified.extend(replacement)
        }
        let edited_morph = splice_bytes(morph, selected, &modified)?;
        let result = splice_bytes(&self.current, root, &edited_morph)?;
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
}
#[cfg(test)]
mod tests {
    use super::*;
    fn v(tag: u32, value: u64) -> Vec<u8> {
        let mut out = vec![];
        put(u64::from(tag) << 3, &mut out);
        put(value, &mut out);
        out
    }
    fn b(tag: u32, value: &[u8]) -> Vec<u8> {
        let mut out = vec![];
        put((u64::from(tag) << 3) | 2, &mut out);
        put(value.len() as u64, &mut out);
        out.extend(value);
        out
    }
    fn modifier(key: Option<u64>, value: Option<f32>) -> Vec<u8> {
        let mut out = key.map_or(vec![], |key| v(1, key));
        if let Some(a) = value {
            out.push(21);
            out.extend(a.to_le_bytes())
        }
        out.extend(b(700, b"future-modifier"));
        out
    }
    fn record(morph: &[u8]) -> Vec<u8> {
        let mut out = vec![9];
        out.extend(42u64.to_le_bytes());
        out.extend(b(18, morph));
        out.extend(b(900, b"future-root"));
        out
    }
    fn morph(raw: &[u8]) -> Vec<u8> {
        let f = one(raw, 18, 2).unwrap();
        raw[f.value..f.end].to_vec()
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
    fn aged_override_is_not_added_to_base() {
        let mut m = b(2, &modifier(Some(9), Some(0.2)));
        m.extend(b(4, &modifier(Some(9), Some(0.7))));
        let mut d = Draft::new(42, record(&m)).unwrap();
        let e = d.effective_modifier(true, 9).unwrap().unwrap();
        assert_eq!(e.amount, 0.7);
        assert_eq!(e.selection.layer, Layer::AgedFace);
        let basic = d.modifiers(Layer::Face).unwrap()[0]
            .selection(Layer::Face)
            .unwrap();
        d.edit_modifier(0, basic, 0.4).unwrap();
        assert_eq!(d.effective_modifier(true, 9).unwrap().unwrap().amount, 0.7);
        d.edit_modifier(1, e.selection, 0.8).unwrap();
        assert_eq!(d.effective_modifier(true, 9).unwrap().unwrap().amount, 0.8);
    }
    #[test]
    fn only_selected_modifier_amount_changes_unknowns_stay_exact() {
        let target = modifier(Some(u64::MAX), Some(0.25));
        let mut m = v(1, 999);
        m.extend(b(3, &target));
        m.extend(b(5, &modifier(Some(8), Some(0.4))));
        m.extend(b(800, b"future-morph"));
        let raw = record(&m);
        let mut d = Draft::new(42, raw.clone()).unwrap();
        let select = d.modifiers(Layer::Body).unwrap()[0]
            .selection(Layer::Body)
            .unwrap();
        d.edit_modifier(0, select, -0.5).unwrap();
        assert_eq!(outside(&raw, 18), outside(d.bytes(), 18));
        let new = morph(d.bytes());
        assert_eq!(outside(&m, 3), outside(&new, 3));
        let f = one(&new, 3, 2).unwrap();
        assert_eq!(outside(&target, 2), outside(&new[f.value..f.end], 2));
        d.undo(1).unwrap();
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn duplicate_keys_have_explicit_ordinal_and_last_wins() {
        let mut m = b(2, &modifier(Some(9), Some(0.2)));
        m.extend(b(2, &modifier(Some(9), Some(0.5))));
        let mut d = Draft::new(42, record(&m)).unwrap();
        assert_eq!(d.effective_modifier(true, 9).unwrap().unwrap().amount, 0.5);
        let first = d.modifiers(Layer::Face).unwrap()[0]
            .selection(Layer::Face)
            .unwrap();
        d.edit_modifier(0, first, 0.3).unwrap();
        assert_eq!(d.modifiers(Layer::Face).unwrap()[0].amount, Some(0.3));
        assert_eq!(d.effective_modifier(true, 9).unwrap().unwrap().amount, 0.5);
    }
    #[test]
    fn optional_amount_presence_and_positive_zero_noop() {
        let raw = record(&b(2, &modifier(Some(9), None)));
        let mut d = Draft::new(42, raw.clone()).unwrap();
        let s = d.modifiers(Layer::Face).unwrap()[0]
            .selection(Layer::Face)
            .unwrap();
        assert_eq!(d.edit_modifier(0, s, 0.0).unwrap(), 0);
        assert_eq!(d.bytes(), raw);
        d.edit_modifier(0, s, -0.0).unwrap();
        assert_eq!(
            d.modifiers(Layer::Face).unwrap()[0]
                .amount
                .unwrap()
                .to_bits(),
            (-0.0f32).to_bits()
        );
    }
    #[test]
    fn stale_key_amount_ordinal_and_revision_refuse() {
        let raw = record(&b(2, &modifier(Some(9), Some(0.2))));
        let mut d = Draft::new(42, raw.clone()).unwrap();
        let s = d.modifiers(Layer::Face).unwrap()[0]
            .selection(Layer::Face)
            .unwrap();
        for bad in [
            Selection { key: 8, ..s },
            Selection { ordinal: 1, ..s },
            Selection {
                expected_amount_bits: None,
                ..s
            },
        ] {
            assert!(d.edit_modifier(0, bad, 0.3).is_err());
            assert_eq!(d.bytes(), raw);
        }
        assert!(d.edit_modifier(1, s, 0.3).is_err());
    }
    #[test]
    fn missing_key_is_visible_but_not_silently_zero_selected() {
        let raw = record(&b(2, &modifier(None, Some(0.2))));
        let mut d = Draft::new(42, raw.clone()).unwrap();
        let entry = d.modifiers(Layer::Face).unwrap()[0];
        assert_eq!(entry.key, None);
        assert!(entry.selection(Layer::Face).is_err());
        assert!(
            d.edit_modifier(
                0,
                Selection {
                    layer: Layer::Face,
                    ordinal: 0,
                    key: 0,
                    expected_amount_bits: Some(0.2f32.to_bits())
                },
                0.3
            )
            .is_err()
        );
        assert_eq!(d.bytes(), raw);
    }
    #[test]
    fn nonfinite_and_ambiguous_members_refuse() {
        for a in [f32::NAN, f32::INFINITY, f32::NEG_INFINITY] {
            let raw = record(&b(2, &modifier(Some(9), Some(0.2))));
            let mut d = Draft::new(42, raw.clone()).unwrap();
            let s = d.modifiers(Layer::Face).unwrap()[0]
                .selection(Layer::Face)
                .unwrap();
            assert!(d.edit_modifier(0, s, a).is_err());
            assert_eq!(d.bytes(), raw);
            let invalid = Draft::new(42, record(&b(2, &modifier(Some(9), Some(a))))).unwrap();
            assert!(invalid.modifiers(Layer::Face).is_err());
        }
        let mut bad = modifier(Some(9), Some(0.2));
        bad.extend(v(1, 9));
        let d = Draft::new(42, record(&b(2, &bad))).unwrap();
        assert!(d.modifiers(Layer::Face).is_err());
    }
    #[test]
    fn all_four_layers_are_separate() {
        let mut m = vec![];
        for layer in [Layer::Face, Layer::Body, Layer::AgedFace, Layer::AgedBody] {
            m.extend(b(
                layer.tag(),
                &modifier(Some(9), Some(layer.tag() as f32 / 10.0)),
            ))
        }
        let mut d = Draft::new(42, record(&m)).unwrap();
        let s = d.modifiers(Layer::AgedBody).unwrap()[0]
            .selection(Layer::AgedBody)
            .unwrap();
        d.edit_modifier(0, s, 0.9).unwrap();
        assert_eq!(d.effective_modifier(false, 9).unwrap().unwrap().amount, 0.9);
        assert_eq!(d.effective_modifier(true, 9).unwrap().unwrap().amount, 0.4);
    }
}
