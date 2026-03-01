#include "record_manager.hpp"
#include <cstring>

RecordManager::RecordManager(PageManager* page_manager) : pm(page_manager) {}
RecordManager::~RecordManager() {}

std::shared_mutex& RecordManager::get_page_latch(int page_id) {
    std::shared_lock<std::shared_mutex> read_lock(latch_map_mutex);
    auto it = page_latches.find(page_id);
    if (it != page_latches.end()) return *(it->second);
    read_lock.unlock();

    std::unique_lock<std::shared_mutex> write_lock(latch_map_mutex);
    it = page_latches.find(page_id);
    if (it == page_latches.end()) {
        it = page_latches.emplace(page_id, std::make_unique<std::shared_mutex>()).first;
    }
    return *(it->second);
}

void RecordManager::initialize_page_if_needed(uint8_t* page_data, size_t page_size) {
    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    // If it's a completely fresh, zeroed-out page from the memory map
    if (header->num_slots == 0 && header->free_space_offset == 0) {
        header->num_slots = 0;
        header->free_space_offset = page_size;
        header->deleted_bytes = 0;
    }
}

int RecordManager::insert_record(int page_id, const uint8_t* data, uint32_t size) {
    std::unique_lock<std::shared_mutex> lock(get_page_latch(page_id));
    
    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return -1;
    
    size_t page_size = pm->get_data_size(page_id);
    initialize_page_if_needed(page_data, page_size);

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    Slot* slots = reinterpret_cast<Slot*>(page_data + sizeof(PageHeader));

    // Search for a tombstoned slot to reuse
    int target_slot = -1;
    for (uint32_t i = 0; i < header->num_slots; ++i) {
        if (slots[i].length == 0) {
            target_slot = i;
            break;
        }
    }

    // Check if we have enough contiguous free space at the end of the page
    uint32_t space_needed = size + (target_slot == -1 ? sizeof(Slot) : 0);
    uint32_t space_available = header->free_space_offset - (sizeof(PageHeader) + (header->num_slots * sizeof(Slot)));
    
    if (space_needed > space_available) {
        // TODO: In a production system, you'd implement a defragmentation pass here
        // to reclaim deleted_bytes before rejecting the insert.
        return -1; // Page full
    }

    // Append new slot if we didn't recycle an old one
    if (target_slot == -1) {
        target_slot = header->num_slots;
        header->num_slots++;
    }

    // Shift free space offset backwards to make room for the payload
    header->free_space_offset -= size;
    slots[target_slot].offset = header->free_space_offset;
    slots[target_slot].length = size;

    // Drop the payload directly into the OS memory map
    std::memcpy(page_data + slots[target_slot].offset, data, size);
    
    return target_slot;
}

bool RecordManager::delete_record(int page_id, int slot_id) {
    std::unique_lock<std::shared_mutex> lock(get_page_latch(page_id));
    
    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return false;

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    if (slot_id < 0 || (uint32_t)slot_id >= header->num_slots) return false;

    Slot* slots = reinterpret_cast<Slot*>(page_data + sizeof(PageHeader));
    if (slots[slot_id].length == 0) return false; // Already tombstoned

    header->deleted_bytes += slots[slot_id].length;
    slots[slot_id].length = 0; // The Tombstone

    return true;
}

uint8_t* RecordManager::get_record(int page_id, int slot_id, uint32_t* out_size) {
    std::shared_lock<std::shared_mutex> lock(get_page_latch(page_id));
    
    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return nullptr;

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    if (slot_id < 0 || (uint32_t)slot_id >= header->num_slots) return nullptr;

    Slot* slots = reinterpret_cast<Slot*>(page_data + sizeof(PageHeader));
    if (slots[slot_id].length == 0) return nullptr; // Dead row

    *out_size = slots[slot_id].length;
    return page_data + slots[slot_id].offset;
}

// NEW: Core logic for the Sequential Scanner
int RecordManager::get_num_slots(int page_id) {
    std::shared_lock<std::shared_mutex> lock(get_page_latch(page_id));
    
    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return 0;

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    return header->num_slots;
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    RecordManager* RM_Create(PageManager* pm) { 
        return new RecordManager(pm); 
    }
    
    void RM_Destroy(RecordManager* rm) { 
        if (rm) delete rm; 
    }
    
    int RM_InsertRecord(RecordManager* rm, int page_id, const uint8_t* data, uint32_t size) {
        return rm ? rm->insert_record(page_id, data, size) : -1;
    }
    
    bool RM_DeleteRecord(RecordManager* rm, int page_id, int slot_id) {
        return rm ? rm->delete_record(page_id, slot_id) : false;
    }
    
    uint8_t* RM_GetRecord(RecordManager* rm, int page_id, int slot_id, uint32_t* out_size) {
        return rm ? rm->get_record(page_id, slot_id, out_size) : nullptr;
    }

    int RM_GetNumSlots(RecordManager* rm, int page_id) {
        return rm ? rm->get_num_slots(page_id) : 0;
    }
}