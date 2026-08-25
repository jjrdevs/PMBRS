package com.pmbrs.mobile.collectors

import com.pmbrs.mobile.utils.CanonicalClock
import android.content.Context
import android.location.LocationManager
import android.util.Log
import com.pmbrs.mobile.data.PmbrsArtifact
import com.pmbrs.mobile.data.ProvenanceMetadata
import com.pmbrs.mobile.settings.SyncSettings
import java.util.Locale
import java.util.UUID
import kotlin.math.roundToInt

class GeolocationCollector(private val context: Context) : BaseCollector() {

    companion object {
        private const val TAG = "GeolocationCollector"
        private const val LAT_LON_PRECISION = 2 // ~1.1 km resolution
    }

    suspend fun collect(): Result<PmbrsArtifact> {
        val settings = SyncSettings(context)
        if (!settings.geolocationEnabled) {
            Log.d(TAG, "Coarse geolocation is disabled by settings")
            return Result.failure(
                IllegalStateException("Coarse geolocation is disabled. This signal is opt-in and uses coarse place-level buckets.")
            )
        }

        if (!PermissionHelper.canAccessFineLocation(context)) {
            Log.d(TAG, "ACCESS_FINE_LOCATION not granted - skipping")
            return PermissionHelper.permissionDeniedResult("ACCESS_FINE_LOCATION or ACCESS_COARSE_LOCATION")
        }

        try {
            val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            val location = providers.asSequence()
                .mapNotNull { provider ->
                    try {
                        locationManager.getLastKnownLocation(provider)
                    } catch (_: SecurityException) {
                        null
                    }
                }
                .firstOrNull()

            if (location == null) {
                Log.w(TAG, "No recent location available - returning failure instead of stub data")
                return Result.failure(Exception("No recent cached location available"))
            }

            val coarseLat = roundToPrecision(location.latitude, LAT_LON_PRECISION)
            val coarseLon = roundToPrecision(location.longitude, LAT_LON_PRECISION)
            val accuracyMeters = location.accuracy.roundToInt().coerceAtLeast(1)
            val timestampMs = CanonicalClock.now()

            val payload = mapOf<String, Any?>(
                "latitude_coarse" to coarseLat,
                "longitude_coarse" to coarseLon,
                "latitude_raw" to null,
                "longitude_raw" to null,
                "geohash_bucket" to "lat${String.format(Locale.US, "%.2f", coarseLat)}-lon${String.format(Locale.US, "%.2f", coarseLon)}",
                "accuracy_meters" to accuracyMeters,
                "provider" to (location.provider ?: "fused"),
                "timestamp_ms" to location.time,
                "coarsening_precision_degrees" to LAT_LON_PRECISION,
                "coarsening_note" to "Coarse bucket only; exact movement trace is not collected by default"
            )

            val safePayload = payload.filterValues { it != null }.mapValues { (_, value) -> value!! }

            return Result.success(
                PmbrsArtifact(
                    id = UUID.randomUUID().toString(),
                    source = "geolocation",
                    payload = safePayload,
                    createdAtEpochMs = timestampMs,
                    deviceAlias = null,
                    provenanceMetadata = ProvenanceMetadata(
                        artifactType = "observational.phone.geolocation_event",
                        sourceDeviceId = getDeviceId(context)
                    )
                )
            )
        } catch (e: Exception) {
            if (e is PermissionHelper.PermissionException) throw e
            Log.e(TAG, "Geolocation collection failed", e)
            return Result.failure(e)
        }
    }

    private fun roundToPrecision(value: Double, decimals: Int): Double {
        val factor = Math.pow(10.0, decimals.toDouble())
        return kotlin.math.round(value * factor) / factor
    }
}

