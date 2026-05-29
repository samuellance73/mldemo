.PHONY: all build deploy clean lint lint-fix format

# Default covert logging level to forward (0=Disabled, 1=File, 2=Console+File)
LOGS ?= 2
# Hardening mode: pyminifier (default) | cython | bytecode
HARDENER ?= bytecode

# Default target
all: build

# Build the main deployment flavor
build:
	$(MAKE) -C main build LOGS=$(LOGS) HARDENER=$(HARDENER)

# Build then deploy all nodes from the universal deploy script
deploy: build
	uv run python scripts/deploy.py

# Delegate linting to main/ (uv finds pyproject.toml at root)
lint:
	$(MAKE) -C main lint

# Delegate lint auto-fixing
lint-fix:
	$(MAKE) -C main lint-fix

# Delegate formatting
format:
	$(MAKE) -C main format

# Delegate clean to the main deployment directory
clean:
	$(MAKE) -C main clean

