#ifndef RECORD_MANAGER_HPP
#define RECORD_MANAGER_HPP

#include "page.hpp"
#include <cstdint>
#include <vector>
#include <shared_mutex>
#include <mutex>
#include <unordered_map>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

// Disable C++ struct padding to ensure exact byte alignment on disk
#pragma pack(push, 1)

struct PageHeader {
    uint32_t num_slots;
    uint32_t free_space_offset; // Grows backwards from the end of the page
    uint32_t deleted_bytes;     // Tracks fragmentation
};

struct Slot {
    uint32_t offset; // Where the record starts
    uint32_t length; // How big it is (0 means deleted/empty)
};

#pragma pack(pop)

class RecordManager {
private:
    PageManager* pm;
    
    // Page-level latches to prevent two threads from corrupting the slot array
    std::unordered_map<int, std::unique_ptr<std::shared_mutex>> page_latches;
    std::shared_mutex latch_map_mutex;

    std::shared_mutex& get_page_latch(int page_id);
    void initialize_page_if_needed(uint8_t* page_data, size_t page_size);

public:
    RecordManager(PageManager* page_manager);
    ~RecordManager();

    // Returns the slot_id (or -1 if full)
    int insert_record(int page_id, const uint8_t* data, uint32_t size);
    
    // Deletes a record by zeroing its slot (returns true on success)
    bool delete_record(int page_id, int slot_id);
    
    // Gets a pointer to the record and sets out_size to its length
    uint8_t* get_record(int page_id, int slot_id, uint32_t* out_size);
};

// --- C-Compatible Export Interface ---
extern "C" {
    DLL_EXPORT RecordManager* RM_Create(PageManager* pm);
    DLL_EXPORT void RM_Destroy(RecordManager* rm);
    DLL_EXPORT int RM_InsertRecord(RecordManager* rm, int page_id, const uint8_t* data, uint32_t size);
    DLL_EXPORT bool RM_DeleteRecord(RecordManager* rm, int page_id, int slot_id);
    DLL_EXPORT uint8_t* RM_GetRecord(RecordManager* rm, int page_id, int slot_id, uint32_t* out_size);
}

#endif // RECORD_MANAGER_HPP