#!/bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Run all phases by default
phase=${1:-all}
examples=$(ls -d /usr/share/doc/fmf*/examples/wget)

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm "fmf"
        rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "pushd $TmpDir"
        rlRun "set -o pipefail"
    rlPhaseEnd

    [[ $phase =~ all|ls ]] && {
    rlPhaseStartTest "Test listing available nodes"
        rlRun "fmf ls --path $examples | tee output"
        rlAssertGrep "/protocols/https" "output"
        rlAssertNotGrep "priority: high" "output"
    rlPhaseEnd; }

    [[ $phase =~ all|show ]] && {
    rlPhaseStartTest "Test showing node attributes"
        rlRun "fmf show --path $examples | tee output"
        rlAssertGrep "/protocols/https" "output"
        rlAssertGrep "priority: high" "output"
    rlPhaseEnd; }

    [[ $phase =~ all|name ]] && {
    rlPhaseStartTest "Test selecting nodes by name"
        rlRun "fmf show --path $examples --name /recursion/deep | tee output"
        rlAssertGrep "/recursion/deep" "output"
        rlAssertGrep "depth: 1000" "output"
    rlPhaseEnd; }

    [[ $phase =~ all|filter ]] && {
    rlPhaseStartTest "Test advanced filter"
        rlRun "fmf ls --path $examples --filter priority:high | tee output"
        rlAssertGrep "/requirements/protocols/https" "output"
        rlAssertNotGrep "/requirements/protocols/progress" "output"
    rlPhaseEnd; }

    [[ $phase =~ all|condition ]] && {
    rlPhaseStartTest "Test arbitrary condition"
        rlRun "fmf ls --path $examples --condition 'depth < 100' | tee output"
        rlAssertGrep "/recursion/fast" "output"
        rlAssertNotGrep "/recursion/deep" "output"
    rlPhaseEnd; }

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
    rlPhaseEnd
rlJournalEnd
