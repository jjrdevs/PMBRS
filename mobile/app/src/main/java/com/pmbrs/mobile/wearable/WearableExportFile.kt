package com.pmbrs.mobile.wearable

import java.io.File

/**
 * One wearable export file ready to push to the hub (ADR-021 D2/D3).
 *
 * [relPath] is the canonical export-relative path the host route
 * (`POST /api/v1/wearable/files`) expects and validates against:
 *   com.samsung.shealth.tracker.heart_rate/<shard>/<file>.json
 *   com.samsung.health.hrv/<shard>/<file>.json
 *
 * The Samsung Health export nests these under a `jsons/` prefix on the
 * device; [com.pmbrs.mobile.wearable.WearableExportDiscovery] strips it and
 * remaps onto the canonical layout so the host inbox and the adb-pull copy
 * are indistinguishable downstream (parser `discover_export_files`).
 *
 * [sha256] is the hex digest the client computed over [file]; the host
 * verifies it pre-write and re-hashes post-write (ADR-020 D1 precedent).
 */
class WearableExportFile(
    val relPath: String,
    val file: File,
    val sha256: String,
    val sizeBytes: Long,
) {
    override fun toString(): String =
        "WearableExportFile(relPath=$relPath, size=$sizeBytes, sha=${sha256.take(12)}…)"
}

/**
 * Discovers wearable-relevant files under the Samsung Health export tree —
 * the on-device layout of the boox [com.pmbrs.boox.NoteDiscovery]. The
 * export lives at (scoped storage):
 *
 *   /sdcard/Download/Samsung Health/<exportTs>/
 *     jsons/com.samsung.shealth.tracker.heart_rate/<shard>/<file>.json
 *     jsons/com.samsung.health.hrv/<shard>/<file>.json
 *     files/stress.csv  (csv mirror — NOT tunnel-accepted; rides the ADB path)
 *
 * Only the two JSON data types the host tunnel route accepts are returned
 * (HR binning + HRV). Stress/sleep CSVs are deliberately excluded here —
 * the host route's `WEARABLE_ALLOWED_PREFIXES` does not list them (ADR-021 D2),
 * and the ADB orchestrator path is the canonical source for those.
 *
 * Reading under `Download/` requires MANAGE_EXTERNAL_STORAGE (declared in the
 * app manifest) or a user SAF grant; [discover] surfaces the missing grant
 * as a [Result.failure] rather than a crash.
 */
object WearableExportDiscovery {

    /** The two canonical export subpaths the client pushes. MUST stay in
     *  lockstep with `WEARABLE_ALLOWED_PREFIXES` in the host route. */
    const val HR_PREFIX = "com.samsung.shealth.tracker.heart_rate/"
    const val HRV_PREFIX = "com.samsung.health.hrv/"

    private val JSON_PREFIX = "jsons/"

    /** Root of the Samsung Health export on shared external storage. */
    fun exportRoot(): File =
        File(android.os.Environment.getExternalStorageDirectory(), "Download/Samsung Health")

    /**
     * Enumerate wearable JSON files under the most recent export dir.
     * Returns an empty list if the export is absent (nothing to push).
     * "Most recent" = the exportTs directory with the highest mtime.
     */
    fun discover(): Result<List<WearableExportFile>> = runCatching {
        val root = exportRoot()
        if (!root.isDirectory) return@runCatching emptyList()

        // Most recent export wins (ADR-021 D3.1: "most recent wins per data type").
        val exportDir: File? = root.listFiles()
            ?.filter { it.isDirectory && it.name.startsWith("samsunghealth_") }
            ?.maxByOrNull { it.lastModified() }
        if (exportDir == null) return@runCatching emptyList()

        val jsonsDir = File(exportDir, JSON_PREFIX)
        if (!jsonsDir.isDirectory) {
            // Fallback: some exports place the type dirs flat under the export.
            discoverIn(exportDir, "") + discoverIn(exportDir, JSON_PREFIX)
        } else {
            discoverIn(jsonsDir, JSON_PREFIX)
        }
    }

    private fun discoverIn(base: File, relPrefix: String): List<WearableExportFile> {
        val out = ArrayList<WearableExportFile>()
        for (dataDir in listOf(HR_PREFIX, HRV_PREFIX)) {
            val typeDir = File(base, dataDir)
            if (!typeDir.isDirectory) continue
            typeDir.walkTopDown().forEach { f ->
                if (!f.isFile || !f.name.endsWith(".json")) return@forEach
                // Build the canonical type-relative path by stripping the
                // typeDir prefix and normalizing separators to forward-slashes
                // (which the host's WEARABLE_ALLOWED_PREFIXES expect).
                val typeDirAbs = File(typeDir.absolutePath, File.separator).path
                val fAbs = f.absolutePath
                val typeRel = fAbs.removePrefix(typeDirAbs)
                    .trimStart(File.separatorChar, '/')
                    .replace(File.separatorChar, '/')
                val canonical = dataDir + typeRel
                out += WearableExportFile(
                    relPath = canonical,
                    file = f,
                    sha256 = sha256Of(f),
                    sizeBytes = f.length(),
                )
            }
        }
        // Deterministic order (shard, then filename) for stable push batch + manifest.
        return out.sortedBy { it.relPath }
    }

    private fun sha256Of(file: File): String {
        val md = java.security.MessageDigest.getInstance("SHA-256")
        file.inputStream().use { ins ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = ins.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}
