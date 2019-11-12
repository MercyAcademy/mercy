#!/usr/bin/env python3

"""
Script to set the Gmail signature of a set of users specified by a CSV.

In November 2019, Mercy wanted to set a common signature for all of its faculty
and staff.  This script was written to do the following:

1. Read a file containing a signature HTML template.
2. Read a CSV containing a list of email addresses, names, and titles.
3. For each email address in the CSV, customize the signature HTML template and
apply it to that Gmail account.

The API for setting a Gmail signature on a "SendAs" alias is relatively
straightforward.  There are two tricky parts to the process:

1. Getting the signature HTML correct.  There was a *lot* of trial and error
getting the HTML just right:

- getting the colors right
- hosting the images somewhere stable.  Notes:
    - Google Sites does not work because it customizes its image URLs depending
      on what type of device is requesting the image -- it flat-out refuses to
      serve some of its image URL forms to certain devices
    - Google Drive does not work -- at least as of Nov 2019 -- because you
    - cannot get a URL that points directly to the raw image
    - Dropbox does work, because you can get a URL to the raw image
    - Posting the images to a Mercy-specific web site would also work, but we
      did not go that route (because the current Mercy web site is in the middle
      of being migrated to a new site / new vendor)
- testing to see how the signature looks on different platforms

*NOTE:* Google has a 10K character limit on signatures.  While the API allows
*you to set signatures that are greater than 10K characters in length, users
*will get an amorphous error if they try to edit / save their signatures in the
*Gmail UI in this case.  It is therefore strongly advisable to check the HTML
*that you are setting as users' signatures and ensure it is (well) under 10K
*characters.

2. Getting the authorization to Google correct.  Setting a Gmail signature is a
user-specific action, but it is also possible for a G Suite administrator to set
such things.  However, Google (rightfully) makes a Very Big Deal about getting
or setting user-specific data without their consent, so you have to have a very
specific type of authorization to do this.  Specifically: it's not just G Suite
Super Admins that can do this -- you have to setup domain-wide delegation of
authority.

*NOTE:* Although we are obviously keeping this script after using it, we are
*destroying the credentials after using this script.  The credentials necessary
*to run this script are *very* powerful and should not be left lying around.
*Instead, run this script to do what you need to do and then destroy the
*credentials.  If necessary, just create new credentials to run the script again
*someday if necessary.

Here's a Google tutorial on how to make domain-wide delegation credentials (see
the two notes below):

https://developers.google.com/admin-sdk/directory/v1/guides/delegation

Two differences from the tutorial:

1. The tutorial is for the Admin SDK API instead of the Gmail API.  But but the
   procedure is exactly the same -- the only thing that differs is the scopes
   that are used.
2. Use a JSON file, not a p12 keyfile.  The correct Python API to load a JSON
   file (vs. a p12 keyfile) is in the code, below.

The general scheme with domain-wide delegation is:

- create a domain-wide delegation key
- download it
- load it in your program
- create a credential with it
- then say "I want to act as user foo@mercyjaguars.com with this credential"

Meaning that you have to re-create the credential for every user whose signature
you want to set.

The Gmail scopes that are necessary are the following:

scopes = ['https://www.googleapis.com/auth/gmail.labels',
          'https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.settings.basic',
          'https://www.googleapis.com/auth/gmail.settings.sharing']

I'm not actually sure that the first two are ncessary, but I ran out of patience
in trial-and-error testing to figure out the correct scopes.  Those 4 worked, so
I left it at that.  :-)

"""

import sys
sys.path.insert(0, '../python')

import os
import csv

import Mercy
import Google

from oauth2client import tools
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

from pprint import pprint
from pprint import pformat

scopes = ['https://www.googleapis.com/auth/gmail.labels',
          'https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.settings.basic',
          'https://www.googleapis.com/auth/gmail.settings.sharing']

#-------------------------------------------------------------------

def google_auth(user_email, args, log):
    credentials = service_account.Credentials.from_service_account_file(
        args.delegation_credential,
        scopes=scopes)
    delegated_credentials = credentials.with_subject(user_email)

    service = build('gmail', 'v1', credentials=delegated_credentials)
    return service

#-------------------------------------------------------------------

def set_signature(row, signature, args, log):
    email = row['Email']
    log.debug("Setting signature for: {e}".format(e=email))

    # Make a delegated credential for the target user
    gmail = google_auth(email, args, log)

    # Find the target user's primary "SendAs" alias (there will be exactly one).
    # 'me' is a special user indicating the current user (i.e., identified by
    # their credential).
    primary_alias = None
    aliases = gmail.users().settings().sendAs().list(userId='me').execute()
    for alias in aliases.get('sendAs'):
        if alias.get('isPrimary'):
            primary_alias = alias
            break

    log.debug("Primary alias: {a}".format(a=alias['sendAsEmail']))

    # Customize the signature for this user
    mysig = ''.join(signature)
    mysig = mysig.replace("EMAIL_ADDRESS", alias['sendAsEmail'])
    mysig = mysig.replace("FIRST_NAME", row['First Name'])
    mysig = mysig.replace("LAST_NAME", row['Last Name'])
    mysig = mysig.replace("TITLE", row['Title'])

    # Set the signature on this SendAs alias
    sendAsConfiguration = {
        'signature': mysig,
    }
    result = gmail.users().settings().sendAs().patch(userId='me',
               sendAsEmail=primary_alias.get('sendAsEmail'),
               body=sendAsConfiguration).execute()

    # Done!
    log.info('Updated signature for: {r}'.format(r=result.get('sendAsEmail')))

#-------------------------------------------------------------------

def read_sig(args):
    with open(args.signature, 'r') as f:
        signature = f.readlines()

    return signature

def read_names(args):
    with open(args.namefile, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        names = list()
        for row in reader:
            names.append(row)

    return names

#-------------------------------------------------------------------

def add_cli_args():
    tools.argparser.add_argument('--namefile',
                                 required=True,
                                 default='namefile.csv',
                                 help='CSV with the names/etc.')
    tools.argparser.add_argument('--signature',
                                 required=True,
                                 default='signature.html',
                                 help='Signature HTML file')
    tools.argparser.add_argument('--delegation-credential',
                                 required=True,
                                 help='Google domain-wide credential (see https://developers.google.com/admin-sdk/directory/v1/guides/delegation)')

    tools.argparser.add_argument('--verbose',
                                 required=False,
                                 action='store_true',
                                 default=True,
                                 help='If enabled, emit extra status messages during run')
    tools.argparser.add_argument('--debug',
                                 required=False,
                                 action='store_true',
                                 default=False,
                                 help='If enabled, emit even more extra status messages during run')

    args = tools.argparser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True

    # Sanity check that the specified files all exist
    for f in [args.namefile, args.signature, args.delegation_credential]:
        if not os.path.exists(f):
            print("File does not exist: {f}".format(f=f))
            exit(1)

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = add_cli_args()
    log  = Mercy.setup_logging(info=args.verbose,
                               debug=args.debug,
                               logfile=None)

    # Read in the signature file
    signature = read_sig(args)

    # Read in the names CSV
    names = read_names(args)

    # Set the signature for each row in the CSV
    for row in names:
        set_signature(row, signature, args, log)

    log.info("All done!")

if __name__ == "__main__":
    main()
