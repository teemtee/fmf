Name: fmf
Version: 0.7
Release: 1%{?dist}

Summary: Flexible Metadata Format
License: GPLv2+
BuildArch: noarch

URL: https://github.com/psss/fmf
Source: https://github.com/psss/fmf/releases/download/%{version}/fmf-%{version}.tar.gz

# Depending on the distro, we set some defaults.
# Note that the bcond macros are named for the CLI option they create.
# "%%bcond_without" means "ENABLE by default and create a --without option"

# Fedora 30+ or RHEL 8+ (py3 executable, py3 subpackage, auto build requires)
%if 0%{?fedora} > 29 || 0%{?rhel} > 7
%bcond_with python2
%bcond_without python3
%bcond_with py2executable
%bcond_with oldreqs

# Older RHEL (py2 executable, py2 subpackage, manual build requires)
%else
%if 0%{?rhel}
%bcond_without python2
%bcond_with python3
%bcond_without py2executable
%bcond_without oldreqs

# Older Fedora (py3 executable, py3 & py2 subpackage, auto build requires)
%else
%bcond_without python2
%bcond_without python3
%bcond_with py2executable
%bcond_with oldreqs
%endif
%endif

# Main fmf package requires corresponding python module
%if %{with py2executable}
Requires: python2-%{name} == %{version}-%{release}
%else
Requires: python%{python3_pkgversion}-%{name} == %{version}-%{release}
%endif

%description
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the command line tool.

%?python_enable_dependency_generator


# Python 2
%if %{with python2}
%package -n     python2-%{name}
Summary:        %{summary}
BuildRequires: python2-devel
BuildRequires: python2-setuptools
%if %{with oldreqs}
BuildRequires: pytest
BuildRequires: PyYAML
%else
BuildRequires: python2dist(pytest)
BuildRequires: python2dist(pyyaml)
%endif
%{?python_provide:%python_provide python2-%{name}}
%if %{with oldreqs}
Requires:       PyYAML
%endif

%description -n python2-%{name}
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the Python 2 module.
%endif


# Python 3
%if %{with python3}
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
%endif


%prep
%setup -q


%build
%if 0%{?fedora} < 30 || 0%{?rhel}
export LANG=en_US.utf-8 # for Python <= 3.6 and EPEL <= 7, but harmless
%endif

%if %{with python2}
%py2_build
%endif
%if %{with python3}
%py3_build
%endif


%install
%if 0%{?fedora} < 30 || 0%{?rhel}
export LANG=en_US.utf-8
%endif

%if %{with python2}
%py2_install
%endif

%if %{with python3}
%py3_install
%endif

%if %{with py2executable} && %{with python3}
rm -f %{buildroot}%{_bindir}/*
%py2_install
%endif

mkdir -p %{buildroot}%{_mandir}/man1
install -pm 644 fmf.1* %{buildroot}%{_mandir}/man1


%check
export LANG=en_US.utf-8

%if %{with python2}
%{__python2} -m pytest -vv
%endif

%if %{with python3}
%{__python3} -m pytest -vv
%endif


%{!?_licensedir:%global license %%doc}


%files
%{_mandir}/man1/*
%{_bindir}/%{name}
%doc README.rst examples
%license LICENSE

%if %{with python2}
%files -n python2-%{name}
%{python2_sitelib}/%{name}/
%{python2_sitelib}/%{name}-*.egg-info
%license LICENSE
%endif

%if %{with python3}
%files -n python%{python3_pkgversion}-%{name}
%{python3_sitelib}/%{name}/
%{python3_sitelib}/%{name}-*.egg-info
%license LICENSE
%endif


%changelog
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
