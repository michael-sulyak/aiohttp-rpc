clean: clean-build clean-pyc clean-test

clean-build: # remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: # remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: # remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache

lint:
	flake8 aiohttp_rpc tests

typing:
	mypy aiohttp_rpc

test:
	pytest tests

test-all:
	tox

build: clean
	python -m build

release: build
	twine check dist/*
	twine upload dist/*

install:
	pip install -e .

check: test lint typing
