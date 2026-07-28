#include <stdio.h>

#ifndef SAMPLE_ARCH
#define SAMPLE_ARCH "unknown"
#endif

int main() {
    printf("hello %s\n", SAMPLE_ARCH);
    return 0;
}
