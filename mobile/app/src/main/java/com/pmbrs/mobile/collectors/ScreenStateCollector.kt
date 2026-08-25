package com.pmbrs.mobile.collectors

import com.pmbrs.mobile.utils.CanonicalClock
import android.content.Context
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.ProvenanceMetadata
import java.util.UUID

class ScreenStateCollector(private val context: Context) : BaseCollector() {
    suspend fun collect(): Result<PmbrsArtifact> {
        val payload = mapOf(
            "event_type" to "screen_state",
            "screen_on" to true,
            "source" to "android_phone"
        )

        val artifact = PmbrsArtifact(
            id = UUID.randomUUID().toString(),
            source = "screen_state",
            payload = payload,
            createdAtEpochMs = CanonicalClock.now(),
            provenanceMetadata = ProvenanceMetadata(
                artifactType = "observational.phone.screen_state",
                sourceDeviceId = getDeviceId(context)
            )
        )

        return Result.success(artifact)
    }
}
