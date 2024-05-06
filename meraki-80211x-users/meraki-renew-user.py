#!/usr/bin/env python3
#
# See the README.md file in this directory for information about this
# script.

import meraki
import string
import secrets
import argparse
import datetime

# See https://github.com/redacted/XKCD-password-generator
from xkcdpass import xkcd_password as xp

#----------------------------------------------------------------------

def get_org(dashboard, name):
    print(f"Finding Meraki org: {name}")

    organizations = dashboard.organizations.getOrganizations()
    for org in organizations:
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

def get_user(dashboard, network_id, email):
    print(f"Finding Meraki user: {email}")

    users = dashboard.networks.getNetworkMerakiAuthUsers(network_id)
    for user in users:
        if user['email'] == email:
            return user

    print(f"Could not find user {email}")
    exit(1)

########################################################################

def setup_cli():
    parser = argparse.ArgumentParser(description='Renew Meraki 802.11x user for 7 days')
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
                        default='Mercy Guest',
                        help='Meraki SSID')
    parser.add_argument('--email',
                        default='mercyguest@mercyjaguars.com',
                        help='Email address of Meraki 802.11x/wifi user')

    expires = datetime.datetime.now() + datetime.timedelta(hours=7*24)
    parser.add_argument('--expires',
                        default=expires.isoformat(),
                        help='Expiration of renewal')

    args = parser.parse_args()
    return args

#----------------------------------------------------------------------

def reset_user(dashboard, network_id, ssid_number, user_id, args):
    authorizations = [
        {
            'ssidNumber' : ssid_number,
            'expiresAt' : args.expires,
        },
    ]

    sources = string.ascii_letters + string.digits + string.punctuation

    # create a wordlist from the default wordfile
    # use words between 5 and 8 letters long
    wordfile = xp.locate_wordfile()
    mywords = xp.generate_wordlist(wordfile=wordfile, min_length=5, max_length=6)
    password = xp.generate_xkcdpassword(mywords, acrostic="mercy")
    password = password.title().replace(' ', '')

    dashboard.networks.updateNetworkMerakiAuthUser(network_id,
                                                   user_id,
                                                   emailPasswordToUser=True,
                                                   password=password,
                                                   authorizations=authorizations)
    print("Set password!")

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
    meraki_user = get_user(meraki_dashboard, network_id,
                           args.email)

    reset_user(meraki_dashboard, network_id, meraki_ssid['number'],
               meraki_user['id'], args)

main()
