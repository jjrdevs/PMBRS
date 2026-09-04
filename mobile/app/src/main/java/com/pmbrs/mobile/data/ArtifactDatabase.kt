package com.pmbrs.mobile.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

class ArtifactDatabase private constructor(context: Context) : SQLiteOpenHelper(
    context.applicationContext,
    DB_NAME,
    null,
    DB_VERSION
) {
    private val dao = object : ArtifactDao {
        override fun insert(entity: ArtifactEntity): Long {
            val values = ContentValues().apply {
                put(COLUMN_ARTIFACT_ID, entity.artifactId)
                put(COLUMN_SOURCE, entity.source)
                put(COLUMN_PAYLOAD, entity.payload)
                put(COLUMN_CREATED_AT, entity.createdAtEpochMs)
                put(COLUMN_SCHEMA_VERSION, entity.schemaVersion)
                put(COLUMN_DEVICE_ALIAS, entity.deviceAlias)
                put(COLUMN_PROVENANCE_METADATA, entity.provenanceMetadataJson)
                put(COLUMN_SYNCED, if (entity.synced) 1 else 0)
            }
            return writableDatabase.insert(TABLE_NAME, null, values)
        }

        override fun getAll(): List<ArtifactEntity> {
            val cursor = readableDatabase.query(
                TABLE_NAME,
                arrayOf(
                    COLUMN_ID,
                    COLUMN_ARTIFACT_ID,
                    COLUMN_SOURCE,
                    COLUMN_PAYLOAD,
                    COLUMN_CREATED_AT,
                    COLUMN_SCHEMA_VERSION,
                    COLUMN_DEVICE_ALIAS,
                    COLUMN_PROVENANCE_METADATA,
                    COLUMN_SYNCED
                ),
                null,
                null,
                null,
                null,
                "$COLUMN_CREATED_AT DESC"
            )
            return cursor.use { c ->
                val items = mutableListOf<ArtifactEntity>()
                while (c.moveToNext()) {
                    items.add(
                        ArtifactEntity(
                            id = c.getLong(c.getColumnIndexOrThrow(COLUMN_ID)),
                            artifactId = c.getString(c.getColumnIndexOrThrow(COLUMN_ARTIFACT_ID)),
                            source = c.getString(c.getColumnIndexOrThrow(COLUMN_SOURCE)),
                            payload = c.getString(c.getColumnIndexOrThrow(COLUMN_PAYLOAD)),
                            createdAtEpochMs = c.getLong(c.getColumnIndexOrThrow(COLUMN_CREATED_AT)),
                            schemaVersion = c.getString(c.getColumnIndexOrThrow(COLUMN_SCHEMA_VERSION)),
                            deviceAlias = c.getString(c.getColumnIndexOrThrow(COLUMN_DEVICE_ALIAS)),
                            provenanceMetadataJson = c.getString(c.getColumnIndexOrThrow(COLUMN_PROVENANCE_METADATA)),
                            synced = c.getInt(c.getColumnIndexOrThrow(COLUMN_SYNCED)) == 1
                        )
                    )
                }
                items
            }
        }

        override fun getPending(): List<ArtifactEntity> {
            val cursor = readableDatabase.query(
                TABLE_NAME,
                arrayOf(
                    COLUMN_ID,
                    COLUMN_ARTIFACT_ID,
                    COLUMN_SOURCE,
                    COLUMN_PAYLOAD,
                    COLUMN_CREATED_AT,
                    COLUMN_SCHEMA_VERSION,
                    COLUMN_DEVICE_ALIAS,
                    COLUMN_PROVENANCE_METADATA,
                    COLUMN_SYNCED
                ),
                "$COLUMN_SYNCED = 0",
                null,
                null,
                null,
                "$COLUMN_CREATED_AT DESC"
            )
            return cursor.use { c ->
                val items = mutableListOf<ArtifactEntity>()
                while (c.moveToNext()) {
                    items.add(
                        ArtifactEntity(
                            id = c.getLong(c.getColumnIndexOrThrow(COLUMN_ID)),
                            artifactId = c.getString(c.getColumnIndexOrThrow(COLUMN_ARTIFACT_ID)),
                            source = c.getString(c.getColumnIndexOrThrow(COLUMN_SOURCE)),
                            payload = c.getString(c.getColumnIndexOrThrow(COLUMN_PAYLOAD)),
                            createdAtEpochMs = c.getLong(c.getColumnIndexOrThrow(COLUMN_CREATED_AT)),
                            schemaVersion = c.getString(c.getColumnIndexOrThrow(COLUMN_SCHEMA_VERSION)),
                            deviceAlias = c.getString(c.getColumnIndexOrThrow(COLUMN_DEVICE_ALIAS)),
                            provenanceMetadataJson = c.getString(c.getColumnIndexOrThrow(COLUMN_PROVENANCE_METADATA)),
                            synced = false
                        )
                    )
                }
                items
            }
        }

        override fun markSynced(id: Long) {
            val values = ContentValues().apply {
                put(COLUMN_SYNCED, 1)
            }
            writableDatabase.update(TABLE_NAME, values, "$COLUMN_ID = ?", arrayOf(id.toString()))
        }

        override fun markSyncedByArtifactId(artifactId: String) {
            val values = ContentValues().apply {
                put(COLUMN_SYNCED, 1)
            }
            writableDatabase.update(TABLE_NAME, values, "$COLUMN_ARTIFACT_ID = ?", arrayOf(artifactId))
        }

        override fun getByArtifactId(artifactId: String): ArtifactEntity? {
            val cursor = readableDatabase.query(
                TABLE_NAME,
                arrayOf(
                    COLUMN_ID,
                    COLUMN_ARTIFACT_ID,
                    COLUMN_SOURCE,
                    COLUMN_PAYLOAD,
                    COLUMN_CREATED_AT,
                    COLUMN_SCHEMA_VERSION,
                    COLUMN_DEVICE_ALIAS,
                    COLUMN_PROVENANCE_METADATA,
                    COLUMN_SYNCED
                ),
                "$COLUMN_ARTIFACT_ID = ?",
                arrayOf(artifactId),
                null,
                null,
                null,
                "1"
            )
            return cursor.use { c ->
                if (c.moveToFirst()) {
                    ArtifactEntity(
                        id = c.getLong(c.getColumnIndexOrThrow(COLUMN_ID)),
                        artifactId = c.getString(c.getColumnIndexOrThrow(COLUMN_ARTIFACT_ID)),
                        source = c.getString(c.getColumnIndexOrThrow(COLUMN_SOURCE)),
                        payload = c.getString(c.getColumnIndexOrThrow(COLUMN_PAYLOAD)),
                        createdAtEpochMs = c.getLong(c.getColumnIndexOrThrow(COLUMN_CREATED_AT)),
                        schemaVersion = c.getString(c.getColumnIndexOrThrow(COLUMN_SCHEMA_VERSION)),
                        deviceAlias = c.getString(c.getColumnIndexOrThrow(COLUMN_DEVICE_ALIAS)),
                        provenanceMetadataJson = c.getString(c.getColumnIndexOrThrow(COLUMN_PROVENANCE_METADATA)),
                        synced = c.getInt(c.getColumnIndexOrThrow(COLUMN_SYNCED)) == 1
                    )
                } else {
                    null
                }
            }
        }

        override fun getByFingerprint(source: String, payload: String, createdAtEpochMs: Long): ArtifactEntity? {
            val cursor = readableDatabase.query(
                TABLE_NAME,
                arrayOf(
                    COLUMN_ID,
                    COLUMN_ARTIFACT_ID,
                    COLUMN_SOURCE,
                    COLUMN_PAYLOAD,
                    COLUMN_CREATED_AT,
                    COLUMN_SCHEMA_VERSION,
                    COLUMN_DEVICE_ALIAS,
                    COLUMN_PROVENANCE_METADATA,
                    COLUMN_SYNCED
                ),
                "$COLUMN_SOURCE = ? AND $COLUMN_PAYLOAD = ? AND $COLUMN_CREATED_AT = ?",
                arrayOf(source, payload, createdAtEpochMs.toString()),
                null,
                null,
                null,
                "1"
            )
            return cursor.use { c ->
                if (c.moveToFirst()) {
                    ArtifactEntity(
                        id = c.getLong(c.getColumnIndexOrThrow(COLUMN_ID)),
                        artifactId = c.getString(c.getColumnIndexOrThrow(COLUMN_ARTIFACT_ID)),
                        source = c.getString(c.getColumnIndexOrThrow(COLUMN_SOURCE)),
                        payload = c.getString(c.getColumnIndexOrThrow(COLUMN_PAYLOAD)),
                        createdAtEpochMs = c.getLong(c.getColumnIndexOrThrow(COLUMN_CREATED_AT)),
                        schemaVersion = c.getString(c.getColumnIndexOrThrow(COLUMN_SCHEMA_VERSION)),
                        deviceAlias = c.getString(c.getColumnIndexOrThrow(COLUMN_DEVICE_ALIAS)),
                        provenanceMetadataJson = c.getString(c.getColumnIndexOrThrow(COLUMN_PROVENANCE_METADATA)),
                        synced = c.getInt(c.getColumnIndexOrThrow(COLUMN_SYNCED)) == 1
                    )
                } else {
                    null
                }
            }
        }

        override fun insertIfMissing(entity: ArtifactEntity): Long {
            val existing = getByFingerprint(entity.source, entity.payload, entity.createdAtEpochMs)
            if (existing != null) {
                return existing.id
            }
            return insert(entity)
        }

        override fun deleteOlderThan(cutoffEpochMs: Long): Int {
            return writableDatabase.delete(
                TABLE_NAME,
                "$COLUMN_CREATED_AT < ?",
                arrayOf(cutoffEpochMs.toString())
            )
        }
    }

    fun artifactDao(): ArtifactDao = dao

    private fun ensureArtifactsTable(db: SQLiteDatabase) {
        val tableExists = db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            arrayOf(TABLE_NAME)
        ).use { it.moveToFirst() }
        if (!tableExists) {
            db.execSQL(
                "CREATE TABLE $TABLE_NAME (" +
                    "$COLUMN_ID INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "$COLUMN_ARTIFACT_ID TEXT NOT NULL, " +
                    "$COLUMN_SOURCE TEXT NOT NULL, " +
                    "$COLUMN_PAYLOAD TEXT NOT NULL, " +
                    "$COLUMN_CREATED_AT INTEGER NOT NULL, " +
                    "$COLUMN_SCHEMA_VERSION TEXT NOT NULL, " +
                    "$COLUMN_DEVICE_ALIAS TEXT, " +
                    "$COLUMN_PROVENANCE_METADATA TEXT NOT NULL DEFAULT '{}', " +
                    "$COLUMN_SYNCED INTEGER NOT NULL DEFAULT 0)"
            )
        }
    }

    override fun onCreate(db: SQLiteDatabase) {
        ensureArtifactsTable(db)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            ensureArtifactsTable(db)
            return
        }
        db.execSQL("DROP TABLE IF EXISTS $TABLE_NAME")
        onCreate(db)
    }

    companion object {
        private const val DB_NAME = "pmbrs-artifacts.db"
        private const val DB_VERSION = 2
        private const val TABLE_NAME = "artifacts"
        private const val COLUMN_ID = "id"
        private const val COLUMN_ARTIFACT_ID = "artifact_id"
        private const val COLUMN_SOURCE = "source"
        private const val COLUMN_PAYLOAD = "payload"
        private const val COLUMN_CREATED_AT = "createdAtEpochMs"
        private const val COLUMN_SCHEMA_VERSION = "schema_version"
        private const val COLUMN_DEVICE_ALIAS = "device_alias"
        private const val COLUMN_PROVENANCE_METADATA = "provenance_metadata"
        private const val COLUMN_SYNCED = "synced"

        @Volatile
        private var INSTANCE: ArtifactDatabase? = null

        /** Reset the singleton (and close the handle) — test-only. */
        internal fun resetForTests() {
            INSTANCE?.close()
            INSTANCE = null
        }

        fun getInstance(context: Context): ArtifactDatabase {
            val dbFile = context.getDatabasePath(DB_NAME)

            if (INSTANCE != null && !dbFile.exists()) {
                INSTANCE?.close()
                INSTANCE = null
            }

            return INSTANCE ?: synchronized(this) {
                val current = INSTANCE
                if (current != null && dbFile.exists()) {
                    current
                } else {
                    INSTANCE?.close()
                    ArtifactDatabase(context).also {
                        INSTANCE = it
                        it.ensureArtifactsTable(it.writableDatabase)
                    }
                }
            }
        }
    }
}
