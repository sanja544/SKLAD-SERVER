package com.scan.warehouse

import android.content.Intent
import android.os.Bundle
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
    }

    private fun setBarcode(barcode: String) {
        currentBarcode = barcode
        binding.tvBarcodeValue.text = barcode
        binding.tvNameValue.text = "—"
        binding.tvQtyValue.text = "—"
    }

    private fun loadProduct(barcode: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            val product = withContext(Dispatchers.IO) { dao.getByBarcode(barcode) }

            if (product == null) {
                binding.tvNameValue.text = "НЕ ЗНАЙДЕНО"
                binding.tvQtyValue.text = "0"
                Toast.makeText(this@IssueActivity, "Товар не знайдено. Додай його в каталог.", Toast.LENGTH_SHORT).show()
            } else {
                binding.tvNameValue.text = product.name
                binding.tvQtyValue.text = product.qty.toString()
                binding.etIssueQty.setText("1")
            }
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

            val ok = withContext(Dispatchers.IO) {
                // 1) якщо товару нема — поверне 0
                // 2) якщо не вистачає — поверне 0
                dao.decrementQtyIfEnough(barcode, delta) > 0
            }

            if (ok) {
                Toast.makeText(this@IssueActivity, "Видано: $delta", Toast.LENGTH_SHORT).show()
                loadProduct(barcode) // оновити залишок
            } else {
                Toast.makeText(this@IssueActivity, "Немає товару або недостатній залишок", Toast.LENGTH_SHORT).show()
                loadProduct(barcode)
            }
        }
    }
}
