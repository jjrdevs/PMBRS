package com.pmbrs.mobile.sync

import android.net.Uri
import com.pmbrs.mobile.data.ArtifactEntity
import com.google.gson.Gson
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class NetworkSyncClient(private val api: SyncApi) : SyncClient {
    override suspend fun syncArtifacts(artifacts: List<ArtifactEntity>): SyncResult {
        return try {
            val request = SyncRequest(artifacts.map { artifact ->
                ArtifactPayload(
                    artifactId = artifact.artifactId,
                    source = artifact.source,
                    payload = artifact.payload,
                    createdAtEpochMs = artifact.createdAtEpochMs,
                    schemaVersion = artifact.schemaVersion,
                    deviceAlias = artifact.deviceAlias,
                    provenanceMetadata = artifact.provenanceMetadataJson
                )
            })
            // Record approximate payload size for telemetry (UTF-8 byte length of JSON body)
            try {
                val gson = Gson()
                val json = gson.toJson(request)
                com.pmbrs.mobile.telemetry.Telemetry.recordPayloadBytesSent(json.toByteArray(Charsets.UTF_8).size)
            } catch (_: Exception) {
            }

            val response = api.syncArtifacts(request)
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    if (body.syncedIds.isNotEmpty()) {
                        SyncResult.Success(body.syncedIds)
                    } else {
                        SyncResult.ClientFailure("Empty syncedIds in response")
                    }
                } else {
                    SyncResult.ClientFailure("Empty sync response body")
                }
            } else {
                val code = response.code()
                val message = response.message()
                if (code in 500..599) {
                    SyncResult.ServerFailure(code, message)
                } else {
                    SyncResult.ClientFailure("Sync failed: $code $message")
                }
            }
        } catch (e: Exception) {
            SyncResult.NetworkFailure("Network exception: ${e.message}")
        }
    }

    companion object {
        fun create(baseUrl: String, authToken: String? = null): NetworkSyncClient {
            val normalizedBaseUrl = normalizeSyncBaseUrl(baseUrl)
                ?: throw IllegalArgumentException("Invalid sync base URL: $baseUrl")

            val clientBuilder = OkHttpClient.Builder()
            if (!authToken.isNullOrBlank()) {
                val interceptor = Interceptor { chain ->
                    val request = chain.request().newBuilder()
                        .addHeader("Authorization", "Bearer $authToken")
                        .build()
                    chain.proceed(request)
                }
                clientBuilder.addInterceptor(interceptor)
            }

            val retrofit = Retrofit.Builder()
                .baseUrl(normalizedBaseUrl)
                .client(clientBuilder.build())
                .addConverterFactory(GsonConverterFactory.create())
                .build()
            return NetworkSyncClient(retrofit.create(SyncApi::class.java))
        }
    }
}
