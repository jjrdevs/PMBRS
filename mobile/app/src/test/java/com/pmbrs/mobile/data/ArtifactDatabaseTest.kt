package com.pmbrs.mobile.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [34])
class ArtifactDatabaseTest {
    @Test
    fun artifactEntityHoldsExpectedFields() {
        val entity = ArtifactEntity(
            artifactId = "artifact-1",
            source = "screen_state",
            payload = "{\"screen_on\":true}",
            createdAtEpochMs = 1L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadataJson = "{\"artifactType\":\"screen_state\"}",
            synced = false
        )

        assertEquals("artifact-1", entity.artifactId)
        assertEquals("screen_state", entity.source)
        assertEquals(1L, entity.createdAtEpochMs)
        assertTrue(entity.payload.contains("screen_on"))
        assertEquals(false, entity.synced)
    }

    @Test
    fun createsArtifactsTableWhenDatabaseFileExistsWithoutSchema() {
        val context: Context = RuntimeEnvironment.getApplication()
        // The companion singleton persists across test classes in a single
        // Gradle test worker (statics are not cleared between classes), so
        // any other test that touched the DB can leave a stale INSTANCE.
        // Force a clean slate so this test exercises the real create-path.
        ArtifactDatabase.resetForTests()
        context.deleteDatabase("pmbrs-artifacts.db")

        val dbFile = context.getDatabasePath("pmbrs-artifacts.db")
        SQLiteDatabase.openOrCreateDatabase(dbFile.path, null).close()

        val database = ArtifactDatabase.getInstance(context)
        val tableExists = database.readableDatabase.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'artifacts' LIMIT 1",
            null
        ).use { it.moveToFirst() }

        assertTrue(tableExists)
        assertEquals(0, database.artifactDao().getAll().size)
    }
}
