.PHONY: dev test test-fast test-coverage lint format demo clean help dashboard build-dashboard setup-vps deploy

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

help:
	@echo "KonnexCore — make targets:"
	@echo "  dev               install pinned Python dependencies"
	@echo "  test              run the full test suite"
	@echo "  test-fast         run tests not marked 'slow'"
	@echo "  test-coverage     run tests with HTML coverage report at htmlcov/"
	@echo "  lint              ruff + mypy strict on core/"
	@echo "  format            black + ruff --fix"
	@echo "  demo              run the end-to-end honeypot demo"
	@echo "  dashboard         run the Vite dev server (requires pnpm)"
	@echo "  build-dashboard   build the dashboard for production"
	@echo "  setup-vps         run scripts/setup_vps.sh on this host"
	@echo "  deploy            ship to remote VPS via scripts/deploy.sh"
	@echo "  clean             remove caches and build artefacts"

dev:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest

test-fast:
	$(PYTHON) -m pytest -m "not slow"

test-coverage:
	$(PYTHON) -m pytest --cov=core --cov=rootid --cov=detverify --cov=honeynet --cov=api \
		--cov-report=term-missing --cov-report=html

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m mypy --strict core/

format:
	$(PYTHON) -m black .
	$(PYTHON) -m ruff check --fix .

demo:
	$(PYTHON) examples/05_honeypot_demo.py

dashboard:
	cd dashboard && pnpm install && pnpm dev

build-dashboard:
	cd dashboard && pnpm install --frozen-lockfile && pnpm run build

setup-vps:
	./scripts/setup_vps.sh

deploy:
	./scripts/deploy.sh

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
