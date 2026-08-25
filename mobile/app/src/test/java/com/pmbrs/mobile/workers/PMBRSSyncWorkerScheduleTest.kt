package com.pmbrs.mobile.workers

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.Configuration
import androidx.work.WorkManager
import androidx.work.testing.WorkManagerTestInitHelper
import com.pmbrs.mobile.settings.SyncSettings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class PMBRSSyncWorkerScheduleTest {
    @Test
    fun schedulePeriodicSync_enqueuesWorkAndMatchesRequest() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val config = Configuration.Builder().build()
        WorkManagerTestInitHelper.initializeTestWorkManager(ctx, config)

        val settings = SyncSettings(ctx)
        settings.syncIntervalHours = 3L
        settings.trustedNetworkOnly = true

        val request = PMBRSSyncWorker.schedulePeriodicSync(ctx, null)

        val workInfos = WorkManager.getInstance(ctx).getWorkInfosByTag(PMBRSSyncWorker.TAG_WORK_REQUEST).get()
        assertTrue(workInfos.isNotEmpty())
        assertEquals(request.id, workInfos[0].id)
    }
}
