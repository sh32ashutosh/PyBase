// engine/pdbx.h

#ifndef PDBX_H
#define PDBX_H

#ifdef _WIN32
#define DLL_EXPORT __declspec(dllexport)
#else
#define DLL_EXPORT
#endif

#include <stdint.h>

// Simple functions for now
DLL_EXPORT int create_pdbx(const char* filepath);
DLL_EXPORT int add_entry(const char* filepath, const char* key, const char* value);
DLL_EXPORT const char* read_entry(const char* filepath, const char* key);

#endif
