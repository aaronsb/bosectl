// Minimal test framework — no external deps.
#pragma once

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

struct Test {
    std::string name;
    std::function<void()> fn;
};

// Shared across all translation units via inline.
inline std::vector<Test>& test_registry() {
    static std::vector<Test> tests;
    return tests;
}

struct TestRegistrar {
    TestRegistrar(const char* name, std::function<void()> fn) {
        test_registry().push_back({name, fn});
    }
};

#define TEST(name) \
    static void test_##name(); \
    static TestRegistrar reg_##name(#name, test_##name); \
    static void test_##name()

#define ASSERT_EQ(a, b) do { \
    auto _a = (a); auto _b = (b); \
    if (_a != _b) { \
        fprintf(stderr, "  FAIL %s:%d: %s != %s\n", __FILE__, __LINE__, #a, #b); \
        abort(); \
    } \
} while(0)

#define ASSERT_TRUE(x) do { \
    if (!(x)) { \
        fprintf(stderr, "  FAIL %s:%d: %s is false\n", __FILE__, __LINE__, #x); \
        abort(); \
    } \
} while(0)

#define ASSERT_FALSE(x) ASSERT_TRUE(!(x))

/// Read a hex fixture relative to the tests directory.
inline std::vector<uint8_t> decode_hex_fixture(const std::string& relative_path) {
    auto path = std::filesystem::path(__FILE__).parent_path() / relative_path;
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Could not open fixture: " + path.string());
    std::string hex((std::istreambuf_iterator<char>(input)), {});
    hex.erase(std::remove_if(hex.begin(), hex.end(), [](unsigned char c) {
        return std::isspace(c);
    }), hex.end());
    if (hex.size() % 2 != 0) throw std::runtime_error("Fixture contains incomplete hex byte");
    std::vector<uint8_t> bytes;
    for (size_t i = 0; i < hex.size(); i += 2) {
        bytes.push_back(static_cast<uint8_t>(std::stoul(hex.substr(i, 2), nullptr, 16)));
    }
    return bytes;
}
