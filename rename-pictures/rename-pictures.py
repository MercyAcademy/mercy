#!/usr/bin/env python3
#
# Simple Python script to rename a whole bunch of files.
#
# See the README.md script for instructions on how to run this script.

import os
import csv
import sys

# Check to make sure the command line argument was specified.
if not sys.argv[1]:
    print("ERROR: Need to specify CSV filename")
    exit(1)

# Check to make sure that the specified CSV filename actually exists.
if not os.path.exists(sys.argv[1]):
    print(f"ERROR: Cannot find file {sys.argv[1]}")
    exit(1)

# Open the file
with open(sys.argv[1]) as csv_file:
    # Setup to read the file as a CSV
    reader = csv.reader(csv_file)

    # Read (and discard) the first row -- it's just the column title names.
    first_row = next(reader)

    # Now read every row in the CSV file
    for row in reader:
        # The first item is the new filename; the second item is the old filename
        new_filename = row[0]
        old_filename = row[1]

        # Split out just the suffix (e.g., ".jpg") from the old filename
        parts  = os.path.splitext(old_filename)
        suffix = "." + parts[1]

        # Check to see if the new filename has the same suffix as the old
        # filename.  If it does not, add the suffix to it.
        if not new_filename.endswith(parts[1]):
            new_filename += parts[1]

        if os.path.exists(old_filename):
            # If the old filename eixsts, rename it
            os.rename(old_filename, new_filename)
            print(f"Renamed: {old_filename} --> {new_filename}")
        else:
            # If the old filename does not exist, print an error
            print(f"ERROR: File {old_filename} not found!")
