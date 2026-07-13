# QuickMUD development Makefile
# Simple shortcuts for common tasks. Works on Unix-like shells and Windows
# shells that understand standard Make (MSYS2, Git Bash, WSL, etc.).

# Default interpreter: modern Linux/WSL often lacks a bare `python` symlink,
# so prefer python3 on Unix-like systems.
ifeq ($(OS),Windows_NT)
    PYTHON ?= python
else
    PYTHON ?= python3
endif

# Detect venv Python path: Windows uses Scripts/, Unix uses bin/.
ifeq ($(OS),Windows_NT)
    VENV_DIR := .venv
    VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
    VENV_PIP := $(VENV_DIR)/Scripts/pip.exe
else
    VENV_DIR := .venv
    VENV_PYTHON := $(VENV_DIR)/bin/python
    VENV_PIP := $(VENV_DIR)/bin/pip
endif

.PHONY: help install install-dev test test-parallel test-integration test-parity test-coverage lint format format-check typecheck server websocket ssh clean

help:
	@echo "QuickMUD development tasks"
	@echo ""
	@echo "  make install          Create .venv and install pinned dev dependencies"
	@echo "  make install-dev      Alias for install"
	@echo "  make test             Run the default pytest suite (excludes the 2987"
	@echo "                        ROM-parity tests in tests/integration/, which"
	@echo "                        are skipped by default — see test-parity)"
	@echo "  make test-parallel    Run the default suite with 5 xdist workers"
	@echo "  make test-integration Alias for test-parity (runs tests/integration/)"
	@echo "  make test-parity      Run the ROM-parity integration tests (~3000 tests,"
	@echo "                        ~4 min). Off by default since the project no"
	@echo "                        longer treats ROM parity as a goal."
	@echo "  make test-coverage    Run tests with coverage report (default suite)"
	@echo "  make lint             Run ruff linter"
	@echo "  make format           Auto-format code with ruff"
	@echo "  make format-check     Check formatting without changing files"
	@echo "  make typecheck        Run mypy on selected modules"
	@echo "  make server           Start the telnet server (port 5001)"
	@echo "  make websocket        Start the WebSocket server (port 8000)"
	@echo "  make ssh              Start the SSH server (port 2222)"
	@echo "  make multi            Start WebSocket + telnet + SSH in one process"
	@echo "  make clean            Remove .venv and Python cache files"
	@echo ""
	@echo "Override Python interpreter: make install PYTHON=python3.12"

install: $(VENV_PYTHON)
	$(VENV_PIP) install -r requirements-dev.txt
	@echo ""
	@echo "Setup complete. Activate the virtualenv:"
ifeq ($(OS),Windows_NT)
	@echo "  .venv\\Scripts\\activate.bat"
else
	@echo "  source .venv/bin/activate"
endif

install-dev: install

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip

test:
	$(VENV_PYTHON) -m pytest

test-parallel:
	$(VENV_PYTHON) -m pytest -n 5 --dist loadscope

# tests/integration/ holds the ROM 2.4 parity harness. The default pytest
# run SKIPS it (see tests/conftest.py:_PARITY_SKIP_REASON) because the
# project no longer treats ROM parity as a goal. Pass --include-parity to
# actually run it. test-integration is kept as an alias for muscle memory.
test-integration: test-parity

test-parity:
	$(VENV_PYTHON) -m pytest tests/integration/ --include-parity -v

test-coverage:
	$(VENV_PYTHON) -m pytest --cov=mud --cov-report=term --cov-fail-under=80

lint:
	$(VENV_PYTHON) -m ruff check .

format:
	$(VENV_PYTHON) -m ruff format .

format-check:
	$(VENV_PYTHON) -m ruff format --check .

typecheck:
	$(VENV_PYTHON) -m mypy mud/net/ansi.py mud/security/hash_utils.py --follow-imports=skip

server:
	$(VENV_PYTHON) -m mud socketserver

websocket:
	$(VENV_PYTHON) -m mud websocketserver

ssh:
	$(VENV_PYTHON) -m mud sshserver

multi:
	$(VENV_PYTHON) -m mud multiserver

clean:
	rm -rf $(VENV_DIR)
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
