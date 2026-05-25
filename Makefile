.PHONY: all build deploy clean

# Default covert logging level to forward (0=Disabled, 1=File, 2=Console+File)
LOGS ?= 2

# Default target
all: build

# Delegate build to the main backend project directory
build:
	$(MAKE) -C main build LOGS=$(LOGS)

# Delegate deploy to the main backend project directory
deploy:
	$(MAKE) -C main deploy LOGS=$(LOGS)

# Delegate clean to the main backend project directory
clean:
	$(MAKE) -C main clean
