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
import java.util.concurrent.TimeUnit

private const val TAG = "PMBRSSyncWorker"

class PMBRSSyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        const val TAG_WORK_REQUEST = "pmbrs_periodic_sync"
        internal var syncServiceProvider: ((Context) -> SyncService)? = null

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
    }

    override suspend fun doWork(): Result {
        return try {
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

            when (val result = syncService.syncPending()) {
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
        } catch (e: Exception) {
            Log.e(TAG, "Periodic sync worker failed", e)
            Result.retry()
        }
    }
}
