package com.chanarchiver.app.archiver

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.security.MessageDigest

/**
 * Robust asynchronous media archiver with cryptographic checksum verification
 * and transactional Room persistence.
 */
@Entity(tableName = "archived_media")
data class MediaRecord(
    @PrimaryKey val sha256: String,
    val originalUrl: String,
    val localFilePath: String,
    val fileSizeBytes: Long,
    val mimeType: String,
    val timestampUtc: Long,
    val boardId: String,
    val threadNumber: Long
)

@Dao
interface MediaRecordDao {
    @Query("SELECT * FROM archived_media WHERE sha256 = :hash LIMIT 1")
    suspend fun getByHash(hash: String): MediaRecord?

    @Query("SELECT * FROM archived_media WHERE threadNumber = :threadNumber ORDER BY timestampUtc ASC")
    fun observeThreadMedia(threadNumber: Long): Flow<List<MediaRecord>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRecord(record: MediaRecord)

    @Delete
                return@withContext Result.failure(IOException("HTTP ${response.code}: Failed to fetch media"))
            }

            val body = response.body ?: return@withContext Result.failure(IOException("Empty response body"))
            val tempFile = File.createTempFile("dl_", ".part", targetDir)
            val digest = MessageDigest.getInstance("SHA-256")

            body.byteStream().use { input ->
                FileOutputStream(tempFile).use { output ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        digest.update(buffer, 0, bytesRead)
                        output.write(buffer, 0, bytesRead)
                    }
                }
            }

            val hashBytes = digest.digest()
            val hashHex = hashBytes.joinToString("") { "%02x".format(it) }
            val finalFile = File(targetDir, "$hashHex.bin")
            tempFile.renameTo(finalFile)

            val record = MediaRecord(
                sha256 = hashHex,
                originalUrl = mediaUrl,
                localFilePath = finalFile.absolutePath,
                fileSizeBytes = finalFile.length(),
                mimeType = response.header("Content-Type", "application/octet-stream")!!,
                timestampUtc = System.currentTimeMillis(),
                boardId = boardId,
                threadNumber = threadNumber
            )
            dao.insertRecord(record)
            Result.success(record)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}