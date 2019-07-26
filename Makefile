# Prepare variables
TMP = $(CURDIR)/tmp
VERSION = $(shell grep ^Version fmf.spec | sed 's/.* //')
PACKAGE = fmf-$(VERSION)
FILES = LICENSE README.rst \
		Makefile fmf.spec setup.py \
		examples fmf bin tests

# Define special targets
all: docs packages
.PHONY: docs hooks

# Temporary directory
tmp:
	mkdir $(TMP)


# Run the test suite, optionally with coverage
test: tmp
	python2 -m pytest tests
	python3 -m pytest tests
smoke: tmp
	python2 -m pytest tests/test_smoke.py
	python3 -m pytest tests/test_smoke.py
coverage: tmp
	coverage run --source=fmf,bin -m py.test tests
	coverage report
	coverage annotate


# Build documentation, prepare man page
docs: man
	cd docs && make html
man: source
	cp docs/header.txt $(TMP)/man.rst
	tail -n+7 README.rst >> $(TMP)/man.rst
	rst2man $(TMP)/man.rst > $(TMP)/$(PACKAGE)/fmf.1


# RPM packaging
source: clean
	mkdir -p $(TMP)/SOURCES
	mkdir -p $(TMP)/$(PACKAGE)
	cp -a $(FILES) $(TMP)/$(PACKAGE)
tarball: source man
	cd $(TMP) && tar cfz SOURCES/$(PACKAGE).tar.gz $(PACKAGE)
rpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bb fmf.spec
srpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bs fmf.spec
packages: rpm srpm


# Python packaging
wheel:
	python setup.py bdist_wheel
	python3 setup.py bdist_wheel
upload:
	twine upload dist/*.whl


# Git hooks, vim tags and cleanup
hooks:
	ln -snf ../../hooks/pre-commit .git/hooks
	ln -snf ../../hooks/commit-msg .git/hooks
tags:
	find fmf -name '*.py' | xargs ctags --python-kinds=-i
clean:
	rm -rf $(TMP) build dist fmf.egg-info .cache .pytest_cache
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*,cover" -delete
	find . -type d -name "__pycache__" -delete
	cd docs && make clean
	rm -f .coverage tags
