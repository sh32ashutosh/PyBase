#ifndef class_h
#define class_h
#ifndef Complex_API
    #define Complex_API __declspec(dllexport)
#else
    #define Complex_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C"{
#endif
    Complex_API void * createComplex(double real, double imag);
    Complex_API double getReal();
    Complex_API double getImag();
    Complex_API void * add(double real, double cmplx);

#ifdef __cplusplus
}
#endif
#endif