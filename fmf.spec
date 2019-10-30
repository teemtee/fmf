Name: fmf
Version: 0.10
Release: 1%{?dist}

Summary: Flexible Metadata Format
License: GPLv2+
BuildArch: noarch

URL: https://github.com/psss/fmf
Source0: https://github.com/psss/fmf/releases/download/%{version}/fmf-%{version}.tar.gz

# Depending on the distro, we set some defaults.
# Note that the bcond macros are named for the CLI option they create.
# "%%bcond_without" means "ENABLE by default and create a --without option"

# Fedora or RHEL 8+
%if 0%{?fedora} || 0%{?rhel} > 7
%bcond_with oldreqs
%bcond_with englocale
%else
# The automatic runtime dependency generator doesn't exist yet
%bcond_without oldreqs
# The C.UTF-8 locale doesn't exist, Python defaults to C (ASCII)
%bcond_without englocale
%endif

# Main tmt package requires the Python module
Requires: python%{python3_pkgversion}-%{name} == %{version}-%{release}

%description
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the command line tool.

%?python_enable_dependency_generator


%package -n     python%{python3_pkgversion}-%{name}
Summary:        %{summary}
BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: python%{python3_pkgversion}-setuptools
BuildRequires: python%{python3_pkgversion}-pytest
BuildRequires: python%{python3_pkgversion}-PyYAML
%{?python_provide:%python_provide python%{python3_pkgversion}-%{name}}
%if %{with oldreqs}
Requires:       python%{python3_pkgversion}-PyYAML
%endif

%description -n python%{python3_pkgversion}-%{name}
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the Python 3 module.


%prep
%autosetup


%build
%if %{with englocale}
export LANG=en_US.utf-8
%endif

%py3_build


%install
%if %{with englocale}
export LANG=en_US.utf-8
%endif

%py3_install

mkdir -p %{buildroot}%{_mandir}/man1
install -pm 644 fmf.1* %{buildroot}%{_mandir}/man1


%check
%if %{with englocale}
export LANG=en_US.utf-8
%endif

%{__python3} -m pytest -vv


%{!?_licensedir:%global license %%doc}

%files
%{_mandir}/man1/*
%{_bindir}/%{name}
%doc README.rst examples
%license LICENSE

%files -n python%{python3_pkgversion}-%{name}
%{python3_sitelib}/%{name}/
%{python3_sitelib}/%{name}-*.egg-info
%license LICENSE


%changelog
* Wed Oct 30 2019 Petr Šplíchal <psplicha@redhat.com> - 0.10-1
- Mock is not needed for docs, fix missing new line
- Provide a public static method Tree.init()

* Wed Oct 09 2019 Petr Šplíchal <psplicha@redhat.com> - 0.9-1
- Support custom conjunction like 'or' in listed()
- Update smoke testset to the latest L2 spec
- Fix build conditional default for englocale
- Use raw strings for regular expression patterns

* Mon Sep 30 2019 Petr Šplíchal <psplicha@redhat.com> - 0.8-1
- Update spec to build Python 3 packages only
- Move unit tests into a separate directory
- Move testsets, include a super simple smoke test
- Initial set of stories and tests
- Enable beakerlib smoke test in the testing farm
- Add a simple beakerlib test for command line help
- Clean up the docs build folder directly
- Enable packit

* Fri Jul 26 2019 Petr Šplíchal <psplicha@redhat.com> - 0.7-1
- Support both old and new yaml loader
- Add advanced python filtering [fix #55]
- Drop explicit locale setting during build and install
- Drop Python 2 subpackage on Fedora 30+ (#1647798)
- Better handle yaml errors [fix #50]
- Support reducing attributes using the "-" suffix
- Prevent extra new lines in the show() output
- Adjust FullLoader to load all strings as unicode
- Suppress yaml warnings by specifying the loader
- Support Tree.find() for non-leaf nodes as well

* Mon Oct 08 2018 Petr Šplíchal <psplicha@redhat.com> 0.6-1
- Ignore directories with no metadata defined
- Give a nice error when .fmf file exists [fix #37]
- Ignore metadata subtrees [fix #43]
- Support for direct deep dictionary value retrieval
- Separate exception for missing tree root [fix #42]
- Move data merging into a separate method [fix #41]
- Ensure that data or parent are provided for Tree
- Test coverage for yaml syntax and finding root
- Do not walk through the whole directory hierarchy
- Example typo, handle yaml parse errors [fix #38]
- Require the same version of the rpm package

* Tue Jun 12 2018 Petr Šplíchal <psplicha@redhat.com> 0.5-1
- Add support for subcommands [fix #32]
- Define metadata tree root [fix #26]
- Enable regular expressions in --filter [fix #35]
- Support merging dictionary values as well
- Build Python 3 package for pip as well
- Add more detailed logging for easier debugging
- Correctly handle deep inheritance [fix #31]
- Load all strings from YAML files as Unicode
- Prevent data modification in filter [fix #30]
- Fix inheritance of scattered files [fix #25]

* Wed May 09 2018 Petr Šplíchal <psplicha@redhat.com> 0.4-1
- Do not gzip the man page, fix the source link [BZ#1575645]

* Wed Apr 25 2018 Petr Šplíchal <psplicha@redhat.com> 0.3-1
- Remove the unreliable syntactic sugar [fix #2]
- Add a simple example of a BeakerLib test
- Improve the output, fix the encoding issue [#21]
- Add sources as value for string formatting
- Show source files in debug mode [fix #15]
- Allow deeper one-line hierarchy [fix #17]
- Update the list of supported Python versions
- Use name 'root' for directory where Tree is rooted
- Fix the full path custom format example
- Move documentation to the fmf rpm package
- Remove entry_points, custom format merged into fmf
- Add a few custom format examples
- Update docs with the custom format support
- Run both Python 2 and Python 3 tests locally
- Make eval() work with with Python 3 as well
- Integrate custom formatting into base & cli
- The first draft of output formatting
- Enable python3 tests, python3 executable in Fedora
- Python 3 compatibility changes
- Show nothing if there are no metadata [fix #12]
- Clean up before preparing the source files
- Make setup methods compatible with older pytest

* Mon Apr 09 2018 Petr Šplíchal <psplicha@redhat.com> 0.2-1
- Build a separate fmf package for the executable
- Add docs example for setting up storage
- Improve command line test coverage
- Smoke tests for logging and coloring
- Tests for pluralize, listed and split
- Include a simple example of python code
- Separate base tests, forgotten asserts, cleanup
- Several adjustments for the attributes adding
- Adding ability to add value to parent attribute
- Fix Tree.get() to correctly return data
- Make the spec do python2 & python3 and EPEL & Fedora
- Ignore hidden files and directories when searching
- Add test coverage for the filter function
- Extend the list of examples, fix hierarchy typos
- Enable Travis Continuous Integration

* Mon Jan 22 2018 Petr Šplíchal <psplicha@redhat.com> 0.1-1
- Initial packaging.
