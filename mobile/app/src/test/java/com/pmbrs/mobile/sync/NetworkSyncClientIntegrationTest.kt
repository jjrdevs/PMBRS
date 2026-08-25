package com.pmbrs.mobile.sync

import com.google.gson.Gson
import com.pmbrs.mobile.data.ArtifactEntity
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

class NetworkSyncClientIntegrationTest {
    private lateinit var server: MockWebServer

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun makeArtifact(id: String) = ArtifactEntity(
        artifactId = id,
        source = "screen_state",
        payload = "{}",
        createdAtEpochMs = 1000L,
        schemaVersion = "1.0",
        deviceAlias = "test-device",
        provenanceMetadataJson = "{}",
        synced = false
    )

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun syncArtifacts_returnsClientFailure_onUnauthorized() = runTest {
        server.enqueue(MockResponse().setResponseCode(401).setBody("Unauthorized"))

        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        val client = NetworkSyncClient(retrofit.create(SyncApi::class.java))

        val result = client.syncArtifacts(listOf(makeArtifact("a1")))
        assertTrue(result is SyncResult.ClientFailure)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun syncArtifacts_timesOut_returnsNetworkFailure() = runTest {
        // Enqueue a response that delays the body so a short timeout will trigger
        val response = SyncResponse(listOf("a1"), "OK")
        server.enqueue(
            MockResponse()
                .setBody(Gson().toJson(response))
                .setBodyDelay(5, TimeUnit.SECONDS)
                .setResponseCode(200)
        )

        val okClient = OkHttpClient.Builder()
            .callTimeout(1, TimeUnit.SECONDS)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .client(okClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        val client = NetworkSyncClient(retrofit.create(SyncApi::class.java))

        val result = client.syncArtifacts(listOf(makeArtifact("a1")))
        assertTrue(result is SyncResult.NetworkFailure)
    }
}
