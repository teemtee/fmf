#!/bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE="fmf"
EXAMPLES=$(ls -d /usr/share/doc/fmf*/examples)

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE
        rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "pushd $TmpDir"
        rlRun "set -o pipefail"
    rlPhaseEnd

    rlPhaseStartTest "help"
        rlRun "fmf --help | tee help" 0 "Run help"
        rlAssertGrep "command line interface" "help"
    rlPhaseEnd

    rlPhaseStartTest "man"
        rlRun "man fmf | tee man" 0 "Check man page"
        rlAssertGrep "usage is straightforward" "man"
    rlPhaseEnd

    rlPhaseStartTest "examples"
        rlRun "ls $EXAMPLES | tee examples" 0 "Check examples"
        rlAssertGrep "wget" "examples"
        rlRun "fmf ls --path $EXAMPLES/wget | tee wget"
        rlAssertGrep "/protocols/https" "wget"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
    rlPhaseEnd
rlJournalEnd
