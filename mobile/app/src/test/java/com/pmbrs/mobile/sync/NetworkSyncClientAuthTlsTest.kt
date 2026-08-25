package com.pmbrs.mobile.sync

import com.google.gson.Gson
import com.pmbrs.mobile.data.ArtifactEntity
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

@OptIn(ExperimentalCoroutinesApi::class)
class NetworkSyncClientAuthTlsTest {
    private lateinit var server: MockWebServer
    private lateinit var client: NetworkSyncClient

    @Before
    fun setUp() {
        server = MockWebServer()

        // Create a self-signed cert for the mock server and configure TLS
        val heldCertificate = HeldCertificate.Builder()
            .addSubjectAlternativeName("localhost")
            .build()
        val serverCertificates = HandshakeCertificates.Builder()
            .heldCertificate(heldCertificate)
            .build()
        val clientCertificates = HandshakeCertificates.Builder()
            .addTrustedCertificate(heldCertificate.certificate)
            .build()

        server.useHttps(serverCertificates.sslSocketFactory(), false)
        server.start()

        // Build an OkHttpClient trusting the server cert and adding an Authorization header
        val okClient = OkHttpClient.Builder()
            .sslSocketFactory(clientCertificates.sslSocketFactory(), clientCertificates.trustManager)
            .addInterceptor { chain ->
                val request = chain.request().newBuilder()
                    .addHeader("Authorization", "Bearer test-token")
                    .build()
                chain.proceed(request)
            }
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .client(okClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        client = NetworkSyncClient(retrofit.create(SyncApi::class.java))
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun syncArtifacts_overTls_withAuthHeader() = runTest {
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
        assertEquals("Bearer test-token", request.getHeader("Authorization"))
    }
}
