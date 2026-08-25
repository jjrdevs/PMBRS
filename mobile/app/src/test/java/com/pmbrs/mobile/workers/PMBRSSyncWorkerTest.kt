package com.pmbrs.mobile.workers

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.data.ArtifactEntity
import com.pmbrs.mobile.settings.SyncSettings
import com.pmbrs.mobile.sync.SyncResult
import com.pmbrs.mobile.sync.SyncService
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import java.util.concurrent.TimeUnit
import java.lang.reflect.Field
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [34])

@OptIn(ExperimentalCoroutinesApi::class)
class PMBRSSyncWorkerTest {
    private lateinit var server: MockWebServer
    private lateinit var context: Context
    private lateinit var database: ArtifactDatabase

    private fun resetArtifactDatabaseInstance() {
        val field: Field = ArtifactDatabase::class.java.getDeclaredField("INSTANCE")
        field.isAccessible = true
        val current = field.get(null) as? ArtifactDatabase
        current?.close()
        field.set(null, null)
    }

    @Before
    fun setUp() {
        resetArtifactDatabaseInstance()
        server = MockWebServer()
        server.start()
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences("pmbrs_sync_settings", Context.MODE_PRIVATE)
            .edit().clear().commit()
        context.deleteDatabase("pmbrs-artifacts.db")
        database = ArtifactDatabase.getInstance(context)

        val syncSettings = SyncSettings(context)
        val mockUrl = server.url("/").toString()
        syncSettings.syncBaseUrl = mockUrl
        syncSettings.fallbackSyncBaseUrl = mockUrl
        syncSettings.trustedNetworkOnly = false
    }

    @After
    fun tearDown() {
        PMBRSSyncWorker.syncServiceProvider = null
        server.shutdown()
        context.deleteDatabase("pmbrs-artifacts.db")
        resetArtifactDatabaseInstance()
    }

    @Test
    fun periodicSyncWorker_succeedsWhenServerReturnsSyncedIds() = runTest {
        val response = "{\"syncedIds\":[\"artifact-1\"],\"message\":\"OK\"}"
        server.enqueue(MockResponse().setBody(response).setResponseCode(200))

        database.artifactDao().insert(
            ArtifactEntity(
                artifactId = "artifact-1",
                source = "screen_state",
                payload = "{\"screen_on\":true}",
                createdAtEpochMs = 1000L,
                schemaVersion = "1.0",
                deviceAlias = "test-device",
                provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
                synced = false
            )
        )

        val worker = TestListenableWorkerBuilder<PMBRSSyncWorker>(context).build()
        val result = worker.startWork().get()

        assertEquals(ListenableWorker.Result.success(), result)
    }

    @Test
    fun periodicSyncWorker_retriesOnServerFailure() = runTest {
        database.artifactDao().insert(
            ArtifactEntity(
                artifactId = "artifact-1",
                source = "screen_state",
                payload = "{\"screen_on\":true}",
                createdAtEpochMs = 1000L,
                schemaVersion = "1.0",
                deviceAlias = "test-device",
                provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
                synced = false
            )
        )
        PMBRSSyncWorker.syncServiceProvider = {
            SyncService(
                ArtifactDatabase.getInstance(it),
                object : com.pmbrs.mobile.sync.SyncClient {
                    override suspend fun syncArtifacts(artifacts: List<com.pmbrs.mobile.data.ArtifactEntity>): SyncResult {
                        return SyncResult.ServerFailure(500, "Internal error")
                    }
                }
            )
        }
        val worker = TestListenableWorkerBuilder<PMBRSSyncWorker>(context).build()
        val result = worker.startWork().get()

        assertTrue(result is ListenableWorker.Result.Retry)
        val persistedSettings = SyncSettings(context)
        assertTrue(
            "Expected server failure log, got=${persistedSettings.lastSyncLog}",
            persistedSettings.lastSyncLog?.startsWith("Periodic sync server failure") == true
        )
    }

    @Test
    fun periodicSyncWorker_persistsLastSyncLogOnSuccess() = runTest {
        val response = "{\"syncedIds\":[\"artifact-1\"],\"message\":\"OK\"}"
        server.enqueue(MockResponse().setBody(response).setResponseCode(200))

        database.artifactDao().insert(
            ArtifactEntity(
                artifactId = "artifact-1",
                source = "screen_state",
                payload = "{\"screen_on\":true}",
                createdAtEpochMs = 1000L,
                schemaVersion = "1.0",
                deviceAlias = "test-device",
                provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
                synced = false
            )
        )

        val worker = TestListenableWorkerBuilder<PMBRSSyncWorker>(context).build()
        val result = worker.startWork().get()

        assertEquals(ListenableWorker.Result.success(), result)
        val syncSettings = SyncSettings(context)
        assertEquals("Periodic sync succeeded: synced 1 artifacts", syncSettings.lastSyncLog)
    }
}
