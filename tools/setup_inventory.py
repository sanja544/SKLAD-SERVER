from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
JAVA_BASE = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
DATA_DIR = JAVA_BASE / "data"
UI_DIR = JAVA_BASE / "ui"
LAYOUT_DIR = APP / "src" / "main" / "res" / "layout"

MAIN_ACTIVITY = JAVA_BASE / "MainActivity.kt"

DAO_FILE = DATA_DIR / "ProductDao.kt"
INVENTORY_ACTIVITY = JAVA_BASE / "InventoryActivity.kt"
INVENTORY_LAYOUT = LAYOUT_DIR / "activity_inventory.xml"
ITEM_LAYOUT = LAYOUT_DIR / "item_product.xml"
ADAPTER_FILE = UI_DIR / "ProductAdapter.kt"

# 1) DAO: додамо методи list + search
def patch_dao():
    if not DAO_FILE.exists():
        raise SystemExit(f"Not found: {DAO_FILE}")

    text = DAO_FILE.read_text(encoding="utf-8")

    # Якщо вже додано — не чіпаємо
    if "suspend fun getAll()" in text and "suspend fun search(" in text:
        return

    # Вставляємо перед закриваючою }
    insert = """
    @Query("SELECT * FROM products ORDER BY name COLLATE NOCASE ASC")
    suspend fun getAll(): List<ProductEntity>

    @Query("SELECT * FROM products WHERE name LIKE :q OR barcode LIKE :q ORDER BY name COLLATE NOCASE ASC")
    suspend fun search(q: String): List<ProductEntity>
"""
    text = re.sub(r"\n}\s*$", f"{insert}\n}}\n", text, flags=re.DOTALL)
    DAO_FILE.write_text(text, encoding="utf-8")

# 2) Layouts
INVENTORY_LAYOUT_CONTENT = """\
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/main"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:padding="16dp">

    <TextView
        android:id="@+id/tvTitle"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Склад"
        android:textSize="20sp"
        android:textStyle="bold"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilSearch"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/tvTitle"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/etSearch"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:hint="Пошук: назва або штрихкод" />
    </com.google.android.material.textfield.TextInputLayout>

    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/rvProducts"
        android:layout_width="0dp"
        android:layout_height="0dp"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/tilSearch"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

ITEM_LAYOUT_CONTENT = """\
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:padding="12dp">

    <TextView
        android:id="@+id/tvName"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Name"
        android:textStyle="bold"
        android:textSize="16sp"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvBarcode"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Barcode"
        android:textSize="12sp"
        app:layout_constraintTop_toBottomOf="@id/tvName"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvPrice"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="0.00"
        android:textStyle="bold"
        app:layout_constraintTop_toBottomOf="@id/tvBarcode"
        app:layout_constraintStart_toStartOf="parent" />

    <TextView
        android:id="@+id/tvQty"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="qty: 0"
        android:textStyle="bold"
        app:layout_constraintTop_toTopOf="@id/tvPrice"
        app:layout_constraintEnd_toEndOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

# 3) Adapter
ADAPTER_CONTENT = """\
package com.scan.warehouse.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.scan.warehouse.data.ProductEntity
import com.scan.warehouse.databinding.ItemProductBinding

class ProductAdapter(
    private val onClick: (ProductEntity) -> Unit
) : RecyclerView.Adapter<ProductAdapter.VH>() {

    private val items = ArrayList<ProductEntity>()

    fun submit(list: List<ProductEntity>) {
        items.clear()
        items.addAll(list)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val binding = ItemProductBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return VH(binding)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.bind(items[position], onClick)
    }

    override fun getItemCount(): Int = items.size

    class VH(private val b: ItemProductBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(p: ProductEntity, onClick: (ProductEntity) -> Unit) {
            b.tvName.text = p.name
            b.tvBarcode.text = p.barcode
            b.tvPrice.text = "₴ ${"%.2f".format(p.price)}"
            b.tvQty.text = "qty: ${p.qty}"
            b.root.setOnClickListener { onClick(p) }
        }
    }
}
"""

# 4) InventoryActivity
INVENTORY_ACTIVITY_CONTENT = """\
package com.scan.warehouse

import android.content.Intent
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

        adapter = ProductAdapter { p ->
            startActivity(
                Intent(this, AddProductActivity::class.java)
                    .putExtra(AddProductActivity.EXTRA_BARCODE, p.barcode)
            )
        }

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
}
"""

# 5) Patch MainActivity: додаємо кнопку "Склад" якщо нема, і відкриваємо InventoryActivity
def patch_main_activity_add_inventory_button():
    if not MAIN_ACTIVITY.exists():
        return

    text = MAIN_ACTIVITY.read_text(encoding="utf-8")

    # якщо вже є startActivity(Intent(this, InventoryActivity::class.java)) — не чіпаємо
    if "InventoryActivity::class.java" in text:
        return

    # Додаємо третю кнопку в activity_main.xml? Не тут. Тут лише підключимо, якщо кнопка вже буде.
    # Тому ми зробимо м'яко: якщо є binding.btnInventory, то додамо обробник.
    # І паралельно створимо activity_main.xml patch в окремому скрипті не будемо — просто додамо кнопку через заміну layout нижче.

    # Додамо обробник після btnIssue
    marker = "binding.btnIssue.setOnClickListener"
    if marker in text and "binding.btnInventory" not in text:
        text = text.replace(
            "binding.btnIssue.setOnClickListener {\n            startActivity(Intent(this, IssueActivity::class.java))\n        }\n",
            "binding.btnIssue.setOnClickListener {\n            startActivity(Intent(this, IssueActivity::class.java))\n        }\n\n        binding.btnInventory.setOnClickListener {\n            startActivity(Intent(this, InventoryActivity::class.java))\n        }\n"
        )

    MAIN_ACTIVITY.write_text(text, encoding="utf-8")

def patch_activity_main_xml_add_button():
    xml = LAYOUT_DIR / "activity_main.xml"
    if not xml.exists():
        return
    text = xml.read_text(encoding="utf-8")
    if "btnInventory" in text:
        return

    # Вставимо кнопку після btnIssue
    text = text.replace(
        '</Button>\n\n</androidx.constraintlayout.widget.ConstraintLayout>',
        '</Button>\n\n    <Button\n        android:id="@+id/btnInventory"\n        android:layout_width="0dp"\n        android:layout_height="wrap_content"\n        android:text="Склад"\n        android:layout_marginTop="12dp"\n        app:layout_constraintTop_toBottomOf="@id/btnIssue"\n        app:layout_constraintStart_toStartOf="parent"\n        app:layout_constraintEnd_toEndOf="parent" />\n\n</androidx.constraintlayout.widget.ConstraintLayout>'
    )
    xml.write_text(text, encoding="utf-8")

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def main():
    patch_dao()

    write_file(INVENTORY_LAYOUT, INVENTORY_LAYOUT_CONTENT)
    write_file(ITEM_LAYOUT, ITEM_LAYOUT_CONTENT)

    write_file(ADAPTER_FILE, ADAPTER_CONTENT)
    write_file(INVENTORY_ACTIVITY, INVENTORY_ACTIVITY_CONTENT)

    patch_activity_main_xml_add_button()
    patch_main_activity_add_inventory_button()

    print("OK: InventoryActivity + layouts + adapter + DAO updated + MainActivity updated")

if __name__ == "__main__":
    main()
