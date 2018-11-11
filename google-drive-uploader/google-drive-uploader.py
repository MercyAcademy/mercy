#!/usr/bin/env python3

"""Script to upload specific files to Google Drive.

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

-----

This script requires a "client_id.json" file with the app credentials
from the Google App dashboard.  This file is not committed here in git
for obvious reasons (!).

This script will create a "user-credentials.json" file in the same
directory with the result of getting user consent for the Google
Account being used to authenticate.

Note that this script works on Windows, Linux, and OS X.  But first,
you need to install some Python classes (if you can find them in your
native package manager, so much the better):

    pip3 install --upgrade [--user] google-api-python-client
    pip3 install --upgrade [--user] httplib2

Regarding Google Drive / Google Python API documentation:

1. In terms of authentication, this is very helpful to read:

    https://developers.google.com/identity/protocols/OAuth2

This script is using the "Installed Applications" scheme.

2. In terms of the Google Python docs, this is very helpful to read:

    https://developers.google.com/api-client-library/python/start/get_started

We are using Authorized API access (OAuth 2.0).

Steps:

2a. Request a(n application) token
2b. Provider user consent
2c. Get an authorization code from Google
2d. Send the code to Google
2e. Receive access token and refresh token
2f. Can make API calls with the access token
2g. If the access token is expired, use the refresh token.  If the
    refresh token doesn't work, go back to step 2 (or step 1?).

"""

import json
import os
import time
import httplib2
import logging
import logging.handlers
import traceback
import mimetypes

from pprint import pprint

from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
guser_cred_file = 'user-credentials.json'
guser_agent = 'py_uploader'
gauth_grace_period = 60
gauth_max_attempts = 3
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
gscope = 'https://www.googleapis.com/auth/drive'

folder_mime_type = 'application/vnd.google-apps.folder'

####################################################################
#
# Google Team Drive functions
#
####################################################################

def gd_load_app_credentials(app_id_file, log):
    # Read in the JSON file to get the client ID and client secret
    if not os.path.isfile(app_id_file):
        diediedie("Error: JSON file {0} does not exist"
                  .format(app_id_file))
    if not os.access(app_id_file, os.R_OK):
        diediedie("Error: JSON file {0} is not readable"
                  .format(app_id_file))

    with open(app_id_file) as data_file:
        app_cred = json.load(data_file)

    log.debug('Loaded application credentials from {0}'
              .format(app_id_file))
    return app_cred

#-------------------------------------------------------------------

def gd_load_user_credentials(scope, app_cred, user_cred_filename, log):
    # Get user consent
    client_id       = app_cred['installed']['client_id']
    client_secret   = app_cred['installed']['client_secret']
    flow            = OAuth2WebServerFlow(client_id, client_secret, scope)
    flow.user_agent = guser_agent

    storage   = Storage(user_cred_filename)
    user_cred = storage.get()

    # If no credentials are able to be loaded, fire up a web
    # browser to get a user login, etc.  Then save those
    # credentials in the file listed above so that next time we
    # run, those credentials are available.
    if user_cred is None or user_cred.invalid:
        user_cred = tools.run_flow(flow, storage,
                                        tools.argparser.parse_args())

    log.debug('Loaded user credentials from {0}'
                  .format(user_cred_filename))
    return user_cred

#-------------------------------------------------------------------

def gd_authorize(user_cred, log):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    log.debug('Authorized to Google')
    return service

#-------------------------------------------------------------------

def gd_login(args, log):
    # Put a loop around this so that it can re-authenticate via the
    # OAuth refresh token when possible.  Real errors will cause the
    # script to abort, which will notify a human to fix whatever the
    # problem was.
    auth_count = 0
    while auth_count < gauth_max_attempts:
        try:
            # Authorize the app and provide user consent to Google
            log.debug("Authenticating to Google...")
            app_cred  = gd_load_app_credentials(args.app_id, log)
            user_cred = gd_load_user_credentials(gscope, app_cred,
                                                 args.user_credentials, log)
            service   = gd_authorize(user_cred, log)
            log.info("Authenticated to Google")
            break

        except AccessTokenRefreshError:
            # The AccessTokenRefreshError exception is raised if the
            # credentials have been revoked by the user or they have
            # expired.
            log.error("Failed to authenticate to Google (will sleep and try again)")

            # Delay a little and try to authenticate again
            time.sleep(10)

        auth_count = auth_count + 1

    if auth_count > gauth_max_attempts:
        log.error("Failed to authenticate to Google {0} times.\nA human needs to figure this out."
                  .format(gauth_max_attempts))

    return service

#===================================================================

def gd_find_folder(service, folder_id, log):
    # See if this folder ID exists (and is a folder)
    try:
        response = (service.files()
                    .get(fileId=folder_id,
                         supportsTeamDrives=True).execute())
    except:
        log.error("Failed to find Google Drive ID {f}".format(f=folder_id))
        exit(1)

    log.debug("Validated Google Drive destination ID exists: {id}"
              .format(id=folder_id))

    mime = response.get('mimeType', [])
    if not mime:
        log.error("Failed to verify that Google Drive ID is a folder")
        exit(1)

    if mime != folder_mime_type:
        log.error("Destination Google Drive ID is not a folder")
        log.error("It's actually: {m}".format(m=mime))
        exit(1)

    log.debug("Validated Google Drive destination ID is a folder")

    return response

#===================================================================

def gd_upload_file(service, dest_folder, upload_filename, log):
    basename = os.path.basename(upload_filename)
    mime     = mimetypes.guess_type('file://{f}'
                                    .format(f=upload_filename))
    if mime == (None, None):
        mime = 'application/x-sqlite3'
        log.debug('Got no mime type: assume {m}'.format(m=mime))

    log.debug('Uploading file "{base}" (Google Drive folder ID: {folder}, MIME type {m})'
              .format(base=basename,
                      folder=dest_folder['id'],
                      m=mime))
    metadata = {
        'name'     : basename,
        'mimeType' : mime,
        'parents'  : [ dest_folder['id'] ]
    }
    media = MediaFileUpload(upload_filename,
                            mimetype=mime,
                            resumable=True)
    file = service.files().create(body=metadata,
                                  media_body=media,
                                  supportsTeamDrives=True,
                                  fields='name,id,webContentLink,webViewLink').execute()
    log.debug('Successfully uploaded file: "{f}" --> Google Drive file ID {id}'
              .format(f=basename, id=file['id']))

####################################################################
#
# Setup functions
#
####################################################################

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
        level="DEBUG"
    elif args.verbose:
        level="INFO"

    log = logging.getLogger('mp3')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    return log

#-------------------------------------------------------------------

def add_cli_args():
    tools.argparser.add_argument('--app-id',
                                 default='client_id.json',
                                 help='Filename containing Google application credentials')
    tools.argparser.add_argument('--user-credentials',
                                 default='user-credentials.json',
                                 help='Filename containing Google user credentials')

    tools.argparser.add_argument('files',
                                 metavar='file',
                                 nargs='+',
                                 help='File (or files) to upload to Google Drive')

    tools.argparser.add_argument('--dest',
                                 required=True,
                                 help='ID of target Google Folder')

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
    log = setup_logging(args)

    # Sanity check that the specified files all exist
    for f in args.files:
        if not os.path.exists(f):
            log.error("File does not exist: {f}".format(f=f))
            exit(1)

    return log, args

####################################################################
#
# Main
#
####################################################################

def main():
    log, args   = add_cli_args()
    service     = gd_login(args, log)
    dest_folder = gd_find_folder(service, args.dest, log)

    for f in args.files:
        log.info("Uploading file: {f}".format(f=f))
        gd_upload_file(service, dest_folder, f, log)

    log.info("Finished uploading files")

if __name__ == '__main__':
    main()
