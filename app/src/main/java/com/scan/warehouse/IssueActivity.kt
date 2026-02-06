package com.scan.warehouse

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.scan.warehouse.data.AppDatabase
import com.scan.warehouse.databinding.ActivityIssueBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class IssueActivity : AppCompatActivity() {

    private lateinit var binding: ActivityIssueBinding
    private var currentBarcode: String? = null

    private val scanLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
            if (res.resultCode == RESULT_OK) {
                val barcode = res.data?.getStringExtra(ScannerActivity.EXTRA_BARCODE)
                if (!barcode.isNullOrBlank()) {
                    setBarcode(barcode)
                    loadProduct(barcode)
                }
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityIssueBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        binding.btnScan.setOnClickListener {
            scanLauncher.launch(Intent(this, ScannerActivity::class.java))
        }

        binding.btnIssue.setOnClickListener {
            issue()
        }

        // стартовий стан
        renderPhoto(null)
    }

    private fun setBarcode(barcode: String) {
        currentBarcode = barcode.trim()
        binding.tvBarcodeValue.text = currentBarcode
        binding.tvNameValue.text = "—"
        binding.tvQtyValue.text = "—"
        renderPhoto(null)
    }

    private fun loadProduct(barcode: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            val product = withContext(Dispatchers.IO) { dao.getAnyByBarcode(barcode.trim()) }

            if (product == null) {
                binding.tvNameValue.text = "НЕ ЗНАЙДЕНО"
                binding.tvQtyValue.text = "0"
                renderPhoto(null)

                Toast.makeText(
                    this@IssueActivity,
                    "Товар не знайдено. Додай його в каталог.",
                    Toast.LENGTH_SHORT
                ).show()
            } else {
                binding.tvNameValue.text = product.name
                binding.tvQtyValue.text = product.qty.toString()
                binding.etIssueQty.setText("1")

                // показ фото (якщо є)
                renderPhoto(product.photoUri)
            }
        }
    }

    private fun renderPhoto(photoUri: String?) {
        // ВАЖЛИВО: ці id повинні бути в activity_issue.xml:
        // ivIssuePhoto і tvIssuePhotoHint
        val iv = binding.ivIssuePhoto
        val tv = binding.tvIssuePhotoHint

        if (photoUri.isNullOrBlank()) {
            iv.setImageDrawable(null)
            iv.visibility = View.GONE
            tv.visibility = View.VISIBLE
            tv.text = "Фото не додано"
            return
        }

        try {
            iv.setImageURI(Uri.parse(photoUri))
            iv.visibility = View.VISIBLE
            tv.visibility = View.GONE
        } catch (_: Exception) {
            iv.setImageDrawable(null)
            iv.visibility = View.GONE
            tv.visibility = View.VISIBLE
            tv.text = "Не вдалося відкрити фото"
        }
    }

    private fun issue() {
        val barcode = currentBarcode?.trim()
        if (barcode.isNullOrEmpty()) {
            Toast.makeText(this, "Спочатку відскануй товар", Toast.LENGTH_SHORT).show()
            return
        }

        val qtyStr = binding.etIssueQty.text?.toString()?.trim().orEmpty()
        val delta = qtyStr.toIntOrNull()
        if (delta == null || delta <= 0) {
            Toast.makeText(this, "Введи кількість для видачі", Toast.LENGTH_SHORT).show()
            return
        }

        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            val now = System.currentTimeMillis()

            val ok = withContext(Dispatchers.IO) {
                dao.decrementQtyIfEnough(barcode, delta, now) > 0
            }

            if (ok) {
                Toast.makeText(this@IssueActivity, "Видано: $delta", Toast.LENGTH_SHORT).show()

                // автосинхронізація після видачі
                SyncManager.requestSync(applicationContext)

                loadProduct(barcode)
            } else {
                Toast.makeText(
                    this@IssueActivity,
                    "Немає товару або недостатній залишок",
                    Toast.LENGTH_SHORT
                ).show()
                loadProduct(barcode)
            }
        }
    }
}
