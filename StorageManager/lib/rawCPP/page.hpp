#ifndef PAGE_HPP
#define PAGE_HPP

#include <string>
#include <fstream>
#include <vector>
#include <unordered_map>
#include <mutex>
#include <cstdint>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

class PageManager {
private:
    std::string db_file_path;
    std::fstream db_file;
    int max_pages;
    int page_size;
    std::mutex pm_mutex;

    // Simple in-memory buffer pool
    std::unordered_map<int, std::vector<uint8_t>> buffer_pool;

public:
    PageManager(const std::string& db_path, int max_pages, int page_size);
    ~PageManager();

    bool create_page(int page_id);
    bool read_page(int page_id, uint8_t* buffer);
    bool write_page(int page_id, const uint8_t* buffer);
    void flush_all();
};

// --- C-Compatible Export Interface ---
extern "C" {
    DLL_EXPORT PageManager* PM_Create(const char* db_path, int max_pages, int page_size);
    DLL_EXPORT void PM_Destroy(PageManager* pm);
    DLL_EXPORT bool PM_CreatePage(PageManager* pm, int page_id);
    // THESE WERE MISSING! Now Python can actually see them:
    DLL_EXPORT bool PM_ReadPage(PageManager* pm, int page_id, uint8_t* buffer);
    DLL_EXPORT bool PM_WritePage(PageManager* pm, int page_id, const uint8_t* buffer);
    DLL_EXPORT void PM_FlushAll(PageManager* pm);
}

#endif // PAGE_HPP