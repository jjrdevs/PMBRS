package com.pmbrs.mobile.wearable

import android.content.Context
import com.pmbrs.mobile.settings.SyncSettings

/**
 * Phone-side wearable export collector (ADR-021 D3).
 *
 * Pipeline (one pass):
 *   1. Discover wearable JSON files (HR + HRV binning) from the most recent
 *      Samsung Health export dir under `Download/Samsung Health/`.
 *   2. Diff against [WearablePushTracking] to find pending files.
 *   3. Push each pending file over the LAN→cloud fallback [WearableSyncClient].
 *   4. On Ok → markPushed; on NetworkError/4xx → leave for next pass.
 *
 * Reuse of existing app plumbing (per ADR-021 D3):
 *   - Endpoint + token come from the app's `SyncSettings` (LAN base URL,
 *     fallback base URL, bearer token). The same SharedPreferences the
 *     existing artifact sync path uses — no new credential surface.
 *   - The collector itself is a plain class: `WearableExportCollector(context)`
 *     or `WearableExportCollector(client, ctx)` for injectable tests.
 *
 * NOT a service/worker: the app schedules it from its existing
 * `PMBRSSyncWorker` (or the boox-equivalent worker) on the same periodic pass.
 * Keeping it synchronous makes it easy to unit-test and lets the host-side
 * nightly drain (which is idempotent by sha256) be the sole ordering owner.
 */
class WearableExportCollector(
    private val context: Context,
    private val client: WearableSyncClient,
) {
    constructor(context: Context) : this(
        context,
        Wireup.fromSyncSettings(context),
    )

    data class Summary(
        val discovered: Int,
        val pending: Int,
        val pushed: Int,
        val failed: Int,
        val errors: List<Error>,
    ) {
        data class Error(val relPath: String, val reason: String)
    }

    fun collect(): Summary {
        val discovered = WearableExportDiscovery.discover().getOrElse { e ->
            return Summary(
                discovered = 0,
                pending = 0,
                pushed = 0,
                failed = 0,
                errors = listOf(Summary.Error("<discovery>", e.message ?: e::class.java.simpleName)),
            )
        }

        val pending = discovered.filter { !WearablePushTracking.isPushed(context, it) }
        val errors = ArrayList<Summary.Error>()
        var pushed = 0
        var failed = 0

        for (exp in pending) {
            when (val r = client.upload(exp)) {
                is WearableUploadResult.Ok -> {
                    WearablePushTracking.markPushed(context, exp)
                    pushed++
                }
                is WearableUploadResult.ClientError -> {
                    // A wrong token is a wrong token (ADR-020 D3.3) — do NOT
                    // mark pushed; do NOT keep re-surfacing the error per-file, cap it.
                    failed++
                    if (errors.size < 5) errors += Summary.Error(exp.relPath, "${r.code} ${r.body.take(200)}")
                }
                is WearableUploadResult.NetworkError -> {
                    failed++
                    if (errors.size < 5) errors += Summary.Error(exp.relPath, r.reason.take(200))
                }
            }
        }

        return Summary(
            discovered = discovered.size,
            pending = pending.size,
            pushed = pushed,
            failed = failed,
            errors = errors,
        )
    }

    /** Test hook: wipe the device-side push manifest. */
    fun resetTracking() = WearablePushTracking.clear(context)
}

/**
 * Builds a [WearableSyncClient] from the app's [SyncSettings]:
 *   - LAN  = `syncBaseUrl`        (default `http://127.0.0.1:8788/`)
 *   - Cloud = `fallbackSyncBaseUrl` (default `https://mobile-sync.jjrdev.com/`)
 *   - Token = the same bearer token the existing artifact sync uses.
 *
 * This mirrors the boox module's `BuildConfig`-injected wiring but routes
 * through the app's user-visible SharedPreferences so the user can update
 * endpoint/token without rebuilding the APK.
 */
internal object Wireup {

    /** Test seam: override which [WearableSyncClient] the collector builds.
     *  Mirror of the existing `PMBRSSyncWorker.syncServiceProvider` injection
     *  pattern (see the boox / app test files). Null → use SyncSettings. */
    var wireupOverride: ((Context) -> WearableSyncClient)? = null

    fun fromSyncSettings(ctx: Context): WearableSyncClient {
        wireupOverride?.let { return it(ctx) }
        val s = SyncSettings(ctx)
        val lanUrl = s.syncBaseUrl.trimEnd('/') + "/"
        val cloudUrl = s.fallbackSyncBaseUrl.trimEnd('/') + "/"
        val token = s.authToken.orEmpty()
        // The wearable route allows `mobile | dev` roles (host route line 71);
        // the app's default `authToken` is the `mobile` role token. If the user
        // has only configured one token, we try it on both endpoints — the
        // hub's 401/403 surface is returned verbatim (BooxSyncClient contract).
        return WearableSyncClient(lanUrl, token, cloudUrl, token)
    }
}
