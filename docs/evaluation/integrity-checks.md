# System Integrity Evaluation Checks

## Purpose

Validate subsystem health per Constitution §14 — not model accuracy but whether the data pipeline itself is functioning correctly. Nightly scheduled check per §14-6 evaluation cycle.

## Check Categories

### Data Ingestion Reliability

| Metric | Pass/Fail Threshold | Notes |
|---|---|---|
Ingestor success rate per adapter   >95% over rolling 7-day window           Drops below trigger manual review; silent failures are worse than noisy ones                || 
Latency between data availability and artifact creation    <24h for batch sync (mobile), <1h for API adapters      Defined by each adapter's declared sync interval                                            | Duplicate rejection rate                      Normal: >85% of retries rejected as duplicates   Indicates dedup logic is working                                                   

### Sync Correctness
| Check                                    Success Condition                                                 || 
---|---- |    
Lineage DAG consistency                No orphan artifacts (derived without parent); no cycles                       Full lineage graph validated nightly                                            || 
Schema version coverage               All artifacts readable under current schema + one prior major   Migration readers catch up                                                  
Artifact count monotonicity           Total authoritative artifacts never decreases          User deletes excluded — accidental loss is caught                               

### Temporal Alignment Integrity
| Check                                          | Success Condition                                  | Notes |
---|----|    
Canonical window gap detection            # No missing windows between start date and latest ingest date    Gaps >1 day generate warning (could indicate adapter failure)                                    ||     
Alignment overlap check                   Zero overlap between adjacent canonical windows; no gaps in coverage           Boundary policy validation per ADR-002                                    Modality coverage minimum threshold           Warning if <10% of random sample falls below expected modalities  Detects silent adapter dropouts                                          

### Signal Quality Monitoring
| Check                                          | Threshold                                        Notes                                                         |  
---|---|----   
Wearable device uptime                      >90% of days have at least 8 hours active wearable data   Low uptime → low-confidence windows; derived features flagged accordingly                       || 
Browser activity coverage                  Variable — no hard threshold yet, but monitor relative changes | Sudden drops: device change/new OS?                                    

### Corruption Detection
| Check                                  | Action                                                                  
---|----    
Artifact validation on load              Validate schema compliance (required fields present and types match)   Corrupted artifacts quarantined to `failed` state + logged.                                   || 
Content hash integrity check             Repr-content-hashes for reproducible artifacts and compare against stored     Mismatch → recompute from lineage ancestors                             

## Scheduling

Per Constitution §14-6: **Nightly** runs during batch pipeline cycle (e.g., 02:00 AM local time). Results written as `integrity_evaluation_report` artifact with timestamp and per-check status.

---

> Constitution Reference: §14 — Evaluation Operationalization, Proxy Philosophy (§15)
