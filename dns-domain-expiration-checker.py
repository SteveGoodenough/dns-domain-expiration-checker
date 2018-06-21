#!/usr/bin/env python3
# Program: DNS Domain Expiration Checker
# Author: Matty < matty91 at gmail dot com >
# Current Version: 7.0
# Date: 08-02-2017
# License:
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.

import sys
import time
import argparse
import smtplib
import dateutil.parser
import subprocess
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EXPIRE_STRINGS = [ "Expiry date:",
                   "Registry Expiry Date:",
                   "Expiration:",
                   "Domain Expiration Date",
                   "Registrar Registration Expiration Date:"
                 ]

REGISTRAR_STRINGS = [
                      "Registrar:"
                    ]
DEBUG = 0


def debug(string_to_print):
    """
       Helper function to assist with printing debug messages.
    """
    if DEBUG:
        print(string_to_print)


def print_heading():
    """
       Print a formatted heading when called interactively
    """
    print("%-25s  %-20s  %-30s  %-4s" % ("Domain Name", "Registrar",
          "Expiration Date", "Days Left"))


def print_domain(domain, registrar, expiration_date, days_remaining):
    """
       Pretty print the domain information on stdout
    """
    print("%-25s  %-20s  %-30s  %-d" % (domain, registrar,
          expiration_date, days_remaining))


def make_whois_query(domain):
    """
       Execute whois and parse the data to extract specific data
    """
    debug("Sending a WHOIS query for the domain %s" % domain)
    try:
        p = subprocess.Popen(['whois', domain],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:
        print("Unable to Popen() the whois binary. Exception %s" % e)
        sys.exit(1)

    try:
        whois_data = p.communicate()[0].decode('ascii')
    except Exception as e:
        print("Unable to read from the Popen pipe. Exception %s" % e)
        sys.exit(1)

    # TODO: Work around whois issue #55 which returns a non-zero
    # exit code for valid domains.
    # if p.returncode != 0:
    #    print("The WHOIS utility exit()'ed with a non-zero return code")
    #    sys.exit(1)

    return(parse_whois_data(whois_data))


def parse_whois_data(whois_data):
    """
       Grab the registrar and expiration date from the WHOIS data
    """
    debug("Parsing the whois data blob %s" % whois_data)
    expiration_date = "00/00/00 00:00:00"
    registrar = "Unknown"
    registrar_is_next = False
    found_parts = 0

    for line in whois_data.splitlines():
        if registrar_is_next:
            registrar = line.strip()
            found_parts += 1
            registrar_is_next = False

        if any(expire_string in line for expire_string in EXPIRE_STRINGS):
            expiration_date = dateutil.parser.parse(line.partition(": ")[2], ignoretz=True)
            found_parts += 1

        if any(registrar_string in line for registrar_string in
               REGISTRAR_STRINGS):
            registrar = line.split("Registrar:")[1].strip()
            registrar_is_next = (len(registrar) == 0)
            if not registrar_is_next: found_parts += 1

        if (found_parts==2) : break

    return expiration_date, registrar


def calculate_expiration_days(expire_days, expiration_date):
    """
       Check to see when a domain will expire
    """
    debug("Expiration date %s Time now %s" % (expiration_date, datetime.now()))

    try:
        domain_expire = expiration_date - datetime.now()
    except:
        print("Unable to calculate the expiration days")
        sys.exit(1)

    # if domain_expire.days < int(expire_days):
    #    return domain_expire.days
    # else:
    #     return 0
    return domain_expire.days


def check_expired(expiration_days, days_remaining):
    """
       Check to see if a domain has passed the expiration
       day threshold. If so send out notifications
    """
    if int(days_remaining) < int(expiration_days):
        return days_remaining
    else:
        return 0


def domain_expire_notify(domain, config_options, days):
    """
       Functions to call when a domain is about to expire. Adding support
       for Nagios, SNMP, etc. can be done by defining a new function and
       calling it here.
    """
    debug("Triggering notifications for the DNS domain %s" % domain)

    # Send outbound e-mail if a rcpt is passed in
    if config_options["email"]:
        send_expire_email(domain, days, config_options)


def send_expire_email(domain, days, config_options):
    """
       Generate an e-mail to let someone know a domain is about to expire
    """
    debug("Generating an e-mail to %s for domain %s" %
         (config_options["smtpto"], domain))
    msg = MIMEMultipart()
    msg['From'] = config_options["smtpfrom"]
    msg['To'] = config_options["smtpto"]
    msg['Subject'] = "The DNS Domain %s is set to expire in %d days" % (domain, days)

    body = "Time to renew %s" % domain
    msg.attach(MIMEText(body, 'plain'))

    smtp_connection = smtplib.SMTP(config_options["smtpserver"],config_options["smtpport"])
    message = msg.as_string()
    smtp_connection.sendmail(config_options["smtpfrom"], config_options["smtpto"], message)
    smtp_connection.quit()


def processcli():
    """
        parses the CLI arguments and returns a domain or
        a file with a list of domains.
    """
    parser = argparse.ArgumentParser(description='DNS Statistics Processor')

    parser.add_argument('--domainfile', help="Path to file with list of domains and expiration intervals.")
    parser.add_argument('--domainname', help="Domain to check expiration on.")
    parser.add_argument('--email', action="store_true", help="Enable debugging output.")
    parser.add_argument('--format', default="text", help="Format for input (domainfile) and output. Text (default) or Json.")
    parser.add_argument('--interactive',action="store_true", help="Enable debugging output.")
    parser.add_argument('--expiredays', default=10000, type=int, help="Expiration threshold to check against.")
    parser.add_argument('--sleeptime', default=1, type=int, help="Time to sleep between whois queries.")
    parser.add_argument('--smtpserver', default="localhost", help="SMTP server to use.")
    parser.add_argument('--smtpport', default=25, help="SMTP port to connect to.")
    parser.add_argument('--smtpto', default="root", help="SMTP To: address.")
    parser.add_argument('--smtpfrom', default="root", help="SMTP From: address.")

    # Return a dict() with all of the arguments passed in
    return(vars(parser.parse_args()))


def main():
    """
        Main loop
    """
    days_remaining = 0
    conf_options = processcli()

    JSON = (conf_options["format"].upper() == "JSON")

    if (conf_options["interactive"] and not JSON):
        print_heading()


    if ( conf_options["domainfile"]):
        if JSON:
            debug("Format in JSON")
            domain_result = []
            with open(conf_options["domainfile"], "r") as domains_to_process:
                domains = json.load(domains_to_process)
                for domain in domains["domains"]:
                    try:
                        domainname = domain.get("domain")
                        expiration_days = domain.get("expiration")
                    except Exception as e:
                        print("Unable to parse json configuration file.")
                        sys.exit(1)

                    expiration_date, registrar = make_whois_query(domainname)
                    days_remaining = calculate_expiration_days(expiration_days, expiration_date)

                    alert_level = "Ok"

                    if check_expired(expiration_days, days_remaining):
                        domain_expire_notify(domainname, conf_options, days_remaining)
                        alert_level = "Warning"

                    if (days_remaining <= 0): alert_level = "Error"

                    domain_result.append({"domain": domainname,"registrar":registrar,"days_remaining":days_remaining,"status":alert_level})
                    
                    # Need to wait between queries to avoid triggering DOS measures like so:
                    # Your IP has been restricted due to excessive access, please wait a bit
                    time.sleep(conf_options["sleeptime"])

                with open("./domainresult.json", 'w') as f:
                    json.dump(domain_result, f)

                if conf_options["interactive"]:
                    print(json.dumps(domain_result))

        else:

            debug("Format in Text")
            with open(conf_options["domainfile"], "r") as domains_to_process:
                for line in domains_to_process:
                    try:
                        domainname, expiration_days = line.split()
                    except Exception as e:
                        print("Unable to parse configuration file. Problem line \"%s\"" % line.strip())
                        sys.exit(1)

                    expiration_date, registrar = make_whois_query(domainname)
                    days_remaining = calculate_expiration_days(expiration_days, expiration_date)

                    if check_expired(expiration_days, days_remaining):
                        domain_expire_notify(domainname, conf_options, days_remaining)

                    if conf_options["interactive"]:
                        print_domain(domainname, registrar, expiration_date, days_remaining)

                    # Need to wait between queries to avoid triggering DOS measures like so:
                    # Your IP has been restricted due to excessive access, please wait a bit
                    time.sleep(conf_options["sleeptime"])
    elif conf_options["domainname"]:
        expiration_date, registrar = make_whois_query(conf_options["domainname"])
        days_remaining = calculate_expiration_days(conf_options["expiredays"], expiration_date)

        if check_expired(conf_options["expiredays"], days_remaining):
            domain_expire_notify(conf_options["domainname"], conf_options, days_remaining)

        if conf_options["interactive"]:
            print_domain(conf_options["domainname"], registrar, expiration_date, days_remaining)

        # Need to wait between queries to avoid triggering DOS measures like so:
        # Your IP has been restricted due to excessive access, please wait a bit
        #time.sleep(conf_options["sleeptime"])
        # only 1 domain this way so why wait
 

if __name__ == "__main__":
    main()
