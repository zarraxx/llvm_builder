add_library(thin_b SHARED thin_b.c)
set_target_properties(
    thin_b PROPERTIES C_VISIBILITY_PRESET hidden PREFIX ""
)
