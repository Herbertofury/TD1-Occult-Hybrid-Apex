use std::collections::BTreeSet;
pub fn creator_key(value: &str) -> String {
    value
        .chars()
        .filter(|c| c.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}
pub fn words(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(str::to_lowercase)
        .collect()
}
pub fn aliases(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut split = String::new();
    for (i, &c) in chars.iter().enumerate() {
        if i > 0
            && c.is_uppercase()
            && (chars[i - 1].is_lowercase()
                || chars[i - 1].is_ascii_digit()
                || chars[i - 1].is_uppercase()
                    && chars.get(i + 1).is_some_and(|n| n.is_lowercase()))
        {
            split.push(' ');
        }
        split.push(c);
    }
    words(&split).join(" ")
}
pub fn deletions(value: &str) -> BTreeSet<String> {
    let chars: Vec<_> = value.chars().collect();
    let mut result = BTreeSet::new();
    result.insert(value.into());
    for at in 0..chars.len() {
        result.insert(
            chars
                .iter()
                .enumerate()
                .filter(|(i, _)| *i != at)
                .map(|(_, c)| *c)
                .collect(),
        );
    }
    result
}
pub fn one_typo(left: &str, right: &str) -> bool {
    let a: Vec<_> = left.chars().collect();
    let b: Vec<_> = right.chars().collect();
    if a.len().abs_diff(b.len()) > 1 {
        return false;
    }
    if a.len() == b.len() {
        let diff: Vec<_> = a
            .iter()
            .zip(&b)
            .enumerate()
            .filter_map(|(i, (a, b))| (a != b).then_some(i))
            .collect();
        return diff.len() <= 1
            || diff.len() == 2
                && diff[1] == diff[0] + 1
                && a[diff[0]] == b[diff[1]]
                && a[diff[1]] == b[diff[0]];
    }
    let (small, big) = if a.len() < b.len() {
        (&a, &b)
    } else {
        (&b, &a)
    };
    let (mut x, mut y) = (0, 0);
    let mut skipped = false;
    while x < small.len() && y < big.len() {
        if small[x] == big[y] {
            x += 1;
            y += 1;
        } else if skipped {
            return false;
        } else {
            skipped = true;
            y += 1;
        }
    }
    true
}
