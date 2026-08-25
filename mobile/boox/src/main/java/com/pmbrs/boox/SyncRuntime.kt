package com.pmbrs.boox

import android.content.Context
import android.os.Build
import android.app.AppOpsManager
import android.os.Process
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Logcat + app-private ring file. No UI on this device means logcat + the
 *  notification are the only debug surfaces; the file lets a single
 *  `adb pull` capture history even after logcat has rotated.
 */
object SyncRuntime {
    private const val TAG = "PMBRSBoox"
    private const val LOG_NAME = "pmbrs_boox_sync.log"
    private const val MAX_BYTES = 256L * 1024L

    @Volatile
    private var boundContext: Context? = null

    fun bind(context: Context) {
        boundContext = context.applicationContext
    }

    fun log(message: String) {
        Log.i(TAG, message)
        val ctx = boundContext ?: return
        try {
            val dir = File(ctx.filesDir, "logs")
            if (!dir.exists()) dir.mkdirs()
            val logFile = File(dir, LOG_NAME)
            if (logFile.length() > MAX_BYTES) {
                val raf = java.io.RandomAccessFile(logFile, "rw")
                raf.setLength(MAX_BYTES / 2)
                raf.close()
            }
            val ts = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssX", Locale.US).format(Date())
            synchronized(this) {
                logFile.appendText("$ts $message\n")
            }
        } catch (_: Exception) {
            // logging must never take the pipeline down
        }
    }
}
