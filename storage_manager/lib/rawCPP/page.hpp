#ifndef PAGE_HPP
#define PAGE_HPP

#include <vector>
#include <unordered_map>
#include <string>
#include <cstdio> // FAST I/O
#include <mutex>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

// The Container
struct Page {
    int id;
    bool is_dirty;
    bool is_loaded;
    std::vector<uint8_t> data;
    Page() : id(-1), is_dirty(false), is_loaded(false) {}
};

class PageManager {
private:
    std::unordered_map<int, Page> page_table;
    std::string storage_path; // The folder where .bin files live
    std::mutex mtx;

    // Helper to get filename: "databases/page_1.bin"
    std::string get_page_filename(int page_id);

public:
    PageManager(const std::string& path);
    ~PageManager();

    // Core
    void create_page(int page_id, size_t size);
    bool load_page(int page_id);
    bool unload_page(int page_id);
    void save_page(int page_id);
    void flush_all();

    // Data Access
    uint8_t* get_data_ptr(int page_id);
    size_t get_data_size(int page_id);
    bool write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset);
};

// C-Compatible Interface for Python
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

#endif // PAGE_HPP end