#include "page.hpp"
#include <cstring>
#include <iostream>

PageManager::PageManager(const std::string& db_path, int max_pages, int page_size) 
    : db_file_path(db_path), max_pages(max_pages), page_size(page_size) {
    
    db_file.open(db_file_path, std::ios::in | std::ios::out | std::ios::binary);
    if (!db_file.is_open()) {
        db_file.clear();
        db_file.open(db_file_path, std::ios::out | std::ios::binary);
        db_file.close();
        db_file.open(db_file_path, std::ios::in | std::ios::out | std::ios::binary);
    }
}

PageManager::~PageManager() {
    flush_all();
    if (db_file.is_open()) {
        db_file.close();
    }
}

bool PageManager::create_page(int page_id) {
    std::lock_guard<std::mutex> lock(pm_mutex);
    if (buffer_pool.find(page_id) == buffer_pool.end()) {
        buffer_pool[page_id] = std::vector<uint8_t>(page_size, 0);
    }
    return true;
}

bool PageManager::read_page(int page_id, uint8_t* buffer) {
    std::lock_guard<std::mutex> lock(pm_mutex);
    
    // Check buffer pool first
    if (buffer_pool.find(page_id) != buffer_pool.end()) {
        std::memcpy(buffer, buffer_pool[page_id].data(), page_size);
        return true;
    }

    // Otherwise, fetch from disk
    db_file.seekg(page_id * page_size, std::ios::beg);
    if (db_file.read(reinterpret_cast<char*>(buffer), page_size)) {
        buffer_pool[page_id] = std::vector<uint8_t>(buffer, buffer + page_size);
        return true;
    }
    
    return false; // Page doesn't exist
}

bool PageManager::write_page(int page_id, const uint8_t* buffer) {
    std::lock_guard<std::mutex> lock(pm_mutex);
    
    // Update buffer pool
    buffer_pool[page_id] = std::vector<uint8_t>(buffer, buffer + page_size);
    return true; // We defer the actual disk write to flush_all()
}

void PageManager::flush_all() {
    std::lock_guard<std::mutex> lock(pm_mutex);
    for (const auto& [page_id, data] : buffer_pool) {
        db_file.seekp(page_id * page_size, std::ios::beg);
        db_file.write(reinterpret_cast<const char*>(data.data()), page_size);
    }
    db_file.flush();
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    PageManager* PM_Create(const char* db_path, int max_pages, int page_size) {
        return new PageManager(std::string(db_path), max_pages, page_size);
    }
    
    void PM_Destroy(PageManager* pm) {
        if (pm) delete pm;
    }
    
    bool PM_CreatePage(PageManager* pm, int page_id) {
        return pm ? pm->create_page(page_id) : false;
    }
    
    bool PM_ReadPage(PageManager* pm, int page_id, uint8_t* buffer) {
        return pm ? pm->read_page(page_id, buffer) : false;
    }
    
    bool PM_WritePage(PageManager* pm, int page_id, const uint8_t* buffer) {
        return pm ? pm->write_page(page_id, buffer) : false;
    }
    
    void PM_FlushAll(PageManager* pm) {
        if (pm) pm->flush_all();
    }
}