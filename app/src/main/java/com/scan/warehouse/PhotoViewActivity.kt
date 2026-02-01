package com.scan.warehouse

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
