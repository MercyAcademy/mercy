#!/bin/sh

BASE=/home/jsquyres/git/mercy/linux
export BASE
subdir=`basename $0 | cut -d. -f1`

logfile=$HOME/logs/every.log

echo "`date`: $0: Running" >> $logfile

dir="$BASE/$subdir"

# Make sure the directory exists
if test ! -d "$dir"; then
    echo "`date`: $0: cannot find $dir"
    exit 1
fi

cd "$dir"

# Make sure there's at least one *.sh file
file=`ls | egrep '\.sh$'`
if test -z "$file"; then
    # JMS This will just lead to lots of noise
    #echo "`date`: $0: Nothing to do" >> $logfile
    exit 0
fi

for script in `ls $dir/*.sh`; do
    if test -x "$script"; then
        echo "`date`: $0: Running $script" >> $logfile
        "$script" >> $logfile 2>&1
        st=$?
        echo "`date`: $0: Ran $script; exit status: $st" >> $logfile
    fi
done
