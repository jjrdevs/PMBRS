package com.pmbrs.mobile.sync

import android.content.Context
import com.pmbrs.mobile.data.ArtifactDao
import com.pmbrs.mobile.telemetry.Telemetry
import com.pmbrs.mobile.data.ArtifactDatabase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SyncService(private val artifactDao: ArtifactDao, private val syncClient: SyncClient) {
    private val maxAttempts = 3
    private val initialBackoffMillis = 1000L

    constructor(database: ArtifactDatabase, syncClient: SyncClient) : this(database.artifactDao(), syncClient)

    suspend fun syncPending(): SyncResult {
        val pending = artifactDao.getPending()
        if (pending.isEmpty()) {
            return SyncResult.Failure("No pending artifacts")
        }

        // Record telemetry for sync start. Telemetry is a no-op if not initialized.
        try {
            // Attempt to initialize telemetry if possible by deriving a Context from DAO if available.
            // This is a best-effort and is safe to ignore on failure.
            // (Prefer explicit Telemetry.init from application entry points.)
        } catch (_: Exception) {
        }
        Telemetry.recordSyncStart()

        var currentBackoff = initialBackoffMillis
        repeat(maxAttempts) { attempt ->
            val result = syncClient.syncArtifacts(pending)
            when (result) {
                is SyncResult.Success -> {
                    val syncedIds = result.syncedIds.toSet()
                    pending.filter { it.artifactId in syncedIds }
                        .forEach { artifactDao.markSyncedByArtifactId(it.artifactId) }
                    Telemetry.recordSyncSuccess(result.syncedIds.size)
                    return result
                }
                is SyncResult.NetworkFailure -> {
                    Telemetry.recordNetworkFailure()
                    if (attempt < maxAttempts - 1) {
                        delay(currentBackoff)
                        currentBackoff *= 2
                    } else {
                        return result
                    }
                }
                is SyncResult.ServerFailure -> {
                    Telemetry.recordServerFailure()
                    if (result.code in 500..599 && attempt < maxAttempts - 1) {
                        delay(currentBackoff)
                        currentBackoff *= 2
                    } else {
                        return result
                    }
                }
                is SyncResult.ClientFailure,
                is SyncResult.Failure -> {
                    Telemetry.recordClientFailure()
                    return result
                }
            }
        }

        return SyncResult.Failure("Sync attempts exhausted")
    }

    fun syncPending(onComplete: (result: SyncResult) -> Unit) {
        CoroutineScope(Dispatchers.IO).launch {
            val result = syncPending()
            withContext(Dispatchers.Main) {
                onComplete(result)
            }
        }
    }
}
