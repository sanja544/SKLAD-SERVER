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
