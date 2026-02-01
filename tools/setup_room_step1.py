# tools/setup_room_step1.py
# Створює папки і файли для Room (ProductEntity, ProductDao, AppDatabase)

from pathlib import Path

ROOT = Path(r"E:\SCAN\Projects\WarehouseScanner").resolve()

DATA_DIR = ROOT / "app" / "src" / "main" / "java" / "com" / "scan" / "warehouse" / "data"

FILES = {
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

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for path, content in FILES.items():
        path.write_text(content, encoding="utf-8")
        print(f"wrote: {path}")

    print("OK. Тепер зроби Sync (і бажано Build).")

if __name__ == "__main__":
    main()
