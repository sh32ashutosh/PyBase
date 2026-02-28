#ifndef PAGE_HPP
#define PAGE_HPP

#include <vector>
#include <unordered_map>
#include <string>
#include <cstdio>
#include <shared_mutex> // For Read/Write Locks
#include <mutex>
#include <atomic>       // Lock-free counters
#include <filesystem>   // Modern cross-platform file I/O
#include <cstring> // Required for std::memcpy
#include <cstdint> // Required for uint8_t, uint64_t

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

namespace fs = std::filesystem;

// Aligning to 64 bytes matches the standard CPU Cache Line size.
// This prevents "False Sharing" when multiple threads access different pages.
struct alignas(64) Page {
    int id;
    std::atomic<bool> is_dirty;
    std::atomic<bool> is_loaded;
    std::atomic<uint64_t> access_count; // Modern alternative to 'register' for fast LRU tracking
    
    std::vector<uint8_t> data;
    
    // Fine-grained lock: Multiple threads can read this specific page, 
    // but only one can write to it at a time.
    std::shared_mutex page_lock; 

    Page() : id(-1), is_dirty(false), is_loaded(false), access_count(0) {}
    
    // Delete copy constructors because mutexes cannot be copied
    Page(const Page&) = delete;
    Page& operator=(const Page&) = delete;
    
    // Allow moving
    Page(Page&& other) noexcept : id(other.id), data(std::move(other.data)) {
        is_dirty.store(other.is_dirty.load());
        is_loaded.store(other.is_loaded.load());
        access_count.store(other.access_count.load());
    }
};

class PageManager {
private:
    std::unordered_map<int, Page> page_table;
    std::string storage_path;
    
    // Table-level lock: Only locks when ADDING or REMOVING a page from the map.
    // Does NOT block threads reading/writing to already loaded pages.
    std::shared_mutex table_lock; 

    // Hard limit for RAM (e.g., 1024 pages). Triggers LRU eviction if exceeded.
    size_t max_pages_in_ram; 

    std::string get_page_filename(int page_id) {
        return (fs::path(storage_path) / ("page_" + std::to_string(page_id) + ".bin")).string();
    }

    // Internal helper to evict the coldest page
    void evict_coldest_page_if_needed();

public:
    PageManager(const std::string& path, size_t max_pages = 1000);
    ~PageManager();

    void create_page(int page_id, size_t size);
    bool load_page(int page_id);
    bool unload_page(int page_id);
    void flush_all();

    uint8_t* get_data_ptr(int page_id);
    size_t get_data_size(int page_id);
    bool write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset);
};

// --- Implementation ---

PageManager::PageManager(const std::string& path, size_t max_pages) 
    : storage_path(path), max_pages_in_ram(max_pages) {
    fs::create_directories(storage_path); // Secure, OS-agnostic directory creation
}

PageManager::~PageManager() {
    flush_all();
}

void PageManager::create_page(int page_id, size_t size) {
    evict_coldest_page_if_needed();

    std::unique_lock<std::shared_mutex> lock(table_lock); // Exclusive lock for table modification
    
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
        std::shared_lock<std::shared_mutex> lock(table_lock); // Shared read lock
        auto it = page_table.find(page_id);
        if (it != page_table.end()) {
            it->second.access_count++; // Atomic fast increment
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

    std::unique_lock<std::shared_mutex> lock(table_lock); // Exclusive lock just to insert
    page_table.emplace(page_id, std::move(p));
    return true;
}

bool PageManager::write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset) {
    std::shared_lock<std::shared_mutex> t_lock(table_lock); // Read table
    
    auto it = page_table.find(page_id);
    if (it == page_table.end()) return false;
    
    Page& p = it->second;
    std::unique_lock<std::shared_mutex> p_lock(p.page_lock); // Lock ONLY this specific page
    
    if (offset + size > p.data.size()) {
        p.data.resize(offset + size);
    }
    
    std::memcpy(p.data.data() + offset, buffer, size);
    p.is_dirty = true;
    p.access_count++;
    
    return true;
}

// --- Eviction Policy (LRU / Clock-Sweep Implementation) ---
void PageManager::evict_coldest_page_if_needed() {
    std::unique_lock<std::shared_mutex> lock(table_lock); // Exclusive lock
    
    // If we haven't hit the RAM limit, do nothing
    if (page_table.size() < max_pages_in_ram) return;

    int coldest_id = -1;
    uint64_t lowest_access = UINT64_MAX;

    // Find the page with the lowest access count
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
            
            // If the page was modified, flush it to disk before dropping it from RAM
            if (p.is_dirty.load()) {
                std::string filename = get_page_filename(coldest_id);
                FILE* f = fopen(filename.c_str(), "wb");
                if (f) {
                    fwrite(p.data.data(), 1, p.data.size(), f);
                    fclose(f);
                }
            }
            // Safely erase from the map
            page_table.erase(it);
        }
    }
}

// --- Unload & Flush Mechanics ---
bool PageManager::unload_page(int page_id) {
    std::unique_lock<std::shared_mutex> lock(table_lock); // Exclusive table lock
    
    auto it = page_table.find(page_id);
    if (it == page_table.end()) return false;

    // Flush to disk if dirty
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
    std::shared_lock<std::shared_mutex> t_lock(table_lock); // Shared read lock
    
    for (auto& pair : page_table) {
        Page& p = pair.second;
        
        // Fast atomic check
        if (p.is_dirty.load()) {
            std::unique_lock<std::shared_mutex> p_lock(p.page_lock); // Lock specific page
            
            // Double-check pattern in case another thread just flushed it
            if (p.is_dirty.load()) {
                std::string filename = get_page_filename(p.id);
                FILE* f = fopen(filename.c_str(), "wb");
                if (f) {
                    fwrite(p.data.data(), 1, p.data.size(), f);
                    fclose(f);
                    p.is_dirty.store(false); // Reset dirty flag atomically
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
        it->second.access_count++; // Mark as recently used
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

// --- C-Compatible Export Interface ---
extern "C" {
    // We added max_pages to support the memory limits constraint
    DLL_EXPORT PageManager* PM_Create(const char* path, int max_pages) { 
        return new PageManager(std::string(path), (size_t)max_pages); 
    }
    
    DLL_EXPORT void PM_Destroy(PageManager* pm) { 
        if (pm) delete pm; 
    }
    
    DLL_EXPORT void PM_CreatePage(PageManager* pm, int id, int size) { 
        if (pm) pm->create_page(id, (size_t)size); 
    }
    
    // Returns int (1 for true, 0 for false) to play nice with ctypes
    DLL_EXPORT int PM_Load(PageManager* pm, int id) { 
        return (pm && pm->load_page(id)) ? 1 : 0; 
    }
    
    DLL_EXPORT int PM_Unload(PageManager* pm, int id) { 
        return (pm && pm->unload_page(id)) ? 1 : 0; 
    }
    
    DLL_EXPORT int PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset) { 
        return (pm && pm->write_data(id, data, (size_t)size, (size_t)offset)) ? 1 : 0; 
    }
    
    DLL_EXPORT uint8_t* PM_GetData(PageManager* pm, int id) { 
        if (pm) return pm->get_data_ptr(id); 
        return nullptr; 
    }
    
    DLL_EXPORT int PM_GetSize(PageManager* pm, int id) { 
        if (pm) return (int)pm->get_data_size(id); 
        return 0; 
    }

    DLL_EXPORT void PM_FlushAll(PageManager* pm) {
        if (pm) pm->flush_all();
    }
}
#endif