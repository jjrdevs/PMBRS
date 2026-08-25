package com.pmbrs.mobile.collectors

import com.pmbrs.mobile.utils.CanonicalClock
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.ProvenanceMetadata
import java.util.UUID

class DeviceStateCollector(private val context: Context) : BaseCollector() {

    suspend fun collect(): Result<PmbrsArtifact> = try {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val batteryLevel = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val isCharging = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS) == BatteryManager.BATTERY_STATUS_CHARGING

        val netManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val activeNetwork = netManager.activeNetwork
        val networkCapabilities = netManager.getNetworkCapabilities(activeNetwork)

        val connectionType = when {
            networkCapabilities?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true -> "wifi"
            networkCapabilities?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true -> "cellular"
            networkCapabilities?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true -> "ethernet"
            networkCapabilities == null -> "disconnected"
            else -> "unknown"
        }

        val payload = mapOf<String, Any?>(
            "event_type" to "device_state",
            "battery_level" to batteryLevel,
            "charging" to isCharging,
            "connection_type" to connectionType,
            "source" to "android_phone"
        )

        Result.success(
            PmbrsArtifact(
                id = UUID.randomUUID().toString(),
                source = "device_state",
                payload = payload.filterValues { it != null } as Map<String, Any>,
                createdAtEpochMs = CanonicalClock.now(),
                provenanceMetadata = ProvenanceMetadata(
                    artifactType = "observational.phone.device_state",
                    sourceDeviceId = getDeviceId(context)
                )
            )
        )
    } catch (e: Exception) {
        Result.failure(e)
    }
}
