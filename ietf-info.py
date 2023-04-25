#!/usr/bin/python3

"""Script for attributing RFC and Datatracker activities

https://github.com/paulwouters/ietf-info

Original rewrite by Simo Soini of Martin Duke's code.

Copyright 2023, Simo Soini, Foobar Oy <caps@foobar.fi>
Copyright 2023, Paul Wouters, Aiven <paul.wouters@aiven.io>

License: GPLv2+
"""
import asyncio
import bs4
import sys
import datetime as dt
import getopt
import pprint
import re
import requests
import time
from typing import Dict


# General use global variables
RFC_EDITOR_URL = 'https://www.rfc-editor.org'
DATA_TRACKER_URL = 'https://datatracker.ietf.org'
OPTIONS = 'hvdn:'
LONG_OPTIONS = ['help', 'verbose', 'debug', 'name']
USAGE = f"""
Tool for counting RFC contributions by name.

Usage: ./count_rfcs.py -n "Firstname Lastname"

{"-h, --help:":<20}Print this help message.
{"-d, --debug:":<20}Print debug info.
{"-v, --debug:":<20}Print verbose RFC numbers.
{"-n, --name:":<20}REQUIRED! "Firstname Lastname"
"""

# Global variables edited by commandline arguments
INCLUDE = [
    'PROPOSED STANDARD',
    'BEST CURRENT PRACTICE',
    'HISTORIC',
    'EXPERIMENTAL',
    'INFORMATIONAL',
    'ACKNOWLEDGMENTS',
]
NAME = ''
FIRST_YEAR = 2022
LAST_YEAR = dt.date.today().year
FIRST_RFC = 7000
LAST_RFC = 20_000
DEBUG = False
VERBOSE = False

# Global variables for collecting the results
AUTHOR: Dict[int, str] = {}
RESPONSIBLE_AD: Dict[int, str] = {}
SHEPHERD: Dict[int, str] = {}
CONTRIBUTOR: Dict[int, str] = {}
BALLOTED: Dict[int, str] = {}
DISCUSS: Dict[int, str] = {}
FAILED_CHECK: Dict[int, str] = {}


def parse_rfc_row(row: bs4.element.Tag) -> dict:
    """Parse a row of rfc table into a dict."""
    fields = {}
    fields['number'] = int(row.td.noscript.get_text())
    fields['title'] = row.td.find_next_sibling('td').b.get_text()
    text = row.td.find_next_sibling('td').get_text()
    fields['issued'] = 'Not issued' not in text
    lines = [line.strip() for line in text.splitlines() if
             line.strip() != '']
    for line in lines[1:]:
        if '[' in line:
            fields['year'] = int(line.split()[-2])
        elif ':' in line:
            line = line.replace('(', '')
            line = line.replace(')', '')
            parts = line.split(', ')
            for part in parts:
                key_val_pair = part.split(': ')
                fields[key_val_pair[0].lower()] = key_val_pair[1]
    return fields


def validate_row(row: bs4.element.Tag) -> bool:
    """Tell filtering function if the row should be included."""
    if row.name != 'tr' or row.td.noscript is None:
        return False
    row = parse_rfc_row(row)
    return (
        row['status'] in INCLUDE
        and row['issued']
        and LAST_YEAR >= row['year'] >= FIRST_YEAR
        and LAST_RFC >= row['number'] >= FIRST_RFC
    )


def handle_arguments(arglist) -> None:
    """Parse given arguments and handle."""
    arguments, _ = getopt.getopt(arglist, OPTIONS, LONG_OPTIONS)
    if len(arguments) == 0:
        print(USAGE)
    for arg, val in arguments:
        if arg in ('-h', '--help'):
            print(USAGE)
            sys.exit()
        elif arg in ('-n', '--name'):
            global NAME
            NAME = val
        elif arg in ('-i', '--include'):
            for include in val.split(','):
                INCLUDE.append(include.upper())
        elif arg in ('-d', '--debug'):
            global DEBUG
            DEBUG = True
        elif arg in ('-v', '--verbose'):
            global VERBOSE
            VERBOSE = True
    if not NAME:
        sys.exit()


def print_result() -> None:
    """Print results of the program."""
    print()
    print(f'Search for name {NAME}:')
    print()
    print(f'Authored: {len(AUTHOR)}')
    if VERBOSE:
        pprint.pprint(AUTHOR)
    print(f'Shepherded: {len(SHEPHERD)}')
    if VERBOSE:
        pprint.pprint(SHEPHERD)
    print(f'Responsible AD: {len(RESPONSIBLE_AD)}')
    if VERBOSE:
        pprint.pprint(RESPONSIBLE_AD)
    print(f'Balloted: {len(BALLOTED)}')
    if VERBOSE:
        pprint.pprint(BALLOTED)
    print(f'Discussed: {len(DISCUSS)}')
    if VERBOSE:
        pprint.pprint(DISCUSS)
    print(f'Acknowledged: {len(CONTRIBUTOR)}')
    if VERBOSE:
        pprint.pprint(CONTRIBUTOR)


async def http_get(url: str) -> requests.models.Response:
    """Async http get function."""
    return await asyncio.to_thread(requests.get, url)


async def get_possible_rfcs() -> list:
    """Get list of all RFC:s and do basic filtering."""
    route = '/rfc-index2.html'

    try:
        if DEBUG:
            print(
                f'Requesting data from {RFC_EDITOR_URL + route}... ',
                end=''
            )
        response = await http_get(RFC_EDITOR_URL + route)
    except requests.exceptions.ConnectionError as error:
        print(f'Aborted due to the following error:\n{error}')
        sys.exit()

    soup = bs4.BeautifulSoup(response.content, 'html.parser')
    table = soup.table

    # Find correct table
    for _ in range(2):
        table = table.find_next_sibling('table')

    return [parse_rfc_row(row) for row in table.contents
            if validate_row(row)]


async def check_rfc(rfc: dict) -> None:
    """Check RFC for name match, and add hits to statistics."""
    route = f'/doc/rfc{rfc["number"]}/doc.json'
    try:
        if DEBUG:
            print(f'{rfc["number"]}: Getting rfc data... ', end='')
        response = await http_get(DATA_TRACKER_URL + route)
    except requests.exceptions.ConnectionError as error:
        print(f'check_rfc failed with {error}')
        return
    datatracker_metadata = response.json()
    # print(datatracker_metadata['authors'])
    if NAME in datatracker_metadata['authors']:
        AUTHOR[rfc['number']] = rfc['title']
        if VERBOSE:
            print(f'{rfc["number"]}: Authored')
    # print(datatracker_metadata['shepherd'])
    if (
            datatracker_metadata['shepherd']
            and NAME in datatracker_metadata['shepherd']
    ):
        SHEPHERD[rfc['number']] = rfc['title']
        if VERBOSE:
            print(f'{rfc["number"]}Shepherded')
    if DEBUG:
        print(datatracker_metadata['ad'])
    if (
            datatracker_metadata['ad']
            and NAME in datatracker_metadata['ad']
    ):
        RESPONSIBLE_AD[rfc['number']] = rfc['title']
        if VERBOSE:
            print(f'{rfc["number"]}: Responsible AD')
    if 'ACKNOWLEDGMENTS' in INCLUDE:
        result = await check_acknowledgments(rfc)
    result = await check_ballot(rfc)
    if not result:
        print(f'{rfc["number"]}: Name not found')


async def check_acknowledgments(rfc: dict) -> bool:
    """Check the RFC text for name as an acknowledgment."""
    route = f'/rfc/rfc{rfc["number"]}.txt'
    try:
        if DEBUG:
            print(f'{rfc["number"]}: Getting acknowledgment data... ', end='')
        response = await http_get(RFC_EDITOR_URL + route)
    except requests.exceptions.ConnectionError as error:
        print(f'check_acknowledgments failed with {error}')
        return False
    try:
        rfc_text = response.content.decode()
    except UnicodeDecodeError:
        try:
            rfc_text = response.content.decode('latin-1')
        except UnicodeDecodeError as error:
            FAILED_CHECK[rfc['number']] = rfc['title']
            print(error)
    if rfc_text and NAME in rfc_text:
        CONTRIBUTOR[rfc['number']] = rfc['title']
        if VERBOSE:
            print(f'{rfc["number"]}: Contributed')
        return True
    return False


async def check_ballot(rfc: dict) -> bool:
    """Check if the RFC is balloted."""
    route = f'/doc/rfc{rfc["number"]}/ballot/'
    try:
        if DEBUG:
            print(f'{rfc["number"]}: Getting ballot data... ', end='')
        response = await http_get(DATA_TRACKER_URL + route)
    except requests.exceptions.ConnectionError as error:
        print(f'check_ballot failed with {error}')
        return False
    try:
        rfc_text = response.content.decode()
    except UnicodeDecodeError:
        try:
            rfc_text = response.content.decode('latin-1')
        except UnicodeDecodeError as error:
            FAILED_CHECK[rfc['number']] = rfc['title']
            print(error)
    if NAME in rfc_text:
        BALLOTED[rfc['number']] = rfc['title']
        discuss_regex = re.compile(
            NAME
            + r'\s*</div>\s*<div class=\"flex-fill text-end\">\s*'
            + r'<span class=\"text-muted small\">\(was Discuss\)'
        )

        if DEBUG:
            print(f'{rfc["number"]}: Checking if discussed... ', end='')
        if discuss_regex.search(rfc_text):
            DISCUSS[rfc['number']] = rfc['title']
            if VERBOSE:
                print(f'{rfc["number"]}: Discussed')
        if VERBOSE:
            print(f'{rfc["number"]}: Balloted')
        return True
    return False


async def main() -> None:
    """Execute main program."""
    start = time.time()
    handle_arguments(sys.argv[1:])
    table = await get_possible_rfcs()
    if DEBUG:
        print('Started going through RFC:s left after filtering')
    await asyncio.gather(*[check_rfc(rfc) for rfc in table])
    print_result()
    print(f'finished in {time.time() - start:.2f} s')


if __name__ == '__main__':
    asyncio.run(main())
