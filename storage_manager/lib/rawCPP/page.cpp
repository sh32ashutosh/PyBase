#include "page.hpp"
#include <cstring>
#include <stdexcept>

#ifndef _WIN32
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <sys/stat.h>
#endif

PageManager::PageManager(const std::string& path, size_t max_pages, size_t page_size) 
    : db_file_path(path), global_page_size(page_size), mapped_memory(nullptr) {
    
    total_extent_size = max_pages * page_size;

#ifdef _WIN32
    hFile = CreateFileA(path.c_str(), GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) throw std::runtime_error("Failed to open file natively.");

    hMapping = CreateFileMappingA(hFile, NULL, PAGE_READWRITE, 0, total_extent_size, NULL);
    if (!hMapping) throw std::runtime_error("Failed to create file mapping.");

    mapped_memory = (uint8_t*)MapViewOfFile(hMapping, FILE_MAP_ALL_ACCESS, 0, 0, total_extent_size);
    if (!mapped_memory) throw std::runtime_error("Failed to map view of file.");
#else
    fd = open(path.c_str(), O_RDWR | O_CREAT, 0666);
    if (fd == -1) throw std::runtime_error("Failed to open file natively.");

    if (ftruncate(fd, total_extent_size) == -1) throw std::runtime_error("Failed to resize extent file.");

    mapped_memory = (uint8_t*)mmap(NULL, total_extent_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mapped_memory == MAP_FAILED) throw std::runtime_error("Failed to mmap file.");
#endif
}

PageManager::~PageManager() {
    flush_all();
#ifdef _WIN32
    if (mapped_memory) UnmapViewOfFile(mapped_memory);
    if (hMapping) CloseHandle(hMapping);
    if (hFile != INVALID_HANDLE_VALUE) CloseHandle(hFile);
#else
    if (mapped_memory != MAP_FAILED) munmap(mapped_memory, total_extent_size);
    if (fd != -1) close(fd);
#endif
}

PageLock& PageManager::get_or_create_lock(int page_id) {
    std::shared_lock<std::shared_mutex> read_lock(table_lock);
    auto it = locks.find(page_id);
    if (it != locks.end()) return *(it->second);
    
    read_lock.unlock();
    std::unique_lock<std::shared_mutex> write_lock(table_lock);
    it = locks.find(page_id);
    if (it == locks.end()) {
        it = locks.emplace(page_id, std::make_unique<PageLock>()).first;
    }
    return *(it->second);
}

void PageManager::create_page(int page_id) {
    PageLock& lock = get_or_create_lock(page_id);
    std::unique_lock<std::shared_mutex> p_lock(lock.rw_lock);
    std::memset(mapped_memory + (page_id * global_page_size), 0, global_page_size);
}

bool PageManager::load_page(int page_id) {
    return true; 
}

bool PageManager::write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset) {
    if (offset + size > global_page_size) return false;

    PageLock& lock = get_or_create_lock(page_id);
    std::unique_lock<std::shared_mutex> p_lock(lock.rw_lock);
    
    std::memcpy(mapped_memory + (page_id * global_page_size) + offset, buffer, size);
    return true;
}

bool PageManager::unload_page(int page_id) {
#ifdef _WIN32
    FlushViewOfFile(mapped_memory + (page_id * global_page_size), global_page_size);
#else
    msync(mapped_memory + (page_id * global_page_size), global_page_size, MS_ASYNC);
#endif
    return true;
}

void PageManager::flush_all() {
#ifdef _WIN32
    if (mapped_memory) FlushViewOfFile(mapped_memory, 0);
#else
    if (mapped_memory != MAP_FAILED) msync(mapped_memory, total_extent_size, MS_SYNC);
#endif
}

uint8_t* PageManager::get_data_ptr(int page_id) {
    return mapped_memory + (page_id * global_page_size);
}

size_t PageManager::get_data_size(int page_id) {
    return global_page_size;
}

extern "C" {
    PageManager* PM_Create(const char* path, int max_pages, int page_size) { return new PageManager(std::string(path), (size_t)max_pages, (size_t)page_size); }
    void PM_Destroy(PageManager* pm) { if (pm) delete pm; }
    void PM_CreatePage(PageManager* pm, int id) { if (pm) pm->create_page(id); }
    int PM_Load(PageManager* pm, int id) { return (pm && pm->load_page(id)) ? 1 : 0; }
    int PM_Unload(PageManager* pm, int id) { return (pm && pm->unload_page(id)) ? 1 : 0; }
    int PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset) { return (pm && pm->write_data(id, data, (size_t)size, (size_t)offset)) ? 1 : 0; }
    uint8_t* PM_GetData(PageManager* pm, int id) { if (pm) return pm->get_data_ptr(id); return nullptr; }
    int PM_GetSize(PageManager* pm, int id) { if (pm) return (int)pm->get_data_size(id); return 0; }
    void PM_FlushAll(PageManager* pm) { if (pm) pm->flush_all(); }
}