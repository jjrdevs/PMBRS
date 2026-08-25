package com.pmbrs.mobile.sync

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SyncUrlValidatorTest {
    @Test
    fun normalizeSyncBaseUrl_addsTrailingSlash() {
        val result = normalizeSyncBaseUrl("https://example.com/api")
        assertEquals("https://example.com/", result)
    }

    @Test
    fun normalizeSyncBaseUrl_rejectsMissingScheme() {
        assertNull(normalizeSyncBaseUrl("example.com"))
    }

    @Test
    fun normalizeSyncBaseUrl_rejectsUnsupportedScheme() {
        assertNull(normalizeSyncBaseUrl("ftp://example.com/"))
    }

    @Test
    fun normalizeSyncBaseUrl_allowsHttpAndHttps() {
        // HTTP is disallowed for public hosts; only HTTPS is accepted.
        assertNull(normalizeSyncBaseUrl("http://example.com"))
        assertEquals("https://example.com/", normalizeSyncBaseUrl("https://example.com"))
    }

    @Test
    fun normalizeSyncBaseUrl_allowsPrivateHomeNetworkHttps() {
        assertEquals(
            "https://192.168.1.180:8788/",
            normalizeSyncBaseUrl("https://192.168.1.180:8788/api")
        )
    }

    @Test
    fun normalizeSyncBaseUrl_stripsQueryAndFragment() {
        assertEquals(
            "https://example.com/",
            normalizeSyncBaseUrl("https://example.com/path?query=1#fragment")
        )
    }
}
