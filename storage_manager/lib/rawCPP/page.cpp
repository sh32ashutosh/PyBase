#include "page.hpp"
#include <cstring>
#include <iostream>
#include <sys/stat.h>

// Helper to construct paths safely
std::string PageManager::get_page_filename(int page_id) {
    return storage_path + "/page_" + std::to_string(page_id) + ".bin";
}

PageManager::PageManager(const std::string& path) : storage_path(path) {
    // 1. Create Directory (Windows command)
    std::string cmd = "mkdir \"" + path + "\" >nul 2>nul"; 
    system(cmd.c_str());
}

PageManager::~PageManager() {
    flush_all();
}

void PageManager::create_page(int page_id, size_t size) {
    std::lock_guard<std::mutex> lock(mtx);
    Page p;
    p.id = page_id;
    p.is_loaded = true;
    p.is_dirty = true; // New pages need saving
    p.data.resize(size, 0); // Initialize with zeros
    page_table[page_id] = std::move(p);
}

bool PageManager::load_page(int page_id) {
    std::lock_guard<std::mutex> lock(mtx);
    
    // 1. Check RAM Cache
    if (page_table.find(page_id) != page_table.end()) return true;

    // 2. Open File
    std::string filename = get_page_filename(page_id);
    FILE* f = fopen(filename.c_str(), "rb");
    
    if (!f) return false; // File not found

    // 3. Get File Size
    fseek(f, 0, SEEK_END);
    long filesize = ftell(f);
    fseek(f, 0, SEEK_SET);

    // 4. Read Data
    Page p;
    p.id = page_id;
    p.is_loaded = true;
    p.is_dirty = false;
    p.data.resize(filesize);
    
    fread(p.data.data(), 1, filesize, f);
    fclose(f);

    page_table[page_id] = std::move(p);
    return true;
}

void PageManager::save_page(int page_id) {
    std::lock_guard<std::mutex> lock(mtx);
    if (page_table.find(page_id) == page_table.end()) return;

    Page& p = page_table[page_id];
    if (!p.is_dirty) return;

    std::string filename = get_page_filename(page_id);
    FILE* f = fopen(filename.c_str(), "wb");
    if (f) {
        fwrite(p.data.data(), 1, p.data.size(), f);
        fclose(f);
        p.is_dirty = false;
    }
}

bool PageManager::unload_page(int page_id) {
    std::lock_guard<std::mutex> lock(mtx);
    auto it = page_table.find(page_id);
    if (it == page_table.end()) return false;

    // Save if dirty
    if (it->second.is_dirty) {
        std::string filename = get_page_filename(page_id);
        FILE* f = fopen(filename.c_str(), "wb");
        if (f) {
            fwrite(it->second.data.data(), 1, it->second.data.size(), f);
            fclose(f);
        }
    }

    page_table.erase(it);
    return true;
}

void PageManager::flush_all() {
    std::lock_guard<std::mutex> lock(mtx);
    for (auto& pair : page_table) {
        if (pair.second.is_loaded && pair.second.is_dirty) {
            std::string filename = get_page_filename(pair.first);
            FILE* f = fopen(filename.c_str(), "wb");
            if (f) {
                fwrite(pair.second.data.data(), 1, pair.second.data.size(), f);
                fclose(f);
                pair.second.is_dirty = false;
            }
        }
    }
}

// Data Access & Wrappers
uint8_t* PageManager::get_data_ptr(int page_id) {
    if (page_table.find(page_id) != page_table.end()) return page_table[page_id].data.data();
    return nullptr;
}

size_t PageManager::get_data_size(int page_id) {
    if (page_table.find(page_id) != page_table.end()) return page_table[page_id].data.size();
    return 0;
}

bool PageManager::write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset) {
    std::lock_guard<std::mutex> lock(mtx);
    if (page_table.find(page_id) == page_table.end()) return false;
    
    Page& p = page_table[page_id];
    if (offset + size > p.data.size()) {
        p.data.resize(offset + size);
    }
    
    std::memcpy(p.data.data() + offset, buffer, size);
    p.is_dirty = true;
    return true;
}

// C Interface Exports
PageManager* PM_Create(const char* path) { return new PageManager(std::string(path)); }
void PM_Destroy(PageManager* pm) { if (pm) delete pm; }
void PM_CreatePage(PageManager* pm, int id, int size) { if (pm) pm->create_page(id, size); }
void PM_Load(PageManager* pm, int id) { if (pm) pm->load_page(id); }
void PM_Unload(PageManager* pm, int id) { if (pm) pm->unload_page(id); }
void PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset) { if (pm) pm->write_data(id, data, size, offset); }
uint8_t* PM_GetData(PageManager* pm, int id) { if (pm) return pm->get_data_ptr(id); return nullptr; }
int PM_GetSize(PageManager* pm, int id) { if (pm) return (int)pm->get_data_size(id); return 0; }