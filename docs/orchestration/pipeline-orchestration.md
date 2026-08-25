# Pipeline Orchestration Architecture (Strawman) ADR 04 pending formalization

## Overview

PMBRS follows a single-process modular architecture per 'module-contracts.md'. One orchestrator invocation triggers sequential stages: ingestion, alignment, feature extraction, representation update, evaluation checks. Each stage reads artifacts from store and writes output artifacts back for downstream modules to consume.This document defines the orchestrators structure and sequencing logic formalized as ADR 4 pending.

## Orchestrator Responsibilities

### Core Design Principles
1. Artifact-first Pipeline state is implicit no global variables passed between modules instead every stage reads artifacts defined by its input contract and writes results back to artifact store.The orchestrator controls when each module runs not what data flows internally
2. Failure isolation checkpointing If a stage fails it stops there but previous stages already committed artifacts stay preserved on disk for later retry without rerunning from scratch  
3. Config-driven sequencing Module order configurable via YAML or json default follows lineage DAG: Ingestion to Temporal Alignment to Feature Extraction

## Pipeline Definition Format (Strategic draft):

```yaml
pipeline_name nightly-full 
schedule cron 02 * * # Midnight local time see task scheduling schedule for details       
timeout_ms Maximum run before timeout triggers                     
modules                                                                  
- name ingest_all_providers stage_id ingestion adapter_pool wearable, browser error_on_failure skip_adapter,log_warning 
    retry_count           features extract_incremental                    
|-│ name temporal_align_full windows_processed_max 5760             # Up to one day worth if processing slower than expected  

features extract incremental process new windows not yet feature-extracted
||   
- │name rep_train_or_update If >1% new feats OR weekly forced retrain fallback_action rollback       
evaluation integrity_check validation see eval checks                      
- name log_pipeline_summary Emit readable summary of what ran + timestamps counts produced      
always_runtrue true     # Always runs even if above stages fail for audit trail  
```
