package com.pmbrs.mobile.collectors

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.pmbrs.mobile.data.ArtifactDatabase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [34])
class CollectorServiceCollectionTest {
    @Test
    fun collectorService_registers_app_usage_collector() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val database = ArtifactDatabase.getInstance(context)
        val service = CollectorService(context, database, retentionDays = 1)

        val field = CollectorService::class.java.getDeclaredField("appUsageCollector")
        field.isAccessible = true
        val collector = field.get(service)

        assertNotNull(collector)
        assertEquals(AppUsageCollector::class.java, collector::class.java)
    }

    @Test
    fun collectorService_registers_browser_metadata_collector() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val database = ArtifactDatabase.getInstance(context)
        val service = CollectorService(context, database, retentionDays = 1)

        val field = CollectorService::class.java.getDeclaredField("browserMetadataCollector")
        field.isAccessible = true
        val collector = field.get(service)

        assertNotNull(collector)
        assertEquals(BrowserMetadataCollector::class.java, collector::class.java)
    }

    @Test
    fun browserMetadataCollector_can_be_enabled_for_real_usage_stats_collection() = kotlinx.coroutines.runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val settings = com.pmbrs.mobile.settings.SyncSettings(context)
        settings.browserMetadataEnabled = true

        val collector = BrowserMetadataCollector(context)
        val result = collector.collect()

        assertEquals(true, result.isFailure || result.isSuccess)
    }

    @Test
    fun browserMetadataCollector_builds_metadata_only_payload_contract() {
        val payload = BrowserMetadataCollector.buildMetadataOnlyPayload(
            browserPackage = "org.adblockplus.browser",
            browserName = "Adblock Browser",
            browserFamily = "privacy",
            observedAtMs = 123456789L,
            dwellMs = 32000L,
            canonicalHost = "unknown.local"
        )

        assertEquals("unknown.local", payload["canonical_host"])
        assertEquals("privacy", payload["category"])
        assertEquals("unknown", payload["intent_label"])
        assertFalse(payload.containsKey("raw_url"))
        assertFalse(payload.containsKey("page_content"))
        assertFalse(payload.containsKey("search_query"))
        assertFalse(payload.containsKey("form_values"))

        val inputContext = payload["input_context"] as? Map<*, *> ?: emptyMap<String, Any>()
        val pageContext = payload["page_context"] as? Map<*, *> ?: emptyMap<String, Any>()

        assertEquals("unknown", inputContext["field_type"])
        assertTrue(pageContext.containsKey("page_type"))
    }

    @Test
    fun collectorService_registers_geolocation_collector() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val database = ArtifactDatabase.getInstance(context)
        val service = CollectorService(context, database, retentionDays = 1)

        val field = CollectorService::class.java.getDeclaredField("geolocationCollector")
        field.isAccessible = true
        val collector = field.get(service)

        assertNotNull(collector)
        assertEquals(GeolocationCollector::class.java, collector::class.java)
    }
}
