#ifndef TREE_HPP
#define TREE_HPP

#include "page.hpp"
#include <cstdint>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

struct RecordPointer {
    int page_id;
    int slot_id;
};

class BTreeManager {
private:
    PageManager* pm;
    int root_page_id;

public:
    BTreeManager(PageManager* page_manager, int root_page);
    ~BTreeManager();

    bool insert(uint64_t key, RecordPointer ptr);
    RecordPointer search(uint64_t key);
};

extern "C" {
    // UPDATED NAMES TO MATCH PYTHON WRAPPER
    DLL_EXPORT BTreeManager* BT_Create(PageManager* pm, int root_page_id);
    DLL_EXPORT void BT_Destroy(BTreeManager* tree);
    DLL_EXPORT bool BT_Insert(BTreeManager* tree, uint64_t key, int page_id, int slot_id);
    DLL_EXPORT bool BT_Search(BTreeManager* tree, uint64_t key, int* out_page_id, int* out_slot_id);
}

#endif