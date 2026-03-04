#include "wal.hpp"
#include <iostream>
#include <cstring>
#include <vector>

WALManager::WALManager(const std::string& log_path, PageManager* page_manager) 
    : log_file_path(log_path), pm(page_manager), current_lsn(0) {
    
    // Open in append and read mode, binary.
    log_file.open(log_file_path, std::ios::in | std::ios::out | std::ios::binary | std::ios::app);
    
    if (!log_file.is_open()) {
        // If it doesn't exist, touch it to create it.
        log_file.clear();
        log_file.open(log_file_path, std::ios::out | std::ios::binary);
        log_file.close();
        log_file.open(log_file_path, std::ios::in | std::ios::out | std::ios::binary | std::ios::app);
    }
}

WALManager::~WALManager() {
    if (log_file.is_open()) {
        log_file.flush();
        log_file.close();
    }
}

uint64_t WALManager::log_insert(int page_id, int slot_id, const uint8_t* data, uint32_t size) {
    std::lock_guard<std::mutex> lock(wal_mutex);
    
    LogHeader header;
    header.lsn = ++current_lsn;
    header.type = LogType::INSERT_RECORD;
    header.page_id = page_id;
    header.slot_id = slot_id;
    header.payload_size = size;

    // Append Header
    log_file.write(reinterpret_cast<const char*>(&header), sizeof(LogHeader));
    // Append Raw Payload
    log_file.write(reinterpret_cast<const char*>(data), size);
    
    return header.lsn;
}

uint64_t WALManager::log_delete(int page_id, int slot_id) {
    std::lock_guard<std::mutex> lock(wal_mutex);
    
    LogHeader header;
    header.lsn = ++current_lsn;
    header.type = LogType::DELETE_RECORD;
    header.page_id = page_id;
    header.slot_id = slot_id;
    header.payload_size = 0;

    log_file.write(reinterpret_cast<const char*>(&header), sizeof(LogHeader));
    
    return header.lsn;
}

uint64_t WALManager::log_page_alloc(int page_id) {
    std::lock_guard<std::mutex> lock(wal_mutex);
    
    LogHeader header;
    header.lsn = ++current_lsn;
    header.type = LogType::PAGE_ALLOC;
    header.page_id = page_id;
    header.slot_id = -1;
    header.payload_size = 0;

    log_file.write(reinterpret_cast<const char*>(&header), sizeof(LogHeader));
    
    return header.lsn;
}

void WALManager::flush() {
    std::lock_guard<std::mutex> lock(wal_mutex);
    log_file.flush();
}

void WALManager::recover() {
    std::lock_guard<std::mutex> lock(wal_mutex);
    
    // Reset file pointer to the beginning for reading
    log_file.seekg(0, std::ios::beg);
    
    LogHeader header;
    while (log_file.read(reinterpret_cast<char*>(&header), sizeof(LogHeader))) {
        // Sync the LSN counter
        if (header.lsn > current_lsn) {
            current_lsn = header.lsn;
        }

        if (header.type == LogType::PAGE_ALLOC) {
            // THE FIX: Use the exported C-API function instead of the hidden C++ method
            PM_CreatePage(pm, header.page_id);
        } else if (header.type == LogType::INSERT_RECORD) {
            std::vector<uint8_t> buffer(header.payload_size);
            log_file.read(reinterpret_cast<char*>(buffer.data()), header.payload_size);
            
            // In the fully integrated loop, we pipe this straight into the RecordManager.
        } else if (header.type == LogType::DELETE_RECORD) {
            // Replay delete intent
        }
    }
    
    // Clear EOF flag so we can resume appending new logs after recovery
    log_file.clear(); 
    log_file.seekp(0, std::ios::end);
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    WALManager* WAL_Create(const char* log_path, PageManager* pm) {
        return new WALManager(std::string(log_path), pm);
    }
    
    void WAL_Destroy(WALManager* wal) {
        if (wal) delete wal;
    }
    
    uint64_t WAL_LogInsert(WALManager* wal, int page_id, int slot_id, const uint8_t* data, uint32_t size) {
        return wal ? wal->log_insert(page_id, slot_id, data, size) : 0;
    }
    
    uint64_t WAL_LogDelete(WALManager* wal, int page_id, int slot_id) {
        return wal ? wal->log_delete(page_id, slot_id) : 0;
    }
    
    uint64_t WAL_LogPageAlloc(WALManager* wal, int page_id) {
        return wal ? wal->log_page_alloc(page_id) : 0;
    }
    
    void WAL_Flush(WALManager* wal) {
        if (wal) wal->flush();
    }
    
    void WAL_Recover(WALManager* wal) {
        if (wal) wal->recover();
    }
}