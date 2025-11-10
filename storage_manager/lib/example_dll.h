#pragma once

// Generic helper for Windows DLL export/import
#ifdef BUILD_MYDLL
    #define DLL_API __declspec(dllexport)
#else
    #define DLL_API __declspec(dllimport)
#endif

// 'extern "C"' prevents C++ name mangling, making the DLL 
// easier to use with other languages (like C, C#, Python).
extern "C" {
    DLL_API int math_add(int a, int b);
    DLL_API void print_message(const char* msg);
}