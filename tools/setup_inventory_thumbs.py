from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
JAVA_BASE = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
UI_DIR = JAVA_BASE / "ui"
LAYOUT_DIR = APP / "src" / "main" / "res" / "layout"
MANIFEST = APP / "src" / "main" / "AndroidManifest.xml"

ITEM_LAYOUT = LAYOUT_DIR / "item_product.xml"
ADAPTER_FILE = UI_DIR / "ProductAdapter.kt"
INVENTORY_ACTIVITY = JAVA_BASE / "InventoryActivity.kt"
PHOTO_ACTIVITY = JAVA_BASE / "PhotoViewActivity.kt"
PHOTO_LAYOUT = LAYOUT_DIR / "activity_photo_view.xml"

ITEM_LAYOUT_CONTENT = """<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:padding="12dp">

    <ImageView
        android:id="@+id/ivThumb"
        android:layout_width="56dp"
        android:layout_height="56dp"
        android:scaleType="centerCrop"
        android:contentDescription="Фото"
        android:visibility="gone"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent" />

    <TextView
        android:id="@+id/tvName"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Name"
        android:textStyle="bold"
        android:textSize="16sp"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toEndOf="@id/ivThumb"
        app:layout_constraintEnd_toEndOf="parent"
        android:layout_marginStart="12dp" />

    <TextView
        android:id="@+id/tvBarcode"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="Barcode"
        android:textSize="12sp"
        app:layout_constraintTop_toBottomOf="@id/tvName"
        app:layout_constraintStart_toStartOf="@id/tvName"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvPrice"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="0.00"
        android:textStyle="bold"
        app:layout_constraintTop_toBottomOf="@id/tvBarcode"
        app:layout_constraintStart_toStartOf="@id/tvName" />

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

ADAPTER_CONTENT = """package com.scan.warehouse.ui

import android.net.Uri
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.scan.warehouse.data.ProductEntity
import com.scan.warehouse.databinding.ItemProductBinding

class ProductAdapter(
    private val onClick: (ProductEntity) -> Unit,
    private val onLongClick: (ProductEntity) -> Unit,
    private val onPhotoClick: (String) -> Unit
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
        holder.bind(items[position], onClick, onLongClick, onPhotoClick)
    }

    override fun getItemCount(): Int = items.size

    class VH(private val b: ItemProductBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(
            p: ProductEntity,
            onClick: (ProductEntity) -> Unit,
            onLongClick: (ProductEntity) -> Unit,
            onPhotoClick: (String) -> Unit
        ) {
            b.tvName.text = p.name
            b.tvBarcode.text = p.barcode
            b.tvPrice.text = "₴ ${"%.2f".format(p.price)}"
            b.tvQty.text = "qty: ${p.qty}"

            val uriStr = p.photoUri
            if (!uriStr.isNullOrBlank()) {
                b.ivThumb.visibility = View.VISIBLE
                b.ivThumb.setImageURI(Uri.parse(uriStr))
                b.ivThumb.setOnClickListener { onPhotoClick(uriStr) }
            } else {
                b.ivThumb.visibility = View.GONE
                b.ivThumb.setImageDrawable(null)
                b.ivThumb.setOnClickListener(null)
            }

            b.root.setOnClickListener { onClick(p) }
            b.root.setOnLongClickListener { onLongClick(p); true }
        }
    }
}
"""

PHOTO_ACTIVITY_CONTENT = """package com.scan.warehouse

import android.net.Uri
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.scan.warehouse.databinding.ActivityPhotoViewBinding

class PhotoViewActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPhotoViewBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityPhotoViewBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.main) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        val uriStr = intent.getStringExtra(EXTRA_URI)
        if (!uriStr.isNullOrBlank()) {
            binding.ivFull.setImageURI(Uri.parse(uriStr))
            binding.tvNoPhoto.text = ""
        } else {
            binding.tvNoPhoto.text = "Нема фото"
        }

        binding.btnBack.setOnClickListener { finish() }
    }

    companion object {
        const val EXTRA_URI = "extra_photo_uri"
    }
}
"""

PHOTO_LAYOUT_CONTENT = """<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/main"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <ImageView
        android:id="@+id/ivFull"
        android:layout_width="0dp"
        android:layout_height="0dp"
        android:scaleType="fitCenter"
        android:contentDescription="Фото"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/tvNoPhoto"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text=""
        android:textSize="18sp"
        android:textStyle="bold"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <Button
        android:id="@+id/btnBack"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Назад"
        android:layout_margin="12dp"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
"""

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def patch_inventory_activity():
    if not INVENTORY_ACTIVITY.exists():
        raise SystemExit(f"Not found: {INVENTORY_ACTIVITY}")
    text = INVENTORY_ACTIVITY.read_text(encoding="utf-8")

    # Якщо вже є PhotoViewActivity — не чіпаємо
    if "PhotoViewActivity::class.java" in text:
        return

    # Заміна створення адаптера на версію з onPhotoClick
    # Шукаємо "adapter = ProductAdapter(" або "adapter = ProductAdapter {"
    if "adapter = ProductAdapter(" in text:
        # старий варіант з 2 параметрами — розширимо
        text = re.sub(
            r"adapter\s*=\s*ProductAdapter\(\s*onClick\s*=\s*\{\s*p\s*->.*?\}\s*,\s*onLongClick\s*=\s*\{\s*p\s*->.*?\}\s*\)\s*",
            lambda m: m.group(0).replace(")\n", "" ) + ",\n            onPhotoClick = { uriStr ->\n                startActivity(\n                    Intent(this, PhotoViewActivity::class.java)\n                        .putExtra(PhotoViewActivity.EXTRA_URI, uriStr)\n                )\n            }\n        )\n",
            text,
            flags=re.DOTALL
        )
    else:
        # fallback: нічого
        pass

    INVENTORY_ACTIVITY.write_text(text, encoding="utf-8")

def ensure_manifest_activity():
    if not MANIFEST.exists():
        raise SystemExit(f"Not found: {MANIFEST}")
    text = MANIFEST.read_text(encoding="utf-8")
    if ".PhotoViewActivity" in text:
        return

    block = """
        <activity
            android:name=".PhotoViewActivity"
            android:exported="false" />
"""
    text = re.sub(r"\s*</application>", f"{block}\n    </application>", text, flags=re.DOTALL)
    MANIFEST.write_text(text, encoding="utf-8")

def main():
    write_file(ITEM_LAYOUT, ITEM_LAYOUT_CONTENT)
    write_file(ADAPTER_FILE, ADAPTER_CONTENT)
    write_file(PHOTO_ACTIVITY, PHOTO_ACTIVITY_CONTENT)
    write_file(PHOTO_LAYOUT, PHOTO_LAYOUT_CONTENT)

    ensure_manifest_activity()
    patch_inventory_activity()

    print("OK: thumbnails + PhotoViewActivity added. Sync/Run.")

if __name__ == "__main__":
    main()
