#!/bin/sh

want=0

# If this file exists, make a tunnel
file=$HOME/tunnel
if test -f $file; then
    want=1
    rm -f $file
fi

# If this URL exists, make a tunnel
file=tunnel.txt
wget --quiet http://jeff.squyres.com/mercy/$file
st=$?
if test $st -eq 0; then
    rm -f $file
    want=1
fi

# Did either of the above things happen?
if test $want -eq 1; then
    echo `date`: Creating tunnel
    ssh -fN -R 2222:localhost:22 jeff@squyres.com
fi
