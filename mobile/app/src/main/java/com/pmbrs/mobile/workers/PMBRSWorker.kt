package com.pmbrs.mobile.workers

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.pmbrs.mobile.collectors.CollectorService
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.data.toEntity
import com.pmbrs.mobile.settings.SyncSettings

private const val TAG = "PMBRSWorker"

/**
 * WorkManager worker responsible for periodic PMBRS data collection.
 *
 * Replaces the raw `while(true) { delay() }` loop in [CollectorService] with
 * Android's recommended WorkManager scheduling surface. This means:
 * - Respects Doze / App Standby modes automatically.
 * Survives process death and device reboots (when constrained accordingly).
 */
class PMBRSWorker(
    appContext: Context,
    private val workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    // Exposed so [CollectorService] can override at runtime via WorkSpec.
    companion object {
        const val TAG_WORK_REQUEST = "pmbrs_periodic_collection"
    }

    private val database = ArtifactDatabase.getInstance(applicationContext)

    override suspend fun doWork(): Result {
        return try {
            val retentionDays = SyncSettings(applicationContext).retentionDays
            val collectorService = CollectorService(applicationContext, database, retentionDays)
            val artifacts = collectorService.collectAll()

            // Persist every successful artifact to DB.
            for (artifact in artifacts) {
                database.artifactDao().insertIfMissing(artifact.toEntity())
            }
            database.artifactDao().deleteOlderThan(System.currentTimeMillis() - retentionDays * 60L * 60L * 1000L)

            if (artifacts.isNotEmpty()) {
                Log.d(TAG, "Collected and persisted ${artifacts.size} artifacts")
            } else {
                Log.v(TAG, "Collection cycle completed — 0 new artifacts")
            }
            Result.success()
        } catch (e: Exception) {
            // Do not silently fail; let WorkManager handle retries.
            Log.e(TAG, "PMBRSWorker collection failed", e)
            Result.retry()
        }
    }
}
