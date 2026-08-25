# Calendar Adapter Spec

## Purpose

Sync calendar events as contextual declarative observations that provide structured temporal context (appointments, meetings, scheduled activities) to enrich behavioral analysis windows.

## Data Sources (Options to Evaluate)

| Provider | Integration Approach | Notes |
|---|---|---|
Google Calendar API              REST/GraphQL                      Rich event metadata, reminders, location tags       ✅ Good availability
            || 
Local `.ics` export               File-based                              Pull .ics from device sync, parse locally        Fully offline — no cloud dependency                   

## Artifacts Produced

Artifact type: `calendar_event` (observational class)

| Field | Status      │ Notes                           ||─────────────── | Type     │ Description                                     
│  `artifact_id`    UUID ✅ Globally unique identifier                             ||              `event_uid`       string    Source calendar UID (for deduplication)                       
`summary`             string   title/description                         `description`           text     Full event body if available                                    |:
Start time timestamp               ISO-8601 + timezone                                          | End time                 ISO-8601 + timezone                                      
| Location              string                    Physical or virtual meeting location                   
| Participants         array[string]                                                    Invited attendee lists (may contain PII — consider redaction policy)
| confidence_score     float [0,1]               How aligned with actual behavior (TBD inference later).

## Sync Pattern

- **Incremental fetch** — adapter tracks last sync timestamp per calendar source (`since` cursor)
- Deduplication on `event_uid`. If duplicate exists → skip silently.

# Modality Classification 

- Calendar events are categorized as **declared** contextual overlays in the modality model (§8). They provide structure, not observational evidence themselves — useful for comparing windows that contain scheduled activities vs those that don't.
- Potential PII: participant names considered sensitive data. Redaction policy (TBD): strip participant list or hash identities before storage.

---

> **Constitution Reference**: §10 (Authority model), §8 (Modality Model — declared modality)
