package com.pmbrs.mobile.sync

import com.google.gson.Gson
import com.pmbrs.mobile.data.ArtifactEntity
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class NetworkSyncClientTest {
    private lateinit var server: MockWebServer
    private lateinit var client: NetworkSyncClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        client = NetworkSyncClient(retrofit.create(SyncApi::class.java))
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun syncArtifacts_sendsExpectedRequestAndParsesSuccess() = runTest {
        val response = SyncResponse(listOf("artifact-1"), "OK")
        server.enqueue(MockResponse().setBody(Gson().toJson(response)).setResponseCode(200))

        val artifact = ArtifactEntity(
            artifactId = "artifact-1",
            source = "screen_state",
            payload = "{\"screen_on\":true}",
            createdAtEpochMs = 1000L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
            synced = false
        )

        val result = client.syncArtifacts(listOf(artifact))
        assertEquals(SyncResult.Success(listOf("artifact-1")), result)

        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/v1/artifacts/sync", request.path)
        assertEquals("application/json; charset=UTF-8", request.getHeader("Content-Type"))

        val body = request.body.readUtf8()
        val payload = Gson().fromJson(body, SyncRequest::class.java)
        assertEquals(1, payload.artifacts.size)
        assertEquals("artifact-1", payload.artifacts[0].artifactId)
        assertEquals("test-device", payload.artifacts[0].deviceAlias)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun syncArtifacts_parsesFailureResponse() = runTest {
        server.enqueue(MockResponse().setResponseCode(500).setBody("Server error"))

        val artifact = ArtifactEntity(
            artifactId = "artifact-1",
            source = "screen_state",
            payload = "{\"screen_on\":true}",
            createdAtEpochMs = 1000L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
            synced = false
        )

        val result = client.syncArtifacts(listOf(artifact))
        assertTrue(result is SyncResult.ServerFailure)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun syncArtifacts_rejectsEmptySyncedIdsResponse() = runTest {
        val response = SyncResponse(emptyList(), "OK")
        server.enqueue(MockResponse().setResponseCode(200).setBody(Gson().toJson(response)))

        val artifact = ArtifactEntity(
            artifactId = "artifact-1",
            source = "screen_state",
            payload = "{\"screen_on\":true}",
            createdAtEpochMs = 1000L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
            synced = false
        )

        val result = client.syncArtifacts(listOf(artifact))
        assertTrue(result is SyncResult.ClientFailure)
    }

    /**
     * Regression test — PMBRSSyncWorker artifact-path NPE (2026-09-03).
     *
     * History: before the host fix (scripts/pmbrs_host_sync_ingest.py,
     * _handle_phone_sync) and before the null-safe NetworkSyncClient guard,
     * a 200 response body that omitted the "syncedIds" key — legal from
     * the host's perspective then — deserialized into SyncResponse with
     * `syncedIds == null` (Gson bypasses Kotlin constructors and defaults),
     * and `body.syncedIds.isNotEmpty()` threw
     *   `java.lang.NullPointerException: Attempt to invoke interface method
     *    'boolean java.util.Collection.isEmpty()' on a null object reference`
     * — mislabelled by the `catch` as a NetworkFailure and retried 3×
     * every run (WearableCollectorSmokeTest run, logcat 22:46:25.926).
     *
     * This test feeds the phone the exact shape of that broken response
     * and asserts it surfaces as a *classified* ClientFailure (never NPE,
     * never swallowed-as-Success, never the wrong NetworkFailure class).
     * If someone reverts the NetworkSyncClient guard the test fails; if
     * someone reverts the host fix to omit syncedIds in production, the
     * phone at least no longer NPEs (still ClientFailure, no retry storm).
     */
    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun syncArtifacts_missingSyncedIdsFieldReturnsClientFailureNotNpe() = runTest {
        // Exact shape of the pre-fix host response — "syncedIds" key absent,
        // not null, not empty. This is the shape that used to NPE the phone.
        val brokenHostBody = """{"accepted":1,"message":"OK","storedFiles":["mobile/abc.json"]}"""
        server.enqueue(MockResponse().setResponseCode(200).setBody(brokenHostBody))

        val artifact = ArtifactEntity(
            artifactId = "artifact-1",
            source = "mobile",
            payload = "{}",
            createdAtEpochMs = 1000L,
            schemaVersion = "1.0",
            deviceAlias = "test-phone",
            provenanceMetadataJson = "{}",
            synced = false
        )

        val result = client.syncArtifacts(listOf(artifact))
        // Must be a *classified* ClientFailure — never an NPE (which would
        // escape to the catch and be labelled NetworkFailure), never Success.
        assertTrue(
            "Expected ClientFailure for missing syncedIds, got: $result",
            result is SyncResult.ClientFailure
        )
        // And the message should be informative, not a bare exception string
        // from a NullPointerException (which would say "...Collection.isEmpty()...").
        val cf = result as SyncResult.ClientFailure
        assertTrue(
            "ClientFailure message should classify the shape problem: '${cf.error}'",
            cf.error.contains("syncedIds", ignoreCase = true)
        )
    }
}
