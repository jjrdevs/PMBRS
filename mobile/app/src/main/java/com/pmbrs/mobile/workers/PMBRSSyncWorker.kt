package com.pmbrs.mobile.workers

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkerParameters
import androidx.work.WorkManager
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.network.NetworkStateHelper
import com.pmbrs.mobile.settings.SyncSettings
import com.pmbrs.mobile.sync.NetworkSyncClient
import com.pmbrs.mobile.sync.SyncResult
import com.pmbrs.mobile.sync.SyncService
import com.pmbrs.mobile.wearable.WearableExportCollector
import java.util.concurrent.TimeUnit

private const val TAG = "PMBRSSyncWorker"

class PMBRSSyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        const val TAG_WORK_REQUEST = "pmbrs_periodic_sync"
        internal var syncServiceProvider: ((Context) -> SyncService)? = null
        /** Test seam: inject the wearable collector for unit tests. Null -> Wireup. */
        internal var wearableCollector: ((Context) -> WearableExportCollector)? = null

        fun schedulePeriodicSync(context: Context, intervalHours: Long? = null): androidx.work.PeriodicWorkRequest {
            val settings = SyncSettings(context)
            val requestedInterval = intervalHours ?: settings.syncIntervalHours
            val interval = if (requestedInterval <= 0L) 15L else requestedInterval.coerceAtLeast(15L)

            val requiredNetwork = if (settings.trustedNetworkOnly) NetworkType.UNMETERED else NetworkType.CONNECTED

            val constraints = Constraints.Builder()
                .setRequiredNetworkType(requiredNetwork)
                .build()

            val workRequest = PeriodicWorkRequestBuilder<PMBRSSyncWorker>(interval, TimeUnit.HOURS)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                .addTag(TAG_WORK_REQUEST)
                .build()

            WorkManager.getInstance(context.applicationContext)
                .enqueueUniquePeriodicWork(
                    TAG_WORK_REQUEST,
                    ExistingPeriodicWorkPolicy.KEEP,
                    workRequest
                )

            return workRequest
        }

        internal suspend fun runArtifactPass(applicationContext: Context): androidx.work.ListenableWorker.Result {
            val settings = SyncSettings(applicationContext)
            com.pmbrs.mobile.telemetry.Telemetry.init(applicationContext)
            val networkStateHelper = NetworkStateHelper(applicationContext)

            if (settings.trustedNetworkOnly && !networkStateHelper.isTrustedNetworkConnected()) {
                Log.i(TAG, "Skipping periodic sync because trusted network is not available")
                return Result.success()
            }

            val selectedBase = if (networkStateHelper.isTrustedNetworkConnected()) {
                settings.syncBaseUrl
            } else {
                settings.fallbackSyncBaseUrl
            }

            val syncService = try {
                syncServiceProvider?.invoke(applicationContext) ?: SyncService(
                    ArtifactDatabase.getInstance(applicationContext),
                    NetworkSyncClient.create(selectedBase, settings.authToken)
                )
            } catch (e: IllegalArgumentException) {
                Log.e(TAG, "Invalid sync endpoint: $selectedBase", e)
                return Result.failure()
            }

            return when (val result = syncService.syncPending()) {
                is SyncResult.Success -> {
                    val message = "Periodic sync succeeded: synced ${result.syncedIds.size} artifacts"
                    Log.i(TAG, message)
                    SyncSettings(applicationContext).lastSyncLog = message
                    Result.success()
                }
                is SyncResult.Failure -> {
                    if (result.error == "No pending artifacts") {
                        val message = "Periodic sync completed with no pending artifacts"
                        Log.i(TAG, message)
                        SyncSettings(applicationContext).lastSyncLog = message
                        Result.success()
                    } else {
                        val message = "Periodic sync failure: ${result.error}"
                        Log.w(TAG, message)
                        SyncSettings(applicationContext).lastSyncLog = message
                        Result.retry()
                    }
                }
                is SyncResult.NetworkFailure -> {
                    val message = "Periodic sync network failure: ${result.error}"
                    Log.w(TAG, message)
                    SyncSettings(applicationContext).lastSyncLog = message
                    Result.retry()
                }
                is SyncResult.ServerFailure -> {
                    val message = "Periodic sync server failure: ${result.code} ${result.message}"
                    Log.w(TAG, message)
                    SyncSettings(applicationContext).lastSyncLog = message
                    if (result.code in 500..599) Result.retry() else Result.failure()
                }
                is SyncResult.ClientFailure -> {
                    val message = "Periodic sync client failure: ${result.error}"
                    Log.e(TAG, message)
                    SyncSettings(applicationContext).lastSyncLog = message
                    Result.failure()
                }
            }
        }

        internal fun runWearablePushLog(applicationContext: Context) {
            try {
                val collector = wearableCollector?.invoke(applicationContext)
                    ?: WearableExportCollector(applicationContext)
                val summary = collector.collect()
                val message = when {
                    summary.pushed == 0 && summary.failed == 0 ->
                        "Wearable push: ${summary.discovered} discovered, ${summary.pending} pending (nothing new to push)"
                    summary.failed == 0 ->
                        "Wearable push: ${summary.pushed}/${summary.pending} files pushed to hub"
                    else ->
                        "Wearable push: pushed ${summary.pushed}, failed ${summary.failed}" +
                            (if (summary.errors.isNotEmpty())
                                " first error: ${summary.errors.first().relPath} ${summary.errors.first().reason.take(80)}"
                            else "")
                }
                if (summary.failed > 0) {
                    Log.w(TAG, message)
                } else {
                    Log.i(TAG, message)
                }
                // Recorded in a SEPARATE key so the artifact pass's own
                // `lastSyncLog` assertion (kept in PMBRSSyncWorkerTest) is not
                // clobbered by the wearable pass running after it.
                SyncSettings(applicationContext).lastWearableLog = message
            } catch (e: Exception) {
                // Surface the failure in lastWearableLog so it is visible to
                // the user and to tests; log too. Do not rethrow -- the
                // artifact pass Result is the worker's contract.
                val message = "Wearable push: ${e::class.java.simpleName}: ${e.message?.take(120) ?: "unknown"}"
                Log.w(TAG, message, e)
                try {
                    SyncSettings(applicationContext).lastWearableLog = message
                } catch (e2: Exception) {
                    Log.w(TAG, "Could not record wearable push failure in settings", e2)
                }
            }
        }
    }

    override suspend fun doWork(): Result {
        // Pass 1 (artifact sync) result is the worker contract. Pass 2
        // (wearable push, ADR-021 D3) runs unconditionally after it so it
        // still fires when the artifact pass is skipped (trusted-network
        // gate) or fails, without ever altering that Result.
        val artifactResult = try {
            runArtifactPass(applicationContext)
        } catch (e: Exception) {
            Log.e(TAG, "Periodic sync worker failed", e)
            Result.retry()
        }
        runWearablePushLog(applicationContext)
        return artifactResult
    }
}
