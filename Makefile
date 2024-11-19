# Prepare variables
TMP = $(CURDIR)/tmp
VERSION = $(shell hatch version)
PACKAGE = fmf-$(VERSION)
FILES = LICENSE README.rst \
		Makefile fmf.spec pyproject.toml \
		examples fmf tests

# Define special targets
all: docs packages
.PHONY: docs hooks tmp

# Temporary directory, include .fmf to prevent exploring tests there
tmp:
	mkdir -p $(TMP)/.fmf
	mkdir -p $(TMP)/$(PACKAGE)


# Run the test suite, optionally with coverage
test: tmp
	hatch run test:unit
smoke: tmp
	hatch run test:smoke
coverage: tmp
	hatch run cov:cov


# Build documentation, prepare man page
docs: man
	hatch run docs:html
man: tmp
	cp docs/header.txt $(TMP)/man.rst
	tail -n+7 README.rst >> $(TMP)/man.rst
	rst2man $(TMP)/man.rst > $(TMP)/$(PACKAGE)/fmf.1


# RPM packaging
tarball: man
	hatch build -t sdist
rpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bb fmf.spec
srpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bs fmf.spec
packages: rpm srpm


# Python packaging
wheel:
	hatch build -t wheel
upload: wheel tarball
	hatch publish


# Vim tags and cleanup
tags:
	find fmf -name '*.py' | xargs ctags --python-kinds=-i
clean:
	rm -rf $(TMP) build dist .cache .pytest_cache fmf*.tar.gz
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*,cover" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf docs/_build
	rm -f .coverage tags
