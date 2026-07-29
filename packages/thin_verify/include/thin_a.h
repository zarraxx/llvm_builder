#ifndef THIN_A_H
#define THIN_A_H

#if defined(_WIN32)
#    if defined(THIN_A_BUILD)
#        define THIN_A_API __declspec(dllexport)
#    else
#        define THIN_A_API __declspec(dllimport)
#    endif
#else
#    define THIN_A_API __attribute__((visibility("default")))
#endif

THIN_A_API int thin_a_test(void);

#endif
