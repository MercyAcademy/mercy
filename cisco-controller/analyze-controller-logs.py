#!/usr/bin/env python3

import pprint
import csv
import sys
import os
import re

from datetime import datetime

logs          = dict()
mercy_ap_macs = dict()
rogue_ap_macs = dict()
types_found   = dict()

date_re = re.compile('... (...) (\d\d) (\d\d):(\d\d):(\d\d) (\d\d\d\d)')
months  = [ '',
            'Jan',
            'Feb',
            'Mar',
            'Apr',
            'May',
            'Jun',
            'Jul',
            'Aug',
            'Sep',
            'Oct',
            'Nov',
            'Dec' ]

#####################################################################

coverage_hole = re.compile('Coverage hole pre alarm for client\[\d+\] (..:..:..:..:..:..) on .+ interface of AP (..:..:..:..:..:..) \((\S+)\)')
rogue_removed = re.compile('Rogue AP : (..:..:..:..:..:..) removed from Base Radio MAC : (..:..:..:..:..:..)')
rogue_not_heard = re.compile('Rogue AP : (..:..:..:..:..:..) not heard with (.+)')
rogue_detect  = re.compile('Rogue AP: (..:..:..:..:..:..) detected on Base Radio MAC: (..:..:..:..:..:..)')
profile       = re.compile('(\S+) Profile (\S+?) .*for Base Radio MAC: (..:..:..:..:..:..)')
rf_manager    = re.compile('RF Manager updated (\S+) for Base Radio MAC: (..:..:..:..:..:..)')
attack        = re.compile('Warning: Our AP with Base Radio MAC (..:..:..:..:..:..) is under attack \((.)\) by (.+)')
load          = re.compile('Load Profile Failed for Base Radio MAC: (..:..:..:..:..:..)')

#####################################################################

def find_coverage(d, msg):
    m = coverage_hole.match(msg)
    if not m:
        return None

    item = {
        'type' : 'coverage hole',
        'client' : m.group(1),
        'ap' : m.group(2),
    }
    mercy_ap_macs[m.group(2)] = m.group(3)

    return item

def find_rogue(d, msg):
    item = None
    if item is None:
        item = find_rogue_detect(d, msg)
    if item is None:
        item = find_rogue_not_heard(d, msg)
    if item is None:
        item = find_rogue_removed(d, msg)

    return item

def find_rogue_removed(d, msg):
    m = rogue_removed.match(msg)
    if not m:
        return None

    item = {
        'type' : 'rogue AP removed',
        'rogue' : m.group(1),
        'ap' : m.group(2),
    }

    rap = m.group(2)
    if rap not in rogue_ap_macs:
        rogue_ap_macs[rap] = {
            'detected' : 0,
            'removed' : 0,
            'not heard' : 0,
        }
    rogue_ap_macs[rap]['removed'] = rogue_ap_macs[rap]['removed'] + 1

    return item

def find_rogue_not_heard(d, msg):
    m = rogue_not_heard.match(msg)
    if not m:
        return None

    item = {
        'type' : 'rogue AP not heard',
        'rogue' : m.group(1),
        'msg' : m.group(2),
    }

    rap = m.group(2)
    if rap not in rogue_ap_macs:
        rogue_ap_macs[rap] = {
            'detected' : 0,
            'removed' : 0,
            'not heard' : 0,
        }
    rogue_ap_macs[rap]['not heard'] = rogue_ap_macs[rap]['not heard'] + 1

    return item

def find_rogue_detect(d, msg):
    m = rogue_detect.match(msg)
    if not m:
        return None

    item = {
        'type' : 'rogue AP detected',
        'rogue' : m.group(1),
        'ap' : m.group(2),
    }

    rap = m.group(2)
    if rap not in rogue_ap_macs:
        rogue_ap_macs[rap] = {
            'detected' : 0,
            'removed' : 0,
            'not heard' : 0,
        }
    rogue_ap_macs[rap]['detected'] = rogue_ap_macs[rap]['detected'] + 1

    return item

def find_profile(d, msg):
    m = profile.match(msg)
    if not m:
        return None

    item = {
        'type' : 'profile updated',
        'profile' : m.group(1),
        'action' : m.group(2),
        'ap' : m.group(3),
    }

    return item

def find_rf_manager(d, msg):
    m = rf_manager.match(msg)
    if not m:
        return None

    item = {
        'type' : 'RF manager updated',
        'ap' : m.group(1),
    }

    return item

def find_attack(d, msg):
    m = attack.match(msg)
    if not m:
        return None

    item = {
        'type' : 'attack',
        'ap' : m.group(1),
        'attack_type' : m.group(2),
        'msg' : m.group(3)
    }

    return item

def find_unknown(d, msg):
    item = {
        'type' : 'Unknown',
    }

    return item

#####################################################################

with open('controller-logs.csv') as f:
    reader = csv.reader(f)
    first = True
    for row in reader:
        # First row is headers
        if first:
            first = False
            continue

        # Parse it

        # Timestamp format: Sun Sep 16 18:50:34 2018
        m = date_re.match(row[1])
        if not m:
            continue

        mon  = months.index(m.group(1))
        day  = int(m.group(2))
        year = int(m.group(6))

        hour = int(m.group(3))
        min  = int(m.group(4))
        sec  = int(m.group(5))

        d = datetime(year=year, month=mon, day=day, hour=hour,
                     minute=min, second=sec)

        msg = row[2]

        # Analyze it

        item = None
        if item is None:
            item = find_coverage(d, msg)
        if item is None:
            item = find_rogue(d, msg)
        if item is None:
            item = find_profile(d, msg)
        if item is None:
            item = find_rf_manager(d, msg)
        if item is None:
            item = find_attack(d, msg)
        if item is None:
            item = find_unknown(d, msg)

        # Save it

        t = item['type']
        if t not in types_found:
            types_found[t] = 0
        types_found[t] = types_found[t] + 1

        if d not in logs:
            logs[d] = list()

        item['timestamp'] = d
        item['msg'] = msg

        logs[d].append(item)

pp = pprint.PrettyPrinter()
pp.pprint(logs)
pp.pprint(mercy_ap_macs)
pp.pprint(rogue_ap_macs)
pp.pprint(types_found)
