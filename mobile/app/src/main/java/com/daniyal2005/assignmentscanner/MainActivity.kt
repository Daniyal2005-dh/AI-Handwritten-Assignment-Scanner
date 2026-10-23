package com.daniyal2005.assignmentscanner

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

/**
 * Android client for the AI Handwritten Assignment Scanner web app.
 *
 * The whole product UI lives in the FastAPI-served frontend; this activity
 * hosts it in a WebView and adds the native glue Android users expect:
 * photo picking (SAF chooser with multi-select), pull-to-refresh,
 * an offline screen with retry, back-gesture navigation, and a configurable
 * server URL (HF Space by default, or a laptop on the LAN).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var refreshLayout: SwipeRefreshLayout
    private lateinit var errorPanel: LinearLayout
    private lateinit var errorDetail: TextView

    private lateinit var prefs: android.content.SharedPreferences
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    /** Default: the deployed Hugging Face Space. */
    val defaultUrl = "https://daniyal2005-dh-ai-assignment-scanner.hf.space"

    private fun serverUrl(): String {
        val saved = prefs.getString(KEY_SERVER, null)?.trim().orEmpty()
        return saved.ifEmpty { defaultUrl }
    }

    companion object {
        private const val KEY_SERVER = "server_url"
        private const val FILE_CHOOSER_CODE = 41
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("scanner", Context.MODE_PRIVATE)

        // ---- Minimal layout built in code: web view + refresh + error panel.
        val root = FrameLayout(this)
        refreshLayout = SwipeRefreshLayout(this)
        webView = WebView(this)
        webView.visibility = View.VISIBLE
        refreshLayout.addView(webView)
        root.addView(refreshLayout)

        errorPanel = buildErrorPanel(root)
        root.addView(errorPanel)
        errorPanel.visibility = View.GONE
        lastErrorDetail?.let { errorDetail.text = it }
        setContentView(root)

        // ---- WebView configuration
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            supportZoom = true // pinch zoom on dense assignment pages
        }
        webView.setBackgroundColor(getColor(R.color.page_bg))

        refreshLayout.setColorSchemeColors(getColor(R.color.accent))
        refreshLayout.setOnRefreshListener {
            webView.reload()
            refreshLayout.isRefreshing = false
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                // keep the app inside the scanner service
                val serverHost = Uri.parse(serverUrl()).host.orEmpty()
                val host = request.url.host.orEmpty()
                return host != serverHost && !host.endsWith("hf.space") && !host.endsWith(".hf.space")
            }

            override fun onPageFinished(view: WebView, url: String) {
                refreshLayout.isRefreshing = false
                if (!view.url.isNullOrBlank() && view.url != "about:blank") {
                    lastErrorDetail = null
                    errorPanel.visibility = View.GONE
                }
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: android.webkit.WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    lastErrorDetail = error?.description?.toString()
                        ?: getString(R.string.server_hint)
                    runOnUiThread {
                        errorDetail.text = lastErrorDetail
                        errorPanel.visibility = View.VISIBLE
                    }
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView?,
                callback: ValueCallback<Array<Uri>>?,
                params: FileChooserParams?
            ): Boolean {
                fileCallback?.onReceiveValue(null) // cancel any pending one
                fileCallback = callback
                val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "image/*"
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                }
                startActivityForResult(
                    Intent.createChooser(intent, getString(R.string.choose_pages)), FILE_CHOOSER_CODE
                )
                return true
            }
        }

        loadServer()
    }

    /** Error surface (HCI: clear recovery path — retry or change server). */
    private fun buildErrorPanel(root: FrameLayout): LinearLayout {
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setBackgroundColor(getColor(R.color.page_bg))
            setPadding(48, 48, 48, 48)
        }
        val title = TextView(this).apply {
            text = getString(R.string.cant_reach)
            textSize = 18f
            setTextColor(getColor(R.color.ink))
            gravity = android.view.Gravity.CENTER
        }
        errorDetail = TextView(this).apply {
            textSize = 13f
            setTextColor(getColor(R.color.ink_muted))
            gravity = android.view.Gravity.CENTER
            setPadding(0, 24, 0, 40)
        }
        val retry = Button(this).apply {
            text = getString(R.string.retry)
            setOnClickListener { loadServer() }
        }
        val server = Button(this).apply {
            text = getString(R.string.change_server)
            setOnClickListener { showServerDialog() }
        }
        panel.addView(title)
        panel.addView(errorDetail)
        panel.addView(retry)
        panel.addView(server)
        return panel
    }

    private var lastErrorDetail: String? = null

    fun loadServer() {
        errorPanel.visibility = View.GONE
        webView.loadUrl(serverUrl())
    }

    fun showServerDialog() {
        val input = EditText(this).apply { setText(serverUrl()) }
        AlertDialog.Builder(this)
            .setTitle(R.string.change_server)
            .setMessage(R.string.server_hint)
            .setView(input)
            .setPositiveButton(R.string.save) { _, _ ->
                val url = input.text.toString().trim()
                if (url.startsWith("http")) {
                    prefs.edit().putString(KEY_SERVER, url).apply()
                    Toast.makeText(this, R.string.saved, Toast.LENGTH_SHORT).show()
                    loadServer()
                } else {
                    Toast.makeText(this, R.string.invalid_url, Toast.LENGTH_LONG).show()
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    // ---- photo picker results -> the PWA upload input
    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == FILE_CHOOSER_CODE) {
            val callback = fileCallback
            fileCallback = null
            val uris: Array<Uri>? = when {
                resultCode != Activity.RESULT_OK -> null
                data?.clipData != null -> {
                    val clip = data.clipData!!
                    (0 until clip.itemCount).map { clip.getItemAt(it).uri }.toTypedArray()
                }
                data?.data != null -> arrayOf(Uri.parse(data?.dataString))
                else -> null
            }
            callback?.onReceiveValue(uris)
        } else {
            super.onActivityResult(requestCode, resultCode, data)
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
