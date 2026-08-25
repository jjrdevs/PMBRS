package com.pmbrs.boox

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

/** Device-side "already pushed" record (ADR-020 D5, Stage-3 Phase 1).
 *
 * Why dedup lives on-device:
 *   - The .ksync/document tree is permanent; the hub cannot tell "new page"
 *     from "old page re-pushed" once a sha256 has arrived — it just stores.
 *   - Key is noteUuid; the value carries (sha256, size, atEpochMs) so a
 *     re-render (same uuid, new sha) is re-pushed, and an unmodified note is
 *     skipped on every subsequent wake/boot/nightly-alarm pass.
 *
 * File: filesDir/push_tracking.json (0600), written atomically
 * (tmp → fsync → rename).
 *
 *   { "a1b2…32hex": { "sha256": "…64hex", "size": 123, "atEpochMs": 1755790000000 }, … }
 */
object PushTracking {

    private const val FILE_NAME = "push_tracking.json"

    // -- IO helpers -----------------------------------------------------

    private fun file(ctx: Context): File = File(ctx.filesDir, FILE_NAME)

    private fun readJson(ctx: Context): JSONObject {
        val f = file(ctx)
        return if (!f.exists()) JSONObject()
        else try { JSONObject(f.readText()) } catch (e: Exception) {
            SyncRuntime.log("push-tracking: unreadable file (starting fresh): ${e.message}")
            JSONObject()
        }
    }

    private fun writeJsonAtomic(ctx: Context, json: JSONObject) {
        val f = file(ctx)
        val tmp = File(ctx.filesDir, FILE_NAME + ".tmp")
        FileOutputStream(tmp).use { out ->
            out.write(json.toString(2).toByteArray())
            out.flush()
            out.fd.sync()
        }
        if (f.exists()) f.delete()
        if (!tmp.renameTo(f)) throw java.io.IOException("push-tracking rename failed")
    }

    // -- API ------------------------------------------------------------

    @Volatile
    private var cache: Map<String, JSONObject>? = null

    fun trackingMap(ctx: Context): Map<String, JSONObject> {
        cache?.let { return it }
        val json = readJson(ctx)
        val out = HashMap<String, JSONObject>()
        for (key in json.keys()) out[key] = json.getJSONObject(key)
        cache = out
        return out
    }

    /** True if this exact page (uuid + sha + size) is already on the hub. */
    fun isPushed(ctx: Context, page: PendingPage): Boolean {
        val rec = trackingMap(ctx)[page.noteUuid] ?: return false
        return rec.optString("sha256") == page.sha256 && rec.optLong("size", -1L) == page.sizeBytes
    }

    fun markPushed(ctx: Context, page: PendingPage) {
        val json = readJson(ctx)
        json.put(page.noteUuid, JSONObject().apply {
            put("sha256", page.sha256)
            put("size", page.sizeBytes)
            put("atEpochMs", System.currentTimeMillis())
        })
        runCatching { writeJsonAtomic(ctx, json) }.onFailure { e ->
            SyncRuntime.log("push-tracking write FAILED (will re-push next pass): ${e.message}")
        }
        cache = null  // force reload next pass
        SyncRuntime.log("push-tracking: ${page.noteUuid} sha=${page.sha256.take(12)} size=${page.sizeBytes}")
    }

    /** Forget one note (e.g. force-re-push the re-render of a specific note). */
    fun forget(ctx: Context, noteUuid: String) {
        val json = readJson(ctx)
        if (!json.has(noteUuid)) return
        json.remove(noteUuid)
        writeJsonAtomic(ctx, json)
        cache = null
    }

    fun clear(ctx: Context) {
        val f = file(ctx)
        if (f.exists()) f.delete()
        cache = null
    }
}
