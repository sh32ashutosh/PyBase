#ifndef add_h
#define add_h

#ifdef NUM_TO_ADD
    #define NUM_TO_ADD __declspec(dllexport)
#else
    #define NUM_TO_ADD __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif
    NUM_TO_ADD int addi(int a,int b);
    NUM_TO_ADD float addf(float a,float b);
#ifdef __cplusplus
}
#endif

#endif
