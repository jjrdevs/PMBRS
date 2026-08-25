package com.pmbrs.mobile.battery

import android.content.Context
import android.os.BatteryManager

/**
 * Battery-aware interval scaling for periodic artifact collection.
 *
 * PMBRS §6 Lifecycle + Efficiency (T13): when battery is critically low the
 * adapter MUST either extend or pause its periodic collection cadence so that
 * background activity does not drain a user's device beyond safe thresholds:
 *
 * - **Battery >= 20 % OR charging**                   → normal interval.
 * - **Battery < 20 % AND NOT charging**               → 3× interval slowdown.
 * - **Battery < 15 % AND NOT charging**               → pause entirely (return
 *   `Int.MAX_VALUE` so the scheduler stops).
 */
object BatteryHelper {

    // ------------------------------------------------------------------ Thresholds
    private const val LOW_BATTERY_THRESHOLD = 20   // percent — ramp-down trigger
    private const val CRITICAL_BATTERY_THRESHOLD = 15 // percent — pause trigger

    /**
     * Returns battery level (0-100) read via `BatteryManager.BATTERY_PROPERTY_CAPACITY`.
     */
    fun getBatteryLevel(context: Context): Int {
        try {
            return (context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager)
                .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        } catch (_: Exception) {
            // Fallback for emulators / devices where intent-based approach is needed.
            @Suppress("DEPRECATION")
            return android.os.Build.VERSION.SDK_INT.let { sdk ->
                if (sdk >= 21) -1 else -1 // unknown → will trigger caution path
            }
        }
    }

    /**
     * Returns true when the device is currently charging or battery status is FULL.
     */
    fun isCharging(context: Context): Boolean {
        val status = (context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS)
        return status == BatteryManager.BATTERY_STATUS_CHARGING ||
                status == BatteryManager.BATTERY_STATUS_FULL
    }

    /**
     * Calculates the **effective** collection interval in milliseconds given the
     * base request and live battery state.
     *
     * @param context       Application context (needs application scope, not Activity).
     * @param baseIntervalMs The normal periodic-interval in ms (e.g., 5-min = 300_000).
     * @return Effective interval or `Int.MAX_VALUE` to signal "pause entirely".
     */
    fun getEffectiveIntervalMs(context: Context, baseIntervalMs: Long): Long {
        val charging = isCharging(context)

        // Charging — always return normal cadence.
        if (charging) return baseIntervalMs

        val level = getBatteryLevel(context)

        // Unknown battery info — default to normal (rare; some emulators).
        if (level < 0) return baseIntervalMs

        // Critical: pause entirely when below 15 % and NOT charging.
        if (level <= CRITICAL_BATTERY_THRESHOLD) {
            android.util.Log.d("BatteryHelper", "Critical battery ($level%) — pausing collection")
            return Long.MAX_VALUE
        }

        // Low: extend interval 3× when below 20 %.
        if (level < LOW_BATTERY_THRESHOLD) {
            val extended = baseIntervalMs * 3L
            android.util.Log.d("BatteryHelper", "Low battery ($level%) — extending to ${extended} ms")
            return extended
        }

        // Normal range.
        return baseIntervalMs
    }
}
