# Timeline View — Desktop App Component Spec

## Purpose

Primary temporal visualization view in the PMBRS desktop app. Displays canonical windows, behavioral embeddings, regime transitions, and modality coverage projections across time. Per Constitution §5: *"Batch-first analysis — not real-time streaming."* This is a historical exploration tool, not a live dashboard.**

## UX Layout (Wireframe)

```text
┌─────────────────────────────────────────────────────────┐
│ ← [Date Range Selector] ─── Mode Overlay Toggle ▾ ─▶  │
│                                                         │
│ ─────REGIME A────  ─────REGIME B──  ──GAP──           │
│ ███▓▓▒░░····███▓▓▒░░····███▓▓  Embedding trajectory    │
│ ▂▃▅▇████▇▅▃▂▂▃▅▇████▇▅▃▂▂  Wearable HR heatmap      │
│ ████████████████████████████  Modality coverage bars   │
│ ▁▁▃▅▇████████▇▅▃▁▁         Feature density signal    │
│                                                         │
│ ◀─────── [Hover: 2026-08-05T14:32–14:33 UTC] ─────▶    │
│ Wearable: ✓ HR=72 BPM | Browser: 2 domains             │
│ Regime: A (high focus)  Embedding norm: 2.31          │
└─────────────────────────────────────────────────────────┘
```

## Interactions

| Interaction | Result | Notes |
| --- | --- | --- |
| Zoom in / out by time range | Load canonical windows for the selected period; virtual scrolling handles more than 50k windows | Lazy-load with a SQLite index query |
| Regime filter | Highlight only windows belonging to the selected cluster/regime | Requires a clustering_result artifact |
| Hover/click a window | Open a detail panel showing the raw artifacts contributing to that specific window | Full lineage drill-down per §12 |
| Toggle modality overlay | Add or remove visual layers such as wearable, browser, calendar, or journal contributions | Per-visibility control for each modality |
| Select experiment range | Highlight the temporal span where an experiment was active and color-code it by declaration | Based on the experimentation spec |

## Data Requirements from Artifact Store

```sql
-- Example query shape (conceptual)
SELECT window_id, start_time, end_time, regime_label
FROM canonical_windows c
JOIN behavioral_embeddings b ON c.window_id = b.window_id
WHERE c.start_time BETWEEN ? AND ?
ORDER BY c.start_time ASC;
```

Note: virtual scrolling should load 500–1000 windows at a time at most and should not attempt to render years of data in memory. A SQLite range index on `start_time` makes this fast even for millions of canonical windows.

## Color & Theme Conventions (TBD design)

- **Dark-mode-first** theme per visualization/architecture.md preference.
- Regimes: distinct color palette, at least 8 distinguishable regimes before resorting to legend labels 
- Modalities: Wearables (amber/orange), browser activity (teal/blue), calendar events (yellow/purple outlines), journal entries (green accents)
- Gaps/misalignment windows: dimmed/dashed visual treatment — clearly visible as missing evidence

---

> Constitution reference: §15 and §4. This is a downstream consumer UI design and remains a replaceable subsystem per the constitution.
</tool_call><tool_call>
<function=write_file>
<parameter=cross_profle>false</parameter>
<parameter=path>
/home/jjrdev/workspace/pmbrs/docs/visualization/desktop-app-specs/experiment-comparison.md