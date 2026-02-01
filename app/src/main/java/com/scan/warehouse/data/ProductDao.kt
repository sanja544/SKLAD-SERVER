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
    @Query("SELECT * FROM products ORDER BY name COLLATE NOCASE ASC")
    suspend fun getAll(): List<ProductEntity>

    @Query("SELECT * FROM products WHERE name LIKE :q OR barcode LIKE :q ORDER BY name COLLATE NOCASE ASC")
    suspend fun search(q: String): List<ProductEntity>

    @Query("DELETE FROM products WHERE barcode = :barcode")
    suspend fun deleteByBarcode(barcode: String): Int

}
