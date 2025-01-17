#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Untitled Goose Tool: MessageTrace!
This module performs data collection of a message trace from a M365 environment.
"""

import argparse
import configparser
import json
import os
import pathlib
import requests
import sys
import time

from datetime import datetime, timedelta
from goosey.utils import *
from random import randint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep

MSGTRC_HELP = '''Untitled Goose Tool: Message Trace

To get started, use one of the subcommands.

1. Authenticate
goosey messagetrace --auth

2. Submit a message trace request
goosey messagetrace --submit-report

3. Check on a message trace request
goosey messagetrace --status-check

4a. Gather the completed report (requires user to be present for MFA check)
goosey messagetrace --gather-report
'''

__author__ = "Claire Casalnova, Jordan Eberst, Wellington Lee, Victoria Wallace"
__version__ = "1.0.0"

logger = None

class MessageTrace():

    def __init__(self, logger, output_dir, args, config, auth):
        self.output_dir = output_dir
        self.logger = logger
        self.config = config
        self.auth = auth
        self.msgfile = f'{self.output_dir}{os.path.sep}.msgtrace_info'
        self.jobid = None
        self.headless = False
    
    def parse_config(self, configfile):

        config = configparser.ConfigParser()
        config.read(configfile)

        self.username = config_get(config, 'auth', 'username', self.logger)
        self.password = config_get(config, 'auth', 'password', self.logger)
        self.setemailaddress = config_get(config, 'msgtrc', 'setemailaddress', self.logger)
        if config_get(config, 'msgtrc', 'direction', self.logger):
            self.direction = config_get(config, 'msgtrc', 'direction', self.logger)
        if config_get(config, 'msgtrc', 'messageid', self.logger):
            msgidlist = list()
            msgidlist.append(config_get(config, 'msgtrc', 'messageid', self.logger))
            self.messageid = msgidlist
        else:
            self.messageid = []
        if self.setemailaddress == 'True':
            self.logger.debug('setemailaddress is set to True')
            if config_get(config, 'msgtrc', 'notifyaddress', self.logger):
                notifylist = list()
                notifylist.append(config_get(config, 'msgtrc', 'notifyaddress', self.logger))
                self.notifyaddress = notifylist
            else:
                self.logger.warning('You need to specify a notification address!')
                sys.exit(1)
        else:
            self.logger.debug('Not going to set a notification address.')
            self.notifyaddress = ''
        if config_get(config, 'msgtrc', 'originalclientip', self.logger):
            self.originalclientip = config_get(config, 'msgtrc', 'originalclientip', self.logger)
        else:
            self.originalclientip = ""
        if config_get(config, 'msgtrc', 'recipientaddress', self.logger):
            recipientlist = list()
            recipientlist.append(config_get(config, 'msgtrc', 'recipientaddress', self.logger))
            self.recipientaddress = recipientlist
        else:
            self.recipientaddress = []
        if config_get(config, 'msgtrc', 'reporttitle', self.logger):
            self.reporttitle = config_get(config, 'msgtrc', 'reporttitle', self.logger)
        if config_get(config, 'msgtrc', 'reporttype', self.logger):
            self.reporttype = config_get(config, 'msgtrc', 'reporttype', self.logger)
        if config_get(config, 'msgtrc', 'senderaddress', self.logger):
            senderlist = list()
            senderlist.append(config_get(config, 'msgtrc', 'senderaddress', self.logger))
            self.senderaddress = senderlist
        else:
            self.senderaddress = []
        return config

    def request_msgtrace(self, args):

        date_90_days_ago = '%sT00:00:00.000Z' % ((datetime.now() - timedelta(days=89)).strftime("%Y-%m-%d"))
        date_now = '%sT00:00:00.000Z' % (datetime.now().strftime("%Y-%m-%d"))
        datetime_now = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        
        self.parse_config(args.config)

        ReportName = self.reporttitle + '_' + datetime_now
        ReportName = ReportName.replace('"', '')

        params = {
            'DeliveryStatus': "",
            'Direction': self.direction,
            'EndDate': date_now,
            'MessageID': self.messageid,
            'OriginalClientIP': self.originalclientip,
            'RecipientAddress': self.recipientaddress,
            'ReportTitle': ReportName,
            'ReportType': self.reporttype,
            'SenderAddress': self.senderaddress,
            'StartDate': date_90_days_ago
        }

        if self.setemailaddress == 'True':
            addparams = {'NotifyAddress': self.notifyaddress}
            params.update(addparams)

        parameters = json.dumps(params)
        self.logger.debug(f'Specified parameters are: {params}')
        headers = {
        'authority': 'admin.exchange.microsoft.com',
        'Cookie': '.AspNet.Cookies=' + self.auth['.AspNet.Cookies'],
        'Content-Type': 'application/json',
        'validationkey': self.auth['validationkey']
        }

        url = "https://admin.exchange.microsoft.com/beta/HistoricalSearch"

        self.logger.info('Submitting historical message trace report request...')

        response = requests.request("POST", url, headers=headers, data=parameters)

        data = response.json()
        self.logger.debug(f'Response from server: {data}')
        
        try:
            self.jobid = data['JobId']
        except Exception as e:
            self.logger.debug(f'Error with response: {str(e)}')
            sys.exit(1)

        with open(self.msgfile, 'w') as f:
            f.write(self.jobid + "\n")       

        self.logger.debug('Message trace report job id: %s' % (self.jobid))
        self.logger.info('Successfully submitted message trace report!')
        
    def check_status(self, args):

        if os.path.isfile(self.msgfile):
            with open(self.msgfile, "r") as f:
                self.jobid = f.readline().strip()

        if not self.jobid:
            logger.warning("No job id found in the .msgtrace_info file. Please make sure to either put the job id in the .msgtrace_info file or submit a message trace report request first.")
            sys.exit(1)            

        self.logger.debug('Job id to check: %s' % (self.jobid))

        url = "https://admin.exchange.microsoft.com/beta/HistoricalSearch?$filter=ReportType eq 'MessageTrace' or ReportType eq 'MessageTraceDetail'"
        headers = {
        'authority': 'admin.exchange.microsoft.com',
        'Cookie': '.AspNet.Cookies=' + self.auth['.AspNet.Cookies'],
        'Content-Type': 'application/json',
        'validationkey': self.auth['validationkey']
        }
        response = requests.request("GET", url, headers=headers)
        data = response.json()
        responseValue = data["value"]

        msgrpt = search_results(responseValue, self.jobid)
        statusOfRequest = msgrpt.get("Status")
        
        while statusOfRequest != "Done":
            self.logger.debug('Report status: %s' % (statusOfRequest))
            sleep_time = randint(700,1000)
            self.logger.info("Sleeping for {} seconds...".format(sleep_time))
            sleep(sleep_time)
            self.logger.info("Waking up, checking report status...")
            response = requests.request("GET", url, headers=headers)
            data = response.json()
            responseValue = data["value"]
            msgrpt = search_results(responseValue, self.jobid)
            statusOfRequest = msgrpt.get("Status")
            
        self.logger.info("Report status: %s" %(statusOfRequest))
        self.logger.info("Report is ready to be downloaded.")

    def gather_results(self, args):

        if os.path.isfile(self.msgfile):
            with open(self.msgfile, "r") as f:
                self.jobid = f.readline().strip()

        self.parse_config(args.config)

        EMAILFIELD = (By.ID, "i0116")
        PASSWORDFIELD = (By.ID, "i0118")
        NEXTBUTTON = (By.ID, "idSIButton9")
        browser = None
        result = False

        dldir = pathlib.Path(f'{args.output_dir}{os.path.sep}msgtrc').absolute()
        dldir = str(dldir)

        ffprofile = webdriver.FirefoxProfile()
        opts = webdriver.FirefoxOptions()

        ffprofile.set_preference("browser.preferences.instantApply", True)
        ffprofile.set_preference("browser.download.folderList",2)
        ffprofile.set_preference("browser.download.manager.showWhenStarting", False)
        ffprofile.set_preference("browser.helperApps.alwaysAsk.force", False)
        ffprofile.set_preference("browser.download.dir", dldir)
        ffprofile.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/plain, text/html, application/xhtml+xml, application/xml")

        opts.add_argument("--headless")

        browser = webdriver.Firefox(firefox_profile=ffprofile,options=opts)

        try:
            if browser:
                browser.get("https://login.windows.net")

                WebDriverWait(browser, 10).until(EC.element_to_be_clickable(EMAILFIELD)).send_keys(self.username)
                # Click Next
                WebDriverWait(browser, 10).until(EC.element_to_be_clickable(NEXTBUTTON)).click()
                # find password input field and insert password as well
                WebDriverWait(browser, 10).until(EC.element_to_be_clickable(PASSWORDFIELD)).send_keys(self.password)
                # Click Login 
                WebDriverWait(browser, 10).until(EC.element_to_be_clickable(NEXTBUTTON)).click()
                # Stay signed in
                try:
                    WebDriverWait(browser, 20).until(EC.element_to_be_clickable(NEXTBUTTON)).click()
                except Exception as e:
                    pass
                
                url = "https://admin.protection.outlook.com/ExtendedReport/Download?Type=OnDemandReport&RequestID=" + self.jobid

                browser.get(url)
                isFileDownloaded = False

                while not isFileDownloaded:
                    self.logger.info("Sleeping for 2 minutes...")
                    sleep(120)
                    for filename in os.listdir(dldir):
                        if self.jobid in filename:
                            browser.close()
                            isFileDownloaded = True
                    self.logger.info("Attempting to download file again...")
                    browser.get(url)

                result = True
            else:
                result = False
        except Exception as e:
            result = False

        if browser:
            try:
                browser.quit()
            except Exception as e:
                pass

        return result
    
def getargs(msgtrace_parser) -> None:
    msgtrace_parser.add_argument('--debug',
                                action='store_true',
                                help='Debug output',
                                default=False)
    msgtrace_parser.add_argument('-c',
                                '--config',
                                action='store',
                                help='Path to config file',
                                default='.conf')
    msgtrace_parser.add_argument('-a',
                                '--authfile',
                                action='store',
                                help='File to read credentials from obtained by goosey auth',
                                default='.ugt_auth')
    msgtrace_parser.add_argument('--output-dir',
                                action='store',
                                help='Output directory for output files',
                                default='output')                
    msgtrace_parser.add_argument('--submit-report',
                                action='store_true',
                                help='Submits a message trace report',
                                default=False)
    msgtrace_parser.add_argument('--gather-report',
                                action='store_true',
                                help='Gathers a message trace report',
                                default=False)                               
    msgtrace_parser.add_argument('--status-check',
                                action='store_true',
                                help='Automates check status after submitting trace request',
                                default=False)   
    msgtrace_parser.add_argument('--interactive',
                                action='store_true',
                                help='Interactive mode for Selenium. Default to false (headless).',
                                default=False)

def main(args=None) -> None:
    global logger

    parser = argparse.ArgumentParser(add_help=True, description=MSGTRC_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)

    getargs(parser)

    if args is None:
        args = parser.parse_args()

    logger = setup_logger(__name__, args.debug)

    if not os.path.isfile(args.authfile):
        logger.warning("{} auth file missing. Please auth first. Exiting.".format(args.authfile))
        sys.exit(1)

    auth = {}
    try:
        logger.info("Reading in authfile: {}".format(args.authfile))
        with open(args.authfile, 'r') as infile:
            auth = json.loads(infile.read())['mfa']['https://graph.microsoft.com/.default']
    except Exception as e:
        logger.error("{}".format(str(e)))
        raise e

    check_output_dir(args.output_dir, logger)
    check_output_dir(f'{args.output_dir}{os.path.sep}msgtrc', logger)

    msgtrc = MessageTrace(logger, args.output_dir, args, args.config, auth)
    
    if args.submit_report:
        logger.info("Requesting message trace...")
        seconds = time.perf_counter()
        msgtrc.request_msgtrace(args)
        if args.full:
            msgtrc.check_status(args)
        elapsed = time.perf_counter() - seconds
        logger.info("Message trace request executed in {0:0.2f} seconds.".format(elapsed))
    elif args.status_check:
        logger.info("Checking message trace report status...")
        seconds = time.perf_counter()
        msgtrc.check_status(args)
        elapsed = time.perf_counter() - seconds
        logger.info("Message trace status check executed in {0:0.2f} seconds.".format(elapsed))
    elif args.gather_report:
        logger.info("Exporting completed message trace report...")
        seconds = time.perf_counter()
        msgtrc.gather_results(args)
        elapsed = time.perf_counter() - seconds
        logger.info("Message trace download executed in {0:0.2f} seconds.".format(elapsed))

    
if __name__ == "__main__":
    main()
