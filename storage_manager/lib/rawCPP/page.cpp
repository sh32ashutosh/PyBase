#include "page.hpp"
#include <cstring>

namespace fs = std::filesystem;

// --- Private Helpers ---
std::string PageManager::get_page_filename(int page_id) {
    return (fs::path(storage_path) / ("page_" + std::to_string(page_id) + ".bin")).string();
}

void PageManager::evict_coldest_page_if_needed() {
    std::unique_lock<std::shared_mutex> lock(table_lock); 
    
    if (page_table.size() < max_pages_in_ram) return;

    int coldest_id = -1;
    uint64_t lowest_access = UINT64_MAX;

    for (const auto& pair : page_table) {
        uint64_t accesses = pair.second.access_count.load();
        if (accesses < lowest_access) {
            lowest_access = accesses;
            coldest_id = pair.first;
        }
    }

    if (coldest_id != -1) {
        auto it = page_table.find(coldest_id);
        if (it != page_table.end()) {
            Page& p = it->second;
            
            if (p.is_dirty.load()) {
                std::string filename = get_page_filename(coldest_id);
                FILE* f = fopen(filename.c_str(), "wb");
                if (f) {
                    fwrite(p.data.data(), 1, p.data.size(), f);
                    fclose(f);
                }
            }
            page_table.erase(it);
        }
    }
}

// --- Constructor & Destructor ---
PageManager::PageManager(const std::string& path, size_t max_pages) 
    : storage_path(path), max_pages_in_ram(max_pages) {
    fs::create_directories(storage_path); 
}

PageManager::~PageManager() {
    flush_all();
}

// --- Core Operations ---
void PageManager::create_page(int page_id, size_t size) {
    evict_coldest_page_if_needed();

    std::unique_lock<std::shared_mutex> lock(table_lock); 
    
    Page p;
    p.id = page_id;
    p.is_loaded = true;
    p.is_dirty = true;
    p.access_count = 1;
    p.data.resize(size, 0);
    
    page_table.emplace(page_id, std::move(p));
}

bool PageManager::load_page(int page_id) {
    {
        std::shared_lock<std::shared_mutex> lock(table_lock); 
        auto it = page_table.find(page_id);
        if (it != page_table.end()) {
            it->second.access_count++; 
            return true;
        }
    }

    evict_coldest_page_if_needed();

    std::string filename = get_page_filename(page_id);
    FILE* f = fopen(filename.c_str(), "rb");
    if (!f) return false;

    fseek(f, 0, SEEK_END);
    long filesize = ftell(f);
    fseek(f, 0, SEEK_SET);

    Page p;
    p.id = page_id;
    p.is_loaded = true;
    p.is_dirty = false;
    p.access_count = 1;
    p.data.resize(filesize);
    
    fread(p.data.data(), 1, filesize, f);
    fclose(f);

    std::unique_lock<std::shared_mutex> lock(table_lock); 
    page_table.emplace(page_id, std::move(p));
    return true;
}

bool PageManager::write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset) {
    std::shared_lock<std::shared_mutex> t_lock(table_lock); 
    
    auto it = page_table.find(page_id);
    if (it == page_table.end()) return false;
    
    Page& p = it->second;
    std::unique_lock<std::shared_mutex> p_lock(p.page_lock); 
    
    if (offset + size > p.data.size()) {
        p.data.resize(offset + size);
    }
    
    std::memcpy(p.data.data() + offset, buffer, size);
    p.is_dirty = true;
    p.access_count++;
    
    return true;
}

bool PageManager::unload_page(int page_id) {
    std::unique_lock<std::shared_mutex> lock(table_lock); 
    
    auto it = page_table.find(page_id);
    if (it == page_table.end()) return false;

    if (it->second.is_dirty.load()) {
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
    std::shared_lock<std::shared_mutex> t_lock(table_lock); 
    
    for (auto& pair : page_table) {
        Page& p = pair.second;
        
        if (p.is_dirty.load()) {
            std::unique_lock<std::shared_mutex> p_lock(p.page_lock); 
            
            if (p.is_dirty.load()) {
                std::string filename = get_page_filename(p.id);
                FILE* f = fopen(filename.c_str(), "wb");
                if (f) {
                    fwrite(p.data.data(), 1, p.data.size(), f);
                    fclose(f);
                    p.is_dirty.store(false); 
                }
            }
        }
    }
}

// --- Data Accessors ---
uint8_t* PageManager::get_data_ptr(int page_id) {
    std::shared_lock<std::shared_mutex> lock(table_lock);
    auto it = page_table.find(page_id);
    if (it != page_table.end()) {
        it->second.access_count++; 
        return it->second.data.data();
    }
    return nullptr;
}

size_t PageManager::get_data_size(int page_id) {
    std::shared_lock<std::shared_mutex> lock(table_lock);
    auto it = page_table.find(page_id);
    if (it != page_table.end()) {
        return it->second.data.size();
    }
    return 0;
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    PageManager* PM_Create(const char* path, int max_pages) { 
        return new PageManager(std::string(path), (size_t)max_pages); 
    }
    
    void PM_Destroy(PageManager* pm) { 
        if (pm) delete pm; 
    }
    
    void PM_CreatePage(PageManager* pm, int id, int size) { 
        if (pm) pm->create_page(id, (size_t)size); 
    }
    
    int PM_Load(PageManager* pm, int id) { 
        return (pm && pm->load_page(id)) ? 1 : 0; 
    }
    
    int PM_Unload(PageManager* pm, int id) { 
        return (pm && pm->unload_page(id)) ? 1 : 0; 
    }
    
    int PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset) { 
        return (pm && pm->write_data(id, data, (size_t)size, (size_t)offset)) ? 1 : 0; 
    }
    
    uint8_t* PM_GetData(PageManager* pm, int id) { 
        if (pm) return pm->get_data_ptr(id); 
        return nullptr; 
    }
    
    int PM_GetSize(PageManager* pm, int id) { 
        if (pm) return (int)pm->get_data_size(id); 
        return 0; 
    }

    void PM_FlushAll(PageManager* pm) {
        if (pm) pm->flush_all();
    }
}