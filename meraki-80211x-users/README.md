# Meraki wifi user scripts

There are two scripts in this directory:

1. Bulk create Meraki users.

   * **NOTE:** The script will error if it tries to create a user that
     already exists.

1. Renew the guest account user.

Both are described below.

# Installing

## Python installation

First, install a modern version of Python.  As of this writing (May
2024), the Meraki Python API requires Python 3.10 or later.

* On a Windows machine, go to https://python.org and download + install
  the latest version.
  * Ensure to select the option to put Python in the default PATH.
* On a Mac, use https://brew.sh to install the latest Python (e.g.,
  `brew install python@3.12`).
* On Linux, use the package manager to install a recent Python.

## Virtual environment

You will almost certainly want to run these scripts in a Python
Virtual Environment.  Run the following to create the Python virtual
environment to create a Python Virtual Environment named `sandbox`:

```
# On Windows:
python3 -m venv sandbox

# On Mac and Linux (update for your specific version of Python):
python3.12 -m venv sandbox
```

On Mac and Linux, activate the virtual sandbox:

```
. ./sandbox/bin/activate
```

**Note:** We didn't need to run this on Windows, so I didn't research
how to activate Python virtual environments on Windows.

## Python dependent packages

After activating the virtual environment, the first time you run, you
need to install the Python dependent packages.  Run this command with
the `requirements.txt` file from this git repo:

```
pip install -r requirements.txt
```

## Run the renew script

The first time you get the file, on Mac and Linux, you probably want
to make the script be executable (you only need to do this once):

```
chmod +x meraki-renew-user.py
```

After activating the virtual environment, you can run the renew
script:

```
python3 ./meraki-renew-user.py --api-key YOUR_MERAKI_API_KEY
```

By default, this will:

* Login to the Mercy Meraki Dashboard
* Find the Meraki organization named "Mercy Academy"
* Find the Meraki network named "Mercy"
* Find the Meraki SSID named "Mercy Guest"
* Find the account email with "mercyguest@mercyjaguars.com"
* Reset the password to something new, which will trigger an email to
  that email address containing the new password

You can override any of these defaults on the command line, run the
following command to see all the command line options that are
available:

```
python3 ./meraki-renew-user.py --help
```

# Linux cron job

In Linux, you can set this script to run regularly by setting up a
cron job.  It's convenient to have cron launch a script that activates
the Python virtual environment and then launches the Python script.

The file `cron-run.sh` in this directory can be used for this purpose.
For example, if you use `crontab -e` to edit your crontab file to the
following:

```
0 5 * * 1 /opt/meraki/cron-run.sh 2>/dev/null
```

Assuming that you have put all the files in the `/opt/meraki` folder,
the above crontab will invoke the `cron-run.sh` script every Monday at
5am.  Run the command `man 5 crontab` to see the format of the crontab
file.

The `cron-run.sh` script assumes the following:

1. There is a Python virtual environment directory named `sandbox` in
   the folder.
1. There is a text file named `api-key.txt` that contains a single
   line: the Meraki API key.

(you may need to `chmod +x /opt/meraki/cron-run.sh`)

# MacOS cron job

The MacOS cron job details are the same as the Linux cron job details,
with the one exception that you *must* run the cron job somewhere
outside of any user's home directory (e.g., `/opt/meraki` might be a
good choice).

# Windows Scheduler file

**Note:** We didn't need to run this on Windows, so we didn't
investigate the particulars of how to run this on Windows.
