#ifndef PAGE_HPP
#define PAGE_HPP

#include <vector>
#include <unordered_map>
#include <string>
#include <fstream>
#include <iostream>
#include <mutex>

// Platform-specific export macro for DLL generation
#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

// A Page is a container for raw bytes. 
// It can hold serialized ints, floats, custom classes, or image data.
struct Page {
    int id;
    bool is_dirty;   // Has the data changed since last save?
    bool is_loaded;  // Is the page currently in RAM?
    std::vector<uint8_t> data; // The payload

    Page() : id(-1), is_dirty(false), is_loaded(false) {}
};

class PageManager {
private:
    // The Page Table: Maps Page ID -> Page Object.
    // std::unordered_map provides O(1) average time complexity for lookups.
    std::unordered_map<int, Page> page_table;
    std::string storage_path;
    std::mutex mtx; // For thread safety

public:
    PageManager(const std::string& path);
    ~PageManager();

    // Core Management
    void create_page(int page_id, size_t size);
    bool load_page(int page_id);   // Load from disk to RAM
    bool unload_page(int page_id); // Remove from RAM (save if dirty)
    void save_page(int page_id);   // Write to disk
    
    // Data Access (O(1))
    // We return raw pointers to allow Python ctypes access
    uint8_t* get_data_ptr(int page_id);
    size_t get_data_size(int page_id);
    
    // Manipulation
    bool write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset);
    
    // Helper to simulate "class student" or other custom objects
    // In reality, this just resizes the byte buffer.
    void resize_page(int page_id, size_t new_size);
};

// C-Compatible Interface for Python (ctypes)
extern "C" {
    DLL_EXPORT PageManager* PM_Create(const char* path);
    DLL_EXPORT void PM_Destroy(PageManager* pm);
    DLL_EXPORT void PM_CreatePage(PageManager* pm, int id, int size);
    DLL_EXPORT void PM_Load(PageManager* pm, int id);
    DLL_EXPORT void PM_Unload(PageManager* pm, int id);
    DLL_EXPORT void PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset);
    DLL_EXPORT uint8_t* PM_GetData(PageManager* pm, int id);
    DLL_EXPORT int PM_GetSize(PageManager* pm, int id);
}

#endif // PAGE_HPP