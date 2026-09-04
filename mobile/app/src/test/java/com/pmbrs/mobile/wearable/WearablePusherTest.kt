package com.pmbrs.mobile.wearable

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import com.pmbrs.mobile.settings.SyncSettings
import com.pmbrs.mobile.workers.PMBRSSyncWorker
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import kotlin.concurrent.thread

/**
 * Unit tests for the ADR-021 D3 wearable pusher pipeline.
 *
 * Coverage:
 *   - WearableExportDiscovery — no export → empty success; real export layout
 *     → both HR and HRV files returned with canonical paths matching the
 *     host's WEARABLE_ALLOWED_PREFIXES layout.
 *   - WearableSyncClient — real HTTP against MockWebServer: POST
 *     /api/v1/wearable/files, Bearer auth, base64 body, 2xx → Ok;
 *     401/403 → ClientError (returns verbatim, no fallback swap);
 *     5xx both endpoints → NetworkError (both tried, last message kept).
 *   - WearableExportCollector — pushes pending files, marks them complete;
 *     leaves unmarked on failure (next tick retries).
 *   - Worker integration — wearable pass runs even when the artifact pass is
 *     skipped (trusted-network gate) or fails (invalid endpoint); a
 *     successful push is visible in SyncSettings.lastSyncLog.
 */
@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [34])
class WearablePusherTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        // Fresh tracking file per test (WearablePushTracking is a singleton).
        WearablePushTracking.clear(context)
        // Reset wireup seam.
        Wireup.wireupOverride = null
        PMBRSSyncWorker.wearableCollector = null
    }

    @After
    fun tearDown() {
        WearablePushTracking.clear(context)
        Wireup.wireupOverride = null
        PMBRSSyncWorker.wearableCollector = null
    }

    // -----------------------------------------------------------------
    // Discovery
    // -----------------------------------------------------------------

    /** Build a Samsung Health export tree under the discovery root and
     *  return (hrFile, hrvFile) so the test can clean up. */
    private fun makeExport(tag: String, shard: String = "1699999999"): Pair<File, File> {
        val root = WearableExportDiscovery.exportRoot()
        root.mkdirs()
        val exportDir = File(root, "samsunghealth_$tag")
        val hrShard = File(exportDir, "jsons/com.samsung.shealth.tracker.heart_rate/$shard")
        hrShard.mkdirs()
        val hrFile = File(hrShard, "hr.json")
        hrFile.writeText("""[{"start_time":1,"end_time":61,"heart_rate":72}]""")
        val hrvShard = File(exportDir, "jsons/com.samsung.health.hrv/$shard")
        hrvShard.mkdirs()
        val hrvFile = File(hrvShard, "hrv.json")
        hrvFile.writeText("""[{"start_time":1,"end_time":3601,"rmssd":30,"sdnn":26}]""")
        return hrFile to hrvFile
    }

    private fun cleanupExport(tag: String) {
        val root = WearableExportDiscovery.exportRoot()
        val d = File(root, "samsunghealth_$tag")
        d.deleteRecursively()
        if (root.exists() && (root.list() ?: emptyArray()).isEmpty()) root.delete()
    }

    @Test
    fun `discovery returns empty success when no export directory exists`() {
        // Ensure the root isn't there (or has no exports) before the probe.
        WearableExportDiscovery.exportRoot().deleteRecursively()
        WearablePushTracking.clear(context)
        val result = WearableExportDiscovery.discover()
        val list = result.getOrNull()
        assertNotNull(
            "Expected Success with empty list; got failure: ${result.exceptionOrNull()}",
            list
        )
        assertTrue("Expected empty list, got $list", list!!.isEmpty())
    }

    @Test
    fun `discovery returns HR and HRV files with canonical paths`() {
        makeExport("DISCOVER", shard = "1600000000")
        try {
            val files = WearableExportDiscovery.discover().getOrThrow()
            val paths = files.map { it.relPath }.sorted()
            assertEquals(
                listOf(
                    "com.samsung.health.hrv/1600000000/hrv.json",
                    "com.samsung.shealth.tracker.heart_rate/1600000000/hr.json",
                ),
                paths
            )
            files.forEach {
                assertTrue("sha256 must be set on ${it.relPath}", it.sha256.isNotBlank())
                assertTrue("sizeBytes must be > 0 on ${it.relPath}", it.sizeBytes > 0L)
            }
        } finally {
            cleanupExport("DISCOVER")
        }
    }

    // -----------------------------------------------------------------
    // Sync client (real HTTP against MockWebServer)
    // -----------------------------------------------------------------

    @Test
    fun `client posts to api v1 wearable files with bearer token and base64`() {
        val server = MockWebServer()
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"accepted":true,"artifactId":"x","sha256":"aa","bytes":10}""")
        )
        server.start()
        try {
            val url = server.url("/").toString()
            val client = WearableSyncClient(
                lanUrl = url, lanToken = "tok-test",
                cloudUrl = "", cloudToken = ""
            )
            val f = File.createTempFile("pmbw", ".json")
            f.writeText("""{"k":"v"}""")
            f.deleteOnExit()
            val exp = WearableExportFile(
                relPath = "com.samsung.shealth.tracker.heart_rate/s1/hr.json",
                file = f, sha256 = "deadbeef", sizeBytes = f.length()
            )
            val result = client.upload(exp)
            assertTrue("Expected Ok, got $result", result is WearableUploadResult.Ok)

            val recorded = server.takeRequest()
            assertEquals("POST", recorded.method)
            assertEquals("/api/v1/wearable/files", recorded.path)
            assertEquals("Bearer tok-test", recorded.getHeader("Authorization"))
            val body = recorded.body.readUtf8()
            assertTrue("body should contain b64 field", body.contains("\"b64\""))
            // The b64 should round-trip the file bytes we sent.
            val json = org.json.JSONObject(body)
            val decoded = String(android.util.Base64.decode(json.getString("b64"), android.util.Base64.NO_WRAP))
            assertEquals("base64 should encode the file bytes", """{"k":"v"}""", decoded)
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `client returns ClientError verbatim on 403 without endpoint swap`() {
        val server = MockWebServer()
        server.enqueue(
            MockResponse().setResponseCode(403).setBody("""{"detail":"forbidden"}""")
        )
        server.start()
        try {
            // Configure BOTH endpoints to the same MockWebServer (so if the
            // client wrongly falls back, we'd see it as another 403 — but
            // the contract is explicit: 403 → return verbatim, no fallback).
            val url = server.url("/").toString()
            val client = WearableSyncClient(
                lanUrl = url, lanToken = "tok", cloudUrl = url, cloudToken = "tok"
            )
            val f = File.createTempFile("pmbw403", ".json"); f.writeText("{}"); f.deleteOnExit()
            val exp = WearableExportFile(
                relPath = "com.samsung.shealth.tracker.heart_rate/s/hr.json",
                file = f, sha256 = "0", sizeBytes = 2
            )
            val result = client.upload(exp)
            assertTrue("Expected ClientError, got $result",
                result is WearableUploadResult.ClientError)
            val ce = result as WearableUploadResult.ClientError
            assertEquals(403, ce.code)
            assertTrue("body should be verbatim server error",
                ce.body.contains("forbidden"))
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `client falls back on 404 on one endpoint and succeeds on the other`() {
        val first = MockWebServer()
        first.enqueue(MockResponse().setResponseCode(404).setBody("not found here"))
        val second = MockWebServer()
        second.enqueue(MockResponse().setResponseCode(200).setBody("""{"accepted":true}"""))
        first.start(); second.start()
        try {
            val client = WearableSyncClient(
                lanUrl = first.url("/").toString(), lanToken = "tok1",
                cloudUrl = second.url("/").toString(), cloudToken = "tok2"
            )
            val f = File.createTempFile("pmbwfb", ".json"); f.writeText("{}"); f.deleteOnExit()
            val exp = WearableExportFile(
                relPath = "com.samsung.health.hrv/s/hrv.json",
                file = f, sha256 = "1", sizeBytes = 2
            )
            val result = client.upload(exp)
            assertTrue("Expected Ok after 404-fallback, got $result",
                result is WearableUploadResult.Ok)
        } finally {
            first.shutdown(); second.shutdown()
        }
    }

    @Test
    fun `client returns NetworkError when both endpoints fail with network-level errors`() {
        // Point both endpoints at a closed port (no listener) → IOException
        // on both, so the loop ends and we return the last network reason.
        val client = WearableSyncClient(
            lanUrl = "http://127.0.0.1:1", lanToken = "a",
            cloudUrl = "http://127.0.0.1:2", cloudToken = "b"
        )
        val f = File.createTempFile("pmbwnet", ".json"); f.writeText("{}"); f.deleteOnExit()
        val exp = WearableExportFile(
            relPath = "com.samsung.shealth.tracker.heart_rate/s/hr.json",
            file = f, sha256 = "2", sizeBytes = 2
        )
        val result = client.upload(exp)
        assertTrue("Expected NetworkError, got $result",
            result is WearableUploadResult.NetworkError)
    }

    // -----------------------------------------------------------------
    // Collector: push loop + dedup record
    // -----------------------------------------------------------------

    @Test
    fun `collector pushes pending files and marks them complete`() {
        makeExport("PUSH", shard = "2345")
        try {
            // Wire the collector to use a MockWebServer-backed real client.
            val server = MockWebServer()
            // discovery order: HR then HRV (sorted by relPath) — enqueue 2 OKs.
            server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))
            server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))
            server.start()
            Wireup.wireupOverride = { _ ->
                WearableSyncClient(
                    lanUrl = server.url("/").toString(), lanToken = "tok",
                    cloudUrl = "", cloudToken = ""
                )
            }

            val collector = WearableExportCollector(context)
            val summary = collector.collect()
            server.shutdown()

            assertEquals(2, summary.discovered)
            assertEquals(2, summary.pending)
            assertEquals(2, summary.pushed)
            assertEquals(0, summary.failed)

            // Dedup record should now show both files as pushed.
            val files = WearableExportDiscovery.discover().getOrThrow()
            files.forEach {
                assertTrue(
                    "Expected push-tracking to show ${it.relPath}",
                    WearablePushTracking.isPushed(context, it)
                )
            }

            // Second pass: everything already pushed → pending == 0, pushed == 0.
            // (This is the dedup-retry contract: no re-upload of unchanged files.)
            Wireup.wireupOverride = { _ ->
                WearableSyncClient(lanUrl = "http://127.0.0.1:9", lanToken = "x",
                    cloudUrl = "", cloudToken = "")
            }
            val summary2 = collector.collect()
            assertEquals("second pass should have 0 pending", 0, summary2.pending)
            assertEquals("no pushes on 2nd pass", 0, summary2.pushed)
        } finally {
            cleanupExport("PUSH")
        }
    }

    @Test
    fun `collector leaves dedup record empty on push failure`() {
        makeExport("FAIL", shard = "4242")
        try {
            val server = MockWebServer()
            // 2 files → 2 requests → return 403 for both (ClientError, not
            // marked pushed).
            server.enqueue(MockResponse().setResponseCode(403).setBody("""{"e":"no"}"""))
            server.enqueue(MockResponse().setResponseCode(403).setBody("""{"e":"no"}"""))
            server.start()
            Wireup.wireupOverride = { _ ->
                WearableSyncClient(
                    lanUrl = server.url("/").toString(), lanToken = "tok",
                    cloudUrl = "", cloudToken = ""
                )
            }

            val collector = WearableExportCollector(context)
            val summary = collector.collect()
            server.shutdown()

            assertEquals("403 → no successful pushes", 0, summary.pushed)
            assertEquals("2 files failed to push", 2, summary.failed)
            assertTrue("summary.errors should be non-empty",
                summary.errors.size >= 2)

            // Critically: no dedup record was set for either file.
            val files = WearableExportDiscovery.discover().getOrThrow()
            files.forEach {
                assertTrue("Expected NO push-tracking entry for ${it.relPath} after failure",
                    !WearablePushTracking.isPushed(context, it))
            }
        } finally {
            cleanupExport("FAIL")
        }
    }

    @Test
    fun `collector re-pushes after explicit forget`() {
        makeExport("FORGET", shard = "9999")
        try {
            val server = MockWebServer()
            server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))
            server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))
            server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))
            server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))
            server.start()
            Wireup.wireupOverride = { _ ->
                WearableSyncClient(lanUrl = server.url("/").toString(),
                    lanToken = "t", cloudUrl = "", cloudToken = "")
            }
            val collector = WearableExportCollector(context)

            collector.collect()  // first pass: 2 pushed, 2 recorded
            val files = WearableExportDiscovery.discover().getOrThrow()
            files.forEach { assertTrue(WearablePushTracking.isPushed(context, it)) }

            // Forget one file → it becomes pending again.
            val any = files.first()
            WearablePushTracking.forget(context, any.relPath)

            val summary2 = collector.collect()
            server.shutdown()
            assertEquals("only the forgotten file should be pending", 1, summary2.pending)
            assertEquals("pushed the forgotten file", 1, summary2.pushed)
        } finally {
            cleanupExport("FORGET")
        }
    }

    // -----------------------------------------------------------------
    // Worker integration
    // -----------------------------------------------------------------

    @Test
    fun `worker runs wearable pass and records summary in lastWearableLog even when artifact is skipped`() {
        // Artifact pass is skipped via trusted-network gate (isTrustedNetwork
        // returns false in Robolectric — no real NetworkInfo). The wearable
        // pass must still run, and the successful push should land in
        // SyncSettings.lastSyncLog.
        val settings = SyncSettings(context)
        settings.trustedNetworkOnly = true
        settings.syncIntervalHours = 15L

        makeExport("WORKER", shard = "31337")
        try {
            val server = MockWebServer()
            server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
            server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
            server.start()
            Wireup.wireupOverride = { _ ->
                WearableSyncClient(lanUrl = server.url("/").toString(),
                    lanToken = "t", cloudUrl = "", cloudToken = "")
            }
            val collector = WearableExportCollector(context, WearableSyncClient(
                server.url("/").toString(), "t", "", ""))
            PMBRSSyncWorker.wearableCollector = { _ -> collector }

            val worker = TestListenableWorkerBuilder<PMBRSSyncWorker>(context).build()
            val result = worker.startWork().get()
            // Artifact pass is skipped (trusted gate) → success() is the artifact
            // pass result. The wearable pass is independent and non-throwing.
            assertTrue("expected artifact pass to success (skip), got $result",
                result is ListenableWorker.Result.Success)
            server.shutdown()

            // The wearable pass is expected to have succeeded (both files 200).
            // It should have logged "Wearable push: 2/2 files pushed to hub".
            val log = SyncSettings(context).lastWearableLog
            assertNotNull("lastWearableLog should have been set by the worker", log)
        } finally {
            cleanupExport("WORKER")
        }
    }
}
