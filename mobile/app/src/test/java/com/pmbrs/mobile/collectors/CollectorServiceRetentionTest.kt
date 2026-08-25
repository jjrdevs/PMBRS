package com.pmbrs.mobile.collectors

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.data.ArtifactEntity
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [34])
class CollectorServiceRetentionTest {
    private lateinit var context: Context
    private lateinit var database: ArtifactDatabase
    private lateinit var service: CollectorService

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase("pmbrs-artifacts.db")
        database = ArtifactDatabase.getInstance(context)
        service = CollectorService(context, database, retentionDays = 1)
    }

    @After
    fun tearDown() {
        context.deleteDatabase("pmbrs-artifacts.db")
    }

    @Test
    fun cleanupOldArtifacts_removesArtifactsOlderThanRetention() {
        val now = System.currentTimeMillis()
        database.artifactDao().insert(
            ArtifactEntity(
                artifactId = "old-artifact",
                source = "screen_state",
                payload = "{}",
                createdAtEpochMs = now - 25 * 60 * 60 * 1000,
                schemaVersion = "1.0",
                deviceAlias = "test-device",
                provenanceMetadataJson = "{}",
                synced = false
            )
        )
        database.artifactDao().insert(
            ArtifactEntity(
                artifactId = "new-artifact",
                source = "screen_state",
                payload = "{}",
                createdAtEpochMs = now,
                schemaVersion = "1.0",
                deviceAlias = "test-device",
                provenanceMetadataJson = "{}",
                synced = false
            )
        )

        service.cleanupOldArtifacts()

        val remaining = database.artifactDao().getAll()
        assertEquals(1, remaining.size)
        assertEquals("new-artifact", remaining.first().artifactId)
    }
}
