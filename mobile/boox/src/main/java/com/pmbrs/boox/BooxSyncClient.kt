package com.pmbrs.boox

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import android.util.Base64
import java.io.IOException
import java.util.concurrent.TimeUnit

/** LAN → cloud fallback HTTP client for the Boox page-upload route
 * (`POST /api/v1/boox/pages`, bearer-authed).
 *
 * Endpoint strategy (ADR-020 D2):
 *   1. If the LAN endpoint + LAN token are both configured, try LAN first
 *      (no Cloudflare hop when in the room).
 *   2. Network failure (or a 404 — route not served on that host) → fall
 *      back to the other endpoint.
 *   3. 401/403 / other 4xx are returned verbatim: a wrong token is a wrong
 *      token, and shuffling credentials across endpoints would only obscure
 *      which one was rejected.
 */
sealed class UploadResult
class UploadOk(val bytes: Int, val syncedId: String) : UploadResult()
class UploadClientError(val code: Int, val body: String) : UploadResult()
class UploadNetworkError(val reason: String) : UploadResult()

class BooxSyncClient(
    private val lanUrl: String,
    private val lanToken: String,
    private val cloudUrl: String,
    private val cloudToken: String,
) {
    /** True when a LAN endpoint + local token are both configured. */
    val lanPreferred: Boolean = lanToken.isNotBlank() && !lanToken.startsWith("CHANGE-")

    private val http: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(6, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)     // large PNG across the tunnel
            .writeTimeout(120, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)       // we own endpoint fallback
            .build()
    }

    private data class Endpoint(val label: String, val baseUrl: String, val token: String)

    fun upload(page: PendingPage): UploadResult {
        val pngB64 = Base64.encodeToString(page.file.readBytes(), Base64.NO_WRAP)
        val payload = JSONObject().apply {
            put("noteUuid", page.noteUuid)
            put("pageId", page.pageId)
            put("pageOrder", page.pageOrder)
            put("sha256", page.sha256)
            put("pngB64", pngB64)
        }

        val candidates = listOf(
            Endpoint("lan", lanUrl, lanToken),
            Endpoint("cloud", cloudUrl, cloudToken),
        ).filter { it.token.isNotBlank() && !it.token.startsWith("CHANGE-") }
        if (candidates.isEmpty()) {
            return UploadClientError(0, "no endpoint/token configured")
        }

        var lastNetwork = ""
        for (ep in candidates) {
            val request = Request.Builder()
                .url(ep.baseUrl.trimEnd('/') + "/api/v1/boox/pages")
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
                SyncRuntime.log("upload via ${ep.label} failed (network): ${e.message} — trying next endpoint")
                continue                       // network failure → next endpoint
            } catch (e: Exception) {
                lastNetwork = "${ep.label} exception: ${e::class.java.simpleName}: ${e.message}"
                continue
            }

            if (code in 200..299) {
                SyncRuntime.log("page ${page.noteUuid}/${page.pageId} uploaded via ${ep.label}")
                return UploadOk(page.sizeBytes.toInt(), "${page.noteUuid}/${page.pageId}")
            }
            if (code == 404) {
                // Route might just not be served on this endpoint (e.g. LAN host
                // running an older ingest build) — a fair reason to try the other.
                lastNetwork = "${ep.label} 404: ${body.take(150)}"
                continue
            }
            // Auth / contract errors (400/401/403/405…): surface verbatim, no swap.
            return UploadClientError(code, body.take(500))
        }
        return UploadNetworkError(lastNetwork.ifEmpty { "all endpoints failed" })
    }
}
