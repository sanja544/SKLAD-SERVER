package com.scan.warehouse.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "products")
data class ProductEntity(
    @PrimaryKey val barcode: String,
    val name: String,
    val price: Double,
    val qty: Int,

    // Локальне фото (FileProvider/content Uri) — для показу в UI
    val photoUri: String? = null,

    // Серверне фото (типу /photos/123.jpg) — для синхронізації
    val photoRemoteUrl: String? = null,

    val isDeleted: Int = 0,
    val updatedAt: Long = 0L
)
