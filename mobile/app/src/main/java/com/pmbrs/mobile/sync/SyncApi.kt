package com.pmbrs.mobile.sync

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

interface SyncApi {
    @POST("/api/v1/artifacts/sync")
    suspend fun syncArtifacts(@Body request: SyncRequest): Response<SyncResponse>
}

data class SyncRequest(val artifacts: List<ArtifactPayload>)

data class ArtifactPayload(
    val artifactId: String,
    val source: String,
    val payload: String,
    val createdAtEpochMs: Long,
    val schemaVersion: String,
    val deviceAlias: String?,
    val provenanceMetadata: String
)

data class SyncResponse(val syncedIds: List<String>, val message: String?)
