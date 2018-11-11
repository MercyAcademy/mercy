#!/bin/sh

file="$BASE/crontab.txt"
if test -f "$file"; then
    crontab $file
fi
