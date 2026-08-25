# Bromite → PMBRS Intent Spec

Purpose
- Define a minimal, privacy-conscious Intent contract Bromite can emit so `com.pmbrs.mobile` can persist page-level browser visits when the browser producer opts in.

Intent action
- `com.pmbrs.mobile.ACTION_BROWSER_VISIT`

Recommended extras (all keys are String unless noted)
- `url` — full navigated URL (optional; include only if user-consented)
- `title` — page title (optional)
- `search_query` — extracted search text for search pages (optional)
- `browser_package` — sender package name (optional; defaults to Intent.getPackage())
- `observed_at_ms` — epoch ms timestamp (Long) (optional; receiver defaults to now)
- `pmbrs_sig` — HMAC-SHA256 signature over canonical payload (optional; recommended)

Security and privacy guidance
- This Intent transmits page-level data. Only emit it when the user has explicitly consented and understands local persistence and retention.
- Prefer HMAC validation: Bromite and the mobile app share a short-lived pre-shared key (PSK) used to sign `url||observed_at_ms`. Receiver verifies `pmbrs_sig` to avoid spoofing.
- Avoid exporting any sensitive tokens in the Intent. Do not include user IDs or device identifiers in the Intent extras.

HMAC signing (Kotlin example)
```kotlin
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import android.content.Context
import android.content.Intent

fun hmacSha256Hex(key: ByteArray, data: ByteArray): String {
    val mac = Mac.getInstance("HmacSHA256")
    val spec = SecretKeySpec(key, "HmacSHA256")
    mac.init(spec)
    val raw = mac.doFinal(data)
    return raw.joinToString("") { "%02x".format(it) }
}

fun sendPmbrsVisit(context: Context, url: String?, title: String?, searchQuery: String?, psk: ByteArray?) {
    val action = "com.pmbrs.mobile.ACTION_BROWSER_VISIT"
    val intent = Intent().apply {
        this.action = action
        putExtra("url", url)
        putExtra("title", title)
        putExtra("search_query", searchQuery)
        putExtra("browser_package", context.packageName)
        putExtra("observed_at_ms", System.currentTimeMillis())
    }

    // optional: attach HMAC signature if PSK is configured
    if (psk != null && url != null) {
        val observed = intent.getLongExtra("observed_at_ms", System.currentTimeMillis())
        val payload = (url + observed.toString()).toByteArray(Charsets.UTF_8)
        val sig = hmacSha256Hex(psk, payload)
        intent.putExtra("pmbrs_sig", sig)
    }

    // Safe broadcast: send without explicit permission to allow broad testing;
    // in production consider using a more restrictive channel or dynamic permission.
    context.sendBroadcast(intent)
}
```

Receiver validation (mobile app)
- The mobile receiver should: (1) check intent.action, (2) read extras, (3) if `pmbrs_sig` present verify HMAC using the shared PSK, (4) drop the Intent if signature invalid or missing when PSK is required.
- Keep conservative defaults: if no signature and your phone app requires it, do not persist.

Testing (adb)
```bash
adb shell am broadcast -a com.pmbrs.mobile.ACTION_BROWSER_VISIT \
  --es url "https://www.google.com/search?q=pmbrs+test" \
  --es title "Google Search" \
  --es search_query "pmbrs test" \
  --es browser_package "org.bromite" \
  --el observed_at_ms "$(date +%s%3N)"
```

Implementation notes for Bromite
- Prefer to hook into the navigation commit / page load complete event (TabObserver / WebContentsObserver) and only emit when the page is a top-level navigation or search results page.
- Respect user privacy settings and only enable the broadcast when the user explicitly opts into sharing page-level visits with PMBRS.
- Consider throttling: only emit one broadcast per page load and avoid repeats for same URL within short windows.

Receiver security follow-ups
- If you want stronger sender validation without a PSK, we can implement a permission-based flow where the receiver requires a signature-level permission and Bromite must be signed by the same org — this requires coordination across build/signing.

Next steps I can take
- Produce a small Bromite patch (Java/Kotlin) placing `sendPmbrsVisit()` into the proper navigation callback for a Chromium-based build. I can draft that patch for you — tell me whether you prefer Kotlin or Java and whether you'd like PSK HMAC enabled by default.
