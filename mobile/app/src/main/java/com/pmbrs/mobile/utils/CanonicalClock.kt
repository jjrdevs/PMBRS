package com.pmbrs.mobile.utils

/**
 * PMBRS §6 — Canonical Grid Timestamp.
 *
 * All collectors MUST snap `createdAtEpochMs` to the nearest 60-second grid
 * boundary (snap-down, i.e., floor). This guarantees deterministic timestamps
 * across every collector invocation within the same wall-clock minute and allows
 * downstream pipelines to de-duplicate and align samples to a canonical clock.
 */
object CanonicalClock {

    // Grid alignment window in milliseconds — PMBRS §6 mandates 60-second grid.
    private const val GRID_MS: Long = 60_000L

    /**
     * Returns the current epoch timestamp snapped down to the nearest minute boundary.
     * Equivalent to `(System.currentTimeMillis() / 60,000) * 60,000`.
     */
    fun now(): Long {
        return snap(System.currentTimeMillis())
    }

    /**
     * Snaps an arbitrary epoch-milli timestamp down to the nearest grid boundary.
     *
     * @param ts Epoch milliseconds (e.g., [System.currentTimeMillis]).
     * @return Floored-to-grid timestamp.
     */
    fun snap(ts: Long): Long {
        return (ts / GRID_MS) * GRID_MS
    }

    /**
     * Convenience wrapper — callers that want the current canonical grid time can
     * call this instead of `CanonicalClock.now()` for readability at call-sites.
     */
    fun currentGridTimestamp(): Long = now()
}
