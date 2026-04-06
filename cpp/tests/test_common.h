// Minimal test framework — no external deps.
#pragma once

#include <cstdio>
#include <cstdlib>
#include <functional>
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
