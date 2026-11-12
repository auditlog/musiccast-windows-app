# Desktop remote

Mode: Operate. Scope: one native Qt window and its tray menu.

## Direction contract

THESIS: A desktop mixer for one real receiver. Connection, receiver state and PC audio
are visible together, with commands named in Polish or English.

OWN-WORLD: Light slate workspace, white control surface, blue active controls and
Segoe UI. Actual receiver values lead. Native widgets, visible focus and bounded spacing.

STORY: Connect by IP or discovery, see the receiver's real state, adjust a setting,
then start or stop PC audio. Demo data is explicitly labelled.

FIRST VIEWPORT: Fixed-size two-column window with receiver controls on the left,
connection/discovery and PC audio on the right. A shared title, bounded notice slot
and footer complete the window without scrolling. “Użyj IP” fills the host field;
“Połącz” remains the connection action. Size is measured once using actual Qt metrics.

FORM: Windows mixer, fifth grounded candidate; seed 9b68ed78. Other considered forms:
remote handset, small mixing desk, quick settings, media player, receiver faceplate,
studio monitor control. Roll service was unreachable; no catalog challengers.
The implementation uses the accepted practical tool scope; visual details are assumptions.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review,
the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Verification boundary

No raster assets. Native Qt screenshots and Windows packaging require external
dependencies, which the development sandbox cannot download. Source-level review
cannot certify visual layout or real hardware interoperability. Pending on Windows:
verify measured normal/compact sizes, high DPI, work-area containment, long-text
ellipsis, explicit IP transfer, tray lifecycle and real AirPlay audio.
