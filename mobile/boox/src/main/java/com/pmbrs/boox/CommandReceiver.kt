package com.pmbrs.boox

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Local operator control surface (ADR-020 D3: this app has no screen, so
 *  adb/broadcasts ARE the control plane).
 *
 *   adb shell am broadcast -a com.pmbrs.boox.SYNC            # trigger a pass now
 *   adb shell am broadcast -a com.pmbrs.boox.RESET_TRACKING   # forget push state
 *   adb shell am broadcast -a com.pmbrs.boox.SCHEDULE         # (re)arm the daily alarm
 *
 * Intentionally a broad receiver: the service is non-exported (only this
 * receiver can wake it), and broadcasting on the device's own wifi/usb is
 * only reachable by local actors. Not a network surface.
 */
class CommandReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_SYNC    = "com.pmbrs.boox.SYNC"
        const val ACTION_RESET   = "com.pmbrs.boox.RESET_TRACKING"
        const val ACTION_SCHED   = "com.pmbrs.boox.SCHEDULE"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        SyncRuntime.bind(context)
        val action = intent?.action
        when (action) {
            ACTION_SYNC -> {
                val reason = intent.getStringExtra("reason") ?: "adb-command"
                BooxWakeAlarm.scheduleNext(context)
                Kickoff.startSyncPass(context, reason)
            }
            ACTION_RESET -> {
                val noteUuid = intent.getStringExtra("noteUuid")
                if (noteUuid.isNullOrBlank()) {
                    PushTracking.clear(context)
                    SyncRuntime.log("command: tracking cleared (all notes)")
                } else {
                    PushTracking.forget(context, noteUuid)
                    SyncRuntime.log("command: tracking cleared for $noteUuid")
                }
            }
            ACTION_SCHED -> {
                BooxWakeAlarm.scheduleNext(context)
                SyncRuntime.log("command: daily alarm (re)scheduled")
            }
            else -> SyncRuntime.log("command: unknown action $action (ignored)")
        }
    }
}
