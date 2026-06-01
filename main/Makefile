.PHONY: all build deploy clean lint lint-fix format

# 0 = Disabled, 1 = File Only (default), 2 = Console + File
LOGS ?= 2
# Hardening mode: pyminifier | bytecode (default)
HARDENER ?= bytecode

# Default target
all: build

# Run the build script to generate the dist/ directory
build:
	uv run python scripts/build.py --logs $(LOGS) --hardener $(HARDENER)

# Lint checking
lint:
	uv run ruff check .

# Auto-fix linting issues
lint-fix:
	uv run ruff check --fix .

# Code formatting
format:
	uv run ruff format .

# Remove generated files inside dist/ but preserve dist/.git repository
clean:
	@if [ -d dist ]; then \
		find dist -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +; \
		rm -f dist/sanctuary/core/logging.py 2>/dev/null || true; \
		echo "Cleaned dist/ (preserved .git repo)"; \
	fi