package com.pmbrs.boox

import android.app.Application

class BooxApp : Application() {
    override fun onCreate() {
        super.onCreate()
        SyncRuntime.bind(this)
        SyncRuntime.log("BooxApp onCreate (build=${BuildConfig.VERSION_NAME})")
        BootCompletedReceiver.ensureScheduled(this)
    }
}
