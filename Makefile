.PHONY: all build clean

# 0 = Disabled, 1 = File Only (default), 2 = Console + File
LOGS ?= 1

# Default target
all: build

# Run the build script to generate the dist/ directory
build:
	python3 scripts/build.py --logs $(LOGS)

# Remove generated files inside dist/ but preserve dist/.git repository
clean:
	@if [ -d dist ]; then \
		find dist -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +; \
		echo "Cleaned dist/ (preserved .git repo)"; \
	fi