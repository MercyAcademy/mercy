#!/bin/sh

if test ! -d "$BASE"; then
    echo "Cannot find the BASE directory!"
    exit 1
fi

cd $BASE/..
git pull --rebase --quiet
