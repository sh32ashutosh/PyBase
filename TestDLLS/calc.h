#ifndef CALC_H
#define CALC_H

// The "switch"
#ifdef CALC_EXPORT
    #define CALC_API __declspec(dllexport)
#else 
    #define CALC_API __declspec(dllimport)
#endif

// The "ticket"
typedef void* CalcHandle;

// The "menu" of C functions
#ifdef __cplusplus
extern "C" {
#endif

    CALC_API CalcHandle create(int num1, int num2);
    CALC_API void destroy(CalcHandle handle);
    CALC_API int add_wrapper(CalcHandle handle);
    CALC_API int sub_wrapper(CalcHandle handle);

#ifdef __cplusplus
}
#endif

#endif // CALC_H