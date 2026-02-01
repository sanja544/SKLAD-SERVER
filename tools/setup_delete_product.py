from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

APP = ROOT / "app"
JAVA_BASE = APP / "src" / "main" / "java" / "com" / "scan" / "warehouse"
DATA_DIR = JAVA_BASE / "data"
UI_DIR = JAVA_BASE / "ui"

DAO_FILE = DATA_DIR / "ProductDao.kt"
ADAPTER_FILE = UI_DIR / "ProductAdapter.kt"
INVENTORY_ACTIVITY = JAVA_BASE / "InventoryActivity.kt"

def patch_dao():
    text = DAO_FILE.read_text(encoding="utf-8")
    if "suspend fun deleteByBarcode" in text:
        return
    insert = """
    @Query("DELETE FROM products WHERE barcode = :barcode")
    suspend fun deleteByBarcode(barcode: String): Int
"""
    text = re.sub(r"\n}\s*$", f"{insert}\n}}\n", text, flags=re.DOTALL)
    DAO_FILE.write_text(text, encoding="utf-8")

def patch_adapter():
    text = ADAPTER_FILE.read_text(encoding="utf-8")
    if "onLongClick" in text:
        return

    # Замінимо сигнатуру конструктора і bind()
    text = text.replace(
        "class ProductAdapter(\n    private val onClick: (ProductEntity) -> Unit\n) : RecyclerView.Adapter<ProductAdapter.VH>() {",
        "class ProductAdapter(\n    private val onClick: (ProductEntity) -> Unit,\n    private val onLongClick: (ProductEntity) -> Unit\n) : RecyclerView.Adapter<ProductAdapter.VH>() {"
    )

    text = text.replace(
        "holder.bind(items[position], onClick)",
        "holder.bind(items[position], onClick, onLongClick)"
    )

    text = text.replace(
        "fun bind(p: ProductEntity, onClick: (ProductEntity) -> Unit) {",
        "fun bind(p: ProductEntity, onClick: (ProductEntity) -> Unit, onLongClick: (ProductEntity) -> Unit) {"
    )

    # Додамо long click в кінці bind
    text = text.replace(
        "b.root.setOnClickListener { onClick(p) }",
        "b.root.setOnClickListener { onClick(p) }\n            b.root.setOnLongClickListener { onLongClick(p); true }"
    )

    ADAPTER_FILE.write_text(text, encoding="utf-8")

def patch_inventory_activity():
    text = INVENTORY_ACTIVITY.read_text(encoding="utf-8")
    if "AlertDialog" in text:
        return

    # імпорт AlertDialog
    text = text.replace(
        "import android.content.Intent",
        "import android.content.Intent\nimport androidx.appcompat.app.AlertDialog"
    )

    # заміна створення адаптера
    text = re.sub(
        r"adapter\s*=\s*ProductAdapter\s*\{\s*p\s*->\s*startActivity\(\s*Intent\(this,\s*AddProductActivity::class\.java\)\s*\.putExtra\(AddProductActivity\.EXTRA_BARCODE,\s*p\.barcode\)\s*\)\s*\}\s*",
        """adapter = ProductAdapter(
            onClick = { p ->
                startActivity(
                    Intent(this, AddProductActivity::class.java)
                        .putExtra(AddProductActivity.EXTRA_BARCODE, p.barcode)
                )
            },
            onLongClick = { p ->
                AlertDialog.Builder(this)
                    .setTitle("Видалити товар?")
                    .setMessage("${p.name}\\n${p.barcode}")
                    .setPositiveButton("Видалити") { _, _ ->
                        deleteProduct(p.barcode)
                    }
                    .setNegativeButton("Скасувати", null)
                    .show()
            }
        )
""",
        text,
        flags=re.DOTALL
    )

    # Додати функцію deleteProduct перед останньою }
    insert_fn = """
    private fun deleteProduct(barcode: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val dao = AppDatabase.get(applicationContext).productDao()
            withContext(Dispatchers.IO) { dao.deleteByBarcode(barcode) }
            scheduleSearch(binding.etSearch.text?.toString().orEmpty(), immediate = true)
        }
    }
"""
    text = re.sub(r"\n}\s*$", f"{insert_fn}\n}}\n", text, flags=re.DOTALL)
    INVENTORY_ACTIVITY.write_text(text, encoding="utf-8")

def main():
    for p in [DAO_FILE, ADAPTER_FILE, INVENTORY_ACTIVITY]:
        if not p.exists():
            raise SystemExit(f"Not found: {p}")

    patch_dao()
    patch_adapter()
    patch_inventory_activity()

    print("OK: delete on long-press added (DAO + Adapter + InventoryActivity). Sync/Run.")

if __name__ == "__main__":
    main()
