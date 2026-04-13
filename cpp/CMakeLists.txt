cmake_minimum_required(VERSION 3.14)
project(bmap VERSION 0.3.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Library
add_library(bmap STATIC
    src/transport.cpp
    src/discovery.cpp
)
target_include_directories(bmap PUBLIC src)

# Git hash for version string
execute_process(
    COMMAND git rev-parse --short HEAD
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}/..
    OUTPUT_VARIABLE GIT_HASH
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
if(NOT GIT_HASH)
    set(GIT_HASH "unknown")
endif()

# CLI
add_executable(bmapctl src/main.cpp)
target_compile_definitions(bmapctl PRIVATE GIT_HASH="${GIT_HASH}" BMAP_VERSION="${PROJECT_VERSION}")
target_link_libraries(bmapctl PRIVATE bmap bluetooth)

# Tests
enable_testing()
add_executable(bmap_tests tests/test_main.cpp tests/test_protocol.cpp tests/test_parsers.cpp tests/test_connection.cpp tests/test_catalog.cpp)
target_link_libraries(bmap_tests PRIVATE bmap)
add_test(NAME bmap_tests COMMAND bmap_tests)
