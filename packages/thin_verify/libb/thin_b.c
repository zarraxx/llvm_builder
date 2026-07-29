#if defined(_WIN32)
#    define THIN_B_API __declspec(dllexport)
#else
#    define THIN_B_API __attribute__((visibility("default")))
#endif

THIN_B_API int thin_b_test(void)
{
    return 202;
}
