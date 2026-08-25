package com.pmbrs.mobile.telemetry

import android.content.Context
import android.content.SharedPreferences

object Telemetry {
    private const val PREFS = "pmbrs_telemetry"
    private const val KEY_SYNC_RUNS = "sync_runs"
    private const val KEY_SYNC_SUCCESS = "sync_success"
    private const val KEY_SYNC_NETWORK_FAILURE = "sync_network_failure"
    private const val KEY_SYNC_SERVER_FAILURE = "sync_server_failure"
    private const val KEY_SYNC_CLIENT_FAILURE = "sync_client_failure"
    private const val KEY_SYNCED_COUNT = "synced_count"
    private const val KEY_PAYLOAD_BYTES = "payload_bytes_sent"

    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    }

    private fun increment(key: String, by: Int = 1) {
        val p = prefs ?: return
        val current = p.getInt(key, 0)
        p.edit().putInt(key, current + by).apply()
    }

    fun recordSyncStart() = increment(KEY_SYNC_RUNS)
    fun recordSyncSuccess(syncedCount: Int) {
        increment(KEY_SYNC_SUCCESS)
        if (syncedCount > 0) increment(KEY_SYNCED_COUNT, syncedCount)
    }
    fun recordPayloadBytesSent(bytes: Int) = increment(KEY_PAYLOAD_BYTES, bytes)
    fun recordNetworkFailure() = increment(KEY_SYNC_NETWORK_FAILURE)
    fun recordServerFailure() = increment(KEY_SYNC_SERVER_FAILURE)
    fun recordClientFailure() = increment(KEY_SYNC_CLIENT_FAILURE)

    fun getCounts(): Map<String, Int> {
        val p = prefs ?: return emptyMap()
        return mapOf(
            "sync_runs" to p.getInt(KEY_SYNC_RUNS, 0),
            "sync_success" to p.getInt(KEY_SYNC_SUCCESS, 0),
            "sync_network_failure" to p.getInt(KEY_SYNC_NETWORK_FAILURE, 0),
            "sync_server_failure" to p.getInt(KEY_SYNC_SERVER_FAILURE, 0),
            "sync_client_failure" to p.getInt(KEY_SYNC_CLIENT_FAILURE, 0),
            "synced_count" to p.getInt(KEY_SYNCED_COUNT, 0),
            "payload_bytes_sent" to p.getInt(KEY_PAYLOAD_BYTES, 0)
        )
    }

    fun clearCounts() {
        val p = prefs ?: return
        p.edit().clear().apply()
    }
}
