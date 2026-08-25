# Browser Telemetry Adapter Spec


## Data Sources (Options to Evaluate)

| Option | Platform Coverage | Data Collected | Effort | Privacy Impact                    |     Chrome Extension / Firefox Add-on               # Browser-native        Page titles, URL fingerprints, tab switches, time-on-page         Medium          🔶 Local-first storage on machine; no cloud                                        ||      │
| Desktop Activity Monitor Script       Linux/Windows/Mac              App window focus events, active desktop app                       Low             ✅ Fully local process                                       | CLI log rotation script                        # Simple daemon            Window title polling (e.g., `xdotool getactivewindow`, `xwininfo`)   Very Low      ✅ Least complex; no extension development                                  
## Decision Status: **ADR needed** before implementation.

### Key considerations
- Must be fully local — data never leaves the machine during collection (§16)
- URL fingerprinting (not full URLs) sufficient for behavioral context without excessive privacy exposure
- Page content scraping explicitly excluded by default (§7 §9.) ✅ Least invasive option is preferred.

## Artifacts Produced

| Artifact Type | Notes |
|---|---|
| `browser_event`           # Per event: `domain_hash`, `page_title`, `active_duration_sec`, `timestamp_start`, `category_inferred?`  (TBD)   ||                          `screen_capture_artifact`     ❌ Excluded by default per constitution §7 (screens in scope as raw surveillance)  

---

> **Constitution Reference**: §8 (Modality Model), §9 (Artifact Architecture — excluded modality rule)
