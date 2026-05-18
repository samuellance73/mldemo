.PHONY: all build clean

# 0 = Disabled, 1 = File Only (default), 2 = Console + File
LOGS ?= 2

# Default target
all: build

# Run the build script to generate the dist/ directory
build:
	python3 scripts/build.py --logs $(LOGS)

# Remove the generated dist/ directory
clean:
	rm -rf dist
