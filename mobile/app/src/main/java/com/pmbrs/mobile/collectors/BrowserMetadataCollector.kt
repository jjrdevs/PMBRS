package com.pmbrs.mobile.collectors

import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.ProvenanceMetadata
import com.pmbrs.mobile.settings.SyncSettings
import java.util.UUID

/**
 * Browser metadata collector for the personal local telemetry project.
 *
 * This is a real, best-effort browser signal from Android usage statistics. It captures only
 * what the platform exposes without reading page content or raw URLs.
 *
 * Real extraction available from Android APIs:
 * - browser package name
 * - browser label
 * - foreground dwell time
 * - last used timestamp
 *
 * Not available by default without browser-specific APIs:
 * - full URL
 * - hostname/domain from the current page
 * - page title
 * - page content
 */
class BrowserMetadataCollector(private val context: Context) : BaseCollector() {

    companion object {
        private const val TAG = "BrowserMetadataCollector"
        private const val WINDOW_MS = 120_000L

        fun buildMetadataOnlyPayload(
            browserPackage: String,
            browserName: String,
            browserFamily: String,
            observedAtMs: Long,
            dwellMs: Long,
            canonicalHost: String = "unknown.local",
            category: String = browserFamily,
            pageTitle: String? = null,
            inputContext: Map<String, Any?> = emptyMap(),
            pageContext: Map<String, Any?> = emptyMap(),
            intentLabel: String = "unknown",
            linkSubcategory: String? = null
        ): Map<String, Any> {
            val safeInput = linkedMapOf<String, Any>(
                "field_type" to (inputContext["field_type"] ?: "unknown").toString().lowercase(),
                "interacted" to ((inputContext["interacted"] as? Boolean) ?: false),
                "submitted" to ((inputContext["submitted"] as? Boolean) ?: false),
                "value_logged" to false
            )

            val safePageContext = linkedMapOf<String, Any>(
                "page_type" to (pageContext["page_type"] ?: "unknown").toString().lowercase(),
                "title_length" to (pageTitle?.length?.coerceAtLeast(0) ?: 0),
                "host_type" to (pageContext["host_type"] ?: "unknown").toString().lowercase()
            )
            val normalizedPageContext = pageContext.filterKeys { it !in setOf("page_type", "host_type") }
            normalizedPageContext.forEach { (key, value) ->
                safePageContext[key] = value ?: "unknown"
            }

            val payload = linkedMapOf<String, Any>(
                "browser_package" to browserPackage,
                "browser_name" to browserName,
                "browser_family" to browserFamily,
                "canonical_host" to canonicalHost,
                "dwell_ms" to dwellMs.coerceAtLeast(0L),
                "observed_at_ms" to observedAtMs,
                "collection_mode" to "usage_stats_only",
                "category" to category,
                "intent_label" to intentLabel,
                "input_context" to safeInput,
                "link_subcategory" to (linkSubcategory ?: "unknown"),
                "page_context" to safePageContext,
                "page_title" to (pageTitle ?: "unknown"),
                "hostname" to canonicalHost,
                "domain" to canonicalHost,
                "access_note" to "metadata-only local browser signal; no raw page content, URLs, searches, or form values are retained"
            )

            return payload
        }
    }

    suspend fun collect(): Result<PmbrsArtifact> {
        val settings = SyncSettings(context)
        if (!settings.browserMetadataEnabled) {
            Log.d(TAG, "Browser metadata collection disabled by settings")
            return Result.failure(
                IllegalStateException("Browser metadata collection is disabled. This signal is opt-in and metadata-only.")
            )
        }

        return try {
            val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager
                ?: return Result.failure(IllegalStateException("UsageStatsManager unavailable"))

            val now = System.currentTimeMillis()
            @Suppress("DEPRECATION")
            val stats = usm.queryUsageStats(
                UsageStatsManager.INTERVAL_DAILY,
                now - WINDOW_MS,
                now
            )

            val recentBrowser = stats
                .filter { isLikelyBrowser(it.packageName) }
                .maxByOrNull { it.lastTimeUsed }
                ?: return Result.failure(IllegalStateException("No recent browser usage found"))

            val appLabel = resolveAppLabel(recentBrowser.packageName)
            val category = inferCategory(recentBrowser.packageName)

            val browserDisplayName = when {
                appLabel != null && appLabel.isNotBlank() -> appLabel
                recentBrowser.packageName.contains("adblock", ignoreCase = true) -> "Adblock Browser"
                recentBrowser.packageName.contains("bromite", ignoreCase = true) -> "Bromite"
                recentBrowser.packageName.contains("chromium", ignoreCase = true) -> "Chromium"
                recentBrowser.packageName.contains("chrome", ignoreCase = true) -> "Chrome"
                recentBrowser.packageName.contains("firefox", ignoreCase = true) -> "Firefox"
                recentBrowser.packageName.contains("brave", ignoreCase = true) -> "Brave"
                recentBrowser.packageName.contains("opera", ignoreCase = true) -> "Opera"
                else -> recentBrowser.packageName
            }

            val payload = buildMetadataOnlyPayload(
                browserPackage = recentBrowser.packageName,
                browserName = browserDisplayName,
                browserFamily = category,
                observedAtMs = now,
                dwellMs = recentBrowser.totalTimeInForeground,
                canonicalHost = "unknown.local",
                category = category,
                pageTitle = appLabel ?: browserDisplayName,
                inputContext = mapOf(
                    "field_type" to "unknown",
                    "interacted" to false,
                    "submitted" to false
                ),
                pageContext = mapOf(
                    "page_type" to "unknown",
                    "host_type" to "unknown"
                ),
                intentLabel = "unknown",
                linkSubcategory = "unknown"
            )

            Result.success(
                PmbrsArtifact(
                    id = UUID.randomUUID().toString(),
                    source = "browser",
                    payload = payload,
                    createdAtEpochMs = now,
                    provenanceMetadata = ProvenanceMetadata(
                        artifactType = "observational.phone.browser_metadata_event",
                        sourceDeviceId = getDeviceId(context)
                    )
                )
            )
        } catch (e: Exception) {
            Log.e(TAG, "Browser metadata collection failed", e)
            Result.failure(e)
        }
    }

    private fun resolveAppLabel(packageName: String): String? {
        return try {
            val pm = context.packageManager
            val appInfo = pm.getApplicationInfo(packageName, 0)
            pm.getApplicationLabel(appInfo)?.toString()
        } catch (_: PackageManager.NameNotFoundException) {
            null
        }
    }

    private fun isLikelyBrowser(packageName: String): Boolean {
        val normalized = packageName.lowercase()
        return normalized.contains("browser") ||
            normalized.contains("bromite") ||
            normalized.contains("chromium") ||
            normalized.contains("chrome") ||
            normalized.contains("firefox") ||
            normalized.contains("brave") ||
            normalized.contains("opera") ||
            normalized.contains("duckduckgo") ||
            normalized.contains("adblock")
    }

    private fun inferCategory(packageName: String): String {
        val normalized = packageName.lowercase()
        return when {
            normalized.contains("adblock") -> "privacy"
            normalized.contains("bromite") -> "privacy"
            normalized.contains("chrome") -> "search"
            normalized.contains("firefox") -> "general"
            normalized.contains("brave") -> "privacy"
            normalized.contains("duckduckgo") -> "search"
            normalized.contains("opera") -> "general"
            else -> "unknown_browser"
        }
    }
}
