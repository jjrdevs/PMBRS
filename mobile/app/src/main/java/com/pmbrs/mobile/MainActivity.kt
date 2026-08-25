package com.pmbrs.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pmbrs.mobile.collectors.CollectorService
import com.pmbrs.mobile.collectors.PermissionHelper
import com.pmbrs.mobile.data.ArtifactDatabase
import com.pmbrs.mobile.data.ArtifactEntity
import com.pmbrs.mobile.network.NetworkStateHelper
import com.pmbrs.mobile.settings.SyncSettings
import com.pmbrs.mobile.sync.NetworkSyncClient
import com.pmbrs.mobile.telemetry.Telemetry
import com.pmbrs.mobile.sync.SyncResult
import com.pmbrs.mobile.sync.SyncService
import com.pmbrs.mobile.sync.normalizeSyncBaseUrl
import com.pmbrs.mobile.workers.PMBRSSyncWorker

class MainActivity : ComponentActivity() {
    private lateinit var collectorService: CollectorService
    private var syncService: SyncService? = null
    private lateinit var syncSettings: SyncSettings
    private lateinit var networkStateHelper: NetworkStateHelper
    private var pendingCount by mutableIntStateOf(0)
    private var localArtifactCount by mutableIntStateOf(0)
    private var sentArtifactCount by mutableIntStateOf(0)
    private var pendingArtifacts by mutableStateOf<List<ArtifactEntity>>(emptyList())
    private var pendingPreview by mutableStateOf("No pending artifacts yet")
    private var syncStatus by mutableStateOf("Idle")
    private var lastSyncLog by mutableStateOf("No sync attempt yet")
    private var syncPolicyStatus by mutableStateOf("Trusted network only")
    private var showDiagnostics by mutableStateOf(false)
    private var selectedLogCategory by mutableStateOf("apps")
    private var permissionStatus by mutableStateOf<Map<String, Boolean>>(emptyMap())
    private var trustedNetworkOnly by mutableStateOf(true)
    private var browserMetadataEnabled by mutableStateOf(true)
    private var geolocationEnabled by mutableStateOf(false)
    private var syncBaseUrl by mutableStateOf("")
    private var fallbackSyncBaseUrl by mutableStateOf("")
    private var syncIntervalStr by mutableStateOf("")
    private var retentionDaysStr by mutableStateOf("")
    private var syncAuthToken by mutableStateOf("")
    private var networkStatus by mutableStateOf("Unknown")
    private var telemetryCounts by mutableStateOf<Map<String, Int>>(emptyMap())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        syncSettings = SyncSettings(this)
        Telemetry.init(this)
        telemetryCounts = Telemetry.getCounts()
        networkStateHelper = NetworkStateHelper(this)
        collectorService = CollectorService(this, retentionDays = syncSettings.retentionDays)
        CollectorService.schedulePeriodicCollection(this)
        PMBRSSyncWorker.schedulePeriodicSync(this)
        syncBaseUrl = syncSettings.syncBaseUrl
        fallbackSyncBaseUrl = syncSettings.fallbackSyncBaseUrl
        syncIntervalStr = syncSettings.syncIntervalHours.toString()
        retentionDaysStr = syncSettings.retentionDays.toString()
        syncAuthToken = syncSettings.authToken ?: ""
        val activeBase = if (networkStateHelper.isTrustedNetworkConnected()) syncSettings.syncBaseUrl else syncSettings.fallbackSyncBaseUrl
        syncService = normalizeBaseUrl(activeBase)?.let { createSyncService(it) }
        if (syncService == null) {
            syncStatus = "Stored sync endpoint is invalid"
        }
        lastSyncLog = syncSettings.lastSyncLog ?: "No sync attempt yet"
        trustedNetworkOnly = syncSettings.trustedNetworkOnly
        browserMetadataEnabled = syncSettings.browserMetadataEnabled
        geolocationEnabled = syncSettings.geolocationEnabled
        networkStatus = networkStateHelper.currentNetworkStatus()
        permissionStatus = PermissionHelper.permissionsStatus(this)
        syncPolicyStatus = getSyncPolicyText()
        refreshState()
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    MobileHomeScreen(
                        pendingCount = pendingCount,
                        localArtifactCount = localArtifactCount,
                        sentArtifactCount = sentArtifactCount,
                        pendingArtifacts = pendingArtifacts,
                        syncStatus = syncStatus,
                        trustedNetworkOnly = trustedNetworkOnly,
                        browserMetadataEnabled = browserMetadataEnabled,
                        geolocationEnabled = geolocationEnabled,
                        syncBaseUrl = syncBaseUrl,
                        syncAuthToken = syncAuthToken,
                        onCaptureClick = {
                            collectorService.captureSample {
                                refreshState()
                            }
                        },
                        onGenerateDiagnosticClick = {
                            collectorService.generateDiagnosticBurst {
                                refreshState()
                            }
                        },
                        onWriteDebugArtifactClick = {
                            collectorService.writeDebugArtifact {
                                refreshState()
                                updateLastSyncLog("Debug artifact written")
                            }
                        },
                        onSyncClick = {
                            onSyncRequested()
                        },
                        onTrustedNetworkToggle = { enabled ->
                            trustedNetworkOnly = enabled
                            syncSettings.trustedNetworkOnly = enabled
                            syncStatus = if (enabled) {
                                "Sync restricted to trusted networks"
                            } else {
                                "Sync allowed on any network"
                            }
                        },
                        onBrowserMetadataToggle = { enabled ->
                            browserMetadataEnabled = enabled
                            syncSettings.browserMetadataEnabled = enabled
                            syncStatus = if (enabled) {
                                "Browser metadata collection enabled"
                            } else {
                                "Browser metadata collection disabled"
                            }
                        },
                        onGeolocationToggle = { enabled ->
                            geolocationEnabled = enabled
                            syncSettings.geolocationEnabled = enabled
                            syncStatus = if (enabled) {
                                "Coarse geolocation collection enabled"
                            } else {
                                "Coarse geolocation collection disabled"
                            }
                        },
                        onBaseUrlChange = { value ->
                            syncBaseUrl = value
                        },
                        onSaveBaseUrl = {
                            val normalized = normalizeBaseUrl(syncBaseUrl)
                            if (normalized == null) {
                                syncStatus = "Invalid sync endpoint"
                                return@MobileHomeScreen
                            }
                            syncBaseUrl = normalized
                            syncSettings.syncBaseUrl = syncBaseUrl
                            syncService = createSyncService(syncBaseUrl)
                            syncStatus = "Sync endpoint saved"
                        },
                        syncIntervalStr = syncIntervalStr,
                        onSaveSyncSettings = {
                            val parsed = syncIntervalStr.toLongOrNull()
                            if (parsed == null || parsed <= 0) {
                                syncStatus = "Invalid sync interval"
                                return@MobileHomeScreen
                            }
                            syncSettings.syncIntervalHours = parsed
                            // cancel and reschedule with new interval
                            androidx.work.WorkManager.getInstance(this).cancelUniqueWork(PMBRSSyncWorker.TAG_WORK_REQUEST)
                            PMBRSSyncWorker.schedulePeriodicSync(this)
                            syncStatus = "Sync settings saved"
                        },
                        onSyncIntervalChange = { v -> syncIntervalStr = v },
                        retentionDaysStr = retentionDaysStr,
                        onRetentionDaysChange = { v -> retentionDaysStr = v },
                        onSaveRetentionSettings = {
                            val parsed = retentionDaysStr.toIntOrNull()
                            if (parsed == null || parsed <= 0) {
                                syncStatus = "Invalid retention days"
                                return@MobileHomeScreen
                            }
                            syncSettings.retentionDays = parsed
                            collectorService = CollectorService(this, retentionDays = parsed)
                            collectorService.cleanupOldArtifacts()
                            syncStatus = "Retention policy saved"
                        },
                        onSaveAuthToken = {
                            syncSettings.authToken = syncAuthToken.ifBlank { null }
                            syncService = normalizeBaseUrl(syncBaseUrl)?.let { createSyncService(it) }
                            syncStatus = "Auth token saved"
                        },
                        telemetryCounts = telemetryCounts,
                        onRefreshTelemetry = {
                            telemetryCounts = Telemetry.getCounts()
                        },
                        onClearTelemetry = {
                            Telemetry.clearCounts()
                            telemetryCounts = Telemetry.getCounts()
                        },
                        onAuthTokenChange = { v -> syncAuthToken = v },
                        networkStatus = networkStatus,
                        syncPolicyStatus = syncPolicyStatus,
                        pendingPreview = pendingPreview,
                        lastSyncLog = lastSyncLog,
                        permissionStatus = permissionStatus,
                        retentionDays = syncSettings.retentionDays,
                        syncIntervalHours = syncSettings.syncIntervalHours,
                        showDiagnostics = showDiagnostics,
                        selectedLogCategory = selectedLogCategory,
                        onShowDiagnostics = { showDiagnostics = true },
                        onHideDiagnostics = { showDiagnostics = false },
                        onSelectLogCategory = { selectedLogCategory = it }
                    )
                }
            }
        }
    }

    private fun createSyncService(baseUrl: String): SyncService? = try {
        SyncService(
            ArtifactDatabase.getInstance(this),
            NetworkSyncClient.create(baseUrl, syncSettings.authToken)
        )
    } catch (e: IllegalArgumentException) {
        syncStatus = "Invalid sync endpoint"
        null
    }

    private fun normalizeBaseUrl(url: String): String? {
        return normalizeSyncBaseUrl(url)
    }

    private fun onSyncRequested() {
        if (trustedNetworkOnly && !networkStateHelper.isTrustedNetworkConnected()) {
            updateLastSyncLog("Waiting for trusted Wi-Fi or Ethernet")
            return
        }

        val service = syncService
        if (service == null) {
            updateLastSyncLog("Invalid sync endpoint")
            return
        }

        updateLastSyncLog("Syncing...")
        service.syncPending { result ->
            syncStatus = when (result) {
                is SyncResult.Success -> "Synced ${result.syncedIds.size} artifacts"
                is SyncResult.NetworkFailure -> "Sync failed: ${result.error}"
                is SyncResult.ServerFailure -> "Server error ${result.code}: ${result.message}"
                is SyncResult.ClientFailure -> "Sync failed: ${result.error}"
                is SyncResult.Failure -> "Sync failed: ${result.error}"
            }
            updateLastSyncLog(syncStatus)
            refreshState()
        }
    }

    private fun updateLastSyncLog(message: String) {
        syncStatus = message
        lastSyncLog = message
        syncSettings.lastSyncLog = message
    }

    private fun refreshState() {
        pendingCount = collectorService.pendingArtifactCount()
        localArtifactCount = collectorService.localArtifactCount()
        sentArtifactCount = collectorService.sentArtifactCount()
        pendingArtifacts = collectorService.pendingArtifacts()
        networkStatus = networkStateHelper.currentNetworkStatus()
        permissionStatus = PermissionHelper.permissionsStatus(this)
        syncPolicyStatus = getSyncPolicyText()
        pendingPreview = pendingArtifacts.firstOrNull()?.let {
            "Latest pending: ${it.source} - ${it.payload.take(80)}"
        } ?: "No pending artifacts yet"
    }

    private fun getSyncPolicyText(): String {
        return if (trustedNetworkOnly) "Sync restricted to trusted networks" else "Sync allowed on any network"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MobileHomeScreen(
    pendingCount: Int,
    localArtifactCount: Int,
    sentArtifactCount: Int,
    pendingArtifacts: List<ArtifactEntity>,
    syncStatus: String,
    syncPolicyStatus: String,
    pendingPreview: String,
    lastSyncLog: String,
    permissionStatus: Map<String, Boolean>,
    retentionDays: Int,
    syncIntervalHours: Long,
    showDiagnostics: Boolean,
    selectedLogCategory: String,
    onShowDiagnostics: () -> Unit,
    onHideDiagnostics: () -> Unit,
    onSelectLogCategory: (String) -> Unit,
    trustedNetworkOnly: Boolean,
    browserMetadataEnabled: Boolean,
    geolocationEnabled: Boolean,
    syncBaseUrl: String,
    networkStatus: String,
    onCaptureClick: () -> Unit,
    onGenerateDiagnosticClick: () -> Unit,
    onWriteDebugArtifactClick: () -> Unit,
    onSyncClick: () -> Unit,
    onTrustedNetworkToggle: (Boolean) -> Unit,
    onBrowserMetadataToggle: (Boolean) -> Unit,
    onGeolocationToggle: (Boolean) -> Unit,
    onBaseUrlChange: (String) -> Unit,
    onSaveBaseUrl: () -> Unit,
    syncIntervalStr: String,
    onSyncIntervalChange: (String) -> Unit,
    onSaveSyncSettings: () -> Unit,
    retentionDaysStr: String,
    onRetentionDaysChange: (String) -> Unit,
    onSaveRetentionSettings: () -> Unit,
    syncAuthToken: String,
    onAuthTokenChange: (String) -> Unit,
    onSaveAuthToken: () -> Unit,
    telemetryCounts: Map<String, Int>,
    onRefreshTelemetry: () -> Unit,
    onClearTelemetry: () -> Unit
) {
    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = "PMBRS Home",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f)
                )
                Button(onClick = onShowDiagnostics) {
                    Text("Diagnostics")
                }
            }

            if (!showDiagnostics) {
                Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(text = "Overview", fontWeight = FontWeight.SemiBold)
                        Text(text = "Recently sent: $sentArtifactCount", modifier = Modifier.padding(top = 8.dp))
                        Text(text = "Queued to send: $pendingCount", modifier = Modifier.padding(top = 4.dp))
                        Text(text = "Stored locally: $localArtifactCount", modifier = Modifier.padding(top = 4.dp))
                        Text(text = "Next scheduled sync: ${syncIntervalHours}h", modifier = Modifier.padding(top = 4.dp))
                        Text(text = "Last sync: $lastSyncLog", modifier = Modifier.padding(top = 4.dp))
                        Text(text = "Network: $networkStatus", modifier = Modifier.padding(top = 4.dp))
                    }
                }

                Text(text = "Counts by category", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 20.dp))
                val categoryEntries = listOf(
                    "apps" to pendingArtifacts.count { it.source.contains("app", ignoreCase = true) || it.source.contains("screen", ignoreCase = true) || it.source.contains("device", ignoreCase = true) },
                    "browser" to pendingArtifacts.count { it.source.contains("browser", ignoreCase = true) },
                    "geolocation" to pendingArtifacts.count { it.source.contains("geo", ignoreCase = true) || it.source.contains("location", ignoreCase = true) },
                    "system" to pendingArtifacts.count { it.source.contains("system", ignoreCase = true) || it.source.contains("debug", ignoreCase = true) }
                )
                Row(modifier = Modifier.padding(top = 8.dp)) {
                    categoryEntries.forEach { (key, count) ->
                        Button(
                            onClick = { onSelectLogCategory(key) },
                            modifier = Modifier.padding(end = 8.dp)
                        ) {
                            Text("${key.replaceFirstChar { it.uppercase() }} ($count)")
                        }
                    }
                }

                val selectedLabel = when (selectedLogCategory) {
                    "apps" -> "Apps"
                    "browser" -> "Browser"
                    "geolocation" -> "Geolocation"
                    else -> "System"
                }
                val selectedLogs = pendingArtifacts.filter { artifact ->
                    when (selectedLogCategory) {
                        "apps" -> artifact.source.contains("app", ignoreCase = true)
                            || artifact.source.contains("screen", ignoreCase = true)
                            || artifact.source.contains("device", ignoreCase = true)
                        "browser" -> artifact.source.contains("browser", ignoreCase = true)
                        "geolocation" -> artifact.source.contains("geo", ignoreCase = true)
                            || artifact.source.contains("location", ignoreCase = true)
                        else -> artifact.source.contains("system", ignoreCase = true)
                            || artifact.source.contains("debug", ignoreCase = true)
                    }
                }.sortedByDescending { it.createdAtEpochMs }

                Card(modifier = Modifier.fillMaxWidth().padding(top = 20.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(text = "$selectedLabel details", fontWeight = FontWeight.SemiBold)
                        if (selectedLogs.isEmpty()) {
                            Text(text = "No recent $selectedLabel records yet.", modifier = Modifier.padding(top = 8.dp))
                        } else {
                            selectedLogs.take(8).forEach { artifact ->
                                Text(
                                    text = summarizeArtifactForDisplay(artifact),
                                    modifier = Modifier.padding(top = 8.dp)
                                )
                            }
                        }
                    }
                }

                Button(onClick = onSyncClick, modifier = Modifier.padding(top = 20.dp)) {
                    Text("Sync pending artifacts")
                }
                Button(onClick = onCaptureClick, modifier = Modifier.padding(top = 8.dp)) {
                    Text("Capture sample artifact")
                }
            } else {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
                ) {
                    Button(onClick = onHideDiagnostics) {
                        Text("Back to home")
                    }
                }
                Text(text = "System diagnostics", fontSize = 20.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 16.dp))
                Button(onClick = onGenerateDiagnosticClick, modifier = Modifier.padding(top = 16.dp)) {
                    Text("Generate diagnostic burst")
                }
                Button(onClick = onWriteDebugArtifactClick, modifier = Modifier.padding(top = 8.dp)) {
                    Text("Write debug artifact")
                }

                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 16.dp)) {
                    Text(text = "Trusted network only", modifier = Modifier.weight(1f))
                    Switch(checked = trustedNetworkOnly, onCheckedChange = onTrustedNetworkToggle)
                }
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 12.dp)) {
                    Text(text = "Browser metadata collection", modifier = Modifier.weight(1f))
                    Switch(checked = browserMetadataEnabled, onCheckedChange = onBrowserMetadataToggle)
                }
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 12.dp)) {
                    Text(text = "Coarse geolocation collection", modifier = Modifier.weight(1f))
                    Switch(checked = geolocationEnabled, onCheckedChange = onGeolocationToggle)
                }
                OutlinedTextField(
                    value = syncBaseUrl,
                    onValueChange = onBaseUrlChange,
                    label = { Text("Sync endpoint URL") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 16.dp)
                )
                Button(onClick = onSaveBaseUrl, modifier = Modifier.padding(top = 8.dp)) {
                    Text("Save sync endpoint")
                }

                OutlinedTextField(
                    value = syncIntervalStr,
                    onValueChange = onSyncIntervalChange,
                    label = { Text("Sync interval (hours)") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 12.dp)
                )
                Button(onClick = onSaveSyncSettings, modifier = Modifier.padding(top = 8.dp)) {
                    Text("Save sync settings")
                }
                OutlinedTextField(
                    value = retentionDaysStr,
                    onValueChange = onRetentionDaysChange,
                    label = { Text("Retention days") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 12.dp)
                )
                Button(onClick = onSaveRetentionSettings, modifier = Modifier.padding(top = 8.dp)) {
                    Text("Save retention policy")
                }
                OutlinedTextField(
                    value = syncAuthToken,
                    onValueChange = onAuthTokenChange,
                    label = { Text("Auth token (optional)") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 12.dp)
                )
                Button(onClick = onSaveAuthToken, modifier = Modifier.padding(top = 8.dp)) {
                    Text("Save auth token")
                }

                Text(text = "Telemetry counts:", modifier = Modifier.padding(top = 16.dp))
                if (telemetryCounts.isEmpty()) {
                    Text(text = "No telemetry recorded yet.", modifier = Modifier.padding(top = 4.dp))
                } else {
                    val payloadBytes = telemetryCounts["payload_bytes_sent"] ?: 0
                    val payloadText = when {
                        payloadBytes >= 1024 * 1024 -> "${payloadBytes / (1024 * 1024)} MB"
                        payloadBytes >= 1024 -> "${payloadBytes / 1024} KB"
                        else -> "$payloadBytes B"
                    }
                    Text(text = "Total payload sent: $payloadText", modifier = Modifier.padding(top = 4.dp))
                    telemetryCounts.forEach { (k, v) ->
                        if (k == "payload_bytes_sent") return@forEach
                        Text(text = "$k: $v", modifier = Modifier.padding(top = 4.dp))
                    }
                }
                Row(modifier = Modifier.padding(top = 8.dp)) {
                    Button(onClick = onRefreshTelemetry) { Text("Refresh telemetry") }
                    Button(onClick = onClearTelemetry, modifier = Modifier.padding(start = 8.dp)) { Text("Clear telemetry") }
                }

                Text(text = "Network status: $networkStatus", modifier = Modifier.padding(top = 16.dp))
                Text(text = syncPolicyStatus, modifier = Modifier.padding(top = 8.dp))
                Text(text = pendingPreview, modifier = Modifier.padding(top = 4.dp))
                Text(text = "Sync status: $syncStatus", modifier = Modifier.padding(top = 8.dp))
                Text(text = "Last sync: $lastSyncLog", modifier = Modifier.padding(top = 4.dp))
                Text(text = "Permission status:", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 12.dp))
                if (permissionStatus.isEmpty()) {
                    Text(text = "No permission checks available", modifier = Modifier.padding(top = 4.dp))
                } else {
                    permissionStatus.forEach { (name, granted) ->
                        Text(
                            text = "$name: ${if (granted) "granted" else "denied"}",
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                }
            }
        }
    }
}
