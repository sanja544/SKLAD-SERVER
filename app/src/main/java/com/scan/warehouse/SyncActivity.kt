package com.scan.warehouse

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.util.Base64
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.scan.warehouse.data.AppDatabase
import com.scan.warehouse.data.ProductEntity
import com.scan.warehouse.databinding.ActivitySyncBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.max

class SyncActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySyncBinding
    private val prefs by lazy { getSharedPreferences("sync_prefs", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivitySyncBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        val saved = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL).orEmpty()
        binding.etServer.setText(saved)

        binding.btnPing.setOnClickListener {
            val base = saveBaseUrl()
            ping(base)
        }

        binding.btnPull.setOnClickListener {
            val base = saveBaseUrl()
            pull(base)
        }

        binding.btnPush.setOnClickListener {
            val base = saveBaseUrl()
            push(base)
        }

        binding.btnSync.setOnClickListener {
            val base = saveBaseUrl()
            sync(base)
        }

        binding.btnBack.setOnClickListener { finish() }
    }

    private fun saveBaseUrl(): String {
        val base = normalizeBaseUrl(binding.etServer.text?.toString().orEmpty())
        prefs.edit().putString(KEY_BASE_URL, base).apply()
        return base
    }

    private fun normalizeBaseUrl(input: String): String {
        var s = input.trim()
        if (s.isEmpty()) return DEFAULT_BASE_URL
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://$s"
        while (s.endsWith("/")) s = s.dropLast(1)
        return s
    }

    private fun lastSync(): Long = prefs.getLong(KEY_LAST_SYNC, 0L)
    private fun setLastSync(v: Long) = prefs.edit().putLong(KEY_LAST_SYNC, v).apply()

    // ВАЖЛИВО: після успішного Pull/SYNC вважаємо ініціалізацію виконаною
    private fun markInitDone() {
        prefs.edit().putBoolean(KEY_INIT_DONE, true).apply()
    }

    private fun ping(baseUrl: String) {
        binding.tvStatus.text = "Ping..."
        CoroutineScope(Dispatchers.Main).launch {
            binding.tvStatus.text = withContext(Dispatchers.IO) { httpGet("$baseUrl/ping") }
        }
    }

    private fun pull(baseUrl: String) {
        binding.tvStatus.text = "Pull..."
        CoroutineScope(Dispatchers.Main).launch {
            val since = lastSync()
            val body = withContext(Dispatchers.IO) { httpGet("$baseUrl/pull?since=$since") }

            val parsed = runCatching { JSONObject(body) }.getOrNull()
            if (parsed == null || !parsed.optBoolean("ok", false)) {
                binding.tvStatus.text = body
                return@launch
            }

            val items = parsed.optJSONArray("items") ?: JSONArray()
            val dao = AppDatabase.get(applicationContext).productDao()

            var downloaded = 0
            withContext(Dispatchers.IO) {
                for (i in 0 until items.length()) {
                    val o = items.getJSONObject(i)
                    var p = o.toProductEntity()

                    val remote = p.photoRemoteUrl
                    if (!remote.isNullOrBlank()) {
                        val localUri = downloadPhotoIfNeeded(baseUrl, p.barcode, remote)
                        if (localUri != null) {
                            p = p.copy(photoUri = localUri.toString())
                            downloaded += 1
                        }
                    }

                    dao.upsert(p)
                }
            }

            val newLast = withContext(Dispatchers.IO) { dao.getMaxUpdatedAt() }
            setLastSync(newLast)
            markInitDone()

            binding.tvStatus.text =
                "PULL OK: items=${items.length()} photosDownloaded=$downloaded lastSync $since -> $newLast\n$body"
        }
    }

    private fun push(baseUrl: String) {
        binding.tvStatus.text = "Push..."
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            val since = lastSync()
            val changed = withContext(Dispatchers.IO) { dao.getChangedSince(since) }

            var uploadedPhotos = 0
            var failedPhotos = 0

            val updatedList = ArrayList<ProductEntity>()
            withContext(Dispatchers.IO) {
                for (p in changed) {
                    if (!p.photoUri.isNullOrBlank() && p.photoRemoteUrl.isNullOrBlank() && p.isDeleted == 0) {
                        val uploadRes = uploadPhotoCompressed(baseUrl, p.barcode, Uri.parse(p.photoUri))
                        if (uploadRes != null) {
                            uploadedPhotos += 1
                            val now = System.currentTimeMillis()
                            val p2 = p.copy(photoRemoteUrl = uploadRes, updatedAt = now)
                            dao.upsert(p2)
                            updatedList.add(p2)
                        } else {
                            failedPhotos += 1
                            updatedList.add(p)
                        }
                    } else {
                        updatedList.add(p)
                    }
                }
            }

            val payload = JSONObject().apply {
                put("clientTime", System.currentTimeMillis())
                put("items", JSONArray().apply { for (p in updatedList) put(p.toJson()) })
            }.toString()

            val pushBody = withContext(Dispatchers.IO) { httpPostJson("$baseUrl/push", payload) }

            val newLast = withContext(Dispatchers.IO) { dao.getMaxUpdatedAt() }
            setLastSync(newLast)

            binding.tvStatus.text =
                "PUSH OK: items=${updatedList.size} photosUploaded=$uploadedPhotos photosFailed=$failedPhotos lastSync $since -> $newLast\n$pushBody"
        }
    }

    private fun sync(baseUrl: String) {
        CoroutineScope(Dispatchers.Main).launch {
            push(baseUrl)
            pull(baseUrl) // pull() сам поставить init_done
        }
    }

    private fun uploadPhotoCompressed(baseUrl: String, barcode: String, uri: Uri): String? {
        return try {
            val jpegBytes = compressUriToJpeg(uri, maxDim = 1280, targetBytes = 1_500_000) ?: return null
            val b64 = Base64.encodeToString(jpegBytes, Base64.NO_WRAP)

            val payload = JSONObject().apply {
                put("barcode", barcode)
                put("ext", "jpg")
                put("dataBase64", b64)
            }.toString()

            val resp = httpPostJson("$baseUrl/upload_photo", payload)
            val obj = runCatching { JSONObject(resp) }.getOrNull() ?: return null
            if (!obj.optBoolean("ok", false)) return null
            obj.optString("photoRemoteUrl", null)
        } catch (_: Exception) {
            null
        }
    }

    private fun compressUriToJpeg(uri: Uri, maxDim: Int, targetBytes: Int): ByteArray? {
        val optsBounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, optsBounds) }
        val w = max(optsBounds.outWidth, 1)
        val h = max(optsBounds.outHeight, 1)

        var sample = 1
        while ((w / sample) > maxDim || (h / sample) > maxDim) sample *= 2

        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        val bmp = contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opts) } ?: return null

        val out = ByteArrayOutputStream()
        var quality = 90
        bmp.compress(Bitmap.CompressFormat.JPEG, quality, out)

        while (out.size() > targetBytes && quality > 55) {
            out.reset()
            quality -= 10
            bmp.compress(Bitmap.CompressFormat.JPEG, quality, out)
        }

        bmp.recycle()
        return out.toByteArray()
    }

    private fun downloadPhotoIfNeeded(baseUrl: String, barcode: String, remotePath: String): Uri? {
        return try {
            val url = if (remotePath.startsWith("http://") || remotePath.startsWith("https://")) {
                remotePath
            } else {
                baseUrl + remotePath
            }

            val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 8000
                readTimeout = 8000
            }

            val code = conn.responseCode
            if (code !in 200..299) {
                conn.disconnect()
                return null
            }

            val bytes = conn.inputStream.use { it.readBytes() }
            conn.disconnect()

            val picturesDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: return null
            val imagesDir = File(picturesDir, "images").apply { mkdirs() }

            val file = File(imagesDir, "SYNC_${barcode}.jpg")
            file.outputStream().use { it.write(bytes) }

            FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
        } catch (_: Exception) {
            null
        }
    }

    private fun httpGet(urlStr: String): String {
        return try {
            val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 5000
                readTimeout = 5000
            }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = BufferedReader(InputStreamReader(stream)).use { it.readText() }
            conn.disconnect()
            if (code in 200..299) text else "HTTP $code\n$text"
        } catch (e: Exception) {
            "Нема звʼязку: ${e.message}"
        }
    }

    private fun httpPostJson(urlStr: String, jsonBody: String): String {
        return try {
            val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = 15000
                readTimeout = 15000
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
            conn.outputStream.use { it.write(jsonBody.toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = BufferedReader(InputStreamReader(stream)).use { it.readText() }
            conn.disconnect()
            if (code in 200..299) text else "HTTP $code\n$text"
        } catch (e: Exception) {
            "Нема звʼязку: ${e.message}"
        }
    }

    private fun ProductEntity.toJson(): JSONObject = JSONObject().apply {
        put("barcode", barcode)
        put("name", name)
        put("price", price)
        put("qty", qty)
        if (photoUri != null) put("photoUri", photoUri) else put("photoUri", JSONObject.NULL)
        if (photoRemoteUrl != null) put("photoRemoteUrl", photoRemoteUrl) else put("photoRemoteUrl", JSONObject.NULL)
        put("isDeleted", isDeleted)
        put("updatedAt", updatedAt)
    }

    private fun JSONObject.toProductEntity(): ProductEntity {
        val pUri = if (isNull("photoUri")) null else optString("photoUri", null)
        val pRemote = if (isNull("photoRemoteUrl")) null else optString("photoRemoteUrl", null)
        return ProductEntity(
            barcode = optString("barcode", "").trim(),
            name = optString("name", ""),
            price = optDouble("price", 0.0),
            qty = optInt("qty", 0),
            photoUri = pUri,
            photoRemoteUrl = pRemote,
            isDeleted = optInt("isDeleted", 0),
            updatedAt = optLong("updatedAt", 0L)
        )
    }

    companion object {
        private const val KEY_BASE_URL = "base_url"
        private const val KEY_LAST_SYNC = "last_sync"
        private const val KEY_INIT_DONE = "init_done"

        // ДЕФОЛТНИЙ IP твого ПК-сервера:
        private const val DEFAULT_BASE_URL = "http://192.168.31.28:8000"
    }
}
