package com.pmbrs.mobile.data

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Test

class ArtifactModelTest {
    @Test
    fun toArtifactPayload_usesStringArtifactIdAndJsonPayload() {
        val artifact = PmbrsArtifact(
            id = "abc-123",
            source = "screen_state",
            payload = mapOf("screen_on" to true),
            createdAtEpochMs = 12345L,
            schemaVersion = "1.0",
            deviceAlias = "test-device",
            provenanceMetadata = ProvenanceMetadata(
                artifactType = "screen_state",
                sourceDeviceId = "device-123"
            )
        )

        val payload = artifact.toArtifactPayload()
        assertEquals("abc-123", payload.artifactId)
        assertEquals("screen_state", payload.source)
        assertEquals(12345L, payload.createdAtEpochMs)
        assertEquals("1.0", payload.schemaVersion)
        assertEquals("test-device", payload.deviceAlias)

        val gson = Gson()
        val payloadMap = gson.fromJson(payload.payload, Map::class.java)
        assertEquals(true, payloadMap["screen_on"])

        val provenance = gson.fromJson(payload.provenanceMetadata, ProvenanceMetadata::class.java)
        assertEquals("screen_state", provenance.artifactType)
        assertEquals("device-123", provenance.sourceDeviceId)
    }
}
