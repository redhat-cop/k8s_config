#!/bin/sh

set -e

TESTDIR="$(realpath $(dirname $0))"

for TEST in $(find $TESTDIR -mindepth 1 -maxdepth 1 -type f -name 'unittest-*.py' -print)
do
    echo "================== $(basename $TEST) =================="
    cd "$TESDDIR"
    python $TEST
done

for TEST in $(find $TESTDIR -mindepth 1 -maxdepth 1 -type d -name '[0-9][0-9]-*' -print)
do
    echo "================== $(basename $TEST) =================="
    cd "$TEST"
    ansible-playbook playbook.yaml
done
