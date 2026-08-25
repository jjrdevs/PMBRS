package com.pmbrs.mobile.settings

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class SyncSettingsTest {
    @Test
    fun defaultAndUpdate() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val s = SyncSettings(ctx)
        // default should be 15 minutes because Android PeriodicWorkRequest minimum is 15m
        assertEquals(0L, s.syncIntervalHours)
        s.syncIntervalHours = 24L
        val s2 = SyncSettings(ctx)
        assertEquals(24L, s2.syncIntervalHours)
    }

    @Test
    fun retentionDays_defaultAndUpdate() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val s = SyncSettings(ctx)
        assertEquals(7, s.retentionDays)
        s.retentionDays = 14
        val s2 = SyncSettings(ctx)
        assertEquals(14, s2.retentionDays)
    }
}
