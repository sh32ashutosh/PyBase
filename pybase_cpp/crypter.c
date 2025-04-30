#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#define FILE_NAME "process.txt"
#define MAX_LINE_LENGTH 1024

// Export functions for DLL
__declspec(dllexport) void encrypt();
__declspec(dllexport) void decrypt();

void encrypt() {
    FILE *file = fopen(FILE_NAME, "r");
    if (!file) {
        printf("Error: Could not open %s\n", FILE_NAME);
        return;
    }

    char buffer[MAX_LINE_LENGTH];
    if (!fgets(buffer, sizeof(buffer), file)) {
        printf("Error: File is empty or could not read\n");
        fclose(file);
        return;
    }

    printf("First Line: %s", buffer); // Print the first line

    // Read remaining content
    FILE *temp = fopen("temp.txt", "w");
    if (!temp) {
        printf("Error: Could not create temp file\n");
        fclose(file);
        return;
    }

    while (fgets(buffer, sizeof(buffer), file)) {
        fputs(buffer, temp);
    }

    fclose(file);
    fclose(temp);

    // Replace original file with the modified file
    remove(FILE_NAME);
    rename("temp.txt", FILE_NAME);
}

void decrypt() {
    FILE *file = fopen(FILE_NAME, "r");
    if (!file) {
        printf("Error: Could not open %s\n", FILE_NAME);
        return;
    }

    char buffer[MAX_LINE_LENGTH];
    if (!fgets(buffer, sizeof(buffer), file)) {
        printf("Error: File is empty or could not read\n");
        fclose(file);
        return;
    }

    printf("First Line: %s", buffer); // Print the first line

    // Read remaining content
    FILE *temp = fopen(buffer, "r");
    if (!temp) {
        printf("Error: Could not create temp file\n");
        fclose(file);
        return;
    }

    while (fgets(buffer, sizeof(buffer), file)) {
        fputs(buffer, temp);
    }

    fclose(file);
    fclose(temp);

    // Replace original file with the modified file
    remove(FILE_NAME);
    rename("temp.txt", FILE_NAME);
}


