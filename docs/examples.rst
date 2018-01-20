
======================
    Examples
======================

Let's have a look at a couple of real-life examples!


Relevancy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test Case Relevancy can be naturaly integrated::

    description: Check basic download options
    tags: [Tier2, TierSecurity]
    relevancy:
    - "distro < rhel-7: False"
    - "arch = s390x: False"

Note that, because of YAML parsing, relevancy rules have to be
enclosed in quotes. Another option is to use text format::

    description: Check basic download options
    tags: [Tier2, TierSecurity]
    relevancy: |
        distro < rhel-7: False
        arch = s390x: False

Which seems a bit more clear.


Coverage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test coverage information can be stored in a single file, for
example ``wget/requirements.fmf``::

    /protocols:
        priority: high
        /ftp:
            requirement: Download a file using the ftp protocol.
            coverage: wget/protocols/ftp
        /http:
            requirement: Download a file using the http protocol.
            coverage: wget/protocols/http
        /https:
            requirement: Download a file using the https protocol.
            coverage: wget/protocols/https
    
    /download:
        priority: medium
        /output-document-pipe:
            requirement: Save content to pipe.
            coverage: wget/download
        /output-document-file:
            requirement: Save content to a file.
            coverage: wget/download
    
    /upload:
        priority: medium
        /post-file:
            requirement: Upload a file to the server
            coverage: wget/protocols/http
        /post-data:
            requirement: Upload a string to the server
            coverage: wget/protocols/http

Or split by functionality area into separate files as desired, for
example ``wget/download/requirements.fmf``::

    priority: medium
    /output-document-pipe:
        requirement: Save content to pipe.
        coverage: wget/download
    /output-document-file:
        requirement: Save content to a file.
        coverage: wget/download

Or integrated with test case metadata, e.g.
``wget/download/main.fmf``::

    description: Check basic download options
    tags: [Tier2, TierSecurity]
    test: runtest.sh
    time: 3 min
    
    /requirements
        requirement: Various download options working correctly
        priority: low
        /get-file:
            coverage: wget/download
        /output-document:
            coverage: wget/download
        /continue:
        /timestamping:
        /tries:
        /no-clobber:
            coverage: wget/download
        /progress:
        /quota:
        /server-response:
        /bind-address:
        /spider:

In the example above three requirements are already covered,
the rest still await for test coverage (attributes value is null).


Strategist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's an example implementation of test-strategist__ data for
openscap using the Flexible Metadata Format::

    /probes:
        description: Probes
        /offline:
            description: Offline scanning
        /online:
            description: Online scanning
    /scanning:
        description: Reading and understanding source datastreams
        /oval:
            influencers:
            - openscap/probes/offline
            - openscap/probes/online
        /ds:
            influencers:
            - openscap/scanning/oval
            - openscap/scanning/cpe
        /cpe:
            influencers:
            - openscap/scanning/oval

__ https://github.com/dahaic/test-strategist
