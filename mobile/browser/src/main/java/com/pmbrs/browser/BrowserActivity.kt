package com.pmbrs.browser

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.net.toUri
import com.pmbrs.browser.databinding.ActivityBrowserBinding
import java.util.Locale
import java.util.UUID

class BrowserActivity : AppCompatActivity() {
    private lateinit var binding: ActivityBrowserBinding
    private lateinit var telemetry: BrowserTelemetryLogger

    private var currentPageStartMs: Long = 0L
    private var lastCanonicalUrl: String? = null
    private var lastTitle: String? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityBrowserBinding.inflate(layoutInflater)
        setContentView(binding.root)

        telemetry = BrowserTelemetryLogger(this)

        binding.goButton.setOnClickListener {
            val url = normalizeUrl(binding.urlInput.text?.toString().orEmpty())
            if (url != null) {
                loadUrl(url)
            }
        }

        binding.backButton.setOnClickListener { binding.browserWebView.goBack() }
        binding.forwardButton.setOnClickListener { binding.browserWebView.goForward() }
        binding.refreshButton.setOnClickListener { binding.browserWebView.reload() }

        val webSettings = binding.browserWebView.settings
        webSettings.javaScriptEnabled = true
        webSettings.domStorageEnabled = true
        webSettings.cacheMode = WebSettings.LOAD_DEFAULT
        webSettings.allowFileAccess = false
        webSettings.allowContentAccess = false
        webSettings.databaseEnabled = true
        webSettings.savePassword = false
        webSettings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW

        binding.browserWebView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                currentPageStartMs = System.currentTimeMillis()
                lastCanonicalUrl = normalizeUrl(url)
                if (lastCanonicalUrl != null) {
                    val title = view?.title ?: lastCanonicalUrl ?: ""
                    lastTitle = title
                    telemetry.beginPageVisit(lastCanonicalUrl!!, title)
                }
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                val canonicalUrl = normalizeUrl(url) ?: return
                val title = view?.title ?: lastTitle ?: canonicalUrl
                telemetry.endPageVisit(canonicalUrl, title)
            }

            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val target = request?.url?.toString() ?: return false
                return if (target.startsWith("http://") || target.startsWith("https://")) {
                    false
                } else {
                    true
                }
            }
        }

        binding.browserWebView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                super.onProgressChanged(view, newProgress)
                if (newProgress >= 100) {
                    binding.progressBar.progress = 100
                } else {
                    binding.progressBar.progress = newProgress
                }
            }
        }

        binding.browserWebView.setOnLongClickListener {
            false
        }

        loadUrl("https://example.com")
    }

    private fun loadUrl(rawUrl: String) {
        val url = normalizeUrl(rawUrl) ?: return
        binding.urlInput.setText(url)
        binding.browserWebView.loadUrl(url)
    }

    private fun normalizeUrl(rawUrl: String?): String? {
        val trimmed = rawUrl?.trim() ?: return null
        if (trimmed.isEmpty()) return null
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            return trimmed
        }
        return "https://$trimmed"
    }
}

class BrowserTelemetryLogger(private val context: android.content.Context) {
    private val storage = BrowserTelemetryStore(context)

    fun beginPageVisit(rawUrl: String, title: String?) {
        val normalized = normalizePageUrl(rawUrl)
        if (normalized == null) return
        storage.startVisit(normalized, title ?: "")
    }

    fun endPageVisit(rawUrl: String, title: String?) {
        val normalized = normalizePageUrl(rawUrl)
        if (normalized == null) return
        storage.finishVisit(normalized, title ?: "")
    }

    private fun normalizePageUrl(rawUrl: String): String? {
        val uri = runCatching { rawUrl.toUri() }.getOrNull() ?: return null
        val scheme = uri.scheme ?: return null
        if (scheme != "http" && scheme != "https") return null
        return uri.toString()
    }
}

class BrowserTelemetryStore(private val context: android.content.Context) {
    fun startVisit(url: String, title: String) {
        // Placeholder for the separate browser app: future PMBRS-compatible artifact export
        // should serialize a page visit record here with a canonical domain + page title.
    }

    fun finishVisit(url: String, title: String) {
        // Placeholder for the separate browser app: emit a page-end event to a local queue
        // before exporting to PMBRS through the defined ingest contract.
    }
}
