#!/usr/bin/env python3
import csv
import requests
import sys

cleanedLinks = list()

# Import the CSV into a list of URLs, use the first command line argument as the
# filename
try:
    blockedUrlFile = sys.argv[1]
except IndexError:
    print("Pass the CSV as a command line argument")
    exit()
with open(blockedUrlFile, newline='') as csvFile:
    urlReader = csv.DictReader(csvFile)
    # Go through the list and and remove any regex
    for row in urlReader:
        row["URL PATTERN"] = row["URL PATTERN"].strip("*.")
        cleanedLinks.append(row)

# Go through the sanitized list and see if we get the proper response back from
# each one. (Success from allowed ones, failures from denied ones)
for site in cleanedLinks:
    url = f"https://{site['URL PATTERN']}"
    name = site["NAME"]
    # If there's no name, use the URL instead so we have *something*
    if name == "":
        name = site["URL PATTERN"]
    denied = False
    if site["ACTION"] == "Deny":
        denied = True
    try:
        request = requests.get(url, timeout=1)
        if denied:
            response = f"FAIL: got through with response {request.status_code}"
        else:
            response = "SUCCESS: allowed"
    except requests.Timeout as error:
        if denied:
            response = "SUCCESS: blocked"
        else:
            response = "FAIL: timed out when we shouldn't have"
    except Exception as error:
        response = f"something else went wrong... {error}"
    print(f"{name}: {response}")

