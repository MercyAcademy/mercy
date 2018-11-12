#!/bin/sh

data_dir="$HOME/data"
if test ! -d $data_dir; then
   echo Cannot find data dir: $data_dir
   exit 1
fi

# This is today's filename (i.e., just after midnight -- brand new
# file; don't upload this one yet).
db_filename="`date +'%Y-%m-%d'`.sqlite3"
cd "$data_dir"

if test ! -d archives; then
    mkdir -p archives
fi

script_dir=`readlink -f $BASE/../google-drive-uploader`
script="$script_dir/google-drive-uploader.py"

client_id="$data_dir/google-uploader-client-id.json"
user_credentials="$data_dir/google-uploader-user-credentials.json"

# Mercy Tech Team Drive, "2018 Tech/Cisco wifi controller data" folder
dest_folder=1alOQt8ilQzq-cRWBuqOI16a9fhOuJT_L

for file in `ls *.sqlite3 | grep -v $db_filename`; do
    echo "Uploading file to google: $file"
    $script \
        --app-id $client_id \
        --user-credentials $user_credentials \
        --dest $dest_folder \
        $file
    $st=$?

    # If we were successful uploading, then move this file to the
    # archives folder so that we don't upload it again tomorrow.
    if test $st -eq 0; then
        echo "Successfully uploaded and moved to archive: $file"
        mv -f $file archives
        bzip2 archives/$file
    fi
done
