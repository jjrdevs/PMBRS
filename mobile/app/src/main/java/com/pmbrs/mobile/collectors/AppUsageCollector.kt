package com.pmbrs.mobile.collectors

import com.pmbrs.mobile.utils.CanonicalClock
import android.app.usage.UsageStatsManager
import android.content.Context
import androidx.annotation.RequiresApi
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.ProvenanceMetadata
import java.util.UUID

/**
 * Collects **real** foreground app usage via UsageStatsManager.
 *
 * Phase 3 — stub gating: if PACKAGE_USAGE_STATS permission not available,
 * returns Result.failure immediately. Never fabricates fake events.
 */
class AppUsageCollector(private val context: Context) : BaseCollector() {

    companion object {
        private const val TAG = "AppUsageCollector"
    }

    @RequiresApi(android.os.Build.VERSION_CODES.LOLLIPOP)
    suspend fun collect(): Result<PmbrsArtifact> {
        return try {
            if (!PermissionHelper.canAccessUsageStats(context)) {
                android.util.Log.d(TAG, "PACKAGE_USAGE_STATS not granted — skipping")
                return PermissionHelper.permissionDeniedResult<PmbrsArtifact>("PACKAGE_USAGE_STATS")
            }

            val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val now = CanonicalClock.now()
            val windowMs = 120_000L

            @Suppress("DEPRECATION")
            val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - windowMs, now)
                ?: kotlin.run {
                    android.util.Log.w(TAG, "UsageStats query returned null")
                    return Result.failure(Exception("UsageStats query returned null"))
                }

            val recent = stats.maxByOrNull { it.lastTimeUsed }
                ?: kotlin.run {
                    android.util.Log.d(TAG, "No foreground apps in the last ${windowMs} ms")
                    return Result.failure(Exception("No recent app usage events found"))
                }

            val pkgm = context.packageManager
            val label = try {
                pkgm.getApplicationLabel(pkgm.getApplicationInfo(recent.packageName, 0)) as String?
            } catch (_: Exception) {
                null
            }

            val isSystemApp = recent.packageName.startsWith("com.android.") ||
                    recent.packageName == "android" ||
                    try {
                        pkgm.getApplicationInfo(recent.packageName, 0).flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM != 0
                    } catch (_: Exception) {
                        false
                    }

            val payload = mapOf<String, Any?>(
                "package_name" to recent.packageName,
                "event" to "usage_stat",
                "app_name" to (label ?: recent.packageName),
                "duration_ms" to recent.totalTimeInForeground,
                "is_system_app" to isSystemApp,
                "last_time_used_ms" to recent.lastTimeUsed
            )

            Result.success(
                PmbrsArtifact(
                    id = UUID.randomUUID().toString(),
                    source = "app_usage",
                    payload = payload.filterValues { it != null } as Map<String, Any>,
                    createdAtEpochMs = now,
                    provenanceMetadata = ProvenanceMetadata(
                        artifactType = "observational.phone.app_usage_event",
                        sourceDeviceId = getDeviceId(context)
                    )
                )
            )
        } catch (e: Exception) {
            if (e is PermissionHelper.PermissionException) throw e // re-throw permission failures unchanged
            android.util.Log.e(TAG, "App usage collection failed", e)
            Result.failure(e)
        }
    }
}
