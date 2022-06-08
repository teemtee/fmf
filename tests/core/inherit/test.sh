#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartTest "Valid"
        rlRun "pushd data"

        # Check test
        rlRun -s "fmf show --name /mini"
        rlAssertGrep "Minimal test" $rlRun_LOG
        rlAssertGrep "contact" $rlRun_LOG
        rlAssertGrep "fine" $rlRun_LOG

        # Check plan
        rlRun -s "fmf show --name /plans/features"
        rlAssertGrep "This plan should inherit nothing" $rlRun_LOG
        rlAssertNotGrep "contact" $rlRun_LOG
        rlAssertNotGrep "fine" $rlRun_LOG

        # Check ci
        rlRun -s "fmf show --name /ci"
        rlAssertGrep "resultsdb-testcase: separate" $rlRun_LOG
        rlAssertNotGrep "contact" $rlRun_LOG
        rlAssertNotGrep "fine" $rlRun_LOG

        rlRun "popd"
    rlPhaseEnd

    rlPhaseStartTest "Invalid"
        rlRun "pushd $(mktemp -d)"
        rlRun "fmf init"

        # Directives should be dictionary
        rlRun "echo '/: weird' > file.fmf"
        rlRun -s "fmf show" 1
        rlAssertGrep "Invalid fmf directive in '/file" $rlRun_LOG
        rlAssertGrep "Should be a 'dict', got a 'str' instead." $rlRun_LOG

        # Inherit should be a bool
        rlRun "echo -e '/: \n    inherit: hmmm' > file.fmf"
        rlRun -s "fmf show" 1
        rlAssertGrep "Invalid fmf directive 'inherit'" $rlRun_LOG

        # Unknown directive
        rlRun "echo -e '/: \n    weird: hmmm' > file.fmf"
        rlRun -s "fmf show" 1
        rlAssertGrep "Unknown fmf directive 'weird' in '/file'" $rlRun_LOG

        rlRun "popd"
    rlPhaseEnd

    rlPhaseStartTest "Integration with tmt"
        rlRun "pushd data"

        # Show tests
        rlRun -s "tmt tests show"
        rlAssertGrep "/mini" $rlRun_LOG
        rlAssertGrep "Minimal test" $rlRun_LOG
        rlAssertGrep "echo fine" $rlRun_LOG
        rlAssertNotGrep "/plan" $rlRun_LOG
        rlAssertNotGrep "/ci" $rlRun_LOG

        # Check plan
        rlRun -s "tmt plans show"
        rlAssertGrep "/plan" $rlRun_LOG
        rlAssertGrep "This plan should inherit nothing" $rlRun_LOG
        rlAssertNotGrep "/test" $rlRun_LOG
        rlAssertNotGrep "/ci" $rlRun_LOG

        rlRun "popd"
    rlPhaseEnd
rlJournalEnd
