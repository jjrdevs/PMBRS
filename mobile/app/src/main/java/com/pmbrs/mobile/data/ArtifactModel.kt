package com.pmbrs.mobile.data

import com.google.gson.Gson
import java.util.UUID

/**
 * PMBRS Artifact - structured data model for mobile telemetry
 */
data class PmbrsArtifact(
    val id: String = UUID.randomUUID().toString(),
    val source: String,
    val payload: Map<String, Any>,
    val createdAtEpochMs: Long,
    val schemaVersion: String = "1.0",
    val deviceAlias: String? = null,
    val provenanceMetadata: ProvenanceMetadata
)

data class ProvenanceMetadata(
    val artifactType: String,
    val sourceDeviceId: String,
    val collectionTool: String = "pmbrs-mobile-collector",
    val timestamp: Long = System.currentTimeMillis(),
    val schemaVersion: String = "1.0"
)

/**
 * Convert PmbrsArtifact to UI/API payload via Gson serialization.
 */
fun PmbrsArtifact.toArtifactPayload(): ArtifactPayload {
    val gson = Gson()
    return ArtifactPayload(
        artifactId = this.id,
        source = this.source,
        payload = gson.toJson(this.payload),
        createdAtEpochMs = this.createdAtEpochMs,
        schemaVersion = this.schemaVersion,
        deviceAlias = this.deviceAlias,
        provenanceMetadata = gson.toJson(this.provenanceMetadata)
    )
}

/**
 * Convert PmbrsArtifact to the DB entity stored via ArtifactDatabase.
 */
fun PmbrsArtifact.toEntity(): ArtifactEntity {
    val gson = Gson()
    return ArtifactEntity(
        id = 0,            // auto-generated row ID when inserted
        artifactId = this.id,
        source = this.source,
        payload = gson.toJson(this.payload),
        createdAtEpochMs = this.createdAtEpochMs,
        schemaVersion = this.schemaVersion,
        deviceAlias = this.deviceAlias,
        provenanceMetadataJson = gson.toJson(this.provenanceMetadata),
        synced = false
    )
}

/**
 * Data class for API communication - matches the current SyncApi interface
 */
data class ArtifactPayload(
    val artifactId: String,
    val source: String,
    val payload: String,
    val createdAtEpochMs: Long,
    val schemaVersion: String,
    val deviceAlias: String?,
    val provenanceMetadata: String
)