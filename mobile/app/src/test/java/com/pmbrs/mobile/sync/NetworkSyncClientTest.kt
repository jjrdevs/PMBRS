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
}
