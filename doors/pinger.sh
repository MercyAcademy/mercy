#!/bin/bash

set -euxo pipefail

while /usr/bin/true; do
    d=`date +%Y%m%d-%H%M%S`

    dir=`date +%Y%m%d-%H`
    filename="ping-$d.log"
    mkdir -p $dir
    echo "=== DATE: `date`"
    echo "=== HOSTNAME: `hostname`"
    ip addr
    echo "==="
    ping -c 50 172.16.20.249 2>&1 | tee $dir/$filename

    set +e
    ssh mercy@mercy.squyres.com mkdir -p mercy/logs/$dir
    scp $dir/$filename mercy@mercy.squyres.com:mercy/logs/$dir
    set -e
done
