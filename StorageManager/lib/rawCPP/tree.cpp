#include "tree.hpp"
#include <cstring>
#include <vector>

const int PAGE_SIZE = 102400;

struct TreeNodeHeader {
    uint32_t num_keys;
    uint32_t is_leaf;
    uint32_t next_leaf_page;
};

struct TreeRecord {
    uint64_t key;
    RecordPointer ptr;
};

BTreeManager::BTreeManager(PageManager* page_manager, int root_page) 
    : pm(page_manager), root_page_id(root_page) {
    
    std::vector<uint8_t> buffer(PAGE_SIZE);
    if (!PM_ReadPage(pm, root_page_id, buffer.data())) {
        PM_CreatePage(pm, root_page_id);
        PM_ReadPage(pm, root_page_id, buffer.data());
        TreeNodeHeader* header = reinterpret_cast<TreeNodeHeader*>(buffer.data());
        header->num_keys = 0;
        header->is_leaf = 1;
        header->next_leaf_page = 0;
        PM_WritePage(pm, root_page_id, buffer.data());
    }
}

BTreeManager::~BTreeManager() {}

bool BTreeManager::insert(uint64_t key, RecordPointer ptr) {
    std::vector<uint8_t> buffer(PAGE_SIZE);
    int current_page = root_page_id;
    
    while (true) {
        if (!PM_ReadPage(pm, current_page, buffer.data())) return false;
        
        TreeNodeHeader* header = reinterpret_cast<TreeNodeHeader*>(buffer.data());
        uint32_t max_keys = (PAGE_SIZE - sizeof(TreeNodeHeader)) / sizeof(TreeRecord);
        
        if (header->num_keys < max_keys) {
            TreeRecord* records = reinterpret_cast<TreeRecord*>(buffer.data() + sizeof(TreeNodeHeader));
            records[header->num_keys].key = key;
            records[header->num_keys].ptr = ptr;
            header->num_keys++;
            PM_WritePage(pm, current_page, buffer.data());
            return true;
        } else {
            if (header->next_leaf_page == 0) {
                int new_page = (current_page == 0) ? 2 : current_page + 1;
                PM_CreatePage(pm, new_page);
                header->next_leaf_page = new_page;
                PM_WritePage(pm, current_page, buffer.data());
                
                std::vector<uint8_t> new_buffer(PAGE_SIZE, 0);
                TreeNodeHeader* new_h = reinterpret_cast<TreeNodeHeader*>(new_buffer.data());
                new_h->num_keys = 0;
                new_h->is_leaf = 1;
                new_h->next_leaf_page = 0;
                PM_WritePage(pm, new_page, new_buffer.data());
                current_page = new_page;
            } else {
                current_page = header->next_leaf_page;
            }
        }
    }
}

RecordPointer BTreeManager::search(uint64_t key) {
    std::vector<uint8_t> buffer(PAGE_SIZE);
    int current_page = root_page_id;
    
    while (true) {
        if (!PM_ReadPage(pm, current_page, buffer.data())) return {-1, -1};
        
        TreeNodeHeader* header = reinterpret_cast<TreeNodeHeader*>(buffer.data());
        TreeRecord* records = reinterpret_cast<TreeRecord*>(buffer.data() + sizeof(TreeNodeHeader));
        
        for (uint32_t i = 0; i < header->num_keys; i++) {
            if (records[i].key == key) return records[i].ptr;
        }
        
        if (header->next_leaf_page == 0) break;
        current_page = header->next_leaf_page;
    }
    return {-1, -1};
}

extern "C" {
    BTreeManager* BT_Create(PageManager* pm, int root_page_id) {
        return new BTreeManager(pm, root_page_id);
    }
    void BT_Destroy(BTreeManager* tree) { if (tree) delete tree; }
    
    bool BT_Insert(BTreeManager* tree, uint64_t key, int page_id, int slot_id) {
        return tree ? tree->insert(key, {page_id, slot_id}) : false;
    }
    
    bool BT_Search(BTreeManager* tree, uint64_t key, int* out_page_id, int* out_slot_id) {
        if (!tree) return false;
        RecordPointer res = tree->search(key);
        if (res.page_id == -1) return false;
        *out_page_id = res.page_id;
        *out_slot_id = res.slot_id;
        return true;
    }
}