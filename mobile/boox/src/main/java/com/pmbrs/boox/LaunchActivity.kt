package com.pmbrs.boox

import android.app.Activity
import android.os.Bundle

/** One-shot bootstrap launcher.
 *
 * Why this exists:
 *   Fresh `adb install` puts a package in the AOSP "stopped / notLaunched"
 *   state. While stopped, the app *cannot* receive implicit broadcasts or
 *   have background services started — the ActivityManager just logs
 *   "Unable to start service … not found" and drops the intent, with no
 *   crash. This is the only standard AOSP way to clear the flag for a
 *   non-launcher app: one explicit foreground activity start.
 *
 * What it does:
 *   1. BooxApp.onCreate() runs → seeds the daily exact-alarm (idempotent).
 *   2. Immediately schedules a first sync pass (Wi-Fi is up on the device;
 *      if it's not, Kickoff defers to the next Wi-Fi event).
 *   3. finish() — no UI, no toast.
 *
 * Trigger once after install:
 *   adb shell am start -n com.pmbrs.boox/.LaunchActivity
 */
class LaunchActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        BooxWakeAlarm.scheduleNext(this)
        Kickoff.startSyncPass(this, "launcher-bootstrap")
        finish()
    }
}
