// Example Kotlin patch to integrate with a Chromium-based Bromite build.
// Place `sendPmbrsVisit()` into an appropriate navigation callback such as
// WebContentsObserver.didFinishNavigation or a TabObserver's onUrlUpdated.

import android.content.Context
import android.content.Intent
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

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

    if (psk != null && url != null) {
        val observed = intent.getLongExtra("observed_at_ms", System.currentTimeMillis())
        val payload = (url + observed.toString()).toByteArray(Charsets.UTF_8)
        val sig = hmacSha256Hex(psk, payload)
        intent.putExtra("pmbrs_sig", sig)
    }

    // Send a normal broadcast. For stricter validation, use a permission or
    // sendBroadcastAsUser with a specific user/permission.
    context.sendBroadcast(intent)
}

/* Example usage in a WebContentsObserver-like callback:
override fun didFinishNavigation(webContents: WebContents, navigationHandle: NavigationHandle) {
    if (!navigationHandle.isInMainFrame) return
    val url = navigationHandle.url
    val title = webContents.title
    // rudimentary search detection
    val searchQuery = if (url.contains("/search") || url.contains("/s?")) {
        // extract q= param (simplified)
        val q = Uri.parse(url).getQueryParameter("q")
        q
    } else null

    // pskBytes could be loaded from a build-time config or runtime setting
    val pskBytes: ByteArray? = null // set if configured
    sendPmbrsVisit(context, url, title, searchQuery, pskBytes)
}
*/
