package com.pmbrs.mobile.collectors

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.toEntity
import com.pmbrs.mobile.data.ProvenanceMetadata
import com.pmbrs.mobile.settings.SyncSettings
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import com.pmbrs.mobile.network.NetworkStateHelper
import com.pmbrs.mobile.sync.NetworkSyncClient
import com.pmbrs.mobile.sync.SyncService

/**
 * Receiver to accept explicit browser visit broadcasts from browsers (e.g., Bromite)
 * Expected intent action: "com.pmbrs.mobile.ACTION_BROWSER_VISIT"
 * Extras (recommended):
 *  - "url" (String) optional
 *  - "title" (String) optional
 *  - "search_query" (String) optional
 *  - "browser_package" (String) optional
 *  - "observed_at_ms" (Long) optional
 */
class BrowserIntentReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "BrowserIntentReceiver"
        const val ACTION_BROWSER_VISIT = "com.pmbrs.mobile.ACTION_BROWSER_VISIT"
    }

    override fun onReceive(context: Context, intent: Intent) {
        try {
            if (intent.action != ACTION_BROWSER_VISIT) {
                Log.w(TAG, "Ignored unexpected intent action=${intent.action}")
                return
            }

            val url = intent.extras?.getString("url")
            val title = intent.extras?.getString("title")
            val searchQuery = intent.extras?.getString("search_query")
            val bp = intent.extras?.getString("browser_package")
            val browserPackage = bp ?: intent.`package` ?: "unknown"
            val observedAt = try {
                intent.getLongExtra("observed_at_ms", System.currentTimeMillis())
            } catch (e: Exception) {
                System.currentTimeMillis()
            }

            // optional HMAC validation
            val sig = intent.extras?.getString("pmbrs_sig")
            val settings = SyncSettings(context)
            val configuredPsk = settings.pmbrsPsk
            if (sig != null) {
                if (configuredPsk.isNullOrBlank()) {
                    Log.w(TAG, "Received signed visit but no PSK configured; dropping")
                    return
                }
                val expected = try {
                    val payload = ((url ?: "") + observedAt.toString()).toByteArray(Charsets.UTF_8)
                    hmacSha256Hex(configuredPsk.toByteArray(Charsets.UTF_8), payload)
                } catch (e: Exception) {
                    Log.e(TAG, "Error computing HMAC", e)
                    null
                }
                if (expected == null || !expected.equals(sig, ignoreCase = true)) {
                    Log.w(TAG, "Signature verification failed; dropping broadcast")
                    return
                }
            }

            val urlDisplay = url ?: "<none>"
            val titleDisplay = title ?: "<none>"
            Log.i(TAG, "Received browser visit: package=$browserPackage url=$urlDisplay title=$titleDisplay")

            val payload = linkedMapOf<String, Any>(
                "browser_package" to browserPackage,
                "browser_url" to (url ?: "unknown"),
                "page_title" to (title ?: "unknown"),
                "search_query" to (searchQuery ?: ""),
                "collection_mode" to "explicit_broadcast",
                "observed_at_ms" to observedAt,
                "access_note" to "explicit browser broadcast: page-level content included by browser producer"
            )

            val provenance = ProvenanceMetadata(
                artifactType = "observational.phone.browser_visit",
                sourceDeviceId = android.provider.Settings.Secure.getString(context.contentResolver, android.provider.Settings.Secure.ANDROID_ID) ?: UUID.randomUUID().toString()
            )

            val artifact = PmbrsArtifact(
                id = UUID.randomUUID().toString(),
                source = "browser",
                payload = payload,
                createdAtEpochMs = observedAt,
                provenanceMetadata = provenance
            )

            val db = ArtifactDatabase.getInstance(context)
            val rowId = db.artifactDao().insertIfMissing(artifact.toEntity())
            Log.i(TAG, "Persisted broadcast browser artifact artifactId=${artifact.id} rowId=$rowId")

            // Attempt an immediate sync if allowed by network policy.
            try {
                val networkHelper = NetworkStateHelper(context)
                val trustedOk = !settings.trustedNetworkOnly || networkHelper.isTrustedNetworkConnected()
                if (trustedOk) {
                    val selectedBase = if (networkHelper.isTrustedNetworkConnected()) settings.syncBaseUrl else settings.fallbackSyncBaseUrl
                    Log.i(TAG, "Selected sync base: $selectedBase")
                    val client = NetworkSyncClient.create(selectedBase, settings.authToken)
                    val syncService = SyncService(ArtifactDatabase.getInstance(context), client)
                    syncService.syncPending { result ->
                        Log.i(TAG, "Broadcast-triggered sync result: $result")
                    }
                } else {
                    Log.i(TAG, "Skipping immediate sync due to trusted-network policy")
                }
            } catch (e: Exception) {
                Log.w(TAG, "Immediate sync attempt failed", e)
            }

        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle browser visit intent", e)
        }
    }

    private fun hmacSha256Hex(key: ByteArray, data: ByteArray): String {
        val mac = Mac.getInstance("HmacSHA256")
        val spec = SecretKeySpec(key, "HmacSHA256")
        mac.init(spec)
        val raw = mac.doFinal(data)
        return raw.joinToString("") { "%02x".format(it) }
    }
}
