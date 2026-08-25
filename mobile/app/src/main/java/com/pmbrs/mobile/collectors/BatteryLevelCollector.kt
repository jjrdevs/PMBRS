package com.pmbrs.mobile.collectors

import com.pmbrs.mobile.utils.CanonicalClock
import android.content.Context
import android.os.BatteryManager
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.ProvenanceMetadata
import java.util.UUID

class BatteryLevelCollector(private val context: Context) : BaseCollector() {
    
    suspend fun collect(): Result<PmbrsArtifact> = try {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        
        // Get current battery level (0-100)
        val batteryLevel = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        
        // Check if device is charging
        val isCharging = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS) == 
            BatteryManager.BATTERY_STATUS_CHARGING ||
            batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS) ==
            BatteryManager.BATTERY_STATUS_FULL
        
        val payload = mapOf(
            "event_type" to "battery_state",
            "battery_level_percent" to batteryLevel,
            "is_charging" to isCharging,
            "source" to "android_phone"
        )
        
        Result.success(PmbrsArtifact(
            id = UUID.randomUUID().toString(),
            source = "device_battery",
            payload = payload,
            createdAtEpochMs = CanonicalClock.now(),
            deviceAlias = null,
            provenanceMetadata = ProvenanceMetadata(
                artifactType = "battery_state",
                sourceDeviceId = getDeviceId(context)
            )
        ))
    } catch (e: Exception) {
        Result.failure(e)
    }
}
