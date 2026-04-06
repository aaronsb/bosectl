# pybmap monorepo — build, test, and publish for Python, Rust, and C++

.PHONY: help all test lint clean \
        python-setup python-test python-lint python-build python-publish \
        rust-test rust-build rust-publish \
        cpp-test cpp-build \
        integration

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

all: python-test rust-test cpp-test ## Run all tests

# ── Python ───────────────────────────────────────────────────────────────────

PYTHON_DIR = python
VENV = $(PYTHON_DIR)/.venv
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest
PYTHON = $(VENV)/bin/python

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -q pytest

python-setup: $(VENV)/bin/activate ## Set up Python virtualenv
	$(PIP) install -q -e $(PYTHON_DIR)

python-test: python-setup ## Run Python unit tests
	$(PYTEST) $(PYTHON_DIR)/tests/ -v --tb=short

python-lint: python-setup ## Lint Python code
	$(PYTHON) -m py_compile $(PYTHON_DIR)/pybmap/__init__.py
	$(PYTHON) -m py_compile $(PYTHON_DIR)/pybmap/protocol.py
	$(PYTHON) -m py_compile $(PYTHON_DIR)/pybmap/connection.py
	$(PYTHON) -m py_compile $(PYTHON_DIR)/pybmap/cli.py
	@echo "All Python files compile OK"

python-build: python-setup ## Build Python sdist and wheel
	cd $(PYTHON_DIR) && $(PYTHON) -m build

python-publish: python-build ## Publish to PyPI (requires TWINE_PASSWORD)
	cd $(PYTHON_DIR) && $(PYTHON) -m twine upload dist/*

# ── Rust ─────────────────────────────────────────────────────────────────────

RUST_DIR = rust

rust-test: ## Run Rust tests
	cd $(RUST_DIR) && cargo test

rust-build: ## Build Rust library
	cd $(RUST_DIR) && cargo build --release

rust-publish: rust-test ## Publish to crates.io
	cd $(RUST_DIR) && cargo publish

# ── C++ ──────────────────────────────────────────────────────────────────────

CPP_DIR = cpp
CPP_BUILD = $(CPP_DIR)/build

cpp-test: cpp-build ## Run C++ tests
	cd $(CPP_BUILD) && ctest --output-on-failure
	$(CPP_BUILD)/bmap_tests

cpp-build: ## Build C++ library
	cmake -S $(CPP_DIR) -B $(CPP_BUILD)
	cmake --build $(CPP_BUILD)

# ── Integration Tests ────────────────────────────────────────────────────────

integration: python-setup ## Run integration tests (requires paired BT device)
	BMAP_INTEGRATION=1 $(PYTEST) $(PYTHON_DIR)/tests/ -v --tb=short --integration

# ── Cross-Language ───────────────────────────────────────────────────────────

test: python-test rust-test cpp-test ## Run all tests across all languages

lint: python-lint ## Lint all languages

clean: ## Remove build artifacts
	rm -rf $(VENV) $(PYTHON_DIR)/dist $(PYTHON_DIR)/build $(PYTHON_DIR)/*.egg-info
	rm -rf $(PYTHON_DIR)/.pytest_cache $(PYTHON_DIR)/__pycache__
	cd $(RUST_DIR) && cargo clean 2>/dev/null || true
	rm -rf $(CPP_BUILD)
