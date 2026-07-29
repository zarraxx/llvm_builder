add_executable(thin_verify main.c)
target_include_directories(thin_verify PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_definitions(
    thin_verify
    PRIVATE "THIN_B_LIBRARY_NAME=\"$<TARGET_FILE_NAME:thin_b>\""
)
add_dependencies(thin_verify thin_b)
