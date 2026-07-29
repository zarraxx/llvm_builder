cmake_minimum_required(VERSION 3.20)

project(thin_sysroot_verify LANGUAGES C)

foreach(required_var IN ITEMS THIN_CRT_DIR THIN_OUTPUT_DIR)
    if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
        message(FATAL_ERROR "${required_var} is required")
    endif()
endforeach()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${THIN_OUTPUT_DIR}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${THIN_OUTPUT_DIR}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${THIN_OUTPUT_DIR}")

add_subdirectory(liba)
add_subdirectory(libb)
add_subdirectory(app)

if(WIN32)
    if(NOT DEFINED THIN_BUILTINS_LIB OR NOT EXISTS "${THIN_BUILTINS_LIB}")
        message(FATAL_ERROR "THIN_BUILTINS_LIB is required for Windows")
    endif()
    set(
        thin_windows_libraries
        mingw32
        moldname
        mingwex
        msvcrt
        advapi32
        shell32
        user32
        kernel32
    )
    foreach(dll_target IN ITEMS thin_a thin_b)
        target_link_options(
            ${dll_target} PRIVATE "${THIN_CRT_DIR}/dllcrt2.o"
        )
        target_link_libraries(
            ${dll_target}
            PRIVATE ${thin_windows_libraries} "${THIN_BUILTINS_LIB}"
        )
    endforeach()
    target_link_options(thin_verify PRIVATE "${THIN_CRT_DIR}/crt2.o")
    target_link_libraries(
        thin_verify
        PRIVATE thin_a ${thin_windows_libraries} "${THIN_BUILTINS_LIB}"
    )
else()
    target_link_options(
        thin_verify
        PRIVATE
            "${THIN_CRT_DIR}/Scrt1.o"
            "${THIN_CRT_DIR}/crti.o"
    )
    target_link_libraries(thin_verify PRIVATE thin_a)
    if(DEFINED THIN_DL_LIBRARY AND NOT THIN_DL_LIBRARY STREQUAL "")
        target_link_libraries(thin_verify PRIVATE "${THIN_DL_LIBRARY}")
    endif()
    target_link_libraries(
        thin_verify PRIVATE c "${THIN_CRT_DIR}/crtn.o"
    )
endif()
