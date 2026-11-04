# EA permission evidence directory

The EA permission helper requires its evidence directory to be an existing
descendant of this checkout's `.work` directory. A disposable-profile journal
can instead live elsewhere. Previously the launcher always used the journal's
parent for the helper; an external journal could therefore reach the handoff
and then fail before sending permission input because the directory was invalid.

For a future fresh launch using the explicit or remembered one-shot permission
mode, `--permission-work` selects an existing `.work` evidence directory. The
launcher validates a supplied directory before handing off to EA and rejects it
when one-shot mode is not selected. The helper still receives the original
fresh launch context; this option does not approve UAC or extend a context lease.
When the option is omitted, legacy launch and fallback behavior remains intact.

Nine new mocked cases and the existing launcher suites exercise the integrated
source. A separate real filesystem test accepted a fresh `.work` child and
rejected an external directory. These checks do not prove a future EA dialog or
game launch; capture and reconcile each actual handoff separately.
