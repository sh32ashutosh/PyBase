#include "tree.hpp"
#include <cstring>
#include <iostream>

BTreeManager::BTreeManager(PageManager* page_manager, int root_id) 
    : pm(page_manager), root_page_id(root_id) {
    
    size_t page_size = pm->get_data_size(root_id); 
    size_t available_space = page_size - sizeof(BTreeHeader);
    
    // Calculate branching factors
    max_keys_per_leaf = available_space / (sizeof(uint64_t) + sizeof(RecordPointer));
    max_keys_per_internal = available_space / (sizeof(uint64_t) + sizeof(int32_t));

    uint8_t* root_data = pm->get_data_ptr(root_page_id);
    if (root_data) {
        BTreeHeader* header = reinterpret_cast<BTreeHeader*>(root_data);
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

// Basic allocator for prototype (In a full system, this would read a metadata page)
int BTreeManager::allocate_new_page() {
    static int next_page = 100; // Assuming initial 1-99 are reserved or previously mapped
    int new_id = next_page++;
    pm->create_page(new_id);
    return new_id;
}

bool BTreeManager::insert(uint64_t key, RecordPointer ptr) {
    std::unique_lock<std::shared_mutex> lock(tree_latch);
    
    // 1. Find the correct leaf node (Traverse down)
    int current_page_id = root_page_id;
    uint8_t* node_data = pm->get_data_ptr(current_page_id);
    if (!node_data) return false;

    BTreeHeader* header = reinterpret_cast<BTreeHeader*>(node_data);

    while (!header->is_leaf) {
        uint64_t* keys = reinterpret_cast<uint64_t*>(node_data + sizeof(BTreeHeader));
        int32_t* children = reinterpret_cast<int32_t*>(node_data + sizeof(BTreeHeader) + (max_keys_per_internal * sizeof(uint64_t)));

        uint32_t i = 0;
        while (i < header->num_keys && key >= keys[i]) {
            i++;
        }
        current_page_id = children[i];
        node_data = pm->get_data_ptr(current_page_id);
        header = reinterpret_cast<BTreeHeader*>(node_data);
    }

    // 2. Insert into the target leaf
    return insert_into_leaf(current_page_id, key, ptr);
}

bool BTreeManager::insert_into_leaf(int page_id, uint64_t key, RecordPointer ptr) {
    uint8_t* data = pm->get_data_ptr(page_id);
    BTreeHeader* header = reinterpret_cast<BTreeHeader*>(data);

    if (header->num_keys >= max_keys_per_leaf) {
        split_leaf_node(page_id, data);
        // Retry insertion from root after split alters the tree structure
        tree_latch.unlock();
        return insert(key, ptr); 
    }

    uint64_t* keys = reinterpret_cast<uint64_t*>(data + sizeof(BTreeHeader));
    RecordPointer* pointers = reinterpret_cast<RecordPointer*>(data + sizeof(BTreeHeader) + (max_keys_per_leaf * sizeof(uint64_t)));

    uint32_t insert_idx = 0;
    while (insert_idx < header->num_keys && keys[insert_idx] < key) insert_idx++;

    for (uint32_t i = header->num_keys; i > insert_idx; --i) {
        keys[i] = keys[i - 1];
        pointers[i] = pointers[i - 1];
    }

    keys[insert_idx] = key;
    pointers[insert_idx] = ptr;
    header->num_keys++;

    return true;
}

void BTreeManager::split_leaf_node(int left_id, uint8_t* left_data) {
    int right_id = allocate_new_page();
    uint8_t* right_data = pm->get_data_ptr(right_id);
    
    BTreeHeader* left_header = reinterpret_cast<BTreeHeader*>(left_data);
    initialize_node(right_id, true, left_header->parent_page_id);
    BTreeHeader* right_header = reinterpret_cast<BTreeHeader*>(right_data);

    uint64_t* left_keys = reinterpret_cast<uint64_t*>(left_data + sizeof(BTreeHeader));
    RecordPointer* left_ptrs = reinterpret_cast<RecordPointer*>(left_data + sizeof(BTreeHeader) + (max_keys_per_leaf * sizeof(uint64_t)));

    uint64_t* right_keys = reinterpret_cast<uint64_t*>(right_data + sizeof(BTreeHeader));
    RecordPointer* right_ptrs = reinterpret_cast<RecordPointer*>(right_data + sizeof(BTreeHeader) + (max_keys_per_leaf * sizeof(uint64_t)));

    // Cleave in half
    uint32_t mid = left_header->num_keys / 2;
    uint32_t move_count = left_header->num_keys - mid;

    std::memcpy(right_keys, left_keys + mid, move_count * sizeof(uint64_t));
    std::memcpy(right_ptrs, left_ptrs + mid, move_count * sizeof(RecordPointer));

    left_header->num_keys = mid;
    right_header->num_keys = move_count;

    // Link the leaves for range scans
    right_header->next_leaf_id = left_header->next_leaf_id;
    left_header->next_leaf_id = right_id;

    uint64_t split_key = right_keys[0];
    insert_into_parent(left_id, split_key, right_id);
}

void BTreeManager::insert_into_parent(int left_id, uint64_t split_key, int right_id) {
    uint8_t* left_data = pm->get_data_ptr(left_id);
    BTreeHeader* left_header = reinterpret_cast<BTreeHeader*>(left_data);

    // If root was split, create a new root
    if (left_header->parent_page_id == -1) {
        int new_root_id = allocate_new_page();
        initialize_node(new_root_id, false, -1);
        
        uint8_t* root_data = pm->get_data_ptr(new_root_id);
        BTreeHeader* root_header = reinterpret_cast<BTreeHeader*>(root_data);
        
        uint64_t* root_keys = reinterpret_cast<uint64_t*>(root_data + sizeof(BTreeHeader));
        int32_t* root_children = reinterpret_cast<int32_t*>(root_data + sizeof(BTreeHeader) + (max_keys_per_internal * sizeof(uint64_t)));

        root_keys[0] = split_key;
        root_children[0] = left_id;
        root_children[1] = right_id;
        root_header->num_keys = 1;

        left_header->parent_page_id = new_root_id;
        reinterpret_cast<BTreeHeader*>(pm->get_data_ptr(right_id))->parent_page_id = new_root_id;
        
        root_page_id = new_root_id;
        return;
    }

    int parent_id = left_header->parent_page_id;
    uint8_t* parent_data = pm->get_data_ptr(parent_id);
    BTreeHeader* parent_header = reinterpret_cast<BTreeHeader*>(parent_data);

    if (parent_header->num_keys >= max_keys_per_internal) {
        // Recursive split if parent is full
        // (Simplified for prototype: a true production system handles cascading internal splits here)
        return; 
    }

    uint64_t* p_keys = reinterpret_cast<uint64_t*>(parent_data + sizeof(BTreeHeader));
    int32_t* p_children = reinterpret_cast<int32_t*>(parent_data + sizeof(BTreeHeader) + (max_keys_per_internal * sizeof(uint64_t)));

    uint32_t insert_idx = 0;
    while (insert_idx < parent_header->num_keys && p_keys[insert_idx] < split_key) insert_idx++;

    for (uint32_t i = parent_header->num_keys; i > insert_idx; --i) {
        p_keys[i] = p_keys[i - 1];
        p_children[i + 1] = p_children[i];
    }

    p_keys[insert_idx] = split_key;
    p_children[insert_idx + 1] = right_id;
    parent_header->num_keys++;
}

RecordPointer BTreeManager::search(uint64_t key) {
    std::shared_lock<std::shared_mutex> lock(tree_latch);
    RecordPointer not_found = {-1, -1};

    int current_page_id = root_page_id;
    uint8_t* node_data = pm->get_data_ptr(current_page_id);
    if (!node_data) return not_found;

    BTreeHeader* header = reinterpret_cast<BTreeHeader*>(node_data);

    // Traverse internal nodes
    while (!header->is_leaf) {
        uint64_t* keys = reinterpret_cast<uint64_t*>(node_data + sizeof(BTreeHeader));
        int32_t* children = reinterpret_cast<int32_t*>(node_data + sizeof(BTreeHeader) + (max_keys_per_internal * sizeof(uint64_t)));

        uint32_t i = 0;
        while (i < header->num_keys && key >= keys[i]) i++;
        
        current_page_id = children[i];
        node_data = pm->get_data_ptr(current_page_id);
        header = reinterpret_cast<BTreeHeader*>(node_data);
    }

    // Binary search in leaf
    uint64_t* keys = reinterpret_cast<uint64_t*>(node_data + sizeof(BTreeHeader));
    RecordPointer* pointers = reinterpret_cast<RecordPointer*>(node_data + sizeof(BTreeHeader) + (max_keys_per_leaf * sizeof(uint64_t)));

    uint32_t left = 0, right = header->num_keys;
    while (left < right) {
        uint32_t mid = left + (right - left) / 2;
        if (keys[mid] < key) left = mid + 1;
        else right = mid;
    }

    if (left < header->num_keys && keys[left] == key) return pointers[left];
    return not_found;
}

extern "C" {
    BTreeManager* BT_Create(PageManager* pm, int root_page_id) { return new BTreeManager(pm, root_page_id); }
    void BT_Destroy(BTreeManager* bt) { if (bt) delete bt; }
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