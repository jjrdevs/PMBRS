package com.pmbrs.mobile.collectors

import android.content.Context
import android.util.Log
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.data.ArtifactEntity
import com.pmbrs.mobile.data.ProvenanceMetadata
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.toEntity
import com.pmbrs.mobile.workers.PMBRSWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

class CollectorService(
    private val context: Context,
    private val database: ArtifactDatabase = ArtifactDatabase.getInstance(context),
    private val retentionDays: Int = 7
) {
    // Minimal, real personal telemetry scope: enabled collectors are the safe baseline plus
    // app usage when the user has granted usage access.
    private val screenCollector = ScreenStateCollector(context)
    private val deviceCollector = DeviceStateCollector(context)
    private val appUsageCollector = AppUsageCollector(context)
    private val browserMetadataCollector = BrowserMetadataCollector(context)
    private val geolocationCollector = GeolocationCollector(context)
    private val retentionHours = retentionDays * 24L

    fun captureSample(onComplete: (() -> Unit)? = null) {
        CoroutineScope(Dispatchers.IO).launch {
            val artifacts = collectAll()
            artifacts.forEach { database.artifactDao().insertIfMissing(it.toEntity()) }
            cleanupOldArtifacts(retentionHours)
            withContext(Dispatchers.Main) {
                onComplete?.invoke()
            }
        }
    }

    fun generateDiagnosticBurst(onComplete: (() -> Unit)? = null) {
        CoroutineScope(Dispatchers.IO).launch {
            val collected = collectAll()
            val fallbackArtifacts = listOfNotNull(
                ScreenStateCollector(context).collect().getOrNull(),
                DeviceStateCollector(context).collect().getOrNull()
            )
            val persisted = if (collected.isNotEmpty()) collected else fallbackArtifacts
            persisted.forEach { database.artifactDao().insertIfMissing(it.toEntity()) }
            cleanupOldArtifacts(retentionHours)
            withContext(Dispatchers.Main) {
                onComplete?.invoke()
            }
        }
    }

    fun writeDebugArtifact(onComplete: (() -> Unit)? = null): Long {
        val artifact = PmbrsArtifact(
            id = java.util.UUID.randomUUID().toString(),
            source = "debug_test",
            payload = mapOf(
                "event_type" to "debug_artifact",
                "trigger" to "manual_debug_write",
                "source" to "app_debug_ui",
                "timestamp_ms" to System.currentTimeMillis()
            ),
            createdAtEpochMs = System.currentTimeMillis(),
            provenanceMetadata = ProvenanceMetadata(
                artifactType = "debug.telemetry.test",
                sourceDeviceId = "debug-device"
            )
        )
        Log.i("CollectorService", "Writing debug artifact to database: ${artifact.id}")
        val rowId = database.artifactDao().insertIfMissing(artifact.toEntity())
        val rowCount = database.artifactDao().getAll().size
        Log.i("CollectorService", "Debug artifact persisted with rowId=$rowId, totalRows=$rowCount")
        cleanupOldArtifacts(retentionHours)
        onComplete?.invoke()
        return rowId
    }

    fun cleanupOldArtifacts(retentionHours: Long = this.retentionHours) {
        val cutoff = System.currentTimeMillis() - retentionHours * 60 * 60 * 1000
        database.artifactDao().deleteOlderThan(cutoff)
    }

    suspend fun collectAll(): List<PmbrsArtifact> = coroutineScope {
        listOf(
            async { screenCollector.collect() },
            async { deviceCollector.collect() },
            async { appUsageCollector.collect() },
            async { browserMetadataCollector.collect() },
            async { geolocationCollector.collect() }
        ).mapNotNull { deferred ->
            try {
                val result = deferred.await()
                if (result.isSuccess) {
                    result.getOrNull()
                } else {
                    Log.e("CollectorService", "collector failed", result.exceptionOrNull())
                    null
                }
            } catch (e: Throwable) {
                Log.e("CollectorService", "collector crashed", e)
                null
            }
        }
    }

    fun pendingArtifactCount(): Int = database.artifactDao().getPending().size

    fun pendingArtifacts(): List<ArtifactEntity> = database.artifactDao().getPending()

    fun localArtifactCount(): Int = database.artifactDao().getAll().size

    fun sentArtifactCount(): Int = database.artifactDao().getAll().count { it.synced }

    companion object {
        fun schedulePeriodicCollection(context: Context, intervalHours: Long = 12L) {
            val workRequest = PeriodicWorkRequestBuilder<PMBRSWorker>(intervalHours, TimeUnit.HOURS)
                .addTag(PMBRSWorker.TAG_WORK_REQUEST)
                .build()

            WorkManager.getInstance(context.applicationContext)
                .enqueueUniquePeriodicWork(
                    PMBRSWorker.TAG_WORK_REQUEST,
                    ExistingPeriodicWorkPolicy.KEEP,
                    workRequest
                )
        }
    }
}
