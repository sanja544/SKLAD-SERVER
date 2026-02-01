from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
JAVA_BASE = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
DATA_DIR = JAVA_BASE / "data"
LAYOUT_DIR = APP / "src" / "main" / "res" / "layout"
XML_DIR = APP / "src" / "main" / "res" / "xml"
MANIFEST = APP / "src" / "main" / "AndroidManifest.xml"

PRODUCT_ENTITY = DATA_DIR / "ProductEntity.kt"
APP_DB = DATA_DIR / "AppDatabase.kt"
ADD_PRODUCT = JAVA_BASE / "AddProductActivity.kt"
ADD_PRODUCT_XML = LAYOUT_DIR / "activity_add_product.xml"
FILE_PATHS_XML = XML_DIR / "file_paths.xml"

PRODUCT_ENTITY_CONTENT = """\
package com.scan.warehouse.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "products")
data class ProductEntity(
    @PrimaryKey val barcode: String,
    val name: String,
    val price: Double,
    val qty: Int,
    val photoUri: String? = null
)
"""

APP_DB_CONTENT = """\
package com.scan.warehouse.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [ProductEntity::class], version = 2)
abstract class AppDatabase : RoomDatabase() {

    abstract fun productDao(): ProductDao

    companion object {
        @Volatile private var INSTANCE: AppDatabase? = null

        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE products ADD COLUMN photoUri TEXT")
            }
        }

        fun get(context: Context): AppDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "warehouse.db"
                ).addMigrations(MIGRATION_1_2)
                 .build()
                 .also { INSTANCE = it }
            }
    }
}
"""

ADD_PRODUCT_ACTIVITY_CONTENT = """\
package com.scan.warehouse

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.scan.warehouse.data.AppDatabase
import com.scan.warehouse.data.ProductEntity
import com.scan.warehouse.databinding.ActivityAddProductBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class AddProductActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAddProductBinding

    private var currentBarcode: String? = null
    private var currentPhotoUri: String? = null
    private var pendingCameraUri: Uri? = null

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

    private val takePicture =
        registerForActivityResult(ActivityResultContracts.TakePicture()) { success ->
            val uri = pendingCameraUri
            if (success && uri != null) {
                setPhoto(uri)
            }
            pendingCameraUri = null
        }

    private val pickPhoto =
        registerForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
            if (uri != null) {
                setPhoto(uri)
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

        binding.btnPhotoCamera.setOnClickListener {
            launchCamera()
        }

        binding.btnPhotoGallery.setOnClickListener {
            pickPhoto.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        }

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

    private fun setPhoto(uri: Uri) {
        currentPhotoUri = uri.toString()
        binding.ivPhoto.setImageURI(uri)
        binding.tvPhotoHint.text = ""
    }

    private fun clearPhoto() {
        currentPhotoUri = null
        binding.ivPhoto.setImageDrawable(null)
        binding.tvPhotoHint.text = "Фото не вибрано"
    }

    private fun launchCamera() {
        val uri = createImageUri() ?: run {
            Toast.makeText(this, "Не можу створити файл фото", Toast.LENGTH_SHORT).show()
            return
        }
        pendingCameraUri = uri
        takePicture.launch(uri)
    }

    private fun createImageUri(): Uri? {
        val picturesDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: return null
        val imagesDir = File(picturesDir, "images").apply { mkdirs() }
        val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val file = File(imagesDir, "IMG_$ts.jpg")
        return FileProvider.getUriForFile(
            this,
            "${applicationId}.fileprovider",
            file
        )
    }

    private fun loadIfExists(barcode: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            val existing = withContext(Dispatchers.IO) { dao.getByBarcode(barcode) }

            if (existing != null) {
                binding.etName.setText(existing.name)
                binding.etPrice.setText(existing.price.toString())
                binding.etQty.setText(existing.qty.toString())

                val p = existing.photoUri
                if (!p.isNullOrBlank()) {
                    setPhoto(Uri.parse(p))
                } else {
                    clearPhoto()
                }

                Toast.makeText(this@AddProductActivity, "Товар вже є — відредагуй і збережи", Toast.LENGTH_SHORT).show()
            } else {
                binding.etName.setText("")
                binding.etPrice.setText("")
                binding.etQty.setText("1")
                clearPhoto()
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
            qty = qty,
            photoUri = currentPhotoUri
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

ADD_PRODUCT_XML_CONTENT = """\
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

    <FrameLayout
        android:id="@+id/photoBox"
        android:layout_width="0dp"
        android:layout_height="180dp"
        android:layout_marginTop="12dp"
        android:background="@android:color/darker_gray"
        app:layout_constraintTop_toBottomOf="@id/btnScan"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <ImageView
            android:id="@+id/ivPhoto"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:scaleType="centerCrop" />

        <TextView
            android:id="@+id/tvPhotoHint"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:gravity="center"
            android:text="Фото не вибрано"
            android:textColor="@android:color/white"
            android:textStyle="bold" />
    </FrameLayout>

    <Button
        android:id="@+id/btnPhotoCamera"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Фото з камери"
        android:layout_marginTop="10dp"
        app:layout_constraintTop_toBottomOf="@id/photoBox"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toStartOf="@id/btnPhotoGallery"
        app:layout_constraintWidth_percent="0.5" />

    <Button
        android:id="@+id/btnPhotoGallery"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Фото з галереї"
        android:layout_marginTop="10dp"
        app:layout_constraintTop_toBottomOf="@id/photoBox"
        app:layout_constraintStart_toEndOf="@id/btnPhotoCamera"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintWidth_percent="0.5" />

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilName"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/btnPhotoCamera"
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
    </com.google.android.material.textfield.TextInputEditText>
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
    </com.google.android.material.textfield.TextInputEditText>
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

FILE_PATHS_XML_CONTENT = """\
<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <external-files-path
        name="images"
        path="Pictures/images/" />
</paths>
"""

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def ensure_fileprovider_in_manifest():
    if not MANIFEST.exists():
        raise SystemExit(f"Not found: {MANIFEST}")
    text = MANIFEST.read_text(encoding="utf-8")

    if "androidx.core.content.FileProvider" in text:
        return

    provider_block = """
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>
"""

    # Insert before </application>
    text = re.sub(r"\s*</application>", f"{provider_block}\n    </application>", text, flags=re.DOTALL)
    MANIFEST.write_text(text, encoding="utf-8")

def main():
    write_file(PRODUCT_ENTITY, PRODUCT_ENTITY_CONTENT)
    write_file(APP_DB, APP_DB_CONTENT)
    write_file(ADD_PRODUCT, ADD_PRODUCT_ACTIVITY_CONTENT)
    write_file(ADD_PRODUCT_XML, ADD_PRODUCT_XML_CONTENT)
    write_file(FILE_PATHS_XML, FILE_PATHS_XML_CONTENT)
    ensure_fileprovider_in_manifest()
    print("OK: photos added (DB migration + AddProduct UI + FileProvider). Sync/Run.")

if __name__ == "__main__":
    main()
