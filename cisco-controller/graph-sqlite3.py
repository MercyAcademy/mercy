#!/usr/bin/env python3

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib
import argparse
import logging
import sqlite3
import sys
import os
import re

from matplotlib.ticker import NullFormatter
from datetime import datetime
from datetime import date
from pprint import pformat

#####################################################################

"""

Database schemas

CREATE TABLE controllers (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       name char(30),
       ip char(16)
)


CREATE TABLE wlans (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       controller_id integer,

       wlan_id integer,
       profile_name char(32),
       ssid char(32),
       enabled integer,
       interface char(20)
)

CREATE TABLE aps (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       controller_id integer,

       name char(20),
       ap_model char(20),
       slots integer,
       mac char(20),
       location char(16),
       country char(8)
)

CREATE TABLE clients (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       mac char(18)
)

CREATE TABLE ap_sightings (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       ap_index integer,

       ip char(16),
       num_clients integer
)

CREATE TABLE client_sightings (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       client_index integer,
       ap_index integer,
       wlan_index integer,

       protocol_802dot11 char(4),
       frequency_ghz float
)

"""

#####################################################################

def analyze_find_first_date(databases):
    first = None
    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():
                dt = datetime(int(year), int(month), int(day))

                if not first:
                    first = dt
                elif dt < first:
                    first = dt

    return first

# The data structures end up looking like this:
#
# foo = {
#     'minute' : {
#         'raw' : {
#             minute_timestamp1 : count1,
#             minute_timestamp2 : count2,
#             minute_timestamp3 : count3,
#             ...,
#         },
#         'x' : list(...),
#         'y' : list(...),
#     },
#     'hour' : {
#         'raw' : {
#             hour_timestamp1 : { 'total' : total,
#                                 'count' : count,
#                                  'average' : average
#                               },
#             hour_timestamp2 : { 'total' : total,
#                                 'count' : count,
#                                  'average' : average
#                               },
#             hour_timestamp3 : { 'total' : total,
#                                 'count' : count,
#                                  'average' : average
#                               },
#             ...,
#         },
#         'x' : list(...),
#         'y' : list(...),
#     },
# }

def analyze_create_empty():
    return {
        'minute' : {
            'raw' : dict(),
        },
        'hour' : {
            'raw' : dict(),
        },
    }

# Normalize to 15-minute increments because
# sometimes the controller gets busy and takes 1-3
# minutes to report all the stats.
def analyze_normalize_minute(minute):
    if minute < 15:
        minute = 0
    elif minute < 30:
        minute = 15
    elif minute < 45:
        minute = 30
    else:
        minute = 45

    return minute

def analyze_client_sightings_minute(databases, first, log):
    total          = analyze_create_empty()
    per_controller = dict()
    per_ap         = dict()
    exp            = re.compile("(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):")

    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():

                # Look at each client sighting at this timestamp.
                #
                # Save data both on per-minute and per-hour bases
                for _, client in day_db['client_sightings']['rows'].items():
                    ts_str = client['timestamp']
                    match  = exp.match(ts_str)
                    if not match:
                        log.error("Malformed timestamp ('{ts}') -- skipped"
                                  .format(ts=ts_str))
                        continue

                    year   = int(match.group(1))
                    month  = int(match.group(2))
                    day    = int(match.group(3))
                    hour   = int(match.group(4))
                    minute = analyze_normalize_minute(int(match.group(5)))
                    dt     = datetime(year, month, day, hour, minute)

                    wlan_id = client['wlan_index']
                    ssid    = day_db['wlans']['rows'][wlan_id]['ssid']
                    client['ssid'] = ssid

                    ap_id   = client['ap_index']
                    ap_name = day_db['aps']['rows'][ap_id]['name']
                    client['ap_name'] = ap_name

                    c_id    = day_db['aps']['rows'][ap_id]['controller_id']

                    def _minute_increment(data, timestamp):
                        data_minute = data['minute']['raw']
                        if not timestamp in data_minute:
                            data_minute[timestamp] = 0
                        data_minute[timestamp] += 1

                    # Increment the "total number of clients" count at
                    # this timestamp.
                    _minute_increment(total, dt)

                    # Increment the "number of clients on this AP"
                    # count at this timestamp.
                    if not ap_id in per_ap:
                        per_ap[ap_id] = analyze_create_empty()
                        # Save the name of the AP, too.
                        per_ap[ap_id]['ap_name'] = ap_name
                    _minute_increment(per_ap[ap_id], dt)

                    # Increment the "number of clients on this
                    # controller" count at this timestamp.
                    if not c_id in per_controller:
                        per_controller[c_id] = analyze_create_empty()
                    _minute_increment(per_controller[c_id], dt)

    return total, per_controller, per_ap

# Iterate over the collected data and compute per-hour averages.
def analyze_client_sightings_hour(data, log):
    data_min = data['minute']['raw']
    for dt_min in data_min:
        dt_hour = datetime(year=dt_min.year,
                           month=dt_min.month,
                           day=dt_min.day,
                           hour=dt_min.hour)

        data_hour = data['hour']['raw']
        if dt_hour not in data_hour:
            data_hour[dt_hour] = {
                'total'   : 0,
                'count'   : 0,
            }

        log.debug("Found: min {dtm} --> hour {dth}"
                  .format(dtm=dt_min, dth=dt_hour))
        log.debug(pformat(data_min[dt_min]))

        data_hour[dt_hour]['total'] += data_min[dt_min]
        data_hour[dt_hour]['count'] += 1

    for dt_hour, raw_hour in data_hour.items():
        average = raw_hour['total'] / raw_hour['count']
        raw_hour['average'] = average

# Convert the data from the dict() that it is stored in to be a
# list() (because matplotlib needs data in lists in order to plot
# them).
def analyze_listize(data, sub_name=None):
    x = list()
    y = list()

    sorted_x = sorted(data['raw'])
    for x_value in sorted_x:
        x.append(x_value)
        if sub_name:
            y.append(data['raw'][x_value][sub_name])
        else:
            y.append(data['raw'][x_value])

    data['x'] = x
    data['y'] = y

def analyze_databases(databases, log):
    first = analyze_find_first_date(databases)
    log.debug("Found first date in databases: {dt}".format(dt=first))

    # Analyze all the loaded databases and make unified timelines
    total, per_controller, per_ap = analyze_client_sightings_minute(databases,
                                                                    first, log)

    # Compute per-hour averages
    analyze_client_sightings_hour(total, log)
    for ap_id in per_ap:
        analyze_client_sightings_hour(per_ap[ap_id], log)
    for c_id in per_controller:
        analyze_client_sightings_hour(per_controller[c_id], log)

    # Convert the data into ordered lists
    analyze_listize(total['minute'])
    analyze_listize(total['hour'], 'average')
    for ap_id in per_ap:
        analyze_listize(per_ap[ap_id]['minute'])
        analyze_listize(per_ap[ap_id]['hour'], 'average')
    for c_id in per_controller:
        analyze_listize(per_controller[c_id]['minute'])
        analyze_listize(per_controller[c_id]['hour'], 'average')

    return total, per_controller, per_ap

#####################################################################

def plot_total_clients(total, meta, log):
    log.info("Plotting total number of clients on all controllers")

    fig, ax = plt.subplots()

    str   = 'ax.{function}'.format(function=meta['function'])
    func  = eval(str)
    title = meta['title']
    field = meta['field']

    ax.set(xlabel='Days', ylabel='Number of clients', title=title)
    func(total[field]['x'], total[field]['y'])
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-all-controllers.pdf")
    #plt.show()

def plot_per_controller(per_controller, meta, log):
    fig, ax = plt.subplots()

    str   = 'ax.{function}'.format(function=meta['function'])
    func  = eval(str)
    title = meta['title']
    field = meta['field']

    ax.set(xlabel='Days', ylabel='Number of clients',
           title='{title} on each controller'.format(title=title))

    for c_id, c in per_controller.items():
        log.info("Ploting average number of clients per hour on controller {id}"
                 .format(id=c_id))
        func(c[field]['x'], c[field]['y'],
             label=('Average clients per hour on controller {id}'
                    .format(id=c_id)))

    plt.legend()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-each-controller.pdf")
    #plt.show()

def plot_per_ap(per_ap, meta, log):
    fig, ax = plt.subplots()

    str   = 'ax.{function}'.format(function=meta['function'])
    func  = eval(str)
    title = meta['title']
    field = meta['field']

    ax.set(xlabel='Days', ylabel='Number of clients',
           title='{title} on each AP'.format(title=title))

    for ap_id, a in per_ap.items():
        log.info("Ploting average number of clients per hour on AP {name}"
                 .format(name=a['ap_name']))
        func(a[field]['x'], a[field]['y'], label=a['ap_name'])

    plt.legend()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-each-ap.pdf")
    #plt.show()

    #-----------------------------
    # Plot clients on each AP only when num_clients>=40
    fig, ax = plt.subplots()
    ax.set(xlabel='Days', ylabel='Number of clients',
           title='Average number of wifi clients per hour on each AP')

    min_value = 50
    for ap_id, a in per_ap.items():
        happy = False
        for y in a['hour']['y']:
            if y >= min_value:
                happy = True
                break

        if not happy:
            continue

        log.info("Ploting average number of clients per hour on AP {name} (when  num_clients > {min})"
                 .format(name=a['ap_name'], min=min_value))
        ax.plot(a['hour']['x'], a['hour']['y'],
                label=a['ap_name'])

    plt.legend()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-each-ap-large.pdf")
    plt.show()

#####################################################################

# Read any database table, return it in a dictionary indexed by the
# "id" field.
def read_table(cur, name, log):
    # First, query to get all the field names in this table.
    # a) we know we're using sqlite, so we use an sqlite-specific
    # method
    # b) if we knew for a fact that the table would have data in it,
    # we could just query .keys() off any row result to get the field
    # names.  But the tables may not have data in them, so we can't
    # count on this.
    sql         = 'PRAGMA table_info({name})'.format(name=name)
    log.debug("Executing SQL: {sql}".format(sql=sql))
    result      = cur.execute(sql)
    field_names = list()
    for row in result.fetchall():
        field_names.append(row[1])
    log.debug("Got fields: {f}".format(f=field_names))

    # Now that we have the field names, read in the entire table
    sql    = ("SELECT * FROM {table}".format(table=name))
    log.debug("Executing SQL: {sql}".format(sql=sql))
    result = cur.execute(sql)
    rows   = dict()
    for row in result.fetchall():
        data = dict()
        for fname in field_names:
            data[fname] = row[fname]

        rows[data['id']] = data

    table = {
        'field_names' : field_names,
        'rows'        : rows,
    }

    return table

def normalize_client_sightings(db, log):
    for _, client in db['client_sightings']['rows'].items():
        ap_id     = client['ap_index']
        wlan_id   = client['wlan_index']

        client['ap_name']   = db['aps']['rows'][ap_id]['name']
        client['wlan_ssid'] = db['wlans']['rows'][wlan_id]['ssid']

def normalize_ap_sightings(db):
    for _, ap in db['ap_sightings']['rows'].items():
        ap_id = ap['ap_index']

        ap['ap_name'] = db['aps']['rows'][ap_id]['name']

def read_database(filename, log):
    db               = dict()
    conn             = sqlite3.connect(filename)
    conn.row_factory = sqlite3.Row
    cur              = conn.cursor()

    db['controllers']      = read_table(cur, 'controllers', log)
    db['wlans']            = read_table(cur, 'wlans', log)
    db['aps']              = read_table(cur, 'aps', log)
    db['clients']          = read_table(cur, 'clients', log)
    db['client_sightings'] = read_table(cur, 'client_sightings', log)
    db['ap_sightings']     = read_table(cur, 'ap_sightings', log)

    conn.close()

    # Normalize IDs to names
    normalize_client_sightings(db, log)
    normalize_ap_sightings(db)

    return db

def read_databases(args, log):
    log.debug("Looking for databases in {dir}..."
              .format(dir=args.dir))

    databases = dict()

    r = re.compile('(\d\d\d\d)-(\d\d)-(\d\d)\.sqlite3')
    for f in os.scandir(args.dir):
        match = r.match(f.name)

        if not match:
            log.debug("This file does not match: {f}"
                      .format(f=f.name))
            continue

        year  = match.group(1)
        month = match.group(2)
        day   = match.group(3)

        log.info("Reading database {f}..."
                 .format(f=f.path))

        db = read_database(filename=f.path, log=log)

        if not year in databases:
            databases[year] = dict()
        if not month in databases[year]:
            databases[year][month] = dict()

        databases[year][month][day] = db

    return databases

#####################################################################

def setup_logging(args):
    log = logging.getLogger('CiscoWifiSQLiteAnalyzer')
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    log.setLevel(level)

    ch = logging.StreamHandler()
    ch.setLevel(level)

    format = '%(asctime)s %(levelname)s: %(message)s'
    formatter = logging.Formatter(format)

    ch.setFormatter(formatter)

    log.addHandler(ch)

    return log

def setup_cli():
    parser = argparse.ArgumentParser(description='Analyze Cisco wireless controller stats')

    parser.add_argument('--dir',
                        default='data',
                        help='Directory where sqlite3 data files live')
    parser.add_argument('--out',
                        default='merged.sqlite3',
                        help='Output merged sqlite3 database')

    parser.add_argument('--debug',
                        action='store_true',
                        help='Enable extra output for debugging')

    args = parser.parse_args()

    args.dir = os.path.abspath(args.dir)
    if not os.path.exists(args.dir):
        print("Error: directory '{dir}' does not exist"
              .format(dir=args.dir))
        exit(1)

    return args

#####################################################################

def main():
    args      = setup_cli()
    log       = setup_logging(args)

    databases = read_databases(args, log)

    total, per_controller, per_ap = analyze_databases(databases, log)

    # Which plot?
    # 1. Continuous
    continuous = {
        'field'    : 'minute',
        'function' : 'plot',
        'title'    : 'Number of clients',
    }
    # 2. Step
    step = {
        'field'    : 'hour',
        'function' : 'step',
        'title'    : 'Average number of clients per hour',
    }

    plot_total_clients(total, continuous, log)
    plot_per_controller(per_controller, step, log)
    plot_per_ap(per_ap, step, log)

if __name__ == "__main__":
    main()

