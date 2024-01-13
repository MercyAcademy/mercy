#!/usr/bin/env python3
#
# Simple script to gather some ping-the-gateway data on a continual
# basis for some testing of network behavior in Mercy's environment.

import os
import sys
import json
import time
import datetime
import xmltodict
import subprocess

from pprint import pprint, pformat

# This is where macOS's DHCP leases are located
lease_dir = '/var/db/dhcpclient/leases'

# Used in the examination of the macOS DHCP XML metadata, below.
indexes = {
    'IPAddress' : None,
    'NetworkID' : None,
    'RouterIPAddress' : None,
}

# Use an object to write to the JSON file so that we can use a context
# manager, and prepend / postpend enough to make the output be valid
# JSON.
class JsonFile(object):
    def __init__(self, file_name):
        self.file_name = file_name
        self.first = True

    def __enter__(self):
        print(f"Writing to file: {outfile}")
        self.file = open(self.file_name, 'w')
        self.file.write('[\n')
        return self

    def __exit__(self, *args):
        self.file.write('\n]\n')
        self.file.close()
        print(f"\nWrote to file: {outfile}\n")

    def write_obj(self, obj):
        if not self.first:
            self.file.write(',\n')
        self.first = False

        self.file.write(json.dumps(obj, indent=4, sort_keys=True))
        self.file.flush()

####################################################

# Sanity check to make sure we're running as root (or we won't be able
# to read the DHCP leases).
if os.geteuid() != 0:
    print("ERROR: This script must be run as root (in order to read the macOS DHCP leases)")
    print(f"       Re-run with: sudo {sys.argv[0]}")
    exit(1)

####################################################

# Make an output filename
now = datetime.datetime.now()
outfile = f'ping-data-starting-{now}.txt'

# Run forever; make sure to tidy up the JSON output file when done.
with JsonFile(outfile) as json_fp:
    while True:
        start = datetime.datetime.now(datetime.UTC)
        print(f"=== {start}")

        dhcp_data = list()
        dhcp_leases = os.listdir(lease_dir)
        for lease in dhcp_leases:
            filename = os.path.join(lease_dir, lease)
            if not os.path.isfile(filename):
                continue

            xml_string = None
            with open(filename) as fp:
                xml_string = fp.read()
            lease_data = xmltodict.parse(xml_string)

            if not lease_data:
                continue

            # XML is the worst.
            #
            # We know the lease time is the only integer, and the
            # start time is the only date.  So we can just slurp those
            # directly.
            the_data = lease_data['plist']['dict']

            lease_start_str = the_data['date']
            lease_start = datetime.datetime.fromisoformat(lease_start_str)

            lease_len_seconds = int(the_data['integer'])
            lease_len_delta = datetime.timedelta(seconds=lease_len_seconds)

            lease_end = lease_start + lease_len_delta
            now = datetime.datetime.now(datetime.UTC)
            lease_time_left = lease_end - datetime.datetime.now(datetime.UTC)

            # Get our IP address. There are multiple strings in the
            # orignal XML data, so we have to look through the list of
            # keys, find the string name that we want ('IPAddress'),
            # and index that into the list of 'string' data slurped
            # from the XML.  Ugh.  First, calculate the indexes.
            index = 0
            for key in the_data['key']:
                if key in indexes.keys():
                    indexes[key] = index
                    index += 1

            # Now pull our IPAddress from the list of string data in the
            # dictionary we pulled from the XML data.
            lease_ip_address = the_data['string'][indexes['IPAddress']]

            # Ditto for the gateway IP address
            lease_gateway = the_data['string'][indexes['RouterIPAddress']]

            data = {
                'ip' : lease_ip_address,
                'gateway' : lease_gateway,
                'lease start' : str(lease_start),
                'lease end' : str(lease_end),
                'lease time left' : str(lease_time_left),
            }
            dhcp_data.append(data)

        # Run the ping
        ping_cmd = [ 'ping', '-c', '10', dhcp_data[0]['gateway'] ]
        ping_out = subprocess.run(ping_cmd, check=False,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)

        # Check for some obvious errors
        happy = True
        ping_stdout = ping_out.stdout.decode('utf-8')
        if 'sendto: No route' in ping_stdout or \
           'Request timeout' in ping_stdout or \
           ping_out.returncode != 0:
            print(f"  --> Ping was unhappy (rc={ping_out.returncode}).  Output:")
            print(ping_stdout)
            happy = False

        # Record the end time
        end = datetime.datetime.now(datetime.UTC)

        data = {
            'start' : str(start),
            'dhcp data' : dhcp_data,
            'ping cmd' : ' '.join(ping_cmd),
            'ping stdout' : ping_stdout,
            'ping rc' : ping_out.returncode,
            'ping happy' : happy,
            'end' : str(end),
        }
        json_fp.write_obj(data)

        # Delay a little and run again
        time.sleep(1)
