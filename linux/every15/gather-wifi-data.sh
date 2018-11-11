#!/bin/sh

dir=`dirname $BASE`

data_dir="$HOME/data"
if test ! -d $data_dir; then
   echo Cannot find data dir: $data_dir
   exit 1
fi

file="$data_dir/cisco-controller-credentials.txt"
if test ! -f $file; then
    echo Cannot find $file
    exit 1
fi

# Read in the credentials (not stored in git)
. $file

db_filename="$data_dir/`date +'%Y-%m-%d'`.sqlite3"

script_dir=`readlink -f "$dir/cisco-controller"`
script="$script_dir/gather-controller-logs.py"
if test ! -x "$script"; then
    echo Cannot find $script
    exit 1
fi

$script --user $USER --password $PASSWORD --db $db_filename
