// --- This is Your Hidden C++ Class ---
// You can design this however you want.
#include "complex.h"

class Complex {
private:
    // "Stuff": These are your private member variables
    // Only the class's own methods can touch these.
    double real;
    double imag;

public:
    // "Method 1": The Constructor
    // This is the "blueprint" for how to create a new object.
    Complex(double r, double i) {
        this->real = r;
        this->imag = i;
    }

    // "Method 2": A "setter" or "operator"
    // This changes the object's stuff.
    void add(double r, double i) {
        this->real += r;
        this->imag += i;
    }

    // "Method 3": A "getter"
    // This reads the object's stuff.
    double getReal() {
        return this->real;
    }

    // "Method 4": Another "getter"
    double getImag() {
        return this->imag;
    }

    // You can add more methods here...
    // void subtract(double r, double i) { ... }
    // double getMagnitude() { ... }
};

Complex_API double getImag(Complex c){
    return c.getImag()
}

