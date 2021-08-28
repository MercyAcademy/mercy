#!/bin/bash

set -euxo pipefail

while /usr/bin/true; do
    d=`date +%Y%m%d-%H%M%S`

    dir=`date +%Y%m%d-%H`
    filename="ping-$d.log"
    mkdir -p $dir
    echo "=== DATE: `date`"
    ping -c 50 172.16.20.249 2>&1 | tee $dir/$filename

    set +e
    ssh jeff@squyres.com mkdir -p mercy/logs/$dir
    scp $dir/$filename jeff@squyres.com:mercy/logs/$dir
    set -e
done
