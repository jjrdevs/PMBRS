package com.pmbrs.mobile.sync

import com.pmbrs.mobile.data.ArtifactEntity
import java.util.concurrent.atomic.AtomicInteger

interface SyncClient {
    suspend fun syncArtifacts(artifacts: List<ArtifactEntity>): SyncResult
}

sealed interface SyncResult {
    data class Success(val syncedIds: List<String>) : SyncResult
    data class NetworkFailure(val error: String) : SyncResult
    data class ServerFailure(val code: Int, val message: String) : SyncResult
    data class ClientFailure(val error: String) : SyncResult
    data class Failure(val error: String) : SyncResult
}

class InMemorySyncClient : SyncClient {
    private val attemptCounter = AtomicInteger(0)

    override suspend fun syncArtifacts(artifacts: List<ArtifactEntity>): SyncResult {
        attemptCounter.incrementAndGet()
        return if (artifacts.isNotEmpty()) {
            SyncResult.Success(artifacts.map { it.artifactId })
        } else {
            SyncResult.Failure("No artifacts to sync")
        }
    }

    fun attempts(): Int = attemptCounter.get()
}
