package com.pmbrs.mobile.data

data class ArtifactEntity(
    val id: Long = 0,
    val artifactId: String,
    val source: String,
    val payload: String,
    val createdAtEpochMs: Long,
    val schemaVersion: String = "1.0",
    val deviceAlias: String? = null,
    val provenanceMetadataJson: String = "{}",
    val synced: Boolean = false
)
