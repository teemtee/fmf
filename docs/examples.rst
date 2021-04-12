======================
    Examples
======================

Let's have a look at a couple of real-life examples!


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

    /requirements:
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


Setups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This example shows how to use Flexible Metadata Format to
run tests with different storage setups including cleanup.
This is simplified metadata, whole example including tools
can be found at storage_setup__::

    /setups:
        description: Tests to prepare and clean up devices for tests
        setup: True
        /setup_local:
            test: setup_local.py
            requires_cleanup: setups/cleanup_local
        /cleanup_local:
            test: cleanup_local.py
        /setup_remote:
            test: setup_remote.py
            requires_cleanup: setups/cleanup_remote
        /cleanup_remote:
            test: cleanup_remote.py
        /setup_vdo:
            test: setup_vdo.py
            requires_cleanup: setups/cleanup_vdo
        /cleanup_vdo:
            test: cleanup_vdo.py
    /tests:
        description: Testing 'vdo' command line tool
        requires_setup: [setups/setup_vdo]
        /create
            description: Testing 'vdo create'
            /ack_threads
            /activate
        /modify
            description: Testing 'vdo modify'
            requires_setup+: [setups/setup_remote]
            /block_map_cache_size

__ https://github.com/jkrysl/storage_setup

You can find here not only how to use FMF for setup/cleanup
and group tests based on that, but also installing requirements,
passing values from metadata to tests themself and much more.


Format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Custom format output using ``--format`` and ``value``.

List object name and selected attribute::

    fmf examples/wget --format '{0}: {1}\n' \
        --value 'name' --value 'data["tester"]'

Show missing attributes in red::

    fmf examples/wget/ --format '{}: {}\n' --value 'name' \
        --value 'utils.color(str(data.get("priority")),
        "red" if data.get("priority") is None else "green")'

List all test scripts with full path::

    fmf examples --key test --format "{}/{}/{}\n" \
        --value "os.getcwd()" \
        --value "data.get('path') or name" \
        --value "data['test']"
