.PHONY: all build deploy clean lint lint-fix format

# Default covert logging level to forward (0=Disabled, 1=File, 2=Console+File)
LOGS ?= 2
# Hardening mode: pyminifier (default) | cython | bytecode
HARDENER ?= bytecode

# Default target
all: build

# Delegate build to the main backend project directory
build:
	$(MAKE) -C main build LOGS=$(LOGS) HARDENER=$(HARDENER)

# Delegate deploy to the main backend project directory
deploy:
	$(MAKE) -C main deploy LOGS=$(LOGS) HARDENER=$(HARDENER)

# Delegate linting
lint:
	$(MAKE) -C main lint

# Delegate lint auto-fixing
lint-fix:
	$(MAKE) -C main lint-fix

# Delegate formatting
format:
	$(MAKE) -C main format

# Delegate clean to the main backend project directory
clean:
	$(MAKE) -C main clean

