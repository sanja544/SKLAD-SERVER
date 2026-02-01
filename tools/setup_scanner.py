from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
MANIFEST = APP / "src" / "main" / "AndroidManifest.xml"
JAVA_DIR = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
LAYOUT_DIR = APP / "src" / "main" / "res" / "layout"

SCANNER_ACTIVITY_KT = JAVA_DIR / "ScannerActivity.kt"
MAIN_ACTIVITY_KT = JAVA_DIR / "MainActivity.kt"
ACTIVITY_SCANNER_XML = LAYOUT_DIR / "activity_scanner.xml"
ACTIVITY_MAIN_XML = LAYOUT_DIR / "activity_main.xml"


MAIN_ACTIVITY_CONTENT = """\
package com.scan.warehouse

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.scan.warehouse.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val scanLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
            if (res.resultCode == RESULT_OK) {
                val barcode = res.data?.getStringExtra(ScannerActivity.EXTRA_BARCODE)
                if (!barcode.isNullOrBlank()) {
                    Toast.makeText(this, "Штрихкод: $barcode", Toast.LENGTH_LONG).show()
                }
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        binding.btnAddProduct.setOnClickListener {
            scanLauncher.launch(Intent(this, ScannerActivity::class.java))
        }

        binding.btnIssue.setOnClickListener {
            scanLauncher.launch(Intent(this, ScannerActivity::class.java))
        }
    }
}
"""

ACTIVITY_MAIN_CONTENT = """\
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
        android:text="WarehouseScanner"
        android:textSize="22sp"
        android:textStyle="bold"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <Button
        android:id="@+id/btnAddProduct"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Додати товар (скан)"
        android:layout_marginTop="16dp"
        app:layout_constraintTop_toBottomOf="@id/tvTitle"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <Button
        android:id="@+id/btnIssue"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Видача (скан)"
        android:layout_marginTop="12dp"
        app:layout_constraintTop_toBottomOf="@id/btnAddProduct"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

SCANNER_ACTIVITY_CONTENT = """\
package com.scan.warehouse

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.scan.warehouse.databinding.ActivityScannerBinding
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class ScannerActivity : AppCompatActivity() {

    private lateinit var binding: ActivityScannerBinding
    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private val finished = AtomicBoolean(false)

    private val requestPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startCamera() else finish()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityScannerBinding.inflate(layoutInflater)
        setContentView(binding.root)

        if (hasCameraPermission()) startCamera()
        else requestPermission.launch(Manifest.permission.CAMERA)
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)

        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()

            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.previewView.surfaceProvider)
            }

            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            val scanner = BarcodeScanning.getClient()

            analysis.setAnalyzer(cameraExecutor) { imageProxy ->
                val mediaImage = imageProxy.image
                if (mediaImage == null) {
                    imageProxy.close()
                    return@setAnalyzer
                }

                val image = InputImage.fromMediaImage(
                    mediaImage,
                    imageProxy.imageInfo.rotationDegrees
                )

                scanner.process(image)
                    .addOnSuccessListener { barcodes ->
                        if (finished.get()) return@addOnSuccessListener
                        val raw = barcodes.firstOrNull()?.rawValue?.trim()
                        if (!raw.isNullOrEmpty()) {
                            finished.set(true)
                            setResult(RESULT_OK, Intent().putExtra(EXTRA_BARCODE, raw))
                            finish()
                        }
                    }
                    .addOnCompleteListener {
                        imageProxy.close()
                    }
            }

            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(
                this,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview,
                analysis
            )
        }, ContextCompat.getMainExecutor(this))
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
    }

    companion object {
        const val EXTRA_BARCODE = "extra_barcode"
    }
}
"""

ACTIVITY_SCANNER_CONTENT = """\
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <androidx.camera.view.PreviewView
        android:id="@+id/previewView"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />

    <TextView
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:padding="14dp"
        android:text="Наведи камеру на штрихкод"
        android:textColor="#FFFFFF"
        android:background="#66000000" />

</FrameLayout>
"""


def ensure_dirs():
    JAVA_DIR.mkdir(parents=True, exist_ok=True)
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_manifest():
    if not MANIFEST.exists():
        # Мінімальний manifest, якщо його ще нема.
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text("""\
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.CAMERA" />

    <uses-feature
        android:name="android.hardware.camera.any"
        android:required="true" />

    <application
        android:allowBackup="true"
        android:label="WarehouseScanner"
        android:supportsRtl="true"
        android:theme="@style/Theme.WarehouseScanner">

        <activity
            android:name=".ScannerActivity"
            android:exported="false" />

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

    </application>

</manifest>
""", encoding="utf-8")
        return

    text = MANIFEST.read_text(encoding="utf-8")

    # CAMERA permission
    if 'android.permission.CAMERA' not in text:
        text = re.sub(
            r'(<manifest[^>]*>\s*)',
            r'\\1\n    <uses-permission android:name="android.permission.CAMERA" />\n',
            text,
            flags=re.DOTALL
        )

    # uses-feature camera.any
    if "android.hardware.camera.any" not in text:
        # Після permission або після <manifest>
        if "uses-permission" in text:
            text = re.sub(
                r'(<uses-permission[^>]*CAMERA[^>]*/>\s*)',
                r'\\1\n    <uses-feature\n        android:name="android.hardware.camera.any"\n        android:required="true" />\n',
                text,
                flags=re.DOTALL
            )
        else:
            text = re.sub(
                r'(<manifest[^>]*>\s*)',
                r'\\1\n    <uses-feature\n        android:name="android.hardware.camera.any"\n        android:required="true" />\n',
                text,
                flags=re.DOTALL
            )

    # Додати ScannerActivity якщо нема
    if 'android:name=".ScannerActivity"' not in text:
        text = re.sub(
            r'(<application[^>]*>\s*)',
            r'\\1\n        <activity\n            android:name=".ScannerActivity"\n            android:exported="false" />\n',
            text,
            flags=re.DOTALL
        )

    # Додати android:exported="false" для активіті без exported
    def add_exported_false(m: re.Match) -> str:
        tag = m.group(0)
        if "android:exported=" in tag:
            return tag
        # якщо є intent-filter — це має бути exported=true (але це зазвичай MainActivity)
        if "<intent-filter" in tag:
            return tag
        # самозакривний
        if tag.endswith("/>"):
            return tag[:-2] + '\n            android:exported="false" />'
        return tag

    text = re.sub(
        r'<activity\b(?![^>]*android:exported=)[^>]*?/>',
        add_exported_false,
        text,
        flags=re.DOTALL
    )

    # Якщо MainActivity має intent-filter — постав exported=true
    text = re.sub(
        r'(<activity\b[^>]*android:name="\.MainActivity"(?![^>]*android:exported=)[^>]*>)',
        r'\\1',
        text
    )
    # Якщо exported є, але не true — виправити на true (лише для MainActivity)
    text = re.sub(
        r'(<activity\b[^>]*android:name="\.MainActivity"[^>]*android:exported=")(false)(")',
        r'\\1true\\3',
        text
    )
    # Якщо MainActivity без exported взагалі — додати
    text = re.sub(
        r'(<activity\b[^>]*android:name="\.MainActivity")(?![^>]*android:exported=)([^>]*>)',
        r'\\1 android:exported="true"\\2',
        text
    )

    MANIFEST.write_text(text, encoding="utf-8")


def main():
    settings = ROOT / "settings.gradle.kts"
    if not settings.exists():
        raise SystemExit(f"Не знайдено {settings}. Перевір ROOT у скрипті.")

    ensure_dirs()

    write_file(SCANNER_ACTIVITY_KT, SCANNER_ACTIVITY_CONTENT)
    write_file(ACTIVITY_SCANNER_XML, ACTIVITY_SCANNER_CONTENT)

    write_file(MAIN_ACTIVITY_KT, MAIN_ACTIVITY_CONTENT)
    write_file(ACTIVITY_MAIN_XML, ACTIVITY_MAIN_CONTENT)

    patch_manifest()

    print("OK:")
    print(f"- wrote {SCANNER_ACTIVITY_KT}")
    print(f"- wrote {ACTIVITY_SCANNER_XML}")
    print(f"- wrote {MAIN_ACTIVITY_KT}")
    print(f"- wrote {ACTIVITY_MAIN_XML}")
    print(f"- patched {MANIFEST}")


if __name__ == "__main__":
    main()
