#ifndef WAL_HPP
#define WAL_HPP

#include "page.hpp"
#include <string>
#include <fstream>
#include <mutex>
#include <cstdint>
#include <vector>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

// Disable padding so the log file is perfectly byte-aligned on disk
#pragma pack(push, 1)

enum class LogType : uint8_t {
    INSERT_RECORD = 1,
    DELETE_RECORD = 2,
    PAGE_ALLOC    = 3
};

struct LogHeader {
    uint64_t lsn;         // Log Sequence Number (Strictly increasing)
    LogType type;         // What action is being performed
    int32_t page_id;      // Target page
    int32_t slot_id;      // Target slot (for inserts/deletes)
    uint32_t payload_size;// Size of the data attached immediately after this header
};

#pragma pack(pop)

class WALManager {
private:
    std::string log_file_path;
    std::fstream log_file;
    std::mutex wal_mutex; // Strictly serializes log appends
    uint64_t current_lsn;
    PageManager* pm;      // Reference to the main engine for crash recovery replays

public:
    WALManager(const std::string& log_path, PageManager* page_manager);
    ~WALManager();

    // --- Write-Ahead Methods ---
    // These must be called BEFORE modifying the actual RecordManager/BTree
    uint64_t log_insert(int page_id, int slot_id, const uint8_t* data, uint32_t size);
    uint64_t log_delete(int page_id, int slot_id);
    uint64_t log_page_alloc(int page_id);
    
    // Force the OS to sync the log file to physical spinning rust/SSD NAND
    void flush();
    
    // The Crash Recovery routine. Run this on database boot.
    void recover(); 
};

// --- C-Compatible Export Interface ---
extern "C" {
    DLL_EXPORT WALManager* WAL_Create(const char* log_path, PageManager* pm);
    DLL_EXPORT void WAL_Destroy(WALManager* wal);
    DLL_EXPORT uint64_t WAL_LogInsert(WALManager* wal, int page_id, int slot_id, const uint8_t* data, uint32_t size);
    DLL_EXPORT uint64_t WAL_LogDelete(WALManager* wal, int page_id, int slot_id);
    DLL_EXPORT uint64_t WAL_LogPageAlloc(WALManager* wal, int page_id);
    DLL_EXPORT void WAL_Flush(WALManager* wal);
    DLL_EXPORT void WAL_Recover(WALManager* wal);
}

#endif // WAL_HPP