#ifndef TREE_HPP
#define TREE_HPP

#include "page.hpp"
#include <cstdint>
#include <shared_mutex>
#include <mutex>
#include <unordered_map>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

#pragma pack(push, 1)

// Represents the exact physical location of a row
struct RecordPointer {
    int32_t page_id;
    int32_t slot_id;
};

// Placed at byte 0 of any page acting as a B+ Tree node
struct BTreeHeader {
    uint8_t is_leaf;        // 1 if Leaf, 0 if Internal
    uint32_t num_keys;      // How many keys currently live in this node
    int32_t parent_page_id; // For back-tracking and splits (-1 if root)
    int32_t next_leaf_id;   // For fast range scans (e.g., "WHERE id > 50")
};

#pragma pack(pop)

class BTreeManager {
private:
    PageManager* pm;
    int root_page_id;
    size_t max_keys_per_node;

    std::shared_mutex tree_latch; // Global latch for structural changes (splits)

    void initialize_node(int page_id, bool is_leaf, int parent_id = -1);
    int allocate_new_page();

public:
    BTreeManager(PageManager* page_manager, int root_id);
    ~BTreeManager();

    // Core B+ Tree Operations (Primary Key = 64-bit Integer for now)
    bool insert(uint64_t key, RecordPointer ptr);
    RecordPointer search(uint64_t key);
    
    // Debug helper
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