package com.pmbrs.mobile.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.google.gson.Gson
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [34])
class ArtifactPersistenceTest {
    private lateinit var context: Context
    private lateinit var database: ArtifactDatabase

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase("pmbrs-artifacts.db")
        database = ArtifactDatabase.getInstance(context)
    }

    @After
    fun tearDown() {
        context.deleteDatabase("pmbrs-artifacts.db")
    }

    @Test
    fun insertsAndRetrievesArtifactEntity() {
        val artifact = PmbrsArtifact(
            source = "screen_state",
            payload = mapOf("screen_on" to true),
            createdAtEpochMs = 1000L,
            deviceAlias = "test-device",
            provenanceMetadata = ProvenanceMetadata(
                artifactType = "screen_state",
                sourceDeviceId = "device-123"
            )
        )

        val rowId = database.artifactDao().insert(artifact.toEntity())
        assertEquals(1L, rowId)

        val persisted = database.artifactDao().getByArtifactId(artifact.id)
        assertNotNull(persisted)
        assertEquals(artifact.id, persisted?.artifactId)
        assertEquals("screen_state", persisted?.source)
        assertEquals("test-device", persisted?.deviceAlias)
        assertEquals(artifact.createdAtEpochMs, persisted?.createdAtEpochMs)
        assertEquals("1.0", persisted?.schemaVersion)

        val gson = Gson()
        val payloadMap = gson.fromJson(persisted?.payload, Map::class.java)
        assertEquals(true, payloadMap["screen_on"])

        val provenance = gson.fromJson(persisted?.provenanceMetadataJson, ProvenanceMetadata::class.java)
        assertEquals("screen_state", provenance.artifactType)
        assertEquals("device-123", provenance.sourceDeviceId)
    }
}
