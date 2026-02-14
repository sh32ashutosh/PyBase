#ifndef TREE_HPP
#define TREE_HPP
#include <vector>
#include <cstdlib>
#include<cstdio>
#include<mutex>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

struct Node{
    void * val;
    struct Node* next;
};
