package com.pmbrs.mobile.wearable

import android.util.Base64
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * LAN → cloud fallback HTTP client for the wearable export-upload route
 * (`POST /api/v1/wearable/files`, bearer-authed) — the wearable twin of
 * [com.pmbrs.boox.BooxSyncClient] / ADR-021 D2.
 *
 * Endpoint strategy (ADR-020 D2, reused for wearable):
 *   1. If a LAN endpoint + token are both configured, try LAN first (no
 *      Cloudflare hop when in the room).
 *   2. Network failure (or 404 — route not served on that host, e.g. an older
 *      ingest build) → fall back to the other endpoint.
 *   3. 401/403 / other 4xx are returned verbatim: a wrong token is a wrong
 *      token, and swapping credentials across endpoints would only obscure
 *      which one was rejected.
 *
 * Each push is ONE file: `{relPath, sha256, b64}` — exactly the body contract
 * validated by `handle_wearable_file` in scripts/pmbrs_host_sync_ingest.py.
 * Batching is therefore file-by-file (ADR-021 D3.3 "batch-push"): the
 * [WearableExportCollector] drives a loop over the pending set, one push each.
 */
sealed class WearableUploadResult {
    class Ok(val bytes: Int, val relPath: String) : WearableUploadResult()
    class ClientError(val code: Int, val body: String) : WearableUploadResult()
    class NetworkError(val reason: String) : WearableUploadResult()
}

class WearableSyncClient(
    private val lanUrl: String,
    private val lanToken: String,
    private val cloudUrl: String,
    private val cloudToken: String,
) {
    private val http: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(6, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)      // 826-shard export b64'd across a tunnel
            .writeTimeout(180, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)        // we own endpoint fallback
            .build()
    }

    private data class Endpoint(val label: String, val baseUrl: String, val token: String)

    private fun endpoints(): List<Endpoint> =
        listOf(
            Endpoint("lan", lanUrl, lanToken),
            Endpoint("cloud", cloudUrl, cloudToken),
        ).filter { it.token.isNotBlank() && !it.token.startsWith("CHANGE-") }

    fun upload(exp: WearableExportFile): WearableUploadResult {
        val b64 = Base64.encodeToString(exp.file.readBytes(), Base64.NO_WRAP)
        val payload = JSONObject().apply {
            put("relPath", exp.relPath)
            put("sha256", exp.sha256)
            put("b64", b64)
        }

        val candidates = endpoints()
        if (candidates.isEmpty()) {
            return WearableUploadResult.ClientError(0, "no endpoint/token configured")
        }

        var lastNetwork = ""
        for (ep in candidates) {
            val request = Request.Builder()
                .url(ep.baseUrl.trimEnd('/') + "/api/v1/wearable/files")
                .header("Authorization", "Bearer ${ep.token}")
                .header("Content-Type", "application/json")
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .build()

            val code: Int
            val body: String
            try {
                http.newCall(request).execute().use { response ->
                    code = response.code
                    body = response.body?.string() ?: ""
                }
            } catch (e: IOException) {
                lastNetwork = "${ep.label} network error: ${e.message}"
                continue                                   // network failure → next endpoint
            } catch (e: Exception) {
                lastNetwork = "${ep.label} exception: ${e::class.java.simpleName}: ${e.message}"
                continue
            }

            if (code in 200..299) return WearableUploadResult.Ok(exp.sizeBytes.toInt(), exp.relPath)
            if (code == 404) {                               // route not on this host → try other
                lastNetwork = "${ep.label} 404: ${body.take(150)}"
                continue
            }
            return WearableUploadResult.ClientError(code, body.take(500))
        }
        return WearableUploadResult.NetworkError(lastNetwork.ifEmpty { "all endpoints failed" })
    }
}
