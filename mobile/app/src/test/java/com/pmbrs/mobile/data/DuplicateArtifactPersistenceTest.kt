package com.pmbrs.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class DuplicateArtifactPersistenceTest {
    private lateinit var dao: FakeArtifactDao

    @Before
    fun setUp() {
        dao = FakeArtifactDao()
    }

    @Test
    fun insertIfMissing_skipsDuplicateArtifactsWithSameFingerprint() {
        val artifactA = ArtifactEntity(
            id = 1,
            artifactId = "artifact-1",
            source = "screen_state",
            payload = "{\"screen_on\":true}",
            createdAtEpochMs = 1000L,
            schemaVersion = "1.0",
            deviceAlias = "device-123",
            provenanceMetadataJson = "{}",
            synced = false
        )
        val duplicate = artifactA.copy(artifactId = "artifact-2")

        dao.insertIfMissing(artifactA)
        val secondId = dao.insertIfMissing(duplicate)

        assertEquals(1L, secondId)
        assertEquals(1, dao.getAll().size)
        assertEquals("artifact-1", dao.getAll().first().artifactId)
    }

    private class FakeArtifactDao : ArtifactDao {
        private val artifacts = mutableListOf<ArtifactEntity>()

        override fun insert(entity: ArtifactEntity): Long {
            val id = if (entity.id == 0L) artifacts.size.toLong() + 1 else entity.id
            artifacts.add(entity.copy(id = id))
            return id
        }

        override fun insertIfMissing(entity: ArtifactEntity): Long {
            return getByFingerprint(entity.source, entity.payload, entity.createdAtEpochMs)?.id ?: insert(entity)
        }

        override fun getAll(): List<ArtifactEntity> = artifacts.toList()

        override fun getPending(): List<ArtifactEntity> = artifacts.filter { !it.synced }

        override fun deleteOlderThan(cutoffEpochMs: Long): Int {
            val before = artifacts.size
            artifacts.removeAll { it.createdAtEpochMs < cutoffEpochMs }
            return before - artifacts.size
        }

        override fun markSynced(id: Long) {
            artifacts.replaceAll { if (it.id == id) it.copy(synced = true) else it }
        }

        override fun markSyncedByArtifactId(artifactId: String) {
            artifacts.replaceAll { if (it.artifactId == artifactId) it.copy(synced = true) else it }
        }

        override fun getByArtifactId(artifactId: String): ArtifactEntity? = artifacts.find { it.artifactId == artifactId }

        override fun getByFingerprint(source: String, payload: String, createdAtEpochMs: Long): ArtifactEntity? =
            artifacts.find { it.source == source && it.payload == payload && it.createdAtEpochMs == createdAtEpochMs }
    }
}
