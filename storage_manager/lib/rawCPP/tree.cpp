#include "tree.hpp"
#include <cstring>
#include <iostream>

BTreeManager::BTreeManager(PageManager* page_manager, int root_id) 
    : pm(page_manager), root_page_id(root_id) {
    
    // Calculate the maximum branching factor based on the PageManager's global page size
    size_t page_size = pm->get_data_size(root_id); // Assumes page size is globally consistent
    size_t available_space = page_size - sizeof(BTreeHeader);
    
    // Each entry in a leaf needs 1 Key (8 bytes) + 1 RecordPointer (8 bytes) = 16 bytes
    max_keys_per_node = available_space / (sizeof(uint64_t) + sizeof(RecordPointer));

    // Ensure root exists. If it's empty, format it as a leaf.
    uint8_t* root_data = pm->get_data_ptr(root_page_id);
    if (root_data) {
        BTreeHeader* header = reinterpret_cast<BTreeHeader*>(root_data);
        // If uninitialized (all zeroes from memory map), format it
        if (header->num_keys == 0 && header->is_leaf == 0 && header->parent_page_id == 0) {
            initialize_node(root_page_id, true, -1);
        }
    } else {
        pm->create_page(root_page_id);
        initialize_node(root_page_id, true, -1);
    }
}

BTreeManager::~BTreeManager() {}

void BTreeManager::initialize_node(int page_id, bool is_leaf, int parent_id) {
    uint8_t* data = pm->get_data_ptr(page_id);
    if (!data) return;

    BTreeHeader* header = reinterpret_cast<BTreeHeader*>(data);
    header->is_leaf = is_leaf ? 1 : 0;
    header->num_keys = 0;
    header->parent_page_id = parent_id;
    header->next_leaf_id = -1;
}

bool BTreeManager::insert(uint64_t key, RecordPointer ptr) {
    std::unique_lock<std::shared_mutex> lock(tree_latch);
    
    // For now, we are locking the logic to the Root node to prove the memory layout.
    // Node splitting and traversal will be layered on top of this.
    
    uint8_t* node_data = pm->get_data_ptr(root_page_id);
    if (!node_data) return false;

    BTreeHeader* header = reinterpret_cast<BTreeHeader*>(node_data);
    
    if (header->num_keys >= max_keys_per_node) {
        // TODO: Implement B+ Tree Split Logic
        return false; // Node full
    }

    uint64_t* keys = reinterpret_cast<uint64_t*>(node_data + sizeof(BTreeHeader));
    RecordPointer* pointers = reinterpret_cast<RecordPointer*>(node_data + sizeof(BTreeHeader) + (max_keys_per_node * sizeof(uint64_t)));

    // Find insertion point (Simple linear scan for foundation. Will upgrade to Binary Search).
    uint32_t insert_idx = 0;
    while (insert_idx < header->num_keys && keys[insert_idx] < key) {
        insert_idx++;
    }

    // Shift elements right to make room
    for (uint32_t i = header->num_keys; i > insert_idx; --i) {
        keys[i] = keys[i - 1];
        pointers[i] = pointers[i - 1];
    }

    // Insert
    keys[insert_idx] = key;
    pointers[insert_idx] = ptr;
    header->num_keys++;

    return true;
}

RecordPointer BTreeManager::search(uint64_t key) {
    std::shared_lock<std::shared_mutex> lock(tree_latch);
    RecordPointer not_found = {-1, -1};

    // Traversing from root
    int current_page_id = root_page_id;
    uint8_t* node_data = pm->get_data_ptr(current_page_id);
    if (!node_data) return not_found;

    BTreeHeader* header = reinterpret_cast<BTreeHeader*>(node_data);
    
    uint64_t* keys = reinterpret_cast<uint64_t*>(node_data + sizeof(BTreeHeader));
    RecordPointer* pointers = reinterpret_cast<RecordPointer*>(node_data + sizeof(BTreeHeader) + (max_keys_per_node * sizeof(uint64_t)));

    // Scan for key
    for (uint32_t i = 0; i < header->num_keys; ++i) {
        if (keys[i] == key) {
            return pointers[i]; // Found the exact row coordinates
        }
    }

    return not_found;
}

// --- C-Compatible Export Interface Implementations ---
extern "C" {
    BTreeManager* BT_Create(PageManager* pm, int root_page_id) { 
        return new BTreeManager(pm, root_page_id); 
    }
    
    void BT_Destroy(BTreeManager* bt) { 
        if (bt) delete bt; 
    }
    
    bool BT_Insert(BTreeManager* bt, uint64_t key, int32_t target_page, int32_t target_slot) {
        if (!bt) return false;
        RecordPointer rp = {target_page, target_slot};
        return bt->insert(key, rp);
    }
    
    RecordPointer BT_Search(BTreeManager* bt, uint64_t key) {
        if (!bt) return {-1, -1};
        return bt->search(key);
    }
}