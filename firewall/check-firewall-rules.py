import csv
import requests

cleanedLinks = list()

# Import the CSV into a list of URLs
blockedUrlFile = "blocked.csv"
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

