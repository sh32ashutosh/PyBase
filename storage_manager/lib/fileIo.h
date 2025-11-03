#ifndef FILE_IO_H
#define FILE_IO_H

// Use a macro name that matches the library
#ifdef FILE_IO_EXPORT
    #define FILE_IO_API __declspec(dllexport)
#else
    #define FILE_IO_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Your functions
FILE_IO_API int add(int a, int b);
FILE_IO_API int write_string_to_file(const char* filename, const char* content);
FILE_IO_API int read_string_from_file(const char* filename, char* out_buffer, int buffer_len);

#ifdef __cplusplus
}
#endif

#endif // FILE_IO_H