// Test runner — executes all registered tests.
#include "test_common.h"
#include <cstdio>

int main() {
    int passed = 0;
    for (auto& t : test_registry()) {
        printf("  %s ... ", t.name.c_str());
        t.fn();
        printf("ok\n");
        passed++;
    }
    printf("\n%d tests passed\n", passed);
    return 0;
}
