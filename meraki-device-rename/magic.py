#!/usr/bin/env python3
#
# See the README.md file in this directory for information about this
# script.

import csv
import meraki

# From Meraki: account -> My Profile, make an API key
api_key = 'set your API key here'

jamf_export_filename = "Devices.csv"
# Set this to "True" if the jamf_export_filename is a JAMF School
# export file, or False if it is a JAMF Pro export file.
jamf_export_is_jamf_school = True

meraki_org_name = 'Mercy Academy'
meraki_network_name = 'Mercy'

meraki_policy_name = 'Normal'

#----------------------------------------------------------------------

def read_jamf_export_file(filename, sep):
    devices = list()
    with open(filename) as fp:
        reader = csv.DictReader(fp, delimiter=sep)
        for device in reader:

            # JAMF Pro and JAMF School have slightly different field
            # names for the device name and the wifi MAC.  Make them
            # be the same.
            if 'WiFiMAC' in device:
                device['Mercy:Wifi MAC'] = device['WiFiMAC']
                device['Mercy:Eth MAC'] = device['EthernetMAC']
            elif 'Wi-Fi MAC Address' in device:
                # 2022 Aug: we no longer have JAMF School, so I don't
                # know/care what the ethernet column is.
                device['Mercy:Wifi MAC'] = device['Wi-Fi MAC Address']

            if 'Name' in device:
                device['Mercy:Name'] = device['Name']
            elif 'Display Name' in device:
                device['Mercy:Name'] = device['Display Name']

            devices.append(device)

    return devices

#----------------------------------------------------------------------

def get_org(dashboard, name):
    organizations = dashboard.organizations.getOrganizations()
    for org in organizations:
        if org['name'] == name:
            return org

    return None

#----------------------------------------------------------------------

def get_network(dashboard, org, name):
    networks = dashboard.organizations.getOrganizationNetworks(org['id'])
    for network in networks:
        if network['name'] == name:
            return network

    return None

########################################################################

# JAMF Pro uses "," as a delimiter
sep = ','
if jamf_export_is_jamf_school:
    # JAMF School uses "," as a delimiter.
    sep = ';'

print(f"Reading JAMF export file: {jamf_export_filename}")
devices = read_jamf_export_file(jamf_export_filename, sep)
print(f"Found {len(devices)} devices")

print("Logging in to the Meraki dashboard...")
meraki_dashboard = meraki.DashboardAPI(api_key=api_key,
                                       output_log=False,
                                       print_console=False)

print(f"Finding Meraki org: {meraki_org_name}")
meraki_org = get_org(meraki_dashboard, meraki_org_name)

print(f"Finding Meraki network: {meraki_network_name}")
meraki_network = get_network(meraki_dashboard, meraki_org,
                             meraki_network_name)

# Go through all the devices that we read from the JAMF export file
# and make a Meraki API call to provision each one.
for device in devices:
    # Crude: remove punctuation from the name (Meraki won't let us
    # use () in device names).
    name = device['Mercy:Name'].replace("(", "")
    name = name.replace(")", "")

    client_data = {
        'mac' : device['Mercy:Wifi MAC'],
        'name' : name,
    }

    print(f"- Setting name for wifi MAC {client_data['mac']}: {client_data['name']}")
    response = meraki_dashboard.networks.provisionNetworkClients(
        meraki_network['id'], [ client_data ],
        meraki_policy_name)

    # If we have an Ethernet MAC, set that one, too.
    key = 'Mercy:Eth MAC'
    if key in device:
        eth_mac = device[key]
        if eth_mac != None and eth_mac != '':
            client_data = {
                'mac' : device[key],
                'name' : name,
            }

            print(f"- Setting name for eth MAC {client_data['mac']}: {client_data['name']}")
            response = meraki_dashboard.networks.provisionNetworkClients(
                meraki_network['id'], [ client_data ],
                meraki_policy_name)

print("All done!")
