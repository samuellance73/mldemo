.PHONY: all build deploy docker-push docker-build docker-run clean lint lint-fix format

# Default covert logging level to forward (0=Disabled, 1=File, 2=Console+File)
LOGS ?= 2
# Hardening mode: pyminifier | bytecode (default)
HARDENER ?= bytecode

# Default target
all: build

# Build the main deployment flavor
build:
	$(MAKE) -C main build LOGS=$(LOGS) HARDENER=$(HARDENER)

# Build then deploy all nodes from the universal deploy script
deploy: build
	uv run python scripts/deploy.py

# Build, tag, authenticate, and push the camouflaged container to Docker Hub
docker-push:
	uv run python scripts/push_docker.py

# Compile and build the Docker image locally under the 'sanctuary:local' tag
docker-build: build
	@echo "local-test" > main/dist/whoami.txt
	cd main/dist && docker build -t sanctuary:local .

# Launch the built container locally with correct port mappings and environment configs
docker-run:
	uv run python scripts/run_docker.py




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

