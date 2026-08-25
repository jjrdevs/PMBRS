package com.pmbrs.mobile.sync

import java.net.URI
import java.net.URISyntaxException

fun normalizeSyncBaseUrl(baseUrl: String): String? {
    val trimmed = baseUrl.trim()
    val uri = try {
        URI(trimmed)
    } catch (e: URISyntaxException) {
        return null
    }

    val scheme = uri.scheme?.lowercase() ?: return null
    val host = uri.host ?: return null

    val isLoopback = host == "localhost" || host == "::1" || host.startsWith("127.")
    val isPrivateIPv4 = host.matches(Regex("^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.)"))
    val isPrivateIPv6 = host.startsWith("::1") || host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe80")

    if (scheme == "https") {
        // HTTPS is allowed for public hosts and private LAN hosts.
    } else if (scheme == "http" && (isLoopback || isPrivateIPv4 || isPrivateIPv6)) {
        // Allow private/local HTTP only for trusted personal-home testing.
    } else {
        return null
    }

    val portPart = if (uri.port != -1) ":${uri.port}" else ""
    return "$scheme://$host$portPart/"
}
