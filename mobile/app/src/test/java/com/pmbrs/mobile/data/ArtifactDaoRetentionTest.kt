package com.pmbrs.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class ArtifactDaoRetentionTest {
    private lateinit var dao: FakeArtifactDao

    @Before
    fun setUp() {
        dao = FakeArtifactDao()
    }

    @Test
    fun deleteOlderThan_removesExpiredArtifacts() {
        val oldArtifact = ArtifactEntity(
            id = 1,
            artifactId = "old-artifact",
            source = "screen_state",
            payload = "{}",
            createdAtEpochMs = 1000L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{}",
            synced = false
        )
        val newArtifact = ArtifactEntity(
            id = 2,
            artifactId = "new-artifact",
            source = "screen_state",
            payload = "{}",
            createdAtEpochMs = 2000L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{}",
            synced = false
        )

        dao.insert(oldArtifact)
        dao.insert(newArtifact)

        val deleted = dao.deleteOlderThan(1500L)

        assertEquals(1, deleted)
        assertEquals(1, dao.getAll().size)
        assertEquals("new-artifact", dao.getAll().first().artifactId)
    }

    private class FakeArtifactDao : ArtifactDao {
        private val artifacts = mutableListOf<ArtifactEntity>()

        override fun insert(entity: ArtifactEntity): Long {
            artifacts.add(entity)
            return entity.id
        }

        override fun insertIfMissing(entity: ArtifactEntity): Long {
            val existing = getByFingerprint(entity.source, entity.payload, entity.createdAtEpochMs)
            return existing?.id ?: insert(entity)
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
