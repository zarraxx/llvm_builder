#include "thin_a.h"

#include <stdio.h>

#if defined(_WIN32)
#    include <windows.h>
#else
#    include <dlfcn.h>
#endif

typedef int (*thin_test_function)(void);

static thin_test_function load_thin_b(void **library_handle)
{
#if defined(_WIN32)
    HMODULE handle = LoadLibraryA(THIN_B_LIBRARY_NAME);
    if (handle == NULL) {
        return NULL;
    }
    *library_handle = handle;
    return (thin_test_function)(void *)GetProcAddress(handle, "thin_b_test");
#else
    void *handle = dlopen(THIN_B_LIBRARY_NAME, RTLD_NOW | RTLD_LOCAL);
    if (handle == NULL) {
        return NULL;
    }
    *library_handle = handle;
    return (thin_test_function)dlsym(handle, "thin_b_test");
#endif
}

static void close_thin_b(void *library_handle)
{
#if defined(_WIN32)
    FreeLibrary((HMODULE)library_handle);
#else
    dlclose(library_handle);
#endif
}

int main(void)
{
    void *library_handle = NULL;
    thin_test_function thin_b_test = load_thin_b(&library_handle);
    int a_result = thin_a_test();
    int b_result;

    if (thin_b_test == NULL) {
        fputs("failed to load thin_b_test\n", stderr);
        return 1;
    }

    b_result = thin_b_test();
    printf("thin_a_test=%d\n", a_result);
    printf("thin_b_test=%d\n", b_result);
    close_thin_b(library_handle);

    return a_result == 101 && b_result == 202 ? 0 : 1;
}
