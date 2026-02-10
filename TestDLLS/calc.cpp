// 1. Flip the "switch" *BEFORE* the include
#define CALC_EXPORT

#include "calc.h" // The "menu"
#include <iostream>

typedef void * CalcHandle;
// --- The Hidden C++ Class ---
class Calc {
private:
    int a;
    int b;
public:
    Calc(int a, int b) {
        this->a = a;
        this->b = b;
    }
    ~Calc() {
        // --- THIS IS THE FIX ---
        std::cout << "Calc object destroyed." << std::endl;
    }
    int add() {
        return this->a + this->b;
    }
    int sub() {
        return this->a - this->b;
    }
};
// --- End of Class ---


// --- C Wrapper Function Implementations ---
// These MUST match the .h file

CALC_API CalcHandle create(int num1, int num2) {
    Calc* c = new Calc(num1, num2);
    return static_cast<void*>(c); // Return the "ticket"
}

CALC_API void destroy(CalcHandle handle) {
    if (handle) {
        Calc* c = static_cast<Calc*>(handle);
        delete c; // This calls the ~Calc() destructor
    }
}

CALC_API int add_wrapper(CalcHandle handle) {
    if (!handle) return 0;
    Calc* c = static_cast<Calc*>(handle);
    return c->add(); // Use -> to call the method
}

CALC_API int sub_wrapper(CalcHandle handle) {
    if (!handle) return 0;
    Calc* c = static_cast<Calc*>(handle);
    return c->sub(); // Use -> to call the method
}