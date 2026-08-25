package com.pmbrs.boox

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

/** Central start point used by all three wake triggers: Wi-Fi event
 * (ConnectivityReceiver), daily exact alarm (WakeAlarmReceiver), boot
 * (BootCompletedReceiver), and manual `am startservice` from the host.
 */
object Kickoff {
    const val ACTION_RUN = "com.pmbrs.boox.RUN_SYNC"

    fun startSyncPass(context: Context, reason: String) {
        val intent = Intent(context, BooxSyncService::class.java).setAction(ACTION_RUN)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
            SyncRuntime.log("kickoff: sync pass requested (reason=$reason)")
        } catch (e: Exception) {
            SyncRuntime.log("kickoff FAILED (reason=$reason): ${e.message}")
        }
    }
}

/** Daily exact-alarm fallback (ADR-020 D4). One alarm per day pointing at a
 *  known local-time slot (default 02:00); when it fires we reschedule the
 *  next occurrence first, then kick a sync pass. The service exits immediately
 *  if the queue is empty, so an idle night costs one short CPU+Wi-Fi window.
 */
object BooxWakeAlarm {
    private const val REQUEST_WAKE = 0x42
    const val DEFAULT_HOUR = 2
    const val DEFAULT_MINUTE = 0

    private fun pendingIntent(context: Context): PendingIntent {
        val i = Intent(context, WakeAlarmReceiver::class.java).setAction(WakeAlarmReceiver::class.java.name)
        return PendingIntent.getBroadcast(
            context, REQUEST_WAKE, i,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    fun nextTriggerAt(hour: Int = DEFAULT_HOUR, minute: Int = DEFAULT_MINUTE): Long {
        val cal = java.util.Calendar.getInstance()
        cal.set(java.util.Calendar.HOUR_OF_DAY, hour)
        cal.set(java.util.Calendar.MINUTE, minute)
        cal.set(java.util.Calendar.SECOND, 0)
        cal.set(java.util.Calendar.MILLISECOND, 0)
        if (cal.timeInMillis <= System.currentTimeMillis()) {
            cal.add(java.util.Calendar.DAY_OF_MONTH, 1)
        }
        return cal.timeInMillis
    }

    fun scheduleNext(context: Context, hour: Int = DEFAULT_HOUR, minute: Int = DEFAULT_MINUTE) {
        val atMs = nextTriggerAt(hour, minute)
        val pi = pendingIntent(context)
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                // Exact + survives idle: the whole point of one daily wake window.
                // (set() would batch/coalesce it to "roughly 02:00"; unusable here.)
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi)
            } else {
                am.setExact(AlarmManager.RTC_WAKEUP, atMs, pi)
            }
        } catch (e: SecurityException) {
            // Missing SCHEDULE_EXACT_ALARM on 31+ — degrade, don't crash.
            am.set(AlarmManager.RTC_WAKEUP, atMs, pi)
        }
        SyncRuntime.log("daily wake alarm set for $atMs (hour=$hour min=$minute)")
    }
}

class WakeAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        SyncRuntime.bind(context)
        SyncRuntime.log("WakeAlarmReceiver fired")
        BooxWakeAlarm.scheduleNext(context)
        Kickoff.startSyncPass(context, "daily-alarm")
    }
}

/** Boot → reschedule the daily alarm (idempotent; alarmManager state can be
 *  cleared across reboots on some builds).
 */
class BootCompletedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        SyncRuntime.bind(context)
        SyncRuntime.log("BootCompletedReceiver — ensuring daily alarm exists")
        BooxWakeAlarm.scheduleNext(context)
        // Deliberately no immediate sync on boot: nothing guarantees new data
        // exists yet, and ONYX devices frequently boot from sleep with the
        // queue empty. The Wi-Fi-available receiver + daily alarm cover it.
    }

    companion object {
        fun ensureScheduled(context: Context) {
            try {
                BooxWakeAlarm.scheduleNext(context)
            } catch (e: Exception) {
                SyncRuntime.log("ensureScheduled failed: ${e.message}")
            }
        }
    }
}

/** Wi-Fi-available event → opportunistic sync. Primary wake path (ADR-020 D4):
 *  the device's own ONYX behavior + any user pick-up generates these windows
 *  for free; this receiver rides them with zero scheduling cost.
 */
class ConnectivityReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE)
            as? android.net.ConnectivityManager ?: return
        val net = cm.activeNetwork ?: return
        val caps = cm.getNetworkCapabilities(net) ?: return
        val online = caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
        if (!online) return
        SyncRuntime.bind(context)
        SyncRuntime.log("ConnectivityReceiver: network available — kicking sync")
        BooxWakeAlarm.scheduleNext(context)
        Kickoff.startSyncPass(context, "wifi-available")
    }
}
