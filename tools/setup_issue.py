from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
JAVA_BASE = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
DATA_DIR = JAVA_BASE / "data"
LAYOUT_DIR = APP / "src" / "main" / "res" / "layout"

MAIN_ACTIVITY = JAVA_BASE / "MainActivity.kt"
ISSUE_ACTIVITY = JAVA_BASE / "IssueActivity.kt"
ISSUE_LAYOUT = LAYOUT_DIR / "activity_issue.xml"
DAO_FILE = DATA_DIR / "ProductDao.kt"

ISSUE_ACTIVITY_CONTENT = """\
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
"""

ISSUE_LAYOUT_CONTENT = """\
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
        android:text="Видача зі складу"
        android:textSize="20sp"
        android:textStyle="bold"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvBarcodeLabel"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Штрихкод:"
        android:layout_marginTop="16dp"
        app:layout_constraintTop_toBottomOf="@id/tvTitle"
        app:layout_constraintStart_toStartOf="parent" />

    <TextView
        android:id="@+id/tvBarcodeValue"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="—"
        android:textStyle="bold"
        android:layout_marginStart="8dp"
        app:layout_constraintTop_toTopOf="@id/tvBarcodeLabel"
        app:layout_constraintBottom_toBottomOf="@id/tvBarcodeLabel"
        app:layout_constraintStart_toEndOf="@id/tvBarcodeLabel"
        app:layout_constraintEnd_toEndOf="parent" />

    <Button
        android:id="@+id/btnScan"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Сканувати"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/tvBarcodeLabel"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvNameLabel"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Назва:"
        android:layout_marginTop="16dp"
        app:layout_constraintTop_toBottomOf="@id/btnScan"
        app:layout_constraintStart_toStartOf="parent" />

    <TextView
        android:id="@+id/tvNameValue"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="—"
        android:textStyle="bold"
        android:layout_marginStart="8dp"
        app:layout_constraintTop_toTopOf="@id/tvNameLabel"
        app:layout_constraintBottom_toBottomOf="@id/tvNameLabel"
        app:layout_constraintStart_toEndOf="@id/tvNameLabel"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvQtyLabel"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Залишок:"
        android:layout_marginTop="10dp"
        app:layout_constraintTop_toBottomOf="@id/tvNameLabel"
        app:layout_constraintStart_toStartOf="parent" />

    <TextView
        android:id="@+id/tvQtyValue"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="—"
        android:textStyle="bold"
        android:layout_marginStart="8dp"
        app:layout_constraintTop_toTopOf="@id/tvQtyLabel"
        app:layout_constraintBottom_toBottomOf="@id/tvQtyLabel"
        app:layout_constraintStart_toEndOf="@id/tvQtyLabel"
        app:layout_constraintEnd_toEndOf="parent" />

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilIssueQty"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp"
        app:layout_constraintTop_toBottomOf="@id/tvQtyLabel"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/etIssueQty"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:inputType="number"
            android:hint="Кількість для видачі" />
    </com.google.android.material.textfield.TextInputLayout>

    <Button
        android:id="@+id/btnIssue"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Видати"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/tilIssueQty"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

DAO_REPLACEMENT = """\
package com.scan.warehouse.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface ProductDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(product: ProductEntity)

    @Query("SELECT * FROM products WHERE barcode = :barcode LIMIT 1")
    suspend fun getByBarcode(barcode: String): ProductEntity?

    // Повертає 1 якщо списало, 0 якщо товару нема або недостатній залишок
    @Query("UPDATE products SET qty = qty - :delta WHERE barcode = :barcode AND qty >= :delta")
    suspend fun decrementQtyIfEnough(barcode: String, delta: Int): Int
}
"""

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def patch_main_activity():
    if not MAIN_ACTIVITY.exists():
        return
    text = MAIN_ACTIVITY.read_text(encoding="utf-8")
    text = re.sub(
        r'binding\.btnIssue\.setOnClickListener\s*\{\s*scanLauncher\.launch\(Intent\(this,\s*ScannerActivity::class\.java\)\)\s*\}',
        'binding.btnIssue.setOnClickListener {\n            startActivity(Intent(this, IssueActivity::class.java))\n        }',
        text,
        flags=re.DOTALL
    )
    MAIN_ACTIVITY.write_text(text, encoding="utf-8")

def main():
    write_file(DAO_FILE, DAO_REPLACEMENT)
    write_file(ISSUE_ACTIVITY, ISSUE_ACTIVITY_CONTENT)
    write_file(ISSUE_LAYOUT, ISSUE_LAYOUT_CONTENT)
    patch_main_activity()
    print("OK: IssueActivity + layout + ProductDao updated + MainActivity button patched")

if __name__ == "__main__":
    main()
