add_library(thin_a SHARED thin_a.c)
target_compile_definitions(thin_a PRIVATE THIN_A_BUILD)
target_include_directories(thin_a PUBLIC "${PROJECT_SOURCE_DIR}/include")
set_target_properties(
    thin_a PROPERTIES C_VISIBILITY_PRESET hidden PREFIX ""
)
