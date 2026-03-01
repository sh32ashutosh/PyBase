#ifndef TREE_HPP
#define TREE_HPP

#include "page.hpp"
#include <cstdint>
#include <shared_mutex>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

// Disable padding for airtight memory maps
#pragma pack(push, 1)

// Represents the exact physical location of a row in the Record Manager
struct RecordPointer {
    int32_t page_id;
    int32_t slot_id;
};

// Placed at byte 0 of any page acting as a B+ Tree node
struct BTreeHeader {
    uint8_t is_leaf;        // 1 if Leaf, 0 if Internal
    uint32_t num_keys;      // How many keys currently live in this node
    int32_t parent_page_id; // For back-tracking and splits (-1 if root)
    int32_t next_leaf_id;   // For fast range scans (linked list of leaves)
};

#pragma pack(pop)

class BTreeManager {
private:
    PageManager* pm;
    int root_page_id;
    
    // Calculated dynamically based on PageManager's global page size
    size_t max_keys_per_leaf;
    size_t max_keys_per_internal;

    std::shared_mutex tree_latch; // Global latch to prevent read corruption during splits

    // --- Core Memory Setup ---
    void initialize_node(int page_id, bool is_leaf, int parent_id = -1);
    int allocate_new_page();

    // --- The Splitting Engine ---
    bool insert_into_leaf(int current_page_id, uint64_t key, RecordPointer ptr);
    void split_leaf_node(int leaf_page_id, uint8_t* leaf_data);
    void split_internal_node(int internal_page_id, uint8_t* internal_data);
    void insert_into_parent(int left_page_id, uint64_t split_key, int right_page_id);

public:
    BTreeManager(PageManager* page_manager, int root_id);
    ~BTreeManager();

    // Core B+ Tree Operations
    bool insert(uint64_t key, RecordPointer ptr);
    RecordPointer search(uint64_t key);
    
    int get_root_id() const { return root_page_id; }
};

// --- C-Compatible Export Interface ---
extern "C" {
    DLL_EXPORT BTreeManager* BT_Create(PageManager* pm, int root_page_id);
    DLL_EXPORT void BT_Destroy(BTreeManager* bt);
    DLL_EXPORT bool BT_Insert(BTreeManager* bt, uint64_t key, int32_t target_page, int32_t target_slot);
    DLL_EXPORT RecordPointer BT_Search(BTreeManager* bt, uint64_t key);
}

#endif // TREE_HPP