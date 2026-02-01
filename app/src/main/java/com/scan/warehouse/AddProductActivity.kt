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
                val local = copyIntoAppPictures(uri)
                if (local != null) {
                    setPhoto(local)
                } else {
                    Toast.makeText(this, "Не вдалося зберегти фото", Toast.LENGTH_SHORT).show()
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
    private fun copyIntoAppPictures(source: Uri): Uri? {
        return try {
            val picturesDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: return null
            val imagesDir = File(picturesDir, "images").apply { mkdirs() }

            val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val destFile = File(imagesDir, "IMG_IMPORT_$ts.jpg")

            contentResolver.openInputStream(source)?.use { input ->
                destFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            } ?: return null

            FileProvider.getUriForFile(this, "${packageName}.fileprovider", destFile)
        } catch (e: Exception) {
            null
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
            "${packageName}.fileprovider",
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
