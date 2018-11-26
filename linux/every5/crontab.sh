#!/bin/sh

# Double check to make sure that the crontab file is not empty before
# replacing it (i.e., the "-s" option).
file="$BASE/crontab.txt"
if test -f "$file" -a -s "$file"; then
    crontab $file
fi
