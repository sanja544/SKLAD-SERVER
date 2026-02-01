from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
JAVA_BASE = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
DATA_DIR = JAVA_BASE / "data"
LAYOUT_DIR = APP / "src" / "main" / "res" / "layout"
MANIFEST = APP / "src" / "main" / "AndroidManifest.xml"
APP_GRADLE = APP / "build.gradle.kts"
MAIN_ACTIVITY = JAVA_BASE / "MainActivity.kt"

# ---------- Room files (create if missing) ----------
ROOM_FILES = {
    DATA_DIR / "ProductEntity.kt": """\
package com.scan.warehouse.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "products")
data class ProductEntity(
    @PrimaryKey val barcode: String,
    val name: String,
    val price: Double,
    val qty: Int
)
""",
    DATA_DIR / "ProductDao.kt": """\
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
}
""",
    DATA_DIR / "AppDatabase.kt": """\
package com.scan.warehouse.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [ProductEntity::class], version = 1)
abstract class AppDatabase : RoomDatabase() {

    abstract fun productDao(): ProductDao

    companion object {
        @Volatile private var INSTANCE: AppDatabase? = null

        fun get(context: Context): AppDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "warehouse.db"
                ).build().also { INSTANCE = it }
            }
    }
}
"""
}

# ---------- AddProductActivity + layout ----------
ADD_PRODUCT_ACTIVITY = JAVA_BASE / "AddProductActivity.kt"
ADD_PRODUCT_LAYOUT = LAYOUT_DIR / "activity_add_product.xml"

ADD_PRODUCT_ACTIVITY_CONTENT = """\
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
import com.scan.warehouse.data.ProductEntity
import com.scan.warehouse.databinding.ActivityAddProductBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class AddProductActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAddProductBinding
    private var currentBarcode: String? = null

    private val scanLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
            if (res.resultCode == RESULT_OK) {
                val barcode = res.data?.getStringExtra(ScannerActivity.EXTRA_BARCODE)
                if (!barcode.isNullOrBlank()) {
                    setBarcode(barcode)
                    loadIfExists(barcode)
                }
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityAddProductBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        binding.btnScan.setOnClickListener {
            scanLauncher.launch(Intent(this, ScannerActivity::class.java))
        }

        binding.btnSave.setOnClickListener {
            save()
        }

        // Якщо передали barcode з іншого місця (на майбутнє)
        val fromIntent = intent.getStringExtra(EXTRA_BARCODE)?.trim()
        if (!fromIntent.isNullOrEmpty()) {
            setBarcode(fromIntent)
            loadIfExists(fromIntent)
        }
    }

    private fun setBarcode(barcode: String) {
        currentBarcode = barcode
        binding.tvBarcodeValue.text = barcode
    }

    private fun loadIfExists(barcode: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            val existing = withContext(Dispatchers.IO) { dao.getByBarcode(barcode) }
            if (existing != null) {
                binding.etName.setText(existing.name)
                binding.etPrice.setText(existing.price.toString())
                binding.etQty.setText(existing.qty.toString())
                Toast.makeText(this@AddProductActivity, "Товар вже є — відредагуй і збережи", Toast.LENGTH_SHORT).show()
            } else {
                binding.etName.setText("")
                binding.etPrice.setText("")
                binding.etQty.setText("1")
            }
        }
    }

    private fun save() {
        val barcode = currentBarcode?.trim()
        if (barcode.isNullOrEmpty()) {
            Toast.makeText(this, "Спочатку відскануй штрихкод", Toast.LENGTH_SHORT).show()
            return
        }

        val name = binding.etName.text?.toString()?.trim().orEmpty()
        if (name.isEmpty()) {
            Toast.makeText(this, "Введи назву", Toast.LENGTH_SHORT).show()
            return
        }

        val priceStr = binding.etPrice.text?.toString()?.trim().orEmpty().replace(",", ".")
        val price = priceStr.toDoubleOrNull()
        if (price == null) {
            Toast.makeText(this, "Невірна ціна", Toast.LENGTH_SHORT).show()
            return
        }

        val qtyStr = binding.etQty.text?.toString()?.trim().orEmpty()
        val qty = qtyStr.toIntOrNull()
        if (qty == null || qty < 0) {
            Toast.makeText(this, "Невірна кількість", Toast.LENGTH_SHORT).show()
            return
        }

        val product = ProductEntity(
            barcode = barcode,
            name = name,
            price = price,
            qty = qty
        )

        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            withContext(Dispatchers.IO) { dao.upsert(product) }
            Toast.makeText(this@AddProductActivity, "Збережено", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    companion object {
        const val EXTRA_BARCODE = "extra_barcode"
    }
}
"""

ADD_PRODUCT_LAYOUT_CONTENT = """\
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
        android:text="Додати / Редагувати товар"
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

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilName"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/btnScan"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/etName"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:hint="Назва" />
    </com.google.android.material.textfield.TextInputLayout>

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilPrice"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="8dp"
        app:layout_constraintTop_toBottomOf="@id/tilName"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/etPrice"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:inputType="numberDecimal"
            android:hint="Ціна" />
    </com.google.android.material.textfield.TextInputLayout>

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilQty"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="8dp"
        app:layout_constraintTop_toBottomOf="@id/tilPrice"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/etQty"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:inputType="number"
            android:hint="Кількість" />
    </com.google.android.material.textfield.TextInputLayout>

    <Button
        android:id="@+id/btnSave"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Зберегти"
        android:layout_marginTop="16dp"
        app:layout_constraintTop_toBottomOf="@id/tilQty"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

# ---------- Patch MainActivity button to open AddProductActivity ----------
def patch_main_activity():
    if not MAIN_ACTIVITY.exists():
        return

    text = MAIN_ACTIVITY.read_text(encoding="utf-8")

    # Replace only the AddProduct button click body
    text = re.sub(
        r'binding\.btnAddProduct\.setOnClickListener\s*\{\s*scanLauncher\.launch\(Intent\(this,\s*ScannerActivity::class\.java\)\)\s*\}',
        'binding.btnAddProduct.setOnClickListener {\n            startActivity(Intent(this, AddProductActivity::class.java))\n        }',
        text,
        flags=re.DOTALL
    )

    MAIN_ACTIVITY.write_text(text, encoding="utf-8")

# ---------- Ensure AddProductActivity in manifest ----------
def patch_manifest():
    if not MANIFEST.exists():
        return
    text = MANIFEST.read_text(encoding="utf-8")

    if 'android:name=".AddProductActivity"' not in text:
        # Insert before MainActivity
        text = re.sub(
            r'(\s*<activity\s+android:name="\.MainActivity")',
            '\n        <activity\n            android:name=".AddProductActivity"\n            android:exported="false" />\n\n\\1',
            text
        )
        MANIFEST.write_text(text, encoding="utf-8")

def ensure_room_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in ROOM_FILES.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")

def write_add_product_files():
    JAVA_BASE.mkdir(parents=True, exist_ok=True)
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    ADD_PRODUCT_ACTIVITY.write_text(ADD_PRODUCT_ACTIVITY_CONTENT, encoding="utf-8")
    ADD_PRODUCT_LAYOUT.write_text(ADD_PRODUCT_LAYOUT_CONTENT, encoding="utf-8")

def main():
    ensure_room_files()
    write_add_product_files()
    patch_manifest()
    patch_main_activity()
    print("OK:")
    print(f"- created/updated: {ADD_PRODUCT_ACTIVITY}")
    print(f"- created/updated: {ADD_PRODUCT_LAYOUT}")
    print(f"- ensured Room files in: {DATA_DIR}")
    print(f"- patched MainActivity button: {MAIN_ACTIVITY}")
    print(f"- ensured manifest entry: {MANIFEST}")

if __name__ == "__main__":
    main()
