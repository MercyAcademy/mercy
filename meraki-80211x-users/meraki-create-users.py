#!/usr/bin/env python3
#
# See the README.md file in this directory for information about this
# script.

import os
import csv
import pytz
import meraki
import string
import secrets
import argparse
import datetime

#----------------------------------------------------------------------

def get_org(dashboard, name):
    print(f"Finding Meraki org: {name}")

    organizations = dashboard.organizations.getOrganizations()
    for org in organizations:
        print(f"Found org: {org['name']}")
        if org['name'] == name:
            return org

    print(f"Could not find org {name}")
    exit(1)

#----------------------------------------------------------------------

def get_network(dashboard, org, name):
    print(f"Finding Meraki network: {name}")

    networks = dashboard.organizations.getOrganizationNetworks(org['id'])
    for network in networks:
        if network['name'] == name:
            return network

    print(f"Could not find network {name}")
    exit(1)

#----------------------------------------------------------------------

def get_ssid(dashboard, network_id, name):
    print(f"Finding Meraki SSID: {name}")

    ssids = dashboard.wireless.getNetworkWirelessSsids(network_id)
    for ssid in ssids:
        if ssid['name'] == name:
            return ssid

    print(f"Could not find SSID {name}")
    exit(1)

#----------------------------------------------------------------------

def create_users(dashboard, network_id, ssid_number, args):
    # Same authorization for all users
    authorizations = [
        {
            'ssidNumber' : ssid_number,
            'expiresAt' : args.expires,
        },
    ]

    sources = string.ascii_letters + string.digits + string.punctuation

    # Read the CSV
    csv_users = list()
    with open(args.file) as fp:
        reader = csv.reader(fp)

        for i, row in enumerate(reader):
            name = row[0]
            email = row[1]

            # If the email doesn't have @ in it, skip this row
            if not '@' in email:
                print(f"WARNING: Skipping row {i+1}: {name} / {email}")
                continue

            csv_users.append({
                'name' : name,
                'email' : email,
            })

    # Load all existing Meraki users
    meraki_users = dashboard.networks.getNetworkMerakiAuthUsers(network_id)

    # See if there are any CSV users that already exist as Meraki users
    for csv_user in csv_users:
        csv_email = csv_user['email'].lower()

        for meraki_user in meraki_users:
            if csv_email == meraki_user['email'].lower():
                print(f"ERROR: User in CSV file already exists in Meraki: {csv_user['name']} / {csv_user['email']}")
                exit(1)

    # Ok, all CSV users are new
    # Make them all
    for csv_user in csv_users:

            # Make a password for this user
            password = ''.join([ secrets.choice(sources) for x in range(args.pw_length) ])

            dashboard.networks.createNetworkMerakiAuthUser(network_id,
                                                           csv_user['email'],
                                                           authorizations,
                                                           name=csv_user['name'],
                                                           password=password,
                                                           accountType='802.1X',
                                                           emailPasswordToUser=True,
                                                           isAdmin=False)
            print(f"Created user: {csv_user['name']} / {csv_user['email']}")

########################################################################

def setup_cli():
    parser = argparse.ArgumentParser(description='Renew Meraki 802.11x user for 24 hours')
    parser.add_argument('--api-key',
                        required=True,
                        help='Meraki API key')
    parser.add_argument('--org',
                        default='Mercy Academy',
                        help='Meraki organization name')
    parser.add_argument('--network',
                        default='Mercy',
                        help='Meraki network name')
    parser.add_argument('--ssid',
                        default='Mercy Authorized',
                        help='Meraki SSID')
    parser.add_argument('--file',
                        required=True,
                        help='CSV filename of name,email rows')
    parser.add_argument('--pw-length',
                        default=12,
                        help='Length of password to generate')

    now = datetime.datetime.now()
    year = now.year
    if now.month >= 6:
        year = now.year + 1

    eastern = pytz.timezone('US/Eastern')
    dt = datetime.datetime(year=year, month=6, day=30,
                           hour=23, minute=59, second=59)
    expires = eastern.localize(dt)
    parser.add_argument('--expires',
                        default=expires.isoformat(),
                        help='Expiration of users')

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print("ERROR: File does not exist: {args.file}")
        exit(1)

    return args

#----------------------------------------------------------------------

def main():
    args = setup_cli()

    print("Logging in to the Meraki dashboard...")
    meraki_dashboard = meraki.DashboardAPI(api_key=args.api_key,
                                           output_log=False,
                                           print_console=False)

    meraki_org = get_org(meraki_dashboard, args.org)
    meraki_network = get_network(meraki_dashboard, meraki_org,
                                 args.network)
    network_id = meraki_network['id']
    meraki_ssid = get_ssid(meraki_dashboard, network_id,
                           args.ssid)

    create_users(meraki_dashboard, network_id,
                 meraki_ssid['number'], args)

main()
