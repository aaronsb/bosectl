cmake_minimum_required(VERSION 3.14)
project(bmap VERSION 0.4.1 LANGUAGES CXX)

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
if(APPLE)
    target_link_libraries(bmapctl PRIVATE bmap)
else()
    target_link_libraries(bmapctl PRIVATE bmap bluetooth)
endif()

# Tests
enable_testing()
add_executable(bmap_tests
    tests/test_main.cpp
    tests/test_protocol.cpp
    tests/test_parsers.cpp
    tests/test_connection.cpp
    tests/test_catalog.cpp
    tests/test_transport.cpp
)
# Linked like bmapctl so tests can call the real connect(); no BT at runtime.
if(APPLE)
    target_link_libraries(bmap_tests PRIVATE bmap)
else()
    target_link_libraries(bmap_tests PRIVATE bmap bluetooth)
endif()
add_test(NAME bmap_tests COMMAND bmap_tests)
