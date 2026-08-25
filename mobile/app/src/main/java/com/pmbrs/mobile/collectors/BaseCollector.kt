package com.pmbrs.mobile.collectors

import android.content.Context
import android.provider.Settings.Secure
import java.util.UUID

/**
 * Base class for all collectors in PMBRS mobile application.
 */
abstract class BaseCollector {

    /**
     * Gets the device ID (simulated for now)
     */
    protected fun getDeviceId(context: Context): String {
        return Secure.getString(context.contentResolver, Secure.ANDROID_ID) ?: UUID.randomUUID().toString()
    }
}