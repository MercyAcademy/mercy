# Meraki device naming script

This is a trivial script to read a JAMF export file and set a bunch of
names in the Meraki dashboard.  It's not clever at all, and it relies
on you hard-coding some values (e.g., the Meraki API key, the filename
you want to read, whether it's a JAMF Pro or JAMF School file, etc.).

## Meraki Python API

The Meraki API documentation is available here:
https://developer.cisco.com/meraki/api-v1/#!overview

The Meraki APIs are available in several different forms, to include a
Python library.

For any given API (e.g., for the `provisionNetworkClients` API --
documented under Endpoints --> API --> General --> networks -->
configure --> clients --> Provision Network Clients:
https://developer.cisco.com/meraki/api-v1/#!provision-network-clients):

1. Click on the `Template` tab in the right hand pane.
1. Click on the `Meraki Python Library` tab in the sub pane.

This will show you an example of how to use the Python version of that
Meraki API.

## Initial setup

### MacOS

If running on a Mac, it is advisable to install Homebrew from
https://brew.sh

Once you have Homebrew installed, run the XCode setup (you only need
to do this once) in a Terminal window:

```
$ xcode-select --install
```

This will take several minutes to download and install.

Once that has completed, run this in a Terminal window:

```
$ brew install python3
```

### Linux setup

On Linux, you need to ensure that Python v3.x and `pip` (or `pip3`) is
available.  There are many different ways to do this in Linux, and it
very much depends on which specific Linux distro you are using, so I'm
not going to try to document all the different ways here.

### Python setup

Once you have MacOS or Linux setup, you need to setup Python.

**NOTE:** Most Python developers would use what's called a "virtual
environment" to install a Python library and/or run their Python
application.  For the sake of simplicity here, we're *not* going to
use a Python virtual environment.

You need to install the `meraki` Python library.  In a Terminal:

```
$ pip3 install meraki
```

That should be all that is necessary.

## Meraki API key

1. Login to the Meraki Dashboard
1. Click on your ID in the top right
1. Select "My profile"
1. Scroll down to the "API access" section
1. Generate an API key
1. Copy-n-paste the API key somewhere safe

## Preparing the script

As noted above, the script is pretty stupid.  In the interest of
simplicity (because I'm anticipating that you'll want to edit this
script to make it do other things someday), it doesn't even accept any
command line parameters.

Instead, just edit `magic.py` in a text editor (e.g., `TextEdit` on
Mac -- *not* MS Word!).  If you really care, you might want to get a
code-friendly text editor, such as https://atom.io/.

Open up `magic.py` in the text editor and edit the following:

* Paste the Meraki key into the `api_key` string variable value at the
  top of the file.
  * Note: Python strings are enclosed in either double quotes or
    single quotes.
* Edit the `jamf_export_filename` to be the name of the file you want
  to read.
* Set `jamf_export_is_jamf_school` to `True` if the export file is
  from JAMF School, or to `False` if the export file is from JAMF Pro.
* Set `meraki_org_name` to be the exact string name of the Meraki
  organization name we need to find.
* Set `meraki_network_name` to be the exact string name of the Meraki
  network name (in the target Meraki org) we need to find.
* Set `meraki_policy_name` to be the exact string name of the Meraki
  client policy that you want to set on each device.

## Running the script

You should be able to run the script in a Terminal window via:

```
$ cd DIRECTORY_WHERE_THE_SCRIPT_LIVES
$ python3 ./magic.py
```
