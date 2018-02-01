Name: fmf
Version: 0.1
Release: 1%{?dist}

Summary: Flexible Metadata Format
License: GPLv2+

URL: https://github.com/psss/fmf
Source: https://github.com/psss/fmf/releases/download/%{version}/fmf-%{version}.tar.bz2

BuildArch: noarch
BuildRequires: python-devel
Requires: PyYAML

%description
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_mandir}/man1
mkdir -p %{buildroot}%{python_sitelib}/fmf
install -pm 755 bin/fmf %{buildroot}%{_bindir}/fmf
install -pm 644 fmf/*.py %{buildroot}%{python_sitelib}/fmf
install -pm 644 fmf.1.gz %{buildroot}%{_mandir}/man1


%files
%{_mandir}/man1/*
%{_bindir}/fmf
%{python_sitelib}/*
%doc README.rst examples
%{!?_licensedir:%global license %%doc}
%license LICENSE

%changelog
* Mon Jan 22 2018 Petr Šplíchal <psplicha@redhat.com> 0.1-1
- Initial packaging.
