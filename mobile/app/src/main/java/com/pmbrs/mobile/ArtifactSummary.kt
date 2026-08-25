package com.pmbrs.mobile

import com.google.gson.Gson
import com.google.gson.JsonParser
import com.pmbrs.mobile.data.ArtifactEntity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

fun summarizeArtifactForDisplay(artifact: ArtifactEntity): String {
    val payload = try {
        val json = JsonParser.parseString(artifact.payload)
        if (json.isJsonObject) json.asJsonObject else null
    } catch (_: Exception) {
        null
    }

    val timestampText = runCatching {
        val fmt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
        fmt.format(Date(artifact.createdAtEpochMs))
    }.getOrElse { "ts=${artifact.createdAtEpochMs}" }

    val payloadText = if (payload != null) {
        val fields = linkedSetOf<String>()
        payload.entrySet().forEach { (k, v) ->
            if (k == "payload" || k == "page_content") return@forEach
            val value = when {
                v.isJsonPrimitive && v.asJsonPrimitive.isString -> v.asString
                v.isJsonPrimitive && v.asJsonPrimitive.isNumber -> v.asString
                v.isJsonPrimitive && v.asJsonPrimitive.isBoolean -> v.asBoolean.toString()
                else -> v.toString()
            }
            fields.add("$k=$value")
        }
        fields.joinToString(" | ")
    } else {
        artifact.payload.take(140)
    }

    return "$timestampText | source=${artifact.source} | $payloadText"
}
