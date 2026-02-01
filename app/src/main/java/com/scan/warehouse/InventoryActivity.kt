package com.scan.warehouse

import android.content.Intent
import androidx.appcompat.app.AlertDialog
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.widget.doAfterTextChanged
import androidx.recyclerview.widget.LinearLayoutManager
import com.scan.warehouse.data.AppDatabase
import com.scan.warehouse.databinding.ActivityInventoryBinding
import com.scan.warehouse.ui.ProductAdapter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class InventoryActivity : AppCompatActivity() {

    private lateinit var binding: ActivityInventoryBinding
    private lateinit var adapter: ProductAdapter
    private var searchJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityInventoryBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        adapter = ProductAdapter(
            onClick = { p ->
                startActivity(
                    Intent(this, AddProductActivity::class.java)
                        .putExtra(AddProductActivity.EXTRA_BARCODE, p.barcode)
                )
            },
            onLongClick = { p ->
                AlertDialog.Builder(this)
                    .setTitle("Видалити товар?")
                    .setMessage(p.name + "\n" + p.barcode)
                    .setPositiveButton("Видалити") { _, _ ->
                        deleteProduct(p.barcode)
                    }
                    .setNegativeButton("Скасувати", null)
                    .show()

            }
        )
binding.rvProducts.layoutManager = LinearLayoutManager(this)
        binding.rvProducts.adapter = adapter

        binding.etSearch.doAfterTextChanged {
            scheduleSearch(it?.toString().orEmpty())
        }
    }

    override fun onResume() {
        super.onResume()
        scheduleSearch(binding.etSearch.text?.toString().orEmpty(), immediate = true)
    }

    private fun scheduleSearch(query: String, immediate: Boolean = false) {
        searchJob?.cancel()
        searchJob = CoroutineScope(Dispatchers.Main).launch {
            if (!immediate) delay(250)
            val dao = AppDatabase.get(applicationContext).productDao()
            val list = withContext(Dispatchers.IO) {
                val q = query.trim()
                if (q.isEmpty()) dao.getAll()
                else dao.search("%$q%")
            }
            adapter.submit(list)
        }
    }
    private fun deleteProduct(barcode: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            withContext(Dispatchers.IO) { dao.deleteByBarcode(barcode) }
            scheduleSearch(binding.etSearch.text?.toString().orEmpty(), immediate = true)
        }
    }

}
