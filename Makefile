.PHONY: help install dev test lint fmt run report sweep dashboard clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## install the package
	pip install -e .

dev:  ## install with dev and dashboard extras
	pip install -e ".[dev,dashboard]"

test:  ## run the test suite
	pytest

lint:  ## check style
	ruff check src tests dashboard

fmt:  ## autofix style
	ruff check --fix src tests dashboard

run:  ## run the model, write CSV outputs
	titlei run --out outputs -v

report:  ## build the static HTML report
	titlei report --out outputs -v

sweep:  ## budget sensitivity table
	titlei sweep

dashboard:  ## launch the interactive dashboard
	streamlit run dashboard/app.py

clean:
	rm -rf outputs/charts outputs/tables outputs/report.html .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
