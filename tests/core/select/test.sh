#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartTest
        rlRun "pushd data"

        rlRun -s "fmf ls"
        rlAssertGrep "^/foo$" $rlRun_LOG
        rlAssertGrep "^/foo/child$" $rlRun_LOG
        rlAssertNotGrep "^/foo/hidden$" $rlRun_LOG

        rlRun "popd"
    rlPhaseEnd
rlJournalEnd
