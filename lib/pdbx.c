// engine/pdbx.c
#include "pdbx.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

DLL_EXPORT int create_pdbx(const char* filepath) {
    FILE* file = fopen(filepath, "w");
    if (!file) return -1;
    fprintf(file, "PDBX v1\n");
    fclose(file);
    return 0;
}

DLL_EXPORT int add_entry(const char* filepath, const char* key, const char* value) {
    FILE* file = fopen(filepath, "a");
    if (!file) return -1;
    fprintf(file, "%s=%s\n", key, value);
    fclose(file);
    return 0;
}

DLL_EXPORT const char* read_entry(const char* filepath, const char* key) {
    static char buffer[256];
    FILE* file = fopen(filepath, "r");
    if (!file) return NULL;

    char line[256];
    while (fgets(line, sizeof(line), file)) {
        char* equals = strchr(line, '=');
        if (equals) {
            *equals = '\0';
            if (strcmp(line, key) == 0) {
                strncpy(buffer, equals + 1, sizeof(buffer));
                buffer[strcspn(buffer, "\n")] = '\0';
                fclose(file);
                return buffer;
            }
        }
    }

    fclose(file);
    return NULL;
}
