# Local-First Sync with Cloudflare Fallback Plan

## Goal

Keep the mobile telemetry system primarily local-first while allowing a secure remote fallback when the phone is away from home. The phone should prefer the home machine when it is on the trusted local network, and use a Cloudflare-tunneled endpoint when it is not.

This matches the solo personal telemetry model:

- raw data stays local and private,
- the phone collects locally first,
- sync is opportunistic and low-friction,
- the app never assumes USB transport,
- Hermes remains summary-only and read-only,
- the cloud path is a backup, not the default trust model.

## Design assumptions

1. The phone is usually on the local home Wi‑Fi or Ethernet.
2. The home machine is the primary destination for uploads.
3. The Cloudflare tunnel is the fallback endpoint when the phone is off-network.
4. The user owns the setup and is the only operator.
5. The app remains opt-in and privacy-first.
6. The system is intentionally simple and not production-grade or multi-user.

## High-level architecture

### Primary path: home local network

- The phone checks whether it is connected to a trusted home network.
- If yes, it syncs to the local ingestion endpoint on the home machine.
- This minimizes latency and avoids exposing the raw store externally.

### Fallback path: Cloudflare tunnel

- If the phone is not on the trusted home network, it attempts the remote Cloudflare endpoint instead.
- This path should be HTTPS only.
- It should use a bearer token or similar simple auth mechanism.
- It should be limited to the minimal ingestion API only.

### Boundary model

- Phone -> local ingestion service -> raw local store
- Hermes -> consumes derived summaries only
- Cloudflare endpoint should not expose the raw data root directly
- The secure path should be the ingestion API only, not Hermes or the raw artifact directory

## End-state behavior

The phone should work like this:

1. Collect local telemetry artifacts on a periodic schedule.
2. Queue pending artifacts locally.
3. Check whether the phone is on a trusted home network.
4. If trusted: use the local endpoint.
5. If not trusted: use the Cloudflare endpoint.
6. If neither is reachable: keep the data queued locally and retry later.
7. Only after successful upload should artifacts be marked as synced.

## Implementation plan

### Phase A — Add endpoint selection logic

#### Goal

Allow the app to maintain a primary local endpoint and a fallback remote endpoint.

#### Tasks

- add a `primarySyncBaseUrl` setting,
- add a `fallbackSyncBaseUrl` setting,
- add a `useLocalFirst` or similar mode toggle,
- add a helper to choose the best endpoint based on network status,
- keep the current single-endpoint logic as a compatibility fallback,
- validate both URLs independently with the existing URL normalization rules.

#### Acceptance criteria

- the app can resolve one endpoint from two configured values,
- it prefers the trusted local network when available,
- it falls back to Cloudflare when away from home,
- invalid URLs are rejected cleanly.

### Phase B — Network detection policy

#### Goal

Use the existing trusted-network logic to classify home-network conditions.

#### Tasks

- treat Wi‑Fi and Ethernet as trusted local transport options,
- detect the home profile based on SSID or host-specific policy,
- keep the default simple and private: “trusted Wi‑Fi/Ethernet means local-first,”
- if the user prefers, add a manual override toggle for local-only or cloud-only.

#### Acceptance criteria

- the app recognizes when it is at home,
- it will prefer local sync at home,
- it will not assume cloud is always available.

### Phase C — Cloudflare tunnel endpoint configuration

#### Goal

Expose only a minimal secure ingestion path behind the tunnel.

#### Tasks

- expose a small HTTPS endpoint for artifact upload,
- protect it with basic auth, bearer token, or similar simple secret,
- ensure the tunnel relates only to the ingestion service and not the raw store,
- use a dedicated secret for the mobile app rather than a general-purpose account token,
- keep the local service running as a minimal endpoint with no broad surface area.

#### Acceptance criteria

- the phone can reach the service via Cloudflare without exposing raw data,
- the tunnel path is restricted to the sync API,
- the endpoint is protected by a personal secret.

### Phase D — Local backend for the ingestion endpoint

#### Goal

Accept uploaded artifacts from the phone and place them into the local raw store only.

#### Tasks

- implement a minimal secure ingestion endpoint,
- accept a standardized artifact payload,
- validate schema version and provenance metadata,
- store incoming artifacts in the local raw artifact database or file root,
- do not open a broader API surface than the required sync path,
- record upload success/failure locally for debugging.

#### Acceptance criteria

- the ingestion endpoint accepts only the expected artifact structure,
- the app can queue and send data without exposing unrelated services,
- local raw storage remains the source of truth.

### Phase E — Retry and queue behavior

#### Goal

Ensure the system is resilient and never loses data.

#### Tasks

- keep pending artifacts in the local database when upload fails,
- retry on the next scheduled run,
- prefer the strongest available endpoint each time,
- do not delete queued artifacts unless upload actually succeeds,
- keep the retry policy simple and conservative.

#### Acceptance criteria

- no data is lost simply because a route is unavailable,
- local queue is durable,
- retry logic is transparent and easy to inspect.

### Phase F — Manual override and transparency

#### Goal

Keep the system understandable for a solo user.

#### Tasks

- expose current endpoint choice in the app,
- show whether sync is using local or remote mode,
- allow manual override if the home network is temporarily unpredictable,
- surface a simple status message about the active route.

#### Acceptance criteria

- the user can see what the device is doing at a glance,
- the status is clear even without reading logs,
- local/cloud selection is explicit and user-controlled.

## Detailed operation flow

### At home on trusted network

- phone detects Wi‑Fi/Ethernet connection,
- chooses local sync URL,
- sends pending artifacts over HTTPS to the local ingestion service,
- marks them as synced,
- continues to run periodic collection locally.

### Away from home

- phone detects non-trusted network,
- chooses Cloudflare-tunneled URL,
- sends pending artifacts through the secure remote endpoint,
- stores them locally if the local service is reachable and configured for that flow,
- retries later if remote access fails.

### No network

- collection continues offline,
- artifacts remain queued locally,
- later upload occurs when the phone reconnects to either route.

## Security and privacy model

- only the minimal ingestion API is exposed,
- Cloudflare is used only as a transport path, not for data analysis,
- the raw store remains on the local machine,
- Hermes stays summary-only and read-only,
- the local machine hosts the authoritative raw data,
- the app stores only the URL, auth token, and local settings required for sync.

## What to request from the user

The following can be gathered later by the user and shared as needed:

1. home network details
   - trusted SSID or home network pattern,
   - whether home is Wi‑Fi or Ethernet,
   - whether the local machine is always on and reachable,
2. local service host details
   - local IP/hostname for the ingestion service,
   - local port number,
   - whether TLS is already configured or if a reverse proxy is needed,
3. Cloudflare tunnel details
   - tunnel domain or subdomain,
   - route path for the sync API,
   - token or auth method to use,
4. desired fallback behavior
   - prefer local by default,
   - cloud as backup only,
   - manual override support,
5. privacy preference
   - raw data never exported beyond the private machine,
   - only minimal sync data enters the remote path.

## Failure points and mitigations

### Failure point: local service unreachable at home

Mitigation:
- keep the app retrying,
- fall back to Cloudflare if configured,
- mark the sync route as degraded in the UI.

### Failure point: Cloudflare tunnel is down

Mitigation:
- queue artifacts locally,
- retry later,
- avoid user-visible failure that blocks collection.

### Failure point: local route is selected when the phone is actually off-network

Mitigation:
- keep the network check explicit and conservative,
- require a trusted local network signal before choosing the local URL.

### Failure point: app assumes a single endpoint forever

Mitigation:
- store both local and fallback URLs and resolve dynamically.

### Failure point: raw data accidentally exposed through the tunnel

Mitigation:
- expose only the minimal artifact ingestion API,
- never tunnel Hermes raw paths,
- keep all raw storage behind the local machine boundary.

## Definition of done

This plan is complete when:

- the app supports a primary local URL and a fallback Cloudflare URL,
- local network detection chooses the home endpoint first,
- remote Cloudflare handles off-network sync as needed,
- queue/retry behavior is durable and explicit,
- the app clearly communicates which route is in use,
- the system remains local-first and personal-only.

## Recommended next step

The next concrete implementation is to add the dual-endpoint selection logic in the Android app, then wire the local and Cloudflare host details into the app after the user shares those values.
