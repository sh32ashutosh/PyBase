#ifndef PAGE_HPP
#define PAGE_HPP

#include <string>
#include <shared_mutex>
#include <mutex>
#include <unordered_map>
#include <cstdint>
#include <memory>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
    #include <windows.h>
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

struct PageLock {
    std::shared_mutex rw_lock;
};

class DLL_EXPORT PageManager {
private:
    std::string db_file_path;
    size_t global_page_size;
    size_t total_extent_size;
    
    uint8_t* mapped_memory;
    
#ifdef _WIN32
    HANDLE hFile;
    HANDLE hMapping;
#else
    int fd;
#endif

    std::unordered_map<int, std::unique_ptr<PageLock>> locks;
    std::shared_mutex table_lock; 

    PageLock& get_or_create_lock(int page_id);

public:
    PageManager(const std::string& path, size_t max_pages, size_t page_size);
    ~PageManager();

    void create_page(int page_id);
    bool load_page(int page_id);
    bool unload_page(int page_id);
    void flush_all();

    uint8_t* get_data_ptr(int page_id);
    size_t get_data_size(int page_id);
    bool write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset);
};

extern "C" {
    DLL_EXPORT PageManager* PM_Create(const char* path, int max_pages, int page_size);
    DLL_EXPORT void PM_Destroy(PageManager* pm);
    DLL_EXPORT void PM_CreatePage(PageManager* pm, int id);
    DLL_EXPORT int PM_Load(PageManager* pm, int id);
    DLL_EXPORT int PM_Unload(PageManager* pm, int id);
    DLL_EXPORT int PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset);
    DLL_EXPORT uint8_t* PM_GetData(PageManager* pm, int id);
    DLL_EXPORT int PM_GetSize(PageManager* pm, int id);
    DLL_EXPORT void PM_FlushAll(PageManager* pm);
}

#endif // PAGE_HPP