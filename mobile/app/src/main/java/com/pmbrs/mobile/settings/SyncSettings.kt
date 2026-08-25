package com.pmbrs.mobile.settings

import android.content.Context

private const val PREFERENCES_NAME = "pmbrs_sync_settings"
private const val KEY_SYNC_BASE_URL = "sync_base_url"
private const val KEY_FALLBACK_SYNC_BASE_URL = "fallback_sync_base_url"
private const val KEY_TRUSTED_NETWORK_ONLY = "trusted_network_only"
private const val KEY_LAST_SYNC_LOG = "last_sync_log"
private const val KEY_AUTH_TOKEN = "auth_token"
private const val KEY_SYNC_INTERVAL_HOURS = "sync_interval_hours"
private const val KEY_RETENTION_DAYS = "retention_days"
private const val KEY_BROWSER_METADATA_ENABLED = "browser_metadata_enabled"
private const val KEY_GEOLOCATION_ENABLED = "geolocation_enabled"
private const val KEY_PMBRS_PSK = "pmbrs_psk"

class SyncSettings(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    var syncBaseUrl: String
        get() = preferences.getString(KEY_SYNC_BASE_URL, "http://127.0.0.1:8788/") ?: "http://127.0.0.1:8788/"
        set(value) = preferences.edit().putString(KEY_SYNC_BASE_URL, value).apply()

    var fallbackSyncBaseUrl: String
        get() = preferences.getString(KEY_FALLBACK_SYNC_BASE_URL, "https://mobile-sync.jjrdev.com/") ?: "https://mobile-sync.jjrdev.com/"
        set(value) = preferences.edit().putString(KEY_FALLBACK_SYNC_BASE_URL, value).apply()

    var trustedNetworkOnly: Boolean
        get() = preferences.getBoolean(KEY_TRUSTED_NETWORK_ONLY, true)
        set(value) = preferences.edit().putBoolean(KEY_TRUSTED_NETWORK_ONLY, value).apply()

    var syncIntervalHours: Long
        get() = preferences.getLong(KEY_SYNC_INTERVAL_HOURS, 0L)
        set(value) = preferences.edit().putLong(KEY_SYNC_INTERVAL_HOURS, value).apply()

    var retentionDays: Int
        get() = preferences.getInt(KEY_RETENTION_DAYS, 7)
        set(value) = preferences.edit().putInt(KEY_RETENTION_DAYS, value).apply()

    var browserMetadataEnabled: Boolean
        get() = preferences.getBoolean(KEY_BROWSER_METADATA_ENABLED, true)
        set(value) = preferences.edit().putBoolean(KEY_BROWSER_METADATA_ENABLED, value).apply()

    var geolocationEnabled: Boolean
        get() = preferences.getBoolean(KEY_GEOLOCATION_ENABLED, false)
        set(value) = preferences.edit().putBoolean(KEY_GEOLOCATION_ENABLED, value).apply()

    var pmbrsPsk: String?
        get() = preferences.getString(KEY_PMBRS_PSK, null)
        set(value) = preferences.edit().putString(KEY_PMBRS_PSK, value).apply()

    var lastSyncLog: String?
        get() = preferences.getString(KEY_LAST_SYNC_LOG, null)
        set(value) {
            preferences.edit().putString(KEY_LAST_SYNC_LOG, value).commit()
        }

    var authToken: String?
        get() = preferences.getString(KEY_AUTH_TOKEN, "test-token")
        set(value) = preferences.edit().putString(KEY_AUTH_TOKEN, value).apply()
}
