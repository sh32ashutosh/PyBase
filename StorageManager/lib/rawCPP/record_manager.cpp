#include "record_manager.hpp"
#include <cstring>
#include <vector>
#include <iostream>

const int PAGE_SIZE = 102400;

struct PageHeader {
    uint32_t num_slots;
    uint32_t free_space_offset;
};

struct Slot {
    uint32_t record_offset;
    uint32_t record_size;
};

RecordManager::RecordManager(PageManager* page_manager) : pm(page_manager) {}

RecordManager::~RecordManager() {}

int RecordManager::insert_record(int page_id, const uint8_t* data, uint32_t size) {
    std::vector<uint8_t> buffer(PAGE_SIZE);
    
    if (!PM_ReadPage(pm, page_id, buffer.data())) {
        PM_CreatePage(pm, page_id);
        PM_ReadPage(pm, page_id, buffer.data());
        PageHeader* header = reinterpret_cast<PageHeader*>(buffer.data());
        header->num_slots = 0;
        header->free_space_offset = PAGE_SIZE;
    }

    PageHeader* header = reinterpret_cast<PageHeader*>(buffer.data());
    
    uint32_t required_space = size + sizeof(Slot);
    uint32_t available_space = header->free_space_offset - (sizeof(PageHeader) + header->num_slots * sizeof(Slot));
    
    if (required_space > available_space) {
        return -1; // Out of space
    }

    int slot_id = header->num_slots;
    header->num_slots++;
    header->free_space_offset -= size;

    Slot* slots = reinterpret_cast<Slot*>(buffer.data() + sizeof(PageHeader));
    slots[slot_id].record_offset = header->free_space_offset;
    slots[slot_id].record_size = size;

    std::memcpy(buffer.data() + header->free_space_offset, data, size);

    PM_WritePage(pm, page_id, buffer.data());

    return slot_id;
}

bool RecordManager::delete_record(int page_id, int slot_id) {
    std::vector<uint8_t> buffer(PAGE_SIZE);
    if (!PM_ReadPage(pm, page_id, buffer.data())) return false;

    PageHeader* header = reinterpret_cast<PageHeader*>(buffer.data());
    if (static_cast<uint32_t>(slot_id) >= header->num_slots) return false;

    Slot* slots = reinterpret_cast<Slot*>(buffer.data() + sizeof(PageHeader));
    slots[slot_id].record_size = 0; // Tombstone

    PM_WritePage(pm, page_id, buffer.data());
    return true;
}

bool RecordManager::get_record(int page_id, int slot_id, uint8_t* out_buffer, uint32_t* out_size) {
    std::vector<uint8_t> buffer(PAGE_SIZE);
    if (!PM_ReadPage(pm, page_id, buffer.data())) return false;

    PageHeader* header = reinterpret_cast<PageHeader*>(buffer.data());
    if (static_cast<uint32_t>(slot_id) >= header->num_slots) return false;

    Slot* slots = reinterpret_cast<Slot*>(buffer.data() + sizeof(PageHeader));
    if (slots[slot_id].record_size == 0) return false; // Tombstoned

    std::memcpy(out_buffer, buffer.data() + slots[slot_id].record_offset, slots[slot_id].record_size);
    *out_size = slots[slot_id].record_size;
    
    return true;
}

// IMPLEMENTING THE MISSING FUNCTION
int RecordManager::get_num_slots(int page_id) {
    std::vector<uint8_t> buffer(PAGE_SIZE);
    if (!PM_ReadPage(pm, page_id, buffer.data())) return 0;
    
    PageHeader* header = reinterpret_cast<PageHeader*>(buffer.data());
    return header->num_slots;
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    RecordManager* RM_Create(PageManager* pm) { return new RecordManager(pm); }
    void RM_Destroy(RecordManager* rm) { if (rm) delete rm; }
    
    int RM_InsertRecord(RecordManager* rm, int page_id, const uint8_t* data, uint32_t size) {
        return rm ? rm->insert_record(page_id, data, size) : -1;
    }
    
    bool RM_DeleteRecord(RecordManager* rm, int page_id, int slot_id) {
        return rm ? rm->delete_record(page_id, slot_id) : false;
    }
    
    bool RM_GetRecord(RecordManager* rm, int page_id, int slot_id, uint8_t* out_buffer, uint32_t* out_size) {
        return rm ? rm->get_record(page_id, slot_id, out_buffer, out_size) : false;
    }
    
    // BRIDGING THE MISSING FUNCTION TO PYTHON
    int RM_GetNumSlots(RecordManager* rm, int page_id) {
        return rm ? rm->get_num_slots(page_id) : 0;
    }
}