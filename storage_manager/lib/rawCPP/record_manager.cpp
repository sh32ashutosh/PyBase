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
    // If free_space_offset is 0, this is a brand new page (since memory maps are zero-initialized)
    if (header->free_space_offset == 0 && header->num_slots == 0) {
        header->free_space_offset = static_cast<uint32_t>(page_size);
        header->deleted_bytes = 0;
    }
}

int RecordManager::insert_record(int page_id, const uint8_t* data, uint32_t size) {
    std::unique_lock<std::shared_mutex> lock(get_page_latch(page_id));

    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return -1; // Page not loaded

    size_t page_size = pm->get_data_size(page_id);
    initialize_page_if_needed(page_data, page_size);

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    Slot* slot_array = reinterpret_cast<Slot*>(page_data + sizeof(PageHeader));

    int target_slot = -1;

    // 1. Look for an empty tombstoned slot to reuse
    for (uint32_t i = 0; i < header->num_slots; ++i) {
        if (slot_array[i].length == 0) {
            target_slot = i;
            break;
        }
    }

    // 2. Calculate required space
    uint32_t required_space = size;
    if (target_slot == -1) {
        required_space += sizeof(Slot); // Need room for a new slot entry
    }

    uint32_t current_used_space = sizeof(PageHeader) + (header->num_slots * sizeof(Slot));
    if (header->free_space_offset - current_used_space < required_space) {
        return -1; // Page is full (Requires Compaction or new Page)
    }

    // 3. Allocate space from the bottom of the page (free_space_offset moves UP)
    header->free_space_offset -= size;
    uint32_t write_offset = header->free_space_offset;

    // 4. Copy the raw data directly into the memory map
    std::memcpy(page_data + write_offset, data, size);

    // 5. Update the Slot Array
    if (target_slot == -1) {
        target_slot = header->num_slots;
        header->num_slots++;
    }
    
    slot_array[target_slot].offset = write_offset;
    slot_array[target_slot].length = size;

    return target_slot;
}

uint8_t* RecordManager::get_record(int page_id, int slot_id, uint32_t* out_size) {
    std::shared_lock<std::shared_mutex> lock(get_page_latch(page_id));

    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return nullptr;

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    
    if (slot_id < 0 || (uint32_t)slot_id >= header->num_slots) return nullptr;

    Slot* slot_array = reinterpret_cast<Slot*>(page_data + sizeof(PageHeader));
    Slot target = slot_array[slot_id];

    if (target.length == 0) return nullptr; // Record was deleted

    if (out_size) *out_size = target.length;
    return page_data + target.offset;
}

bool RecordManager::delete_record(int page_id, int slot_id) {
    std::unique_lock<std::shared_mutex> lock(get_page_latch(page_id));

    uint8_t* page_data = pm->get_data_ptr(page_id);
    if (!page_data) return false;

    PageHeader* header = reinterpret_cast<PageHeader*>(page_data);
    
    if (slot_id < 0 || (uint32_t)slot_id >= header->num_slots) return false;

    Slot* slot_array = reinterpret_cast<Slot*>(page_data + sizeof(PageHeader));
    
    if (slot_array[slot_id].length > 0) {
        header->deleted_bytes += slot_array[slot_id].length;
        slot_array[slot_id].offset = 0;
        slot_array[slot_id].length = 0; // Tombstone the slot
        return true;
    }
    return false;
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    RecordManager* RM_Create(PageManager* pm) { return new RecordManager(pm); }
    void RM_Destroy(RecordManager* rm) { if (rm) delete rm; }
    int RM_InsertRecord(RecordManager* rm, int page_id, const uint8_t* data, uint32_t size) {
        if (!rm) return -1;
        return rm->insert_record(page_id, data, size);
    }
    bool RM_DeleteRecord(RecordManager* rm, int page_id, int slot_id) {
        if (!rm) return false;
        return rm->delete_record(page_id, slot_id);
    }
    uint8_t* RM_GetRecord(RecordManager* rm, int page_id, int slot_id, uint32_t* out_size) {
        if (!rm) return nullptr;
        return rm->get_record(page_id, slot_id, out_size);
    }
}