#define BUILD_MYDLL // vital: Enables dllexport from our header
#include "example_dll.h"
#include <iostream>

int math_add(int a, int b) {
    return a + b;
}

void print_message(const char* msg) {
    std::cout << "[DLL] Message: " << msg << std::endl;
}