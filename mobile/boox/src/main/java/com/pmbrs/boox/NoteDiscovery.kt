package com.pmbrs.boox

import android.content.Context
import android.os.Environment
import java.io.File
import java.security.MessageDigest

/** A pending note render to push to the hub.
 *  noteUuid is 32 hex; pageId = noteUuid for a cover render (matches the
 *  ADB collector's page id — ADR-020 D5: same page, same on-disk name
 *  across transports).
 */
data class PendingPage(
    val noteUuid: String,
    val pageId: String,
    val pageOrder: Int,
    val file: File,
    val sha256: String,
    val sizeBytes: Long,
)

/** Discovers note renders under shared external storage — identical layout
 *  to the PC-side ADB collector (src/pmbrs/ingestion/boox/adb.py):
 *    notes:   /storage/emulated/0/.ksync/document/<32-hex-uuid>/
 *    renders: /storage/emulated/0/.noteCache/thumbnail/<noteUuid>.png
 */
class NoteDiscovery(private val context: Context) {

    private val uuidRe = Regex("^[0-9a-f]{32}$")

    private val externalRoot: File
        get() = Environment.getExternalStorageDirectory()
    private val noteDocTree: File
        get() = File(externalRoot, ".ksync/document")
    private val thumbnailDir: File
        get() = File(externalRoot, ".noteCache/thumbnail")

    fun discover(): Result<List<PendingPage>> = runCatching {
        val tree = noteDocTree
        val entries: Array<File>?
        try {
            entries = tree.listFiles()
        } catch (e: SecurityException) {
            throw e.also { SyncRuntime.log("discovery permission-denied: " + it.message) }
        }
        if (entries == null) {
            // listFiles() returns null on permission denial (no exception).
            throw SecurityException(
                "cannot list " + tree + " — grant All-Files-Access: " +
                "adb shell appops set com.pmbrs.boox MANAGE_EXTERNAL_STORAGE allow"
            )
        }
        val names = entries.toList().map { it.name }.sorted()
        if (names.isEmpty()) {
            return runCatching { emptyList<PendingPage>() }
        }
        val pages = mutableListOf<PendingPage>()
        for (name in names) {
            if (!uuidRe.matches(name)) continue
            if (!File(tree, name).isDirectory) continue
            val png = File(thumbnailDir, name + ".png")
            if (!png.isFile) continue
            pages += PendingPage(
                noteUuid = name,
                pageId = name,
                pageOrder = 1,
                file = png,
                sha256 = sha256Of(png),
                sizeBytes = png.length(),
            )
        }
        SyncRuntime.log("discovered " + pages.size + " pending render(s)")
        pages
    }

    private fun sha256Of(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
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
