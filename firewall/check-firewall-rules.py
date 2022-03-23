import csv

# Import the CSV into a list of URLs
blockedUrlFile = "blocked.csv"
with open(blockedUrlFile, newline='') as csvFile:
    urlReader - csv.DictReader(csvFile)

# Go through the list and and remove any regex

# Go through the sanitized list and see if we get the proper response back from
# each one. (Success from allowed ones, failures from denied ones)

