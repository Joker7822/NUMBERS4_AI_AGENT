# Dashboard overview and refresh optimization

The overview moves verified counters to the first screen and distinguishes
official training history, prospective sample count, historical STRAIGHT and
BOX gross recovery, and hypothetical net balance. Existing evidence tables,
research and operational details remain accessible through fragment links.
The browser retains the full existing status and integrated provenance
validators; the optional integrated panel stays hidden when its evidence
is unavailable. Main snapshot failure hides all evidence-bearing panels.

Requests use stable URLs with HTTP revalidation, independent parallel fetches,
12-second per-request abort signals, and a shared in-flight refresh gate.
Automatic refresh remains every 120 seconds when visible, and returning to
a tab does not re-fetch within that interval. HTTP 304 or byte savings depend
on server and browser caching; no network performance claim is made.
CSS improves narrow-screen rows, keyboard focus, table containment and
reduced motion. The test suite covers request orchestration, failure, progress
and finance calculation semantics and markup anchors. Actual browser layout,
accessibility audits and live Pages deployment require separate verification.
No evidence or model authority is changed.
