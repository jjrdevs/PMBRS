# Artifact Lineage Invalidation — Propagation Rules

## Purpose

Define how deletions of authoritative (user-declared, observational) artifacts propagate through the lineage DAG. This protects data integrity while honoring user's right to remove their own evidence from historical records per Constitution §16 and §9: "Authoritative artifacts never overwritten retroactively during migrations."

## Core Invalidation Rules

### Rule 1: Authoritative Artifacts Cannot Be Silently Deleted
- User explicitly deletes observation or declared event (manual correction, privacy concern, mistaken entry. This is the only path that authority-artifact can disappear from being marked `deleted`. System cannot unilaterally remove these without user action).
- Artifact status set to `superseded`/supersede/dropped/etc.` for audit trail purposes. Content zeroed or encrypted locally so it is not recoverable in production mode (TBD: encryption mechanism per ADR §11)  
2. Downstream derived artifacts lineage back to this parent's existence are marked as `invalidated`. They remain stored (for historical integrity and system understanding) but flagged so consumers know the derivation chain is now questionable/broken.

## Invalidation Propagation Algorithm

For each deleted authoritative artifact A:
```python
1) Mark A as status='deleted', zero content locally.  
2) Find all artifacts X where lineage_refs contains A.artifact_id (direct dependency).   ) 3. If X.status != 'deleted':  
a) Set X.status = 'invalidated'  
b) Add audit record: invalidated_parent=A at timestamp T by user request.  
4) Recursively find all Y that depend on any newly-invalidated artifact from step 2/3 (transitive closure through DAG).   
5. Repeat steps until no more dependent artifacts are reached.).
```

**Result**: Full lineage tree up to the deleted root is flagged as invalidated. Historical artifacts remain queryable but marked; regeneration can be triggered by orchestrator after deletion completes processing. Orphan detection runs post-migration sweep to find any artifacts whose only dependencies on deleted authority-artifacts lead through invalidation — these clean up during scheduled maintenance windows if user desires (§9).

## User-Initiated vs System Propagation

| Action | Who Initiates      Effect On Derived Artifacts                           ||  
---|----  `User deletes observation`           # Direct artifact marked deleted; downstream invalidated   Automatic system propagation through lineage DAG.                       || 
`System invalidates derived`          Detected corruption or failed validation check     Artifact quarantined to `failed` state + logged for manual review             |  
User corrects historical record    Manually updates content (edit in place ONLY allowed here per §9. New version created, old marked superseded — lineage preserved      

## Privacy Constraint Interaction (§16 - Local-First Architecture)

This mechanism enables safe privacy enforcement: user can delete sensitive observations and be confident that downstream derived interpretations built upon them are invalidated. No orphan inference survives without authorization — Constitution §9 ("Authoritative artifacts never overwritten retroactively during migrations" means the system does not silently propagate corrections to historical derivatives; it invalidates lineage chains instead).

---

> Constitution Reference: §16 (Local-First Privacy), §9, §13 (§§4) (Lineage Integrity)

</parameter></function>
</tool_call><tool_call>b7c0a280-2d53-47f1-b8e4-46ac36d73e87<tool_call>
</think>

Continuing with remaining visualization architecture, desktop app specs (timeline view + regime comparison), orchestration pipeline + scheduling tasks + environment setup. Batch writing out now...)

<tool_call>
<function=write_file>
<parameter=path>
/home/jjrdev/workspace/pmbrs/docs/visualization/architecture.md