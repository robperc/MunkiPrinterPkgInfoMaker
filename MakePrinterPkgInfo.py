"""
Generates Munki no-pkg pkginfo for printer with specified settings.
Installcheck and postinstall scripts based on Walter Meyer's approach (found here: https://github.com/munki/munki/wiki/Managing-Printers-With-Munki)

"""

import argparse
import plistlib

installcheck_script = """#!/usr/bin/python      

import os
import plistlib
import subprocess
import sys

printername = \"PRINTER_NAME\"
location = \"LOCATION\"
gui_display_name = \"DESCRIPTION\"
address = \"URI\"
driver_ppd = \"PPD\"
currentVersion = VERSION

# Check if receipt is installed
receipt = "/private/etc/cups/deployment/receipts/%s.plist" % (printername)
if os.path.isfile(receipt):
    pl = plistlib.readPlist(receipt)
    storedVersion=float(pl.get("version"))
    print "Stored version: %f" % (storedVersion)
else:
    storedVersion = 0.0

# Printer Install
try:
    subprocess.check_call(["/usr/bin/lpstat", "-p", printername], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    installed = True
except:
    installed = False


if installed:
    if currentVersion <= storedVersion:
        sys.exit(1)

sys.exit(0)""".encode('ascii', 'xmlcharrefreplace')

postinstall_script = """#!/usr/bin/python

import os
import plistlib
import subprocess
import sys

printername = \"PRINTER_NAME\"
location = \"LOCATION\"
gui_display_name = \"DESCRIPTION\"
address = \"URI\"
driver_ppd = \"PPD\"
currentVersion = VERSION
add_opts = \"ADD_OPTS\"

# If driver ppd doesnt exist then fail install
if not os.path.isfile(driver_ppd):
    print "%s doesnt exist!" % (driver_ppd)
    sys.exit(1)

# Check if printer is installed via receipt.
receipt = "/private/etc/cups/deployment/receipts/%s.plist" % (printername)
if os.path.isfile(receipt):
    pl = plistlib.readPlist(receipt)
    storedVersion=float(pl.get("version"))
    print "Stored version: %f" % (storedVersion)
else:
    storedVersion = 0.0

# Check if a version of the printer is already installed.
try:
    subprocess.check_call(["/usr/bin/lpstat", "-p", printername], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    installed = True
except:
    installed = False

# Uninstall if older version installed.
if installed:
    subprocess.call(["/usr/sbin/lpadmin", "-x", printername])

lp_args = ["/usr/sbin/lpadmin", "-p", printername, 
           "-L", location,
           "-D", gui_display_name,
           "-v", address,
           "-P", driver_ppd,
           "-E",
           "-o", "printer-is-shared=PUBLISH",
           "-o", "printer-error-policy=abort-job"]

# Add additional options
for opt in add_opts.split():
    lp_args += ["-o", opt]

try:
    subprocess.check_call(lp_args)
except:
    sys.exit(1)

# Enable and start the printer
subprocess.call(["/usr/sbin/cupsenable", printername])

# Create a receipt for the printer
receipt_dir = "/private/etc/cups/deployment/receipts"
receipt = "%s/%s" % (receipt_dir, printername)
subprocess.call(["/bin/mkdir", "-p", receipt_dir])
contents = dict(version=currentVersion,)
plistlib.writePlist(contents, receipt)

# Permission the directories properly.
subprocess.call(["chown", "-R", "root:_lp", "/private/etc/cups/deployment"])
subprocess.call(["chmod", "-R", "700", "/private/etc/cups/deployment"])

sys.exit(0)""".encode('ascii', 'xmlcharrefreplace')

uninstall_script = """#!/bin/sh
printerName=\"PRINTER_NAME\"
/usr/sbin/lpadmin -x $printerName
rm -f /private/etc/cups/deployment/receipts/$printerName.plist""".encode('ascii', 'xmlcharrefreplace')

def genPlist():
    contents = dict(
        autoremove=False,
        catalogs=list(("testing",)),
        description="",
        display_name="",
        installcheck_script="",
        installer_type="nopkg",
        minimum_os_version="10.7.0",
        name="",
        postinstall_script="",
        unattended_install=True,
        uninstall_method="uninstall_script",
        uninstall_script="",
        uninstallable=True,
        version="",
    )
    return contents

def main():
    parser = argparse.ArgumentParser(description='Command line tool to generate nopkg Munki packages for lpadmin printer installation.')
    parser.add_argument('--name', metavar='SomePrinter', type=str, nargs=1, required=True,
        help='Name of printer to add.',
    )
    parser.add_argument('--description', metavar='"Just Some Printer"', type=str, nargs=1, required=True,
        help='Short description of role that printer fills',
    )
    parser.add_argument('--location', metavar='"On Desk"', type=str, nargs=1, required=True,
        help='Short description of location of printer',
    )
    parser.add_argument('--publish', action="store_true", 
        help='Whether to publish printer.',
    )
    parser.add_argument('--uri', metavar='lpd://x.x.x.x', type=str, nargs=1, required=True,
        help='URI for printer.',
    )
    parser.add_argument('--ppd', metavar='/Library/Printers/PPDs/Contents/Resources/...', type=str, nargs=1, required=True,
        help='Path to PPD for printer.',
    )
    parser.add_argument('--version', metavar='x.x', type=float, nargs=1, required=True,
        help='Version for pkginfo.',
    )
    parser.add_argument('--options', metavar='opt1=foo opt2=bar', type=str, nargs='+', 
        help='String of additional options to configure printer with',
    )
    parser.add_argument('--catalogs', metavar='catalog_name', type=str, nargs='+', 
        help='Additional catalogs to add to catalogs array for pkginfo. "testing" is always added by default."',
    )
    args = parser.parse_args()
    if args.publish:
        publish = True
    else:
        publish = False
    if args.options:
        opts = " ".join(args.options)
    contents = genPlist()
    mappings = dict(
        PRINTER_NAME=args.name[0],
        LOCATION=args.location[0],
        DESCRIPTION=args.description[0],
        PUBLISH=str(publish).lower(),
        URI=args.uri[0],
        PPD=args.ppd[0],
        VERSION=str(args.version[0]),
        ADD_OPTS=opts,
    )
    installcheck = installcheck_script
    postinstall  = postinstall_script
    uninstall    = uninstall_script
    for key, value in mappings.iteritems():
        print "%s: %s" % (key, value)
        installcheck = installcheck.replace(key, value)
        postinstall = postinstall.replace(key, value)
        uninstall = uninstall.replace(key, value)
    if args.catalogs:
        contents["catalogs"] += args.catalogs
    contents["description"]  = "Installer for " + args.description[0]
    contents["display_name"] = args.description[0]
    contents["installcheck_script"] = installcheck
    contents["postinstall_script"] = postinstall
    contents["uninstall_script"] = uninstall
    contents["name"] = args.name[0]
    contents["version"] = args.version[0]
    pkginfo = args.name[0] + ".pkginfo"
    plistlib.writePlist(contents, pkginfo)

if __name__ == "__main__":
    main()