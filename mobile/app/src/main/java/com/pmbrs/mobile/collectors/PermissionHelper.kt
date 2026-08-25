package com.pmbrs.mobile.collectors

import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import java.util.Calendar

/**
 * Centralized runtime-permission checker.
 * Every collector that gates on a sensitive API should call the relevant helper
 * **before** attempting real-data collection; when denied collectors MUST emit
 * [Result.failure] — never fall back to fake / stub data.
 *
 * Permission-requirement matrix:
 *   AppUsageCollector    → PACKAGE_USAGE_STATS  (special-intent, not runtime-grantable)
 *   GeolocationCollector → ACCESS_FINE_LOCATION or ACCESS_COARSE_LOCATION
 *   HealthDataCollector  → BODY_SENSORS  (nice-to-have; degrades gracefully)
 */
object PermissionHelper {

    // -- Standard permission checks ------------------------------------------

    /** Returns `true` if a standard Android runtime permission has been granted. */
    private fun isGranted(context: Context, permission: String): Boolean =
        ContextCompat.checkSelfPermission(
            context.applicationContext,
            permission
        ) == PackageManager.PERMISSION_GRANTED


    // -- Convenience wrappers ------------------------------------------------

    /**
     * PACKAGE_USAGE_STATS requires the user to opt-in via Settings → Privacy → Usage access.
     * This function attempts to query usage stats for the last 24 hours; if it succeeds
     * the permission is available, a SecurityException means it isn't.
     */
    fun canAccessUsageStats(context: Context): Boolean {
        return try {
            val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val now = System.currentTimeMillis()
            val start = now - 86_400_000L // 24 h window
            @Suppress("DEPRECATION") // intervals deprecated in API 35+ but still functional
            usm.queryUsageStats(
                UsageStatsManager.INTERVAL_DAILY,
                start,
                now
            ).isNotEmpty()
        } catch (e: SecurityException) {
            false
        } catch (@Suppress("TooGenericExceptionCaught") e: Exception) {
            // Some OEM flavours throw other exotic exceptions
            true // treat as permitted if no explicit security denial
        }
    }

    /** ACCESS_FINE_LOCATION or coarse alternative for GPS / FusedLocationProviderClient. */
    fun canAccessFineLocation(context: Context): Boolean =
        isGranted(context, android.Manifest.permission.ACCESS_FINE_LOCATION) ||
        isGranted(context, android.Manifest.permission.ACCESS_COARSE_LOCATION)

    /** BODY_SENSORS — optional; health collector emits real but coarser telemetry when missing. */
    fun canAccessBodySensors(context: Context): Boolean =
        isGranted(context, android.Manifest.permission.BODY_SENSORS)


    // -- Failure-factory helpers ---------------------------------------------

    /** Creates a uniform "permission denied" Result for any [T]. */
    inline fun <reified T> permissionDeniedResult(permissionName: String): Result<T> {
        return Result.failure(PermissionException(
            "Permission $permissionName not granted — collector skipped (no stub data produced)"
        ))
    }

    /** Thrown when a collector refuses to emit stale / fabricated artifacts. */
    class PermissionException(message: String) : SecurityException(message)


    // -- Summary for UI ------------------------------------------------------

    /** Map of permission-name → boolean, suitable for passing straight to the Compose UI. */
    fun permissionsStatus(context: Context): Map<String, Boolean> = mapOf(
        "PACKAGE_USAGE_STATS"  to canAccessUsageStats(context),
        "ACCESS_FINE_LOCATION" to canAccessFineLocation(context),
        "BODY_SENSORS"         to canAccessBodySensors(context)
    )

}
