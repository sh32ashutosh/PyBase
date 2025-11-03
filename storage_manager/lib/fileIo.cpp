// Define the new macro name to enable 'dllexport'


// Include the renamed header
#include "fileIo.h"

#include <fstream>
#include <string>
#include <sstream>
#include <cstring>

// Implementations (no change in logic, just the API macro)
// ... (add, write_string_to_file, read_string_from_file) ...

FILE_IO_API int add(int a, int b) {
    return a + b;
}

FILE_IO_API int write_string_to_file(const char* filename, const char* content) {
    std::ofstream fout(filename);
    if (!fout.is_open()) return -1;
    fout << content;
    fout.close();
    return fout.fail() ? -1 : 0;
}

FILE_IO_API int read_string_from_file(const char* filename, char* out_buffer, int buffer_len) {
    std::ifstream fin(filename);
    if (!fin.is_open()) return -1;
    std::stringstream ss;
    ss << fin.rdbuf();
    std::string content = ss.str();
    fin.close();
    strncpy(out_buffer, content.c_str(), buffer_len - 1);
    out_buffer[buffer_len - 1] = '\0';
    return static_cast<int>(content.length());
}