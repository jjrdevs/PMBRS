package com.pmbrs.mobile.data

interface ArtifactDao {
    fun insert(entity: ArtifactEntity): Long
    fun insertIfMissing(entity: ArtifactEntity): Long
    fun getAll(): List<ArtifactEntity>
    fun getPending(): List<ArtifactEntity>
    fun deleteOlderThan(cutoffEpochMs: Long): Int
    fun markSynced(id: Long)
    fun markSyncedByArtifactId(artifactId: String)
    fun getByArtifactId(artifactId: String): ArtifactEntity?
    fun getByFingerprint(source: String, payload: String, createdAtEpochMs: Long): ArtifactEntity?
}
