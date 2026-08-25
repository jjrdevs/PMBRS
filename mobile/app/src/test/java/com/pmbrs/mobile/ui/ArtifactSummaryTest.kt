package com.pmbrs.mobile.ui

import com.pmbrs.mobile.data.ArtifactEntity
import com.pmbrs.mobile.summarizeArtifactForDisplay
import org.junit.Assert.assertTrue
import org.junit.Test

class ArtifactSummaryTest {
    @Test
    fun summarizeArtifactForDisplay_includesTimestampAndBrowserMetadata() {
        val artifact = ArtifactEntity(
            id = 1,
            artifactId = "a-1",
            source = "browser_metadata",
            payload = "{\"browser_package\":\"org.adblockplus.browser\",\"browser_name\":\"Adblock Browser\",\"last_time_used_ms\":1234567890,\"observed_at_ms\":1234567890}",
            createdAtEpochMs = 1000L,
            synced = false
        )

        val summary = summarizeArtifactForDisplay(artifact)

        assertTrue(summary.contains("browser_package=org.adblockplus.browser"))
        assertTrue(summary.contains("browser_name=Adblock Browser"))
        assertTrue(summary.contains("observed_at_ms") || summary.contains("2023") || summary.contains("last_time_used_ms"))
    }
}
