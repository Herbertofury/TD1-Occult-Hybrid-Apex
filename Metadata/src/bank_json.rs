//! Strict lossless JSON spans for owned form-bank bytes; no game/Python objects.
use sha2::{Digest, Sha256};
use std::{collections::HashSet, ops::Range};
pub(crate) type Result<T> = std::result::Result<T, String>;
pub(crate) const MAX_DOCUMENT: usize = 48 * 1024 * 1024;
const MAX_DEPTH: usize = 128;
const MAX_NODES: usize = 2_000_000;
pub(crate) fn check(ok: bool, message: &str) -> Result<()> {
    if ok { Ok(()) } else { Err(message.into()) }
}
pub(crate) fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
pub(crate) fn id(text: &str) -> bool {
    !text.is_empty()
        && text.len() <= 20
        && text.as_bytes()[0] != b'0'
        && text.bytes().all(|b| b.is_ascii_digit())
        && text.parse::<u64>().is_ok()
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) enum Value {
    Object(Vec<(Vec<u16>, Node)>),
    Array(Vec<Node>),
    String(Vec<u16>),
    Number,
    Bool(bool),
    Null,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Node {
    pub(crate) span: Range<usize>,
    pub(crate) value: Value,
}
impl Node {
    pub(crate) fn field(&self, key: &str) -> Option<&Node> {
        match &self.value {
            Value::Object(rows) => rows
                .iter()
                .find(|(k, _)| k.iter().copied().eq(key.encode_utf16()))
                .map(|(_, v)| v),
            _ => None,
        }
    }
    pub(crate) fn string_eq(&self, text: &str) -> bool {
        match &self.value {
            Value::String(s) => s.iter().copied().eq(text.encode_utf16()),
            _ => false,
        }
    }
    pub(crate) fn members(&self) -> Result<&Vec<(Vec<u16>, Node)>> {
        match &self.value {
            Value::Object(rows) => Ok(rows),
            _ => Err("Expected JSON object".into()),
        }
    }
}
struct Parser<'a> {
    raw: &'a [u8],
    at: usize,
    nodes: usize,
}
impl<'a> Parser<'a> {
    fn ws(&mut self) {
        while self
            .raw
            .get(self.at)
            .is_some_and(|b| matches!(*b, b' ' | b'\n' | b'\r' | b'\t'))
        {
            self.at += 1
        }
    }
    fn next(&mut self, b: u8) -> Result<()> {
        check(self.raw.get(self.at) == Some(&b), "Invalid JSON token")?;
        self.at += 1;
        Ok(())
    }
    fn string(&mut self) -> Result<Vec<u16>> {
        self.next(b'"')?;
        let mut decoded = Vec::new();
        loop {
            let b = *self.raw.get(self.at).ok_or("Unterminated JSON string")?;
            self.at += 1;
            match b {
                b'"' => break,
                b'\\' => {
                    let escape = *self.raw.get(self.at).ok_or("Truncated JSON escape")?;
                    self.at += 1;
                    if escape == b'u' {
                        let mut unit = 0u16;
                        for _ in 0..4 {
                            let h = *self.raw.get(self.at).ok_or("Truncated Unicode escape")?;
                            let value = (h as char).to_digit(16).ok_or("Invalid Unicode escape")?;
                            unit = (unit << 4) | value as u16;
                            self.at += 1;
                        }
                        decoded.push(unit);
                    } else {
                        decoded.push(match escape {
                            b'"' => 34,
                            b'\\' => 92,
                            b'/' => 47,
                            b'b' => 8,
                            b'f' => 12,
                            b'n' => 10,
                            b'r' => 13,
                            b't' => 9,
                            _ => return Err("Invalid JSON escape".into()),
                        });
                    }
                }
                0..=31 => return Err("Unescaped control character".into()),
                128..=255 => {
                    let ch = std::str::from_utf8(&self.raw[self.at - 1..])
                        .map_err(|_| "Invalid UTF-8 string")?
                        .chars()
                        .next()
                        .ok_or("Truncated Unicode string")?;
                    self.at += ch.len_utf8() - 1;
                    let mut units = [0u16; 2];
                    decoded.extend_from_slice(ch.encode_utf16(&mut units));
                }
                _ => decoded.push(b as u16),
            }
        }
        // UTF16 units preserve Python's accepted escaped lone surrogates too.
        // Valid pairs and literal astral Unicode compare as the same key.
        Ok(decoded)
    }
    fn number(&mut self) -> Result<()> {
        let start = self.at;
        if self.raw.get(self.at) == Some(&b'-') {
            self.at += 1;
        }
        if self.raw.get(self.at) == Some(&b'0') {
            self.at += 1;
        } else {
            check(
                self.raw
                    .get(self.at)
                    .is_some_and(|b| matches!(*b, b'1'..=b'9')),
                "Invalid JSON number",
            )?;
            while self.raw.get(self.at).is_some_and(u8::is_ascii_digit) {
                self.at += 1;
            }
        }
        let mut float = false;
        if self.raw.get(self.at) == Some(&b'.') {
            float = true;
            self.at += 1;
            let begin = self.at;
            while self.raw.get(self.at).is_some_and(u8::is_ascii_digit) {
                self.at += 1;
            }
            check(self.at > begin, "Missing fractional digits")?;
        }
        if self
            .raw
            .get(self.at)
            .is_some_and(|b| matches!(*b, b'e' | b'E'))
        {
            float = true;
            self.at += 1;
            if self
                .raw
                .get(self.at)
                .is_some_and(|b| matches!(*b, b'+' | b'-'))
            {
                self.at += 1;
            }
            let begin = self.at;
            while self.raw.get(self.at).is_some_and(u8::is_ascii_digit) {
                self.at += 1;
            }
            check(self.at > begin, "Missing exponent digits")?;
        }
        if float {
            let text =
                std::str::from_utf8(&self.raw[start..self.at]).map_err(|_| "Invalid number")?;
            check(
                text.parse::<f64>().is_ok_and(f64::is_finite),
                "Nonfinite JSON number",
            )?;
        }
        // Integers stay raw, including values larger than u64. No f64 conversion.
        Ok(())
    }
    fn value(&mut self, depth: usize) -> Result<Node> {
        check(depth <= MAX_DEPTH, "Explicit JSON depth budget exceeded")?;
        self.nodes += 1;
        check(
            self.nodes <= MAX_NODES,
            "Explicit JSON node budget exceeded",
        )?;
        self.ws();
        let start = self.at;
        let value = match self
            .raw
            .get(self.at)
            .copied()
            .ok_or("Truncated JSON value")?
        {
            b'{' => {
                self.at += 1;
                self.ws();
                let mut rows = Vec::new();
                let mut keys = HashSet::new();
                if self.raw.get(self.at) != Some(&b'}') {
                    loop {
                        self.ws();
                        let key = self.string()?;
                        check(keys.insert(key.clone()), "Duplicate decoded JSON key")?;
                        self.ws();
                        self.next(b':')?;
                        rows.push((key, self.value(depth + 1)?));
                        self.ws();
                        if self.raw.get(self.at) == Some(&b'}') {
                            break;
                        }
                        self.next(b',')?;
                    }
                }
                self.next(b'}')?;
                Value::Object(rows)
            }
            b'[' => {
                self.at += 1;
                self.ws();
                let mut rows = Vec::new();
                if self.raw.get(self.at) != Some(&b']') {
                    loop {
                        rows.push(self.value(depth + 1)?);
                        self.ws();
                        if self.raw.get(self.at) == Some(&b']') {
                            break;
                        }
                        self.next(b',')?;
                    }
                }
                self.next(b']')?;
                Value::Array(rows)
            }
            b'"' => Value::String(self.string()?),
            b't' => {
                check(
                    self.raw.get(self.at..self.at + 4) == Some(b"true"),
                    "Invalid JSON literal",
                )?;
                self.at += 4;
                Value::Bool(true)
            }
            b'f' => {
                check(
                    self.raw.get(self.at..self.at + 5) == Some(b"false"),
                    "Invalid JSON literal",
                )?;
                self.at += 5;
                Value::Bool(false)
            }
            b'n' => {
                check(
                    self.raw.get(self.at..self.at + 4) == Some(b"null"),
                    "Invalid JSON literal",
                )?;
                self.at += 4;
                Value::Null
            }
            b'-' | b'0'..=b'9' => {
                self.number()?;
                Value::Number
            }
            _ => return Err("Invalid JSON value".into()),
        };
        Ok(Node {
            span: start..self.at,
            value,
        })
    }
}
pub(crate) fn parse(raw: &[u8]) -> Result<Node> {
    check(
        !raw.is_empty() && raw.len() <= MAX_DOCUMENT,
        "Explicit JSON byte budget exceeded",
    )?;
    std::str::from_utf8(raw).map_err(|_| "Invalid UTF-8")?;
    let mut p = Parser {
        raw,
        at: 0,
        nodes: 0,
    };
    let value = p.value(0)?;
    p.ws();
    check(p.at == raw.len(), "Trailing JSON bytes")?;
    Ok(value)
}
pub fn validate_json(raw: &[u8]) -> Result<()> {
    parse(raw).map(|_| ())
}
