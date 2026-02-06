package com.scan.warehouse

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Environment
import android.util.Base64
import androidx.core.content.FileProvider
import com.scan.warehouse.data.AppDatabase
import com.scan.warehouse.data.ProductEntity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStreamReader
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import kotlin.math.max

object SyncManager {

    private const val PREFS = "sync_prefs"
    private const val KEY_BASE_URL = "base_url"
    private const val KEY_LAST_SYNC = "last_sync"
    private const val KEY_INIT_DONE = "init_done"

    // дефолтний сервер (твій ПК)
    private const val DEFAULT_BASE_URL = "http://192.168.31.28:8000"

    // статуси для UI
    private const val KEY_LAST_ATTEMPT_MS = "last_sync_attempt_ms"
    private const val KEY_LAST_SUCCESS_MS = "last_sync_success_ms"
    private const val KEY_LAST_ERROR = "last_sync_error"

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()

    /** після Clear data base_url порожній — ставимо дефолт автоматом */
    fun ensureDefaultBaseUrl(context: Context) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_BASE_URL, null)?.trim().orEmpty()
        if (raw.isBlank()) {
            prefs.edit().putString(KEY_BASE_URL, DEFAULT_BASE_URL).apply()
        }
    }

    /** Одноразова синхронізація (для Worker і ручних викликів). Повертає true/false */
    suspend fun syncNow(context: Context): Boolean {
        return mutex.withLock {
            val appCtx = context.applicationContext
            ensureDefaultBaseUrl(appCtx)
            val baseUrl = getBaseUrl(appCtx) ?: return@withLock false

            setStatusAttempt(appCtx)

            try {
                push(appCtx, baseUrl)
                pull(appCtx, baseUrl, since = getLastSync(appCtx))
                setStatusOk(appCtx)
                true
            } catch (e: Exception) {
                setStatusError(appCtx, prettyError(e))
                false
            }
        }
    }

    /** Fire-and-forget для UI: запускає sync у фоні */
    fun requestSync(context: Context) {
        scope.launchSafe { syncNow(context) }
    }

    /** Initial pull (після install/clear data) */
    fun requestInitialPullWithPhotos(context: Context) {
        scope.launchSafe {
            mutex.withLock {
                val appCtx = context.applicationContext
                ensureDefaultBaseUrl(appCtx)
                val baseUrl = getBaseUrl(appCtx) ?: return@withLock

                setStatusAttempt(appCtx)

                try {
                    pull(appCtx, baseUrl, since = 0L)
                    setInitDone(appCtx, true)
                    setStatusOk(appCtx)
                } catch (e: Exception) {
                    setStatusError(appCtx, prettyError(e))
                }
            }
        }
    }

    private suspend fun push(context: Context, baseUrl: String) {
        val dao = AppDatabase.get(context).productDao()
        val since = getLastSync(context)
        val changed = dao.getChangedSince(since)
        if (changed.isEmpty()) return

        val toPush = ArrayList<ProductEntity>(changed.size)

        // 1) спочатку заливаємо фото (якщо треба)
        for (p in changed) {
            if (!p.photoUri.isNullOrBlank() && p.photoRemoteUrl.isNullOrBlank() && p.isDeleted == 0) {
                val remoteUrl = uploadPhotoCompressed(context, baseUrl, p.barcode, Uri.parse(p.photoUri))
                if (!remoteUrl.isNullOrBlank()) {
                    val now = System.currentTimeMillis()
                    val p2 = p.copy(photoRemoteUrl = remoteUrl, updatedAt = now)
                    dao.upsert(p2)
                    toPush.add(p2)
                } else {
                    // якщо фото не залилось (сервер/мережа) — пушимо як є
                    toPush.add(p)
                }
            } else {
                toPush.add(p)
            }
        }

        // 2) пушимо зміни
        val payload = JSONObject().apply {
            put("clientTime", System.currentTimeMillis())
            put("items", JSONArray().apply { toPush.forEach { put(it.toJson()) } })
        }.toString()

        val resp = httpPostJson("$baseUrl/push", payload)
        val obj = runCatching { JSONObject(resp) }.getOrNull()
            ?: throw RuntimeException("Bad server response (push)")

        if (!obj.optBoolean("ok", false)) {
            throw RuntimeException(obj.optString("error", "Server rejected push"))
        }
    }

    private suspend fun pull(context: Context, baseUrl: String, since: Long) {
        val dao = AppDatabase.get(context).productDao()
        val body = httpGet("$baseUrl/pull?since=$since")
        if (body.isBlank()) throw RuntimeException("Empty server response (pull)")

        val obj = runCatching { JSONObject(body) }.getOrNull()
            ?: throw RuntimeException("Bad server response (pull)")

        if (!obj.optBoolean("ok", false)) {
            throw RuntimeException(obj.optString("error", "Server ok=false (pull)"))
        }

        val items = obj.optJSONArray("items") ?: JSONArray()
        for (i in 0 until items.length()) {
            val o = items.getJSONObject(i)
            var p = o.toProductEntity()

            // тягнемо фото, якщо є remoteUrl
            val remote = p.photoRemoteUrl
            if (!remote.isNullOrBlank()) {
                val localUri = downloadPhotoIfNeeded(context, baseUrl, p.barcode, remote)
                if (localUri != null) {
                    p = p.copy(photoUri = localUri.toString())
                }
            }

            dao.upsert(p)
        }

        val newLast = dao.getMaxUpdatedAt()
        setLastSync(context, newLast)
    }

    /** POST /upload_photo, повертає photoRemoteUrl або null */
    private fun uploadPhotoCompressed(context: Context, baseUrl: String, barcode: String, uri: Uri): String? {
        return try {
            val jpegBytes = compressUriToJpeg(context, uri, maxDim = 1280, targetBytes = 1_500_000) ?: return null
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

    private fun compressUriToJpeg(context: Context, uri: Uri, maxDim: Int, targetBytes: Int): ByteArray? {
        val optsBounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, optsBounds) }

        val w = max(optsBounds.outWidth, 1)
        val h = max(optsBounds.outHeight, 1)

        var sample = 1
        while ((w / sample) > maxDim || (h / sample) > maxDim) sample *= 2

        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        val bmp = context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, opts)
        } ?: return null

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

    private fun downloadPhotoIfNeeded(context: Context, baseUrl: String, barcode: String, remotePath: String): Uri? {
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

            val picturesDir = context.getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: return null
            val imagesDir = File(picturesDir, "images").apply { mkdirs() }

            val file = File(imagesDir, "SYNC_${barcode}.jpg")
            file.outputStream().use { it.write(bytes) }

            FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        } catch (_: Exception) {
            null
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

    private fun getBaseUrl(context: Context): String? {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_BASE_URL, null)?.trim().orEmpty()
        if (raw.isBlank()) return null
        return raw.trimEnd('/')
    }

    private fun setLastSync(context: Context, v: Long) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putLong(KEY_LAST_SYNC, v).apply()
    }

    private fun getLastSync(context: Context): Long =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_LAST_SYNC, 0L)

    private fun setInitDone(context: Context, v: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_INIT_DONE, v).apply()
    }

    private fun setStatusAttempt(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putLong(KEY_LAST_ATTEMPT_MS, System.currentTimeMillis())
            .apply()
    }

    private fun setStatusOk(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putLong(KEY_LAST_SUCCESS_MS, System.currentTimeMillis())
            .putString(KEY_LAST_ERROR, "")
            .apply()
    }

    private fun setStatusError(context: Context, msg: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LAST_ERROR, msg)
            .apply()
    }

    private fun prettyError(e: Exception): String {
        return when (e) {
            is UnknownHostException -> "Немає інтернету / DNS"
            is ConnectException -> "Сервер недоступний (не запущений або IP/порт не ті)"
            is SocketTimeoutException -> "Таймаут: сервер не відповідає"
            else -> e.message?.take(80) ?: "Помилка синхронізації"
        }
    }

    private fun httpGet(urlStr: String): String {
        val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 5000
            readTimeout = 5000
        }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = BufferedReader(InputStreamReader(stream)).use { it.readText() }
        conn.disconnect()
        if (code !in 200..299) throw RuntimeException("HTTP $code")
        return text
    }

    private fun httpPostJson(urlStr: String, jsonBody: String): String {
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
        if (code !in 200..299) throw RuntimeException("HTTP $code")
        return text
    }

    private fun CoroutineScope.launchSafe(block: suspend () -> Unit) {
        this.launch {
            try {
                block()
            } catch (_: Exception) {
                // errors are written via setStatusError inside syncNow()
            }
        }
    }
}
