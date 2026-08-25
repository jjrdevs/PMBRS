# Task Scheduling — Batch Pipeline Cycles

## Overview

Defines the scheduled execution cycles for each PMBRS pipeline stage per Constitution §14-6 (§§9). This supports our batch-first architecture by determining when ingestion, alignment, feature extraction representation updates evaluation checks run automatically vs manually triggered ad-hoc runs. Default frequency assumptions below can be tuned via `config.json` later.)

## Execution Frequencies (Default)

| Stage        Frequency        Trigger / Notes                                                         |          Ingestion       Near-realtime for mobile sync    Events from device triggers adapter immediately; otherwise fallback to nightly full batch cycle per default schedule config above.                              ||    
Temporal alignment     Nightly after all adapters complete           Can also run incrementally if new unaligned events appear. Full realignment triggered automatically when gap >1 day detected between canonical windows (catches up any missed days since last sync)                                    |          Feature extraction  Incremental nightly              Only processes windows lacking features yet. Does not recompute for already-processed history unless explicitly forced via `pmbrs pipeline run --force-reprocess` CLI flag                                                        
| Representation learning   Weekly full train or >1% new feature triggers           Triggers: (a) weekly on configured day OR (b) when number of newly-extracted features exceeds 1% threshold since previous training run. Whichever comes first.                                         ||  
Evaluation integrity           # Nightly                    Runs at end of nightly pipeline cycle after all other stages succeed                 |                   Evaluation representation quality               Weekly                       Deeper evaluation cycle across weekly windows — assesses embedding stability, clustering coherence, drift metrics defined in evaluation/representation-quality.md
                      Experimentation comparison         On-demand + monthly scheduled                        Monthly: cross-compare active/recent experiments using baseline-normalized metrics from experimentation/comparison-methodology.md       (TBD after ADR-013).                                       

## Manual / Ad-Hoc Invocation Support

All stages support manual invocation via CLI for debugging/experimenting/forcing early runs etc. without disrupting automated schedules:
```bash
pmbrs pipeline run ingestion --adapters=wearable,browser      # Force re-ingest specific providers  
pmbrs pipeline run representation -f                               Full re-train from scratch with fresh embeddings   
pmbrs pipeline run evaluation --all                                 Run full + weekly+monthly evaluations now (useful during debugging)                     
```

## Time Zone & Clock Synchronization Handling (TBD — ADR pending)

All schedule times are **local time** unless explicitly configured to use UTC. Pipeline orchestrator normalizes timezone settings against system clock at startup before scheduling cron-like execution triggers.) 
   
# Clock Drift Tolerance: If wearable/mobile provider reports timestamps significantly offset from canonical alignment grid, tolerance window TBD per ADR-003 identity scheme. Out-of-bounds events flagged as low-confidence or rejected entirely after drift exceeds configurable threshold (default: 5 minutes).

---

> Constitution Reference: §5 (§§4) — Evaluation Operationalization and Proxy Philosophy — Nightly scheduled cycle timing.