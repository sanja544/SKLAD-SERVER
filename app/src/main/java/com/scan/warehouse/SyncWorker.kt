package com.scan.warehouse

import android.content.Context
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.Worker
import androidx.work.WorkerParameters
import kotlinx.coroutines.runBlocking

class SyncWorker(
    appContext: Context,
    params: WorkerParameters
) : Worker(appContext, params) {

    override fun doWork(): Result {
        SyncManager.ensureDefaultBaseUrl(applicationContext)
        val ok = runBlocking { SyncManager.syncNow(applicationContext) }
        return if (ok) Result.success() else Result.retry()
    }

    companion object {
        fun networkConstraints(): Constraints =
            Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
    }
}
