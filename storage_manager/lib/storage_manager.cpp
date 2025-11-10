#ifndef PYTABASE_KERNEL_H
#define PYTABASE_KERNEL_H

#include <atomic>
#include <vector>
#include <map>
#include <queue>
#include <string>
#include <memory>
#include <mutex>
#include <fstream>
#include <unordered_set> // Added for SSI

// ============================================================================
// 1. FUNDAMENTAL TYPES (Renamed)
// ============================================================================

using BlockID = uint32_t; // Formerly PageID
using LSN = uint64_t;
using TxnID = uint64_t;
using Timestamp = uint64_t;

enum class CompressionCodec {
    NONE,
    RLE,
    SNAPPY
};

// ============================================================================
// 2. SYSTEM SETTINGS (For Self-Adaptation)
// ============================================================================

class SystemSettings {
public:
    std::atomic<size_t> block_size_;
    std::atomic<size_t> vector_size_; // Vector size for vectorized execution
    std::atomic<size_t> write_buffer_flush_threshold_;
    std::atomic<size_t> memory_cache_size_; // In number of blocks
    std::atomic<size_t> bloom_filter_bits_;
    std::atomic<size_t> compaction_threshold_;

    SystemSettings()
        : block_size_(4096),
          vector_size_(2048), // e.g., 2048 tuples per chunk
          write_buffer_flush_threshold_(64 * 1024 * 1024), // 64MB
          memory_cache_size_(1024), // 1024 frames/blocks
          bloom_filter_bits_(1024 * 8),
          compaction_threshold_(4) {}

    size_t GetBlockSize() const { return block_size_.load(); }
};

// ============================================================================
// 3. BLOCK & CIPHER STRUCTURES
// ============================================================================

struct Block {
    std::unique_ptr<char> data; // Data is heap-allocated
    BlockID block_id;
    bool is_dirty;
    int pin_count;
    LSN page_lsn; // LSN of the last log record that modified this page
    std::mutex block_latch;

    Block() : block_id(0), is_dirty(false), pin_count(0), page_lsn(0) {
        // Data is allocated by the MemoryCacheManager
    }

    // Explicitly disable copy, enable move
    Block(const Block&) = delete;
    Block& operator=(const Block&) = delete;
    Block(Block&&) noexcept = default;
    Block& operator=(Block&&) noexcept = default;

    char* GetData() { return data.get(); }
};

class BlockCipher {
    //... (Implementation remains same, but uses BlockID)...
public:
    //...
    bool EncryptBlock(const char* plain_data, BlockID block_id, char* cipher_out, size_t block_size);
    bool DecryptBlock(const char* cipher, BlockID block_id, char* plain_out, size_t block_size);
};

// ============================================================================
// 4. FILE DEVICE MANAGER (Formerly DiskManager)
// ============================================================================

class FileDeviceManager {
private:
    std::string db_file_path_;
    std::fstream db_file_;
    std::unique_ptr<BlockCipher> cipher_;
    std::mutex device_mutex_;
    std::shared_ptr<SystemSettings> settings_;
    std::unique_ptr<char> encrypted_buffer_; // Reusable I/O buffer

public:
    FileDeviceManager(const std::string& path,
                      const unsigned char* encryption_key,
                      const unsigned char* salt,
                      std::shared_ptr<SystemSettings> settings);
    
    ~FileDeviceManager();

    bool ReadBlock(BlockID block_id, char* block_data_out);
    bool WriteBlock(BlockID block_id, const char* block_data);
    BlockID AllocateBlock();
};

// ============================================================================
// 5. BLOOM FILTER
// ============================================================================

class BloomFilter {
    //... (Implementation should be sized from SystemSettings)...
};

// ============================================================================
// 6. MEMORY CACHE MANAGER (Formerly BufferPoolManager)
// ============================================================================

class MemoryCacheManager {
private:
    struct CacheFrame {
        Block block;
        std::atomic<bool> reference_bit; // NEW: For CLOCK algorithm [1, 2]
        //... other frame metadata...
    };

    std::vector<CacheFrame> frames_;
    std::map<BlockID, size_t> block_table_; // Maps BlockID to frame index
    std::queue<size_t> free_list_;
    FileDeviceManager* device_manager_;
    std::shared_ptr<SystemSettings> settings_;
    std::atomic<size_t> clock_hand_; // NEW: Hand for CLOCK algorithm
    std::mutex cache_latch_;

    // REPLACED: Simple LFU is scan-prone. Implement CLOCK.[3, 1]
    size_t SelectVictimNoLock() {
        // This is now the CLOCK algorithm implementation [3, 1, 2]
        // (Pseudocode for implementation)
        // while (true) {
        //   size_t frame_idx = clock_hand_.fetch_add(1) % frames_.size();
        //   auto& frame = frames_[frame_idx];
        // 
        //   if (frame.block.pin_count == 0) {
        //     if (frame.reference_bit.load() == true) {
        //       frame.reference_bit.store(false); // Give second chance
        //     } else {
        //       // Victim found.
        //       return frame_idx;
        //     }
        //   }
        // }
        return 0; // Placeholder
    }

public:
    MemoryCacheManager(FileDeviceManager* device_mgr, std::shared_ptr<SystemSettings> settings);

    Block* FetchBlock(BlockID block_id);
    bool UnpinBlock(BlockID block_id, bool is_dirty);
    Block* NewBlock(BlockID* block_id_out);
    bool FlushBlock(BlockID block_id);
    void FlushAllBlocks();
};

// ============================================================================
// 7. UNIFIED LOG MANAGER (Replaces WAL and UndoLog)
// ============================================================================

// CRITICAL REFACTOR: Removed separate UndoLog and WriteAheadLog.
// Replaced with a unified, ARIES-compliant LogManager.

enum class LogRecordType {
    UPDATE,
    INSERT,
    DELETE,
    BEGIN_TXN,
    COMMIT_TXN,
    ABORT_TXN
};

// Represents a single log entry in the WAL
struct LogRecord {
    LSN lsn_;
    LSN prev_lsn_; // LSN of the previous record for this transaction
    TxnID txn_id_;
    LogRecordType type_;
    
    // REDO and UNDO data (physiological logging)
    BlockID block_id_;
    uint16_t offset_;
    uint16_t length_;
    std::unique_ptr<char> before_image_; // For UNDO
    std::unique_ptr<char> after_image_;  // For REDO

    //... constructors...
};

class LogManager {
private:
    std::fstream log_file_;
    std::mutex log_mutex_;
    std::atomic<LSN> current_lsn_;
    //... more state for recovery...

public:
    LogManager();

    // Appends a new log record and returns its LSN
    LSN AppendLogRecord(LogRecord& record);

    // Forces the log buffer to disk up to the specified LSN
    void ForceFlush(LSN lsn);

    // --- Recovery Phase ---
    void Recover(); // Called on startup to run ARIES recovery
    void Rollback(TxnID txn_id); // Reads WAL backwards to undo a transaction
};

// ============================================================================
// 8. WRITE BUFFER (Formerly MemTable)
// ============================================================================

// NEW: Represents an in-memory chunk of columnar data
struct ColumnChunk {
    std::vector<char> data_buffer_;
    std::vector<bool> null_bitmap_;
    size_t tuple_count_ = 0;
    //... other metadata (e.g., data type)...
};

// This is the in-memory sorted buffer
class WriteBuffer {
private:
    // CRITICAL REFACTOR: Changed from row-oriented map to columnar layout.
    std::map<std::string, std::unique_ptr<ColumnChunk>> columns_;
    
    std::atomic<size_t> size_bytes_;
    std::mutex buffer_mutex_;
    std::shared_ptr<SystemSettings> settings_;

public:
    explicit WriteBuffer(std::shared_ptr<SystemSettings> settings);
    
    // REFACTORED: Insert must now handle columnar data
    bool Insert(const std::map<std::string, std::string>& row, Timestamp ts);
    
    const auto& GetColumns() const { return columns_; }
    //... (other functions adapted for settings_)...
};

// ============================================================================
// 9. COLUMN SEGMENT (Formerly SSTable)
// ============================================================================

struct ColumnSegmentMetadata {
    //... metadata (key ranges, LSN range, etc.)...
    // NEW: Map to store the offset of each compressed column block
    std::map<std::string, std::pair<uint64_t, uint64_t>> column_offsets_;
};

// CRITICAL REFACTOR: This is now a COLUMNAR segment (like Parquet/ORC).
class ColumnSegment {
private:
    ColumnSegmentMetadata metadata_;
    FileDeviceManager* device_manager_;
    std::shared_ptr<SystemSettings> settings_;

public:
    ColumnSegment(FileDeviceManager* device_mgr, std::shared_ptr<SystemSettings> settings, int level = 0);

    // REFACTORED: Writes columnar data, applying compression
    void WriteFromBuffer(const std::map<std::string, std::unique_ptr<ColumnChunk>>& columns,
                         MemoryCacheManager* cache_manager);

    // REFACTORED: `Get` is now a full row "re-hydration" and is slow.
    bool Get(const std::string& key, std::string& value_out,
             MemoryCacheManager* cache_manager);

    // NEW: Primary access path for analytics. Reads *only* specified columns.
    bool ScanColumn(const std::string& column_name, 
                    ColumnChunk& output_chunk,
                    MemoryCacheManager* cache_manager);
};

// ============================================================================
// 10. STORAGE ENGINE (Formerly LSMTreeEngine)
// ============================================================================

class StorageEngine {
private:
    std::shared_ptr<SystemSettings> settings_;
    std::unique_ptr<FileDeviceManager> device_manager_;
    std::unique_ptr<MemoryCacheManager> cache_manager_;
    
    // REFACTORED: Unified LogManager
    std::unique_ptr<LogManager> log_manager_;
    
    std::unique_ptr<WriteBuffer> active_write_buffer_;
    std::vector<std::vector<ColumnSegment>> level_segments_;
    std::atomic<Timestamp> current_timestamp_;
    
    //... (other members)...

public:
    StorageEngine(const std::string& db_path,
                  const unsigned char* encryption_key,
                  const unsigned char* salt,
                  std::shared_ptr<SystemSettings> settings);

    //... (Put, Flush, Compact methods, all now using settings_)...
    bool Put(const std::string& key, const std::string& value, TxnID txn_id);
    bool Get(const std::string& key, std::string& value_out, TxnID txn_id);


    // Public accessors for other modules
    MemoryCacheManager* GetCacheManager() { return cache_manager_.get(); }
    LogManager* GetLogManager() { return log_manager_.get(); }
    std::atomic<Timestamp>* GetTimestampManager() { return &current_timestamp_; }
    //... Accessors for WriteBuffer, Segments for the QueryExecutor...
};

// ============================================================================
// 11. QUERY EXECUTOR (Vectorized Volcano Model)
// ============================================================================

// CRITICAL REFACTOR: Replaced fake executor with a Volcano-style iterator model.

// Base class for all query operators
class BaseOperator {
public:
    virtual ~BaseOperator() = default;
    virtual void Init() = 0;
    // Main vectorized execution method. Fills the chunk with data.
    // Returns false when no more data is available.
    virtual bool Next(ColumnChunk& chunk) = 0;
    virtual void Close() = 0;
};

// Example Operator: Scans a ColumnSegment
class ColumnarScanOperator : public BaseOperator {
private:
    ColumnSegment* segment_;
    std::string column_to_scan_;
public:
    ColumnarScanOperator(ColumnSegment* segment, const std::string& col)
        : segment_(segment), column_to_scan_(col) {}
    
    void Init() override { /*... */ }
    bool Next(ColumnChunk& chunk) override {
        // Calls segment_->ScanColumn(...)
        return false;
    }
    void Close() override { /*... */ }
};

// Example Operator: Filters a chunk
class FilterOperator : public BaseOperator {
private:
    std::unique_ptr<BaseOperator> child_;
    //... filter predicate...
public:
    FilterOperator(std::unique_ptr<BaseOperator> child) : child_(std::move(child)) {}
    
    void Init() override { child_->Init(); }
    bool Next(ColumnChunk& chunk) override {
        // 1. while (child_->Next(chunk))
        // 2.   Apply filter to the chunk
        // 3.   if chunk is not empty, return true
        // 4. return false
        return false;
    }
    void Close() override { child_->Close(); }
};

// QueryExecutor is now a pipeline BUILDER, not an executor
class QueryExecutor {
public:
    // Parses a logical plan (not shown) and builds the operator pipeline
    std::unique_ptr<BaseOperator> BuildQueryPipeline(StorageEngine* engine,
                                                       /*... LogicalPlanNode* plan... */);
};

// ============================================================================
// 12. TRANSACTION MANAGER
// ============================================================================

class Transaction {
public:
    TxnID txn_id_;
    Timestamp start_ts_;
    std::atomic<bool> is_aborted_;
    
    // ADDED: Read/Write sets for Serializable Snapshot Isolation (SSI)
    std::unordered_set<BlockID> read_set_;
    std::unordered_set<BlockID> write_set_;
    std::mutex txn_latch_;

    Transaction(TxnID id, Timestamp ts) 
        : txn_id_(id), start_ts_(ts), is_aborted_(false) {}
};

// REFACTORED: Now implements SSI
class TransactionManager {
private:
    LogManager* log_manager_;
    MemoryCacheManager* cache_manager_;
    std::atomic<Timestamp> global_timestamp_;
    std::atomic<TxnID> next_txn_id_;

    //... map of active transactions...

public:
    TransactionManager(LogManager* log_mgr,
                         MemoryCacheManager* cache_mgr,
                         std::atomic<Timestamp>* global_ts);

    Transaction* Begin();
    // REFACTORED: Commit now performs SSI validation
    bool Commit(Transaction* txn);
    void Abort(Transaction* txn);
};

// ============================================================================
// 13. COMPRESSION CODECS
// ============================================================================

// (Implementations for RLE, Snappy, etc. These are now used by ColumnSegment)
class CompressionCodecRLE {
    //...
};

// ============================================================================
// 14. C-API FOR PYTHON BINDINGS (PYTABASE CFFI)
// ============================================================================

extern "C" {
    typedef void* PytabaseHandle;
    
    // CRITICAL REFACTOR: Changed 'get' from copy-based to zero-copy (Arrow-like).
    // Opaque handle to a result set batch
    typedef void* PytabaseResultBatch;

    PytabaseHandle pytabase_open(const char* path,
                                   const unsigned char* encryption_key,
                                   const unsigned char* salt);
    
    void pytabase_close(PytabaseHandle handle);

    int pytabase_modify_setting(PytabaseHandle handle, const char* key, const char* value);
    
    // 'put' remains mostly the same, but is now transactional
    int pytabase_put(PytabaseHandle handle, const char* key, size_t key_len,
                       const char* value, size_t value_len);
    
    // NEW: Executes a query (e.g., "SELECT...") and returns the first batch
    PytabaseResultBatch pytabase_execute_query(PytabaseHandle handle, const char* query);

    // NEW: Gets a direct, zero-copy pointer to a column's data in the batch
    // This is the model Apache Arrow uses.
    int pytabase_get_column_buffer(PytabaseResultBatch batch,
                                     const char* column_name,
                                     void** data_pointer_out, // Returns a direct pointer
                                     size_t* length_out,
                                     int* type_out); // Returns a type enum

    // NEW: Frees the batch handle when Python is done with it
    void pytabase_free_batch(PytabaseResultBatch batch);
    
    // REMOVED: pytabase_get (replaced by execute_query)
    // REMOVED: pytabase_free_value (replaced by free_batch)
    
    void pytabase_flush(PytabaseHandle handle);
    void pytabase_compact(PytabaseHandle handle);
    
    int pytabase_get_stats(PytabaseHandle handle, size_t* memtable_size,
                           size_t* total_segments, size_t* num_levels);
}

// ============================================================================
// 15. PYTABASE ENGINE (Formerly MergeTreeDBMS)
// ============================================================================

class PytabaseEngine {
private:
    std::shared_ptr<SystemSettings> settings_;
    std::unique_ptr<StorageEngine> storage_engine_;
    std::unique_ptr<QueryExecutor> executor_;
    std::unique_ptr<TransactionManager> txn_manager_;
    std::string db_path_;
    
public:
    PytabaseEngine(const std::string& path,
                   const unsigned char* encryption_key,
                   const unsigned char* salt) {
        
        settings_ = std::make_shared<SystemSettings>();
        // Managers must be created in dependency order (Log -> Cache -> Storage)
        auto log_manager = std::make_unique<LogManager>();
        auto device_manager = std::make_unique<FileDeviceManager>(path, encryption_key, salt, settings_);
        auto cache_manager = std::make_unique<MemoryCacheManager>(device_manager.get(), settings_);

        // Inject dependencies
        storage_engine_ = std::make_unique<StorageEngine>(
            path, encryption_key, salt, settings_,
            log_manager.get(), cache_manager.get()
            /*...pass other managers...*/
        );

        executor_ = std::make_unique<QueryExecutor>();
        
        txn_manager_ = std::make_unique<TransactionManager>(
            log_manager.get(),
            cache_manager.get(),
            storage_engine_->GetTimestampManager()
        );
        
        //... now store the unique_ptrs in class members...
    }
    
    bool ModifySetting(const std::string& key, const std::string& value) {
        if (key == "write_buffer_flush_threshold") {
            settings_->write_buffer_flush_threshold_ = std::stoull(value);
            return true;
        }
        if (key == "compaction_threshold") {
            settings_->compaction_threshold_ = std::stoull(value);
            return true;
        }
        return false;
    }

    //... (Insert, Query, Compact, GetStats, Shutdown methods)...
    // The C-API will call these methods
};

// ============================================================================
// 16. C-API IMPLEMENTATIONS
// ============================================================================

//... (Implementations for all pytabase_* C-API functions)...

int pytabase_modify_setting(PytabaseHandle handle, const char* key, const char* value) {
    if (!handle ||!key ||!value) return -1;
    PytabaseEngine* engine = static_cast<PytabaseEngine*>(handle);
    return engine->ModifySetting(std::string(key), std::string(value))? 0 : -1;
}

//...

#endif // PYTABASE_KERNEL_H split it into n numbers of files if necessary and provide me with .h, .cpp and finally a.py file, along with command to compile them