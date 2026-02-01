package com.scan.warehouse.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.scan.warehouse.data.ProductEntity
import com.scan.warehouse.databinding.ItemProductBinding

class ProductAdapter(
    private val onClick: (ProductEntity) -> Unit,
    private val onLongClick: (ProductEntity) -> Unit
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
        holder.bind(items[position], onClick, onLongClick)
    }

    override fun getItemCount(): Int = items.size

    class VH(private val b: ItemProductBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(p: ProductEntity, onClick: (ProductEntity) -> Unit, onLongClick: (ProductEntity) -> Unit) {
            b.tvName.text = p.name
            b.tvBarcode.text = p.barcode
            b.tvPrice.text = "₴ ${"%.2f".format(p.price)}"
            b.tvQty.text = "qty: ${p.qty}"
            b.root.setOnClickListener { onClick(p) }
            b.root.setOnLongClickListener { onLongClick(p); true }
        }
    }
}
