.PHONY: all build clean

# Default target
all: build

# Run the build script to generate the dist/ directory
build:
	python3 scripts/build.py

# Remove the generated dist/ directory
clean:
	rm -rf dist
