package com.pmbrs.mobile.sync

import com.google.gson.Gson
import com.pmbrs.mobile.data.ArtifactDao
import com.pmbrs.mobile.data.ArtifactEntity
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SyncServiceTest {
    private lateinit var artifactDao: FakeArtifactDao
    private lateinit var syncClient: SyncClient
    private lateinit var syncService: SyncService

    @Before
    fun setUp() {
        artifactDao = FakeArtifactDao()
        syncClient = object : SyncClient {
            override suspend fun syncArtifacts(artifacts: List<ArtifactEntity>): SyncResult {
                return SyncResult.Success(artifacts.map { it.artifactId })
            }
        }
        syncService = SyncService(artifactDao, syncClient)
    }

    @Test
    fun syncPending_marksArtifactsSyncedOnSuccess() = runTest {
        val entity = ArtifactEntity(
            artifactId = "test-artifact",
            source = "screen_state",
            payload = "{}",
            createdAtEpochMs = 1L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{}",
            synced = false
        )
        artifactDao.insert(entity)

        val result = syncService.syncPending()

        assertEquals(SyncResult.Success(listOf("test-artifact")), result)
        val retrieved = artifactDao.getByArtifactId("test-artifact")
        assertEquals(true, retrieved?.synced)
    }

    @Test
    fun syncPending_transmitsPendingArtifactsToNetworkClient() = runTest {
        val server = MockWebServer()
        server.start()
        try {
            val response = SyncResponse(listOf("test-artifact"), "OK")
            server.enqueue(MockResponse().setResponseCode(200).setBody(Gson().toJson(response)))

            val entity = ArtifactEntity(
                artifactId = "test-artifact",
                source = "screen_state",
                payload = "{}",
                createdAtEpochMs = 1L,
                schemaVersion = "1.0",
                deviceAlias = "test-device",
                provenanceMetadataJson = "{}",
                synced = false
            )
            artifactDao.insert(entity)

            val networkClient = NetworkSyncClient.create(server.url("/").toString())
            syncService = SyncService(artifactDao, networkClient)

            val result = syncService.syncPending()

            assertEquals(SyncResult.Success(listOf("test-artifact")), result)
            assertTrue(artifactDao.getByArtifactId("test-artifact")?.synced == true)

            val request = server.takeRequest()
            assertEquals("POST", request.method)
            assertEquals("/api/v1/artifacts/sync", request.path)
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun syncPending_marksOnlyAcknowledgedArtifactsOnPartialSuccess() = runTest {
        val a1 = ArtifactEntity(
            artifactId = "artifact-1",
            source = "screen_state",
            payload = "{}",
            createdAtEpochMs = 1L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{}",
            synced = false
        )
        val a2 = ArtifactEntity(
            artifactId = "artifact-2",
            source = "screen_state",
            payload = "{}",
            createdAtEpochMs = 2L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{}",
            synced = false
        )
        artifactDao.insert(a1)
        artifactDao.insert(a2)

        syncClient = object : SyncClient {
            override suspend fun syncArtifacts(artifacts: List<ArtifactEntity>): SyncResult {
                return SyncResult.Success(listOf("artifact-1"))
            }
        }
        syncService = SyncService(artifactDao, syncClient)

        val result = syncService.syncPending()

        assertEquals(SyncResult.Success(listOf("artifact-1")), result)
        assertTrue(artifactDao.getByArtifactId("artifact-1")?.synced == true)
        assertTrue(artifactDao.getByArtifactId("artifact-2")?.synced == false)
    }

    @Test
    fun syncPending_preservesPendingArtifactsWhenServerFails() = runTest {
        val entity = ArtifactEntity(
            artifactId = "test-artifact",
            source = "screen_state",
            payload = "{}",
            createdAtEpochMs = 1L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{}",
            synced = false
        )
        artifactDao.insert(entity)

        syncClient = object : SyncClient {
            override suspend fun syncArtifacts(artifacts: List<ArtifactEntity>): SyncResult {
                return SyncResult.ServerFailure(500, "Internal error")
            }
        }
        syncService = SyncService(artifactDao, syncClient)

        val result = syncService.syncPending()

        assertTrue(result is SyncResult.ServerFailure)
        assertTrue(artifactDao.getPending().size == 1)
        assertTrue(artifactDao.getByArtifactId("test-artifact")?.synced == false)
    }

    private class FakeArtifactDao : ArtifactDao {
        private val artifacts = mutableListOf<ArtifactEntity>()

        override fun insert(entity: ArtifactEntity): Long {
            artifacts.add(entity.copy(id = artifacts.size.toLong() + 1))
            return artifacts.last().id
        }

        override fun insertIfMissing(entity: ArtifactEntity): Long {
            return getByFingerprint(entity.source, entity.payload, entity.createdAtEpochMs)?.id ?: insert(entity)
        }

        override fun getAll(): List<ArtifactEntity> = artifacts.toList()

        override fun getPending(): List<ArtifactEntity> = artifacts.filter { !it.synced }

        override fun deleteOlderThan(cutoffEpochMs: Long): Int {
            val beforeSize = artifacts.size
            artifacts.removeAll { it.createdAtEpochMs < cutoffEpochMs }
            return beforeSize - artifacts.size
        }

        override fun markSynced(id: Long) {
            artifacts.replaceAll { if (it.id == id) it.copy(synced = true) else it }
        }

        override fun markSyncedByArtifactId(artifactId: String) {
            artifacts.replaceAll { if (it.artifactId == artifactId) it.copy(synced = true) else it }
        }

        override fun getByArtifactId(artifactId: String): ArtifactEntity? = artifacts.find { it.artifactId == artifactId }

        override fun getByFingerprint(source: String, payload: String, createdAtEpochMs: Long): ArtifactEntity? = artifacts.find {
            it.source == source && it.payload == payload && it.createdAtEpochMs == createdAtEpochMs
        }
    }
}
