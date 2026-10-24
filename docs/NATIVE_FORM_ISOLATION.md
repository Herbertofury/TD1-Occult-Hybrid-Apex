# Native form isolation

The installed 1.128.90.1030 game's `OccultTracker._copy_shared_attributes`
assigns the source physique to its destination and generates merged hidden
outfits. Its native callers include form switching, save, and wrapper creation.
Those writes join appearances that a hybrid player expects to keep independent.

`apex_core.native_form_isolation` patches that Python game method through the
mod at runtime. For two distinct, already registered appearance owners on an
existing hybrid, it performs only EA's gender-option trait-ID copy. The physique
assignment and hidden-outfit generation never execute. It reads no historical
bank and performs no appearance restoration. New wrappers are registered after
the native initialization copy, so their creation continues through EA's method.
Single-occult pairs, same-form copies, foreign owners and ambiguous bases retain
the original behavior. Existing transition/save preservation checks remain
enabled alongside the prevention patch. They are an independent permanent
layer, not an optional recovery mode or something disabled after a fix passes.
Explicit player edits/removals still need their own intent and provenance;
unrequested changes and future unknown data never justify silent replacement.

The `native_form_isolation` runtime receipt reports the actual intercepted
source/target and count. It does not certify all CAS code paths. In particular,
client-side CAS serialization can still narrow availability, alter other stored
appearances or drop traits before Live Python receives the result. Ordinary
phone/MCCC entry, every remaining occult/alternate and special-state editing
still require independent runtime qualification. No broad deletion-prevention
or production-save acceptance claim follows from this one method patch.

The private bytecode inspection is read-only and is not shipped. The game
installation and executable are not rewritten on disk.

After a reload, an existing historical bank may lack a current-runtime seal
for a companion. V115 still checkpoints every distinct existing native owner
before switching and verifies them all afterward. The historical bank is kept
as evidence; it never supplies appearance writes for this fresh switch. Missing
native owners, unresolved operations and changed identities continue to refuse
mutation. This avoids requiring a manual recovery transaction for an otherwise
valid loaded member without disabling the permanent preservation layer.
