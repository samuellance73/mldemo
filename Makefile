.PHONY: all build deploy clean

# 0 = Disabled, 1 = File Only (default), 2 = Console + File
LOGS ?= 1

# Default target
all: build

# Run the build script to generate the dist/ directory
build:
	uv run python scripts/build.py --logs $(LOGS)

# Deploy the dist/ directory to configured Hugging Face nodes
deploy: build
	uv run python scripts/deploy.py

# Remove generated files inside dist/ but preserve dist/.git repository
clean:
	@if [ -d dist ]; then \
		find dist -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +; \
		echo "Cleaned dist/ (preserved .git repo)"; \
	fi