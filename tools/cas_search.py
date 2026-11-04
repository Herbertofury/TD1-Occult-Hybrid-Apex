"""Cached, bounded typo planning for the read-only CAS metadata worker.

The vocabulary comes from SQLite's existing FTS tokenizer, not a second CC
scan. Plans contain only escaped FTS terms. They never select/equip an item.
"""
from bisect import bisect_left
from collections import OrderedDict, defaultdict
import re
import unicodedata


def terms(text):
    return re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text).casefold(), re.UNICODE)


def aliases(*names):
    """Index readable words inside EA/CC camel-case names without renaming them."""
    words = set()
    for name in names:
        if isinstance(name, str):
            split = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name)
            split = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', split)
            words.update(terms(split))
    return ' '.join(sorted(words))


def deletes(word):
    return {word[:i] + word[i + 1:] for i in range(len(word))}


def one_typo(left, right):
    """One insertion/deletion/substitution or adjacent transposition."""
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        changed = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return (len(changed) == 1 or len(changed) == 2 and changed[1] == changed[0] + 1 and
                left[changed[0]] == right[changed[1]] and left[changed[1]] == right[changed[0]])
    short, long = (left, right) if len(left) < len(right) else (right, left)
    at = next((i for i in range(len(short)) if short[i] != long[i]), len(short))
    return short[at:] == long[at + 1:]


class Vocabulary:
    def __init__(self, words):
        # Long internal identifiers remain exactly searchable through FTS.
        # Typo assistance is useful for words, not 64-digit resource hashes.
        self.words = sorted({word for word in words if 3 <= len(word) <= 48})
        self.exact = set(self.words)
        self.deleted = defaultdict(list)
        for word in self.words:
            for removed in deletes(word):
                self.deleted[removed].append(word)
        self.plans = OrderedDict()

    def alternatives(self, token):
        if not 3 <= len(token) <= 48:
            return []
        # A valid prefix must not be "corrected" to a different author's name.
        at = bisect_left(self.words, token)
        if at < len(self.words) and self.words[at].startswith(token):
            return []
        candidates = set(self.deleted.get(token, ()))
        for removed in deletes(token):
            if removed in self.exact:
                candidates.add(removed)
            candidates.update(self.deleted.get(removed, ()))
        found = {word for word in candidates if one_typo(token, word)}
        # Search while typing is prefix search too. Correcting a transposed
        # prefix such as "eyeborw" must find "eyebrows" without waiting for
        # the player to type its final letters. Probe the existing sorted
        # vocabulary; do not build another all-prefix index or scan its rows.
        probes = deletes(token)
        probes.update(token[:i] + token[i + 1] + token[i] + token[i + 2:] for i in range(len(token) - 1))
        alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789'
        for i in range(len(token) + 1):
            for char in alphabet:
                probes.add(token[:i] + char + token[i:])
                if i < len(token):
                    probes.add(token[:i] + char + token[i + 1:])
        for prefix in probes:
            if len(prefix) < 3:
                continue
            at = bisect_left(self.words, prefix)
            if at < len(self.words) and self.words[at].startswith(prefix):
                found.add(prefix)
        result = []
        for value in sorted(found):
            if not any(value.startswith(prior) for prior in result):
                result.append(value)
            if len(result) == 8:
                break
        return result

    def plan(self, text):
        tokens = terms(text)
        if len(tokens) > 16 or text.strip() and not tokens:
            raise ValueError('Search needs one to sixteen name terms.')
        key = tuple(tokens)
        if key in self.plans:
            self.plans.move_to_end(key)
            return self.plans[key]
        alternatives = [(token, self.alternatives(token)) for token in tokens]
        corrections = [{'typed': token,
                        'suggestions': sorted({self.words[bisect_left(self.words, prefix)] for prefix in found}),
                        'matched_prefixes': found}
                       for token, found in alternatives if found]
        # All tokens originate from the FTS vocabulary or Unicode word parser;
        # quotes/operators entered by a player can never become FTS syntax.
        expression = ' AND '.join('(' + ' OR '.join('"' + value + '"*' for value in [token] + found) + ')'
                                  for token, found in alternatives)
        result = (expression, corrections)
        self.plans[key] = result
        if len(self.plans) > 256:
            self.plans.popitem(last=False)
        return result
