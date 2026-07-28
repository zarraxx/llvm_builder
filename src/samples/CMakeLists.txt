cmake_minimum_required(VERSION 3.20)

project(sysroot_samples LANGUAGES C CXX)

if(NOT DEFINED SAMPLE_ARCH OR SAMPLE_ARCH STREQUAL "")
    message(FATAL_ERROR "SAMPLE_ARCH is required")
endif()

if(NOT DEFINED SAMPLE_OUTPUT_DIR OR SAMPLE_OUTPUT_DIR STREQUAL "")
    set(SAMPLE_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}")
endif()

add_executable(main main.c)
target_compile_definitions(main PRIVATE "SAMPLE_ARCH=\"${SAMPLE_ARCH}\"")
set_target_properties(
    main
    PROPERTIES
        OUTPUT_NAME "main.${SAMPLE_ARCH}"
        RUNTIME_OUTPUT_DIRECTORY "${SAMPLE_OUTPUT_DIR}"
        SUFFIX ""
)

add_executable(maincxx main.cpp)
target_compile_definitions(maincxx PRIVATE "SAMPLE_ARCH=\"${SAMPLE_ARCH}\"")
target_compile_features(maincxx PRIVATE cxx_std_17)
set_target_properties(
    maincxx
    PROPERTIES
        OUTPUT_NAME "maincxx.${SAMPLE_ARCH}"
        RUNTIME_OUTPUT_DIRECTORY "${SAMPLE_OUTPUT_DIR}"
        SUFFIX ""
)
