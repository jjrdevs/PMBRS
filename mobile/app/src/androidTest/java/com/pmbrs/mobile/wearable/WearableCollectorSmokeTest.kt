package com.pmbrs.mobile.wearable
import android.content.Context
import android.util.Base64
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.pmbrs.mobile.settings.SyncSettings
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.*
/**
 * On-device smoke test.
 *
 * Drives the exact production code path that PMBRSSyncWorker's pass-2
 * calls on every periodic run — `WearableExportCollector(ctx).collect()` —
 * against the real Samsung Health export directory on the device.
 *
 * Setup (run on the host before `am instrument -w`):
 *   1) ADB grant MANAGE_EXTERNAL_STORAGE:
 *        adb shell appops set com.pmbrs.mobile MANAGE_EXTERNAL_STORAGE allow
 *   2) Seed SyncSettings with the jjrdev-phone token + real endpoints so
 *      the test mirrors a real user's configuration. The test itself does
 *      NOT read any token from argv, files, or env — it uses SyncSettings.
 *      Seeding on the host is the same surface a normal user flow writes.
 *
 * On success, N files are uploaded to the hub at
 *   POST /api/v1/wearable/files   (mobile-sync.jjrdev.com, LAN first)
 * and appear in ~/.pmbrs-private/store/inbox/wearable/.
 *
 * This test is deliberately NOT in `src/test` (Robolectric) because the
 * whole point is to exercise the real discovery tree + real network path.
 */
@RunWith(AndroidJUnit4::class)
class WearableCollectorSmokeTest {

    @Test
    fun collectsHrAndHrvBinningFilesOnRealDevice() {
        val ctx: Context = ApplicationProvider.getApplicationContext()

        // Token is seeded into the app's SharedPreferences backing file
        // (pmbrs_sync_settings.xml) via `run-as com.pmbrs.mobile` BEFORE this
        // test runs — the exact surface a real user's in-app configuration
        // step touches, so this exercises production config reading.
        // On this device `am instrument -e` does NOT forward to
        // InstrumentationRegistry.getArguments() (verified: keys = []),
        // so file-seeding is the reliable path. The token value is
        // NEVER printed, logged, or echoed.
        val settings = SyncSettings(ctx)
        val token = settings.authToken.orEmpty()
        assertTrue(
            "SyncSettings.authToken is not a real pmbrs_ token — pass " +
            "`-e auth_token <jjrdev-phone secret>` to am instrument.",
            token.startsWith("pmbrs_") && token.length > 40
        )

        // Fresh-run semantics are owned by the *runner*: it deletes
        // files/wearable_push_tracking.json before `am instrument` when it
        // wants a full re-push. We do NOT clear() here — that would defeat the
        // push-tracking manifest's job of making a timed-out run resume-able
        // (859 re-pushes of the same relPath on a flaky tunnel is wasteful).

        val collector = WearableExportCollector(ctx)
        val summary = collector.collect()

        println("")
        println("=== WearableCollectorSmokeTest Summary ===")
        println("discovered = ${summary.discovered}")
        println("pending    = ${summary.pending}")
        println("pushed     = ${summary.pushed}")
        println("failed     = ${summary.failed}")
        summary.errors.take(8).forEach { err ->
            println("  ERROR: ${err.relPath.take(90)} -> ${err.reason.take(160)}")
        }
        println("==========================================")
        println("")

        // Expect 826 HR + 33 HRV = 859 files on the current export.
        // Tolerate small drift (±10) for partial exports / Samsung renaming.
        assertTrue(
            "Discovered fewer than 830 wearable files — either the export tree " +
            "changed or MANAGE_EXTERNAL_STORAGE was not granted. " +
            "Actual: ${summary.discovered}",
            summary.discovered >= 830
        )
        assertTrue(
            "All ${summary.pending} pending files must have been pushed. " +
            "failed=${summary.failed}; errors=${summary.errors}",
            summary.pushed == summary.pending
        )
        assertEquals("No client/NetworkError entries in the Summary", 0, summary.errors.size)

        // Spot-check that the device-side dedup manifest actually captured
        // the push (so we know the tracking is written, not just returned).
        val all = WearableExportDiscovery.discover().getOrDefault(emptyList())
        assertTrue(
            "WearablePushTracking.markPushed did not persist — device manifest is empty after ${summary.pushed} pushes",
            all.any { WearablePushTracking.isPushed(ctx, it) }
        )
    }
}
