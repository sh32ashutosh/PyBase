#ifndef PAGE_HPP
#define PAGE_HPP

#include <vector>
#include <unordered_map>
#include <string>
#include <cstdio>
#include <shared_mutex>
#include <mutex>
#include <atomic>
#include <filesystem>
#include <cstdint> // Added for fixed-width integers

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

// Aligning to 64 bytes matches the standard CPU Cache Line size.
struct alignas(64) Page {
    int id;
    std::atomic<bool> is_dirty;
    std::atomic<bool> is_loaded;
    std::atomic<uint64_t> access_count;
    
    std::vector<uint8_t> data;
    std::shared_mutex page_lock; 

    Page() : id(-1), is_dirty(false), is_loaded(false), access_count(0) {}
    
    Page(const Page&) = delete;
    Page& operator=(const Page&) = delete;
    
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
    std::shared_mutex table_lock; 
    size_t max_pages_in_ram; 

    std::string get_page_filename(int page_id);
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

// --- C-Compatible Export Interface Declarations ---
extern "C" {
    DLL_EXPORT PageManager* PM_Create(const char* path, int max_pages);
    DLL_EXPORT void PM_Destroy(PageManager* pm);
    DLL_EXPORT void PM_CreatePage(PageManager* pm, int id, int size);
    DLL_EXPORT int PM_Load(PageManager* pm, int id);
    DLL_EXPORT int PM_Unload(PageManager* pm, int id);
    DLL_EXPORT int PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset);
    DLL_EXPORT uint8_t* PM_GetData(PageManager* pm, int id);
    DLL_EXPORT int PM_GetSize(PageManager* pm, int id);
    DLL_EXPORT void PM_FlushAll(PageManager* pm);
}

#endif // PAGE_HPP