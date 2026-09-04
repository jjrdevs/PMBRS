package com.pmbrs.mobile.wearable

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

/**
 * Device-side "already pushed" record for wearable export files
 * (ADR-021 D3, mirrors `com.pmbrs.boox.PushTracking`).
 *
 * Why dedup lives on-device (not hub-side): the Samsung Health export tree is
 * permanent and re-exports share the same on-disk layout, so the hub cannot
 * tell a genuine "new" file from a "old one re-pushed" once a sha256 has
 * arrived. Keyed on the canonical [WearableExportFile.relPath]; value carries
 * (sha256, size, atEpochMs). A new export (different files) is pushed; an
 * unchanged file is skipped on every subsequent pass (nightly / boot /
 * manual sync). On 409 / timeout the caller simply does NOT markPushed, so
 * the next pass retries automatically (ADR-021 D3.4).
 *
 * File: filesDir/wearable_push_tracking.json (0600), written atomically
 * (tmp → fsync → rename).
 *
 *   { "com.samsung.shealth.tracker.heart_rate/<shard>/...json": { "sha256": "…", "size": 123, "atEpochMs": 175… }, … }
 */
object WearablePushTracking {

    private const val FILE_NAME = "wearable_push_tracking.json"

    private fun file(ctx: Context): File = File(ctx.filesDir, FILE_NAME)

    private fun readJson(ctx: Context): JSONObject {
        val f = file(ctx)
        if (!f.exists()) return JSONObject()
        return try {
            JSONObject(f.readText())
        } catch (e: Exception) {
            log("wearable-push-tracking: unreadable file (starting fresh): ${e.message}")
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
        if (!tmp.renameTo(f)) throw java.io.IOException("wearable push-tracking rename failed")
    }

    private fun log(msg: String) {
        // Intentional: the wearable module deliberately does not depend on
        // boox's SyncRuntime (separate Gradle module); the app's SyncSettings
        // lastSyncLog slot is the user-visible log (see WearableExportCollector.sync).
        runCatching {
            android.util.Log.i("WearablePushTracking", msg)
        }
    }

    @Volatile
    private var cache: Map<String, JSONObject>? = null

    private fun trackingMap(ctx: Context): Map<String, JSONObject> {
        cache?.let { return it }
        val json = readJson(ctx)
        val out = HashMap<String, JSONObject>()
        for (key in json.keys()) out[key] = json.getJSONObject(key)
        cache = out
        return out
    }

    /** True iff this exact file (relPath + sha + size) is already on the hub. */
    fun isPushed(ctx: Context, exp: WearableExportFile): Boolean {
        val rec = trackingMap(ctx)[exp.relPath] ?: return false
        return rec.optString("sha256") == exp.sha256 &&
               rec.optLong("size", -1L) == exp.sizeBytes
    }

    fun markPushed(ctx: Context, exp: WearableExportFile) {
        val json = readJson(ctx)
        json.put(exp.relPath, JSONObject().apply {
            put("sha256", exp.sha256)
            put("size", exp.sizeBytes)
            put("atEpochMs", System.currentTimeMillis())
        })
        runCatching { writeJsonAtomic(ctx, json) }.onFailure { e ->
            log("wearable push-tracking write FAILED (will re-push next pass): ${e.message}")
        }
        cache = null
        log("push-tracking: ${exp.relPath} sha=${exp.sha256.take(12)} size=${exp.sizeBytes}")
    }

    /** Force re-push of one canonical file (same key, new sha). */
    fun forget(ctx: Context, relPath: String) {
        val json = readJson(ctx)
        if (!json.has(relPath)) return
        json.remove(relPath)
        writeJsonAtomic(ctx, json)
        cache = null
    }

    fun clear(ctx: Context) {
        val f = file(ctx)
        if (f.exists()) f.delete()
        cache = null
    }
}
