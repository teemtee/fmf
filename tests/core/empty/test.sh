#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartSetup
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "set -o pipefail"
    rlPhaseEnd

    rlPhaseStartTest "Test simple metadata"
        rlRun "pushd $tmp"
        # No fmf files at all
        rlRun "fmf init"
        for action in ls show; do
            rlRun "fmf $action | tee output"
            rlRun "[[ '$(<output)' == '/' ]]" 0 "Output should be '/' only"
        done
        # Just an empty main.fmf
        rlRun "touch main.fmf"
        for action in ls show; do
            rlRun "fmf $action | tee output"
            rlRun "[[ '$(<output)' == '/' ]]" 0 "Output should be '/' only"
        done
        rlRun "popd"
    rlPhaseEnd

    rlPhaseStartTest "Test full metadata"
        rlRun "pushd data"
        for action in ls show; do
            rlRun "fmf $action | tee $tmp/output"
            rlAssertGrep "^/empty$" $tmp/output
            rlAssertGrep "^/one$" $tmp/output
            rlAssertGrep "^/two/empty$" $tmp/output
            rlAssertGrep "/virtual/python3" $tmp/output
            rlAssertGrep "/virtual/default" $tmp/output
            rlAssertGrep "/virtual/name/python3" $tmp/output
            rlAssertGrep "/virtual/name/default" $tmp/output
            rlAssertNotGrep "/other" $tmp/output
        done
        rlRun "popd"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
