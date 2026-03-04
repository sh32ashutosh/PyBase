#ifndef RECORD_MANAGER_HPP
#define RECORD_MANAGER_HPP

#include "page.hpp"
#include <cstdint>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

class RecordManager {
private:
    PageManager* pm;

public:
    RecordManager(PageManager* page_manager);
    ~RecordManager();

    int insert_record(int page_id, const uint8_t* data, uint32_t size);
    bool delete_record(int page_id, int slot_id);
    bool get_record(int page_id, int slot_id, uint8_t* out_buffer, uint32_t* out_size);
    
    // THE MISSING PIECE RESTORED
    int get_num_slots(int page_id);
};

// --- C-Compatible Export Interface ---
extern "C" {
    DLL_EXPORT RecordManager* RM_Create(PageManager* pm);
    DLL_EXPORT void RM_Destroy(RecordManager* rm);
    DLL_EXPORT int RM_InsertRecord(RecordManager* rm, int page_id, const uint8_t* data, uint32_t size);
    DLL_EXPORT bool RM_DeleteRecord(RecordManager* rm, int page_id, int slot_id);
    DLL_EXPORT bool RM_GetRecord(RecordManager* rm, int page_id, int slot_id, uint8_t* out_buffer, uint32_t* out_size);
    
    // EXPORTED SO PYTHON CAN ACTUALLY SEE IT
    DLL_EXPORT int RM_GetNumSlots(RecordManager* rm, int page_id);
}

#endif // RECORD_MANAGER_HPP