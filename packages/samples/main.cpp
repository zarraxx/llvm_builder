#include <iostream>

#ifndef SAMPLE_ARCH
#define SAMPLE_ARCH "unknown"
#endif

int main() {
    std::cout << "hello " << SAMPLE_ARCH << std::endl;
    return 0;
}
