# Family Graph Snapshot Timeline Notes (Task 6C.1)

Date: 2026-04-22  
Scope: Frontend research only (no backend/runtime changes)

## 1) Current year-mode entry point

Primary files:

- `app/web/templates/family_tree.html`
- `app/web/static/js/family_graph.js`

Where year is initialized and stored:

- Template injects `window.GRAPH_YEAR`.
- JS derives:
  - `state.temporalMode` (`now` or `year`),
  - `state.selectedYear`,
  - `state.activeYear`.

Year UI controls already present:

- number input: `#year-input`
- slider: `#year-slider`
- mode toggle: `#btn-mode-now`, `#btn-mode-year`

Helper functions:

- `getCurrentYearFromUI()`
- `setYearInUI(year)`
- `applyYearAndReloadGraph(year)`
- `getRequestedYear()` -> returns selected year in `year` mode, otherwise `null`.

## 2) Where graph reload/fetch happens

Single fetch entry point:

- `loadAndRender(rootId, depth)` calls
  - `fetch('/family/tree/json?...')`
  - then assigns `currentNodes`/`currentLinks`
  - then calls `render()`.

Calls to `loadAndRender(...)` happen from:

- initial page load,
- depth +/- buttons,
- reroot,
- switching temporal mode,
- applying year changes (input/slider).

Important: each year change currently triggers full `render()` with new D3 simulation.

## 3) Can we switch snapshots without full graph recreation?

Current answer: not yet, at least not directly.

Why:

- `render()` clears container (`container.innerHTML = ''`), recreates SVG, markers, layers, nodes, edges.
- New `d3.forceSimulation(currentNodes)` is created each reload.
- Node positions are not persisted by stable cache across snapshots.

What is already good:

- data IDs look stable (`p_<id>`, `u_<id>`), which is useful for future keyed D3 joins.
- visual temporal states (`is_active_for_year`) are already consumed by styling (`edgeStroke`, `edgeDash`, `isUnionInactiveForYear`).

## 4) What currently causes layout jumping

Main contributors:

1. Full DOM rebuild in `render()` on each year update.
2. Force simulation restarts from fresh initial positions.
3. `rootNode.fx/fy` pinning helps center root, but does not stabilize all other nodes.
4. `centerOn(...)` animates viewport each render, reinforcing visual motion even when topology changes slightly.
5. Year slider emits frequent reloads (debounced), so re-layout is visible during scrub.

## 5) Minimal Phase 1 path (without large refactor)

Goal: enable timeline-like navigation (later wheel/swipe) while keeping current architecture mostly intact.

Suggested incremental path:

1. Keep existing backend API and year param contract.
2. Keep one fetch per snapshot year, but add client-side snapshot controller state:
   - `timelineYears[]`,
   - `timelineIndex`,
   - `goToNextSnapshot()`, `goToPrevSnapshot()`.
3. Use current `applyYearAndReloadGraph(year)` as the single transition method.
4. Add timeline event abstraction first (keyboard + buttons), wheel/swipe later.
5. Add request coalescing/guard:
   - ignore stale fetch responses if a newer year request is already in flight.

This gives Snapshot Timeline behavior quickly without backend or schema work.

## 6) What needs a separate task (mandatory)

These items should be tracked as dedicated implementation tasks:

1. Stable D3 update cycle (avoid full `render()` rebuild):
   - switch to keyed enter/update/exit joins for nodes and edges,
   - keep simulation instance alive across adjacent snapshots,
   - preserve `x/y/vx/vy` when node IDs match.
2. Layout continuity policy:
   - control when to reheat simulation,
   - introduce lower alpha on adjacent-year transitions,
   - reduce forced recentering.
3. Gesture timeline UX:
   - wheel/touchpad/swipe input mapping,
   - throttling and accessibility fallback.
4. Optional keyframe timeline source:
   - derive meaningful years from graph data (birth/union start/end/etc.),
   - start client-side, later optionally from backend endpoint.

## 7) Risks and mitigations

Risks:

- perceived instability/jitter when scrubbing years,
- too many network requests while navigating timeline,
- mismatch between temporal narrative expectations and soft-mode visuals.

Mitigations:

- keep Phase 1 intentionally simple,
- add fetch staleness protection,
- delay wheel/swipe until timeline index model exists,
- treat stable layout as Phase 2 objective (aligned with ADR-006).

## 8) Prototype 6C.2 — Stable Update Notes

Implemented approach (frontend prototype):

- Added feature flag in `app/web/static/js/family_graph.js`:
   - `USE_STABLE_UPDATE = true`.
- Stable path is enabled only for year-driven reloads (`applyYearAndReloadGraph` -> `loadAndRender(..., { stable: true })`) and only when temporal mode is `year`.
- First load still uses full `render()`.
- For next year snapshots:
   - existing SVG/layers/simulation are reused,
   - nodes are matched by stable `id` and keep prior `x/y/vx/vy` if present,
   - links are updated via keyed joins,
   - enter/exit nodes and edges use fade-in/fade-out transitions.

What this improves now:

- significantly reduces full-canvas jumps when scrubbing years,
- preserves spatial continuity for persistent nodes,
- keeps temporal status transitions (active/inactive edge styling) visibly smoother.

Known prototype limitations:

- no stale-request guard yet (rapid year changes can race responses),
- new nodes are seeded near root with a small random offset (good enough, but not ideal),
- still no dedicated keyframe index/timeline controller,
- stable mode is currently wired to year-change path only (expected by scope).

Recommended next steps for Phase 2:

1. Add request versioning/cancellation to drop stale year responses.
2. Extract shared node/edge join code to avoid duplication between full render and stable update path.
3. Tune simulation reheating (`alpha`, `alphaTarget`) based on diff size.
4. Add lightweight snapshot index API on frontend (next/prev snapshot abstraction), then plug wheel/swipe on top.

## 9) Prototype 6C.3 — Keyframe Navigation Notes

Implemented approach (frontend prototype on top of 6C.2):

- Added keyframe extraction from currently loaded graph data (`nodes` + `edges`):
   - person: `birth_year`, `death_year`, `birth_date`, `death_date`,
   - union: `start_date`, `end_date`,
   - edges: `valid_from`, `valid_to` (if present).
- Added normalization pipeline:
   - parse to integer year,
   - keep only valid years (`YEAR_MIN..YEAR_MAX`),
   - deduplicate and sort ascending.
- Added keyframe navigation state:
   - `state.keyframes[]`,
   - `state.currentKeyframeIndex`.
- Added minimal UI controls near the timeline slider:
   - `‹ предыдущий слой`,
   - `следующий слой ›`,
   - `Кадр: <year>` label.
- Added wheel prototype in year mode:
   - wheel down -> next keyframe,
   - wheel up -> previous keyframe,
   - throttle lock (~260ms) to prevent over-jumping.
- Navigation uses existing stable year update path (`applyYearAndReloadGraph`) and does not touch backend.

Observed limitations / known quirks:

- Keyframes are derived from the current graph scope (root/depth dependent), not global DB timeline.
- In year mode wheel navigation now prioritizes keyframe stepping over zoom while pointer is in graph/timeline area.
- Parsing of date-like strings is intentionally permissive; malformed values are ignored.

Recommended Phase 2 follow-ups:

1. Add explicit "keyframe mode" toggle to separate wheel-for-zoom and wheel-for-timeline behavior.
2. Add stale request protection (request token/version) for rapid keyframe switching.
3. Provide optional backend endpoint for deterministic keyframe years by scope.
4. Improve year parsing policy with stricter formats and telemetry for dropped date values.

## 10) Prototype 6C.3.1 — Keyframe Mode Toggle + Stale Fetch Guard

Implemented stabilization scope (frontend-only, no backend changes):

- Added explicit keyframe mode switch in UI (`Слои времени: ON/OFF`) in temporal controls.
- Wheel navigation is now explicit and predictable:
   - `OFF`: wheel keeps default D3 zoom behavior, keyframe wheel navigation is disabled.
   - `ON`: wheel in graph/timeline control zones steps through keyframes; D3 wheel zoom is blocked by zoom filter while mode is active.
- Wheel keyframe logic remains scoped to graph/timeline elements (`#graph-wrapper`, `#keyframe-nav`) and is not attached globally to window.

Stale fetch protection:

- Added request sequence guard in `loadAndRender`.
- Each request gets a monotonically increasing `requestId`.
- Response is applied only when `requestId` matches latest active sequence; older responses are ignored silently.

State safety outcomes:

- Prevents stale responses from rolling back rendered snapshot after fast keyframe wheel scrolling.
- `state.activeYear` is assigned only for the accepted latest response.
- `state.selectedYear`, `state.keyframes`, and scene snapshot stay consistent with last user action.

Micro-feedback:

- Added lightweight flash highlight on current keyframe year label when active keyframe changes.
- No heavy loaders/spinners were introduced.
