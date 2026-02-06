package com.scan.warehouse

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.scan.warehouse.databinding.ActivityMainBinding
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val prefs by lazy { getSharedPreferences("sync_prefs", MODE_PRIVATE) }

    private val uiHandler = Handler(Looper.getMainLooper())

    // Пінг раз на 2.5 секунди
    private val pingTicker = object : Runnable {
        override fun run() {
            pingServerOnce()
            uiHandler.postDelayed(this, 2500)
        }
    }

    private var cm: ConnectivityManager? = null
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            // мережа з’явилась → одразу пробуємо sync
            SyncManager.requestSync(applicationContext)
            // і одразу пінгуємо
            pingServerOnce()
        }

        override fun onCapabilitiesChanged(network: Network, networkCapabilities: NetworkCapabilities) {
            if (networkCapabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
                SyncManager.requestSync(applicationContext)
                pingServerOnce()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        binding.btnAddProduct.setOnClickListener {
            startActivity(Intent(this, AddProductActivity::class.java))
        }
        binding.btnIssue.setOnClickListener {
            startActivity(Intent(this, IssueActivity::class.java))
        }
        binding.btnInventory.setOnClickListener {
            startActivity(Intent(this, InventoryActivity::class.java))
        }
        binding.btnSync.setOnClickListener {
            startActivity(Intent(this, SyncActivity::class.java))
        }

        // база url після clear data
        SyncManager.ensureDefaultBaseUrl(applicationContext)

        // initial pull (не блокує)
        SyncManager.requestInitialPullWithPhotos(applicationContext)

        // фонова синхронізація (на випадок коли додаток закритий)
        scheduleBackgroundSync()

        // проба sync одразу
        kickOneTimeSync()

        // підписка на мережу
        cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        runCatching { cm?.registerDefaultNetworkCallback(networkCallback) }

        // показати початковий статус
        setUiOnline(false)
    }

    override fun onResume() {
        super.onResume()

        // коли повернувся у додаток — пробуємо синк
        SyncManager.requestSync(applicationContext)

        // стартуємо швидкий пінг
        uiHandler.removeCallbacks(pingTicker)
        uiHandler.post(pingTicker)

        // одразу раз пінгуємо
        pingServerOnce()
    }

    override fun onPause() {
        super.onPause()
        uiHandler.removeCallbacks(pingTicker)
    }

    override fun onDestroy() {
        super.onDestroy()
        runCatching { cm?.unregisterNetworkCallback(networkCallback) }
    }

    private fun scheduleBackgroundSync() {
        val work = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(SyncWorker.networkConstraints())
            .build()

        WorkManager.getInstance(applicationContext).enqueueUniquePeriodicWork(
            "sync_periodic",
            ExistingPeriodicWorkPolicy.UPDATE,
            work
        )
    }

    private fun kickOneTimeSync() {
        val one = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(SyncWorker.networkConstraints())
            .build()

        WorkManager.getInstance(applicationContext).enqueueUniqueWork(
            "sync_one_time",
            ExistingWorkPolicy.REPLACE,
            one
        )
    }

    // ---------- Ping ----------

    private fun pingServerOnce() {
        val base = prefs.getString("base_url", "").orEmpty().trim()
        val pingUrl = buildPingUrl(base)
        if (pingUrl.isNullOrBlank()) {
            setUiOnline(false)
            return
        }

        Thread {
            val ok = runCatching { httpPingOk(pingUrl) }.getOrDefault(false)
            runOnUiThread { setUiOnline(ok) }
        }.start()
    }

    private fun setUiOnline(online: Boolean) {
        // Тільки короткий статус
        binding.tvSyncStatus.text = if (online) "Online" else "Offline"
    }

    private fun buildPingUrl(base: String): String? {
        if (base.isBlank()) return null

        // base може бути "192.168.1.2:8000" або "http://192.168.1.2:8000"
        val withScheme = if (base.startsWith("http://") || base.startsWith("https://")) base else "http://$base"

        // прибрати хвіст "/" якщо є
        val trimmed = withScheme.trimEnd('/')

        return "$trimmed/ping"
    }

    private fun httpPingOk(urlStr: String): Boolean {
        val url = URL(urlStr)
        val conn = (url.openConnection() as HttpURLConnection)
        return try {
            conn.requestMethod = "GET"
            conn.connectTimeout = 700
            conn.readTimeout = 700
            conn.useCaches = false
            conn.instanceFollowRedirects = true
            val code = conn.responseCode
            code in 200..299
        } finally {
            conn.disconnect()
        }
    }
}
