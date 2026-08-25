package com.pmbrs.boox

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.IBinder
import android.preference.PreferenceManager
import android.util.Log
import androidx.core.app.NotificationCompat
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Persistent status line shared between the service and the host
 *  (`adb shell dumpsys package` / `dumpsys notification`). */
internal fun statusFromPrefs(ctx: Context, default: String = ""): String {
    return PreferenceManager.getDefaultSharedPreferences(ctx)
        .getString("boox_status", default) ?: default
}

internal fun statusToPrefs(ctx: Context, text: String) {
    PreferenceManager.getDefaultSharedPreferences(ctx).edit()
        .putString("boox_status", text).apply()
}

/**
 * Foreground, dataSync-typed service — the ONLY component that moves bytes.
 *
 * Lifecycle (ADR-020 D3/D4):
 *   start:  BootCompletedReceiver / ConnectivityReceiver (Wi-Fi back) /
 *           BooxWakeAlarm (daily 02:00 exact) / manual `am start-foreground-service`.
 *   work:   discover pending pages → upload one at a time → live-progress
 *           notifications + app log.
 *   stop:   self-stops the moment the queue is empty (or on a hard 4xx),
 *           releasing the wakelock immediately. Battery posture: short bursts,
 *           zero idle cost — nothing here polls a timer.
 *
 * The notification IS the UI (ADR-020 D3): no activities, no screens.
 */
class BooxSyncService : Service() {

    companion object {
        const val CHANNEL = "pmbrs_boox_sync"
        const val NOTIF = 1
        const val ACTION_RUN = "com.pmbrs.boox.RUN_SYNC"
    }

    @Volatile
    private var worker: java.util.concurrent.ExecutorService? = null

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(newBase)
        SyncRuntime.bind(newBase)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val text = statusFromPrefs(this, "starting…")
        val foregroundServiceType =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            } else {
                0
            }
        startForegroundCompat(buildNotification("PMBRS Boox sync", text), foregroundServiceType)

        if (intent?.action == ACTION_RUN) {
            val exec = java.util.concurrent.Executors.newSingleThreadExecutor { r ->
                Thread(r, "boox-sync-worker").apply { isDaemon = true }
            }
            worker = exec
            SyncRuntime.log("onStartCommand: launching sync pass")
            exec.execute { runSyncPass() }
        }
        // START_NOT_STICKY: if the OS kills us mid-pass, don't auto-blind-restart —
        // the next event (Wi-Fi, daily alarm, boot) re-triggers a fresh pass that
        // re-scans the queue from scratch (uploads are idempotent by path+sha).
        return START_NOT_STICKY
    }

    private fun startForegroundCompat(notification: Notification, serviceType: Int) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                startForeground(NOTIF, notification, serviceType)
            } else {
                startForeground(NOTIF, notification)
            }
        } catch (e: Exception) {
            SyncRuntime.log("startForeground failed: ${e.message}")
        }
    }

    private fun runSyncPass() {
        try {
            if (!hasNetwork()) {
                SyncRuntime.log("no network available — deferring to next wake event")
                notifyStatus("waiting for network")
                return
            }

            val discovery = NoteDiscovery(this)
            val discovered = discovery.discover()
            if (discovered.isFailure) {
                val msg = discovered.exceptionOrNull()?.localizedMessage ?: "discovery failed"
                SyncRuntime.log("discovery FAILED: $msg")
                notifyStatus("ERROR: $msg")
                return
            }
            val all = discovered.getOrThrow()
            // Device-side dedup (ADR-020 D5): skip pages the hub already has
            // (same uuid + sha + size). This is what makes every wake / boot /
            // nightly-alarm pass cost ~0 uploads once the queue has settled.
            // Note: PushTracking.markPushed is *only* called on a 2xx from
            // the hub — a page that fails on first try will be re-offered next pass.
            val pending = all.filter { page -> !PushTracking.isPushed(this, page) }
            val skipped = all.size - pending.size
            if (skipped > 0) SyncRuntime.log("dedup: skipping $skipped already-synced page(s)")

            if (pending.isEmpty()) {
                SyncRuntime.log("queue settled (all ${all.size} note(s) already at hub)")
                notifyStatus(if (skipped > 0) "idle — $skipped page(s) already synced"
                            else "idle — no new pages since last sync")
                return
            }

            val lanUrl = BuildConfig.BOOX_LAN_URL
            val lanTok = BuildConfig.BOOX_LAN_TOKEN
            val cloudUrl = BuildConfig.BOOX_CLOUD_URL
            val cloudTok = BuildConfig.BOOX_CLOUD_TOKEN
            if (cloudTok.isBlank() || cloudTok.startsWith("CHANGE-")) {
                val msg = "cloud token not configured (set booxCloudToken in local.properties)"
                SyncRuntime.log("ABORT: $msg")
                notifyStatus("ERROR: $msg")
                return
            }

            if (lanTok.isNullOrBlank() || lanTok.startsWith("CHANGE-")) {
                SyncRuntime.log("LAN token not set — using cloud endpoint only")
            }

            SyncRuntime.log("syncing ${pending.size} page(s) …")
            val client = BooxSyncClient(lanUrl, lanTok, cloudUrl, cloudTok)
            var succeeded = 0
            var failed = 0
            var firstError = ""
            for ((i, page) in pending.withIndex()) {
                notifyStatus("uploading ${i + 1}/${pending.size}  (${page.sizeBytes / 1024} KB)" +
                    if (client.lanPreferred) " (LAN)" else " (cloud)")
                when (val r = client.upload(page)) {
                    is UploadOk -> {
                        succeeded++
                        PushTracking.markPushed(this, page)   // only on confirmed 2xx
                        SyncRuntime.log("page ${page.noteUuid}/${page.pageId} OK (${r.bytes}B) — tracking marked")
                    }
                    is UploadClientError -> {
                        failed++
                        val desc = "HTTP ${r.code} ${r.body.take(220)}"
                        firstError = firstError.ifEmpty { desc }
                        SyncRuntime.log("page ${page.noteUuid}/${page.pageId} FAILED: $desc")
                        if (r.code == 401 || r.code == 403) break  // auth: don't retry
                    }
                    is UploadNetworkError -> {
                        failed++
                        firstError = firstError.ifEmpty { r.reason }
                        SyncRuntime.log("page ${page.noteUuid}/${page.pageId} NETWORK: ${r.reason}")
                        break  // network down: retry whole queue on next wake
                    }
                }
            }
            SyncRuntime.log("sync pass done: ok=$succeeded failed=$failed of ${pending.size}")
            notifyStatus(
                if (failed == 0) "synced $succeeded page(s) ✓"
                else "ok=$succeeded failed=$failed — ${firstError.take(70)}"
            )
        } catch (t: Throwable) {
            SyncRuntime.log("runSyncPass uncaught: ${t::class.java.name}: ${t.message}")
            notifyStatus("ERROR: ${t.message?.take(80) ?: "unknown"}")
        } finally {
            worker?.shutdownNow()
            worker = null
            stopSelf()
        }
    }

    private fun hasNetwork(): Boolean {
        val cm = getSystemService(CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    private fun buildNotification(title: String, text: String): Notification {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL,
                    "Boox → hub sync",
                    NotificationManager.IMPORTANCE_LOW, // no sound, no badge
                ).apply { description = "Status of the headless PMBRS Boox sync" }
            )
        }
        // No launcher activity by design (headless app). Tap the notification →
        // kick off a manual sync pass via the service's own RUN_SYNC action.
        val pi = PendingIntent.getService(
            this, 0,
            Intent(this, BooxSyncService::class.java).setAction(ACTION_RUN),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle(title)
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_upload)
            .setOngoing(false)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setContentIntent(pi)
            .build()
    }

    private fun notifyStatus(text: String) {
        try {
            statusToPrefs(this, text)
            val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(NOTIF, buildNotification("PMBRS Boox sync", text))
        } catch (e: Exception) {
            Log.w("BooxSyncService", "notifyStatus failed: ${e.message}")
        }
    }

    override fun onDestroy() {
        worker?.shutdownNow()
        worker = null
        super.onDestroy()
    }
}
