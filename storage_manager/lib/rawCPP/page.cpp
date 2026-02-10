#include "page.hpp"
#include <cstring> // for memcpy
#include <sstream>

PageManager::PageManager(const std::string& path) : storage_path(path) {
    // Ensure the storage directory exists (simplified for this example)
}

PageManager::~PageManager() {
    // Auto-save all dirty pages on destruction
    for (auto& pair : page_table) {
        if (pair.second.is_loaded && pair.second.is_dirty) {
            save_page(pair.first);
        }
    }
}

void PageManager::create_page(int page_id, size_t size) {
    std::lock_guard<std::mutex> lock(mtx);
    Page p;
    p.id = page_id;
    p.is_loaded = true;
    p.is_dirty = true; // New pages are dirty by default until saved
    p.data.resize(size, 0); // Initialize with zeros
    page_table[page_id] = std::move(p);
}

bool PageManager::load_page(int page_id) {
    std::lock_guard<std::mutex> lock(mtx);
    
    // Check if already loaded
    if (page_table.find(page_id) != page_table.end() && page_table[page_id].is_loaded) {
        return true;
    }

    // Construct filename: storage_path/page_ID.bin
    std::stringstream ss;
    ss << storage_path << "/page_" << page_id << ".bin";
    std::string filename = ss.str();

    std::ifstream infile(filename, std::ios::binary | std::ios::ate);
    if (!infile) return false; // File not found

    size_t size = infile.tellg();
    infile.seekg(0, std::ios::beg);

    Page p;
    p.id = page_id;
    p.is_loaded = true;
    p.is_dirty = false;
    p.data.resize(size);
    
    if (infile.read(reinterpret_cast<char*>(p.data.data()), size)) {
        page_table[page_id] = std::move(p);
        return true;
    }
    return false;
}

void PageManager::save_page(int page_id) {
    if (page_table.find(page_id) == page_table.end()) return;
    Page& p = page_table[page_id];

    if (!p.is_dirty) return;

    std::stringstream ss;
    ss << storage_path << "/page_" << page_id << ".bin";
    
    std::ofstream outfile(ss.str(), std::ios::binary);
    outfile.write(reinterpret_cast<const char*>(p.data.data()), p.data.size());
    
    p.is_dirty = false;
    // std::cout << "Saved Page " << page_id << " to disk." << std::endl;
}

bool PageManager::unload_page(int page_id) {
    std::lock_guard<std::mutex> lock(mtx);
    if (page_table.find(page_id) == page_table.end()) return false;

    // Save if dirty before unloading
    if (page_table[page_id].is_dirty) {
        save_page(page_id);
    }

    // Remove from memory (O(1) erase)
    page_table.erase(page_id);
    return true;
}

uint8_t* PageManager::get_data_ptr(int page_id) {
    if (page_table.find(page_id) != page_table.end()) {
        return page_table[page_id].data.data();
    }
    return nullptr;
}

size_t PageManager::get_data_size(int page_id) {
    if (page_table.find(page_id) != page_table.end()) {
        return page_table[page_id].data.size();
    }
    return 0;
}

bool PageManager::write_data(int page_id, const uint8_t* buffer, size_t size, size_t offset) {
    std::lock_guard<std::mutex> lock(mtx);
    if (page_table.find(page_id) == page_table.end()) return false;
    
    Page& p = page_table[page_id];
    
    // Auto-resize if writing past end
    if (offset + size > p.data.size()) {
        p.data.resize(offset + size);
    }
    
    std::memcpy(p.data.data() + offset, buffer, size);
    p.is_dirty = true;
    return true;
}

// --------------------------------------------------------
// C Interface Implementation (The Bridge to Python)
// --------------------------------------------------------

PageManager* PM_Create(const char* path) {
    return new PageManager(std::string(path));
}

void PM_Destroy(PageManager* pm) {
    if (pm) delete pm;
}

void PM_CreatePage(PageManager* pm, int id, int size) {
    if (pm) pm->create_page(id, size);
}

void PM_Load(PageManager* pm, int id) {
    if (pm) pm->load_page(id);
}

void PM_Unload(PageManager* pm, int id) {
    if (pm) pm->unload_page(id);
}

void PM_Write(PageManager* pm, int id, const uint8_t* data, int size, int offset) {
    if (pm) pm->write_data(id, data, size, offset);
}

uint8_t* PM_GetData(PageManager* pm, int id) {
    if (pm) return pm->get_data_ptr(id);
    return nullptr;
}

int PM_GetSize(PageManager* pm, int id) {
    if (pm) return static_cast<int>(pm->get_data_size(id));
    return 0;
}