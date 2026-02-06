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
    suspend fun getAnyByBarcode(barcode: String): ProductEntity?

    @Query("SELECT * FROM products WHERE barcode = :barcode AND isDeleted = 0 LIMIT 1")
    suspend fun getByBarcode(barcode: String): ProductEntity?

    @Query("""
        UPDATE products 
        SET qty = qty - :delta, updatedAt = :now 
        WHERE barcode = :barcode AND isDeleted = 0 AND qty >= :delta
    """)
    suspend fun decrementQtyIfEnough(barcode: String, delta: Int, now: Long): Int

    @Query("SELECT * FROM products WHERE isDeleted = 0 ORDER BY name COLLATE NOCASE ASC")
    suspend fun getAll(): List<ProductEntity>

    @Query("""
        SELECT * FROM products
        WHERE isDeleted = 0 AND (name LIKE :q OR barcode LIKE :q)
        ORDER BY name COLLATE NOCASE ASC
    """)
    suspend fun search(q: String): List<ProductEntity>

    @Query("UPDATE products SET isDeleted = 1, updatedAt = :now WHERE barcode = :barcode")
    suspend fun markDeleted(barcode: String, now: Long): Int

    @Query("SELECT * FROM products WHERE updatedAt > :since ORDER BY updatedAt ASC")
    suspend fun getChangedSince(since: Long): List<ProductEntity>

    @Query("SELECT COALESCE(MAX(updatedAt), 0) FROM products")
    suspend fun getMaxUpdatedAt(): Long
}
