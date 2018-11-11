#!/bin/sh

file=$HOME/tunnel

if test -f $file; then
    echo `date`: Creating tunnel
    ssh -fN -R 2222:localhost:22 jeff@squyres.com
    rm -f $file
fi
