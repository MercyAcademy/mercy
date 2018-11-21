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

# SQL table schemas
def db_get_schemas():
    schemas = {
        'controllers' : '''
CREATE TABLE controllers (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       name char(30),
       ip char(16)
)
''',

        'wlans' : '''
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
''',

        'aps' : '''
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
''',

        'clients' : '''
CREATE TABLE clients (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       mac char(18)
)
''',

        'ap_sightings' : '''
CREATE TABLE ap_sightings (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       ap_index integer,

       ip char(16),
       num_clients integer
)
''',

        'client_sightings' : '''
CREATE TABLE client_sightings (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       client_index integer,
       ap_index integer,
       wlan_index integer,

       protocol_802dot11 char(4),
       frequency_ghz float
)
'''
    }

    return schemas

#####################################################################

def graph_num_clients(databases, log):
    # Find the first date in the databases
    first          = None
    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():
                dt = datetime(int(year), int(month), int(day))

                if not first:
                    first = dt
                elif dt < first:
                    first = dt

    log.debug("Found first: {dt}".format(dt=first))


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
    #             hour_timestamp1 : { 'total' : total, 'count' : count, 'average' : average },
    #             hour_timestamp2 : { 'total' : total, 'count' : count, 'average' : average },
    #             hour_timestamp3 : { 'total' : total, 'count' : count, 'average' : average },
    #             ...,
    #         },
    #         'x' : list(...),
    #         'y' : list(...),
    #     },
    # }

    def _get_empty():
        return {
            'minute' : {
                'raw' : dict(),
            },
            'hour' : {
                'raw' : dict(),
            },
        }

    def _normalize_minute(minute):
        # Normalize to 15-minute increments because
        # sometimes the controller gets busy and takes 1-3
        # minutes to report all the stats.
        if minute < 15:
            minute = 0
        elif minute < 30:
            minute = 15
        elif minute < 45:
            minute = 30
        else:
            minute = 45

        return minute

    #-----------------------------
    # Now plot them all relative to the first date
    total          = _get_empty()
    per_controller = dict()
    per_ap         = dict()
    exp            = re.compile("(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):")
    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():

                # Look at each client sighting at this timestamp.
                #
                # Save data both on a per-minute basis, per-hour
                # basis, and a per-day basis.
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
                    minute = _normalize_minute(int(match.group(5)))

                    ap_id  = client['ap_index']
                    c_id   = day_db['aps']['rows'][ap_id]['controller_id']

                    dt = datetime(year, month, day, hour, minute)

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
                        per_ap[ap_id] = _get_empty()
                    _minute_increment(per_ap[ap_id], dt)

                    # Increment the "number of clients on this
                    # controller" count at this timestamp.
                    if not c_id in per_controller:
                        per_controller[c_id] = _get_empty()
                    _minute_increment(per_controller[c_id], dt)

    #-----------------------------
    # Iterate over the collected data and compute per-hour averages.
    def _average_per_hour(data):
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

    _average_per_hour(total)
    for ap_id in per_ap:
        _average_per_hour(per_ap[ap_id])
    for c_id in per_controller:
        _average_per_hour(per_controller[c_id])

    #-----------------------------
    def _listize(data, sub_name=None):
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

    # Convert the data into ordered lists
    _listize(total['minute'])
    _listize(total['hour'], 'average')
    for ap_id in per_ap:
        _listize(per_ap[ap_id]['minute'])
        _listize(per_ap[ap_id]['hour'], 'average')
    for c_id in per_controller:
        _listize(per_controller[c_id]['minute'])
        _listize(per_controller[c_id]['hour'], 'average')

    #-----------------------------
    # Plot total clients
    fig, ax = plt.subplots()
    ax.set(xlabel='Days', ylabel='Number of clients',
           title='Total number of wifi clients')

    log.info("Plotting total number of clients on all controllers")
    # JMS This makes a very busy plot
    #ax.plot(total['minute']['x'], total['minute']['y'],
    #        label='Total clients')
    ax.step(total['hour']['x'], total['hour']['y'],
            label='Averge clients per hour')

    plt.legend()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-all-controllers.pdf")
    #plt.show()

    #-----------------------------
    # Plot clients on each controller
    fig, ax = plt.subplots()
    ax.set(xlabel='Days', ylabel='Number of clients',
           title='Average number of wifi clients per hour on each controller')

    colors = ['r', 'b']
    i = 0
    for c_id, c in per_controller.items():
        log.info("Ploting average number of clients per hour on controller {id}"
                 .format(id=c_id))
        ax.plot(c['hour']['x'], c['hour']['y'], colors[i],
                label='Average clients per hour on controller {id}'.format(id=c_id))
        i += 1

    plt.legend()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-each-controller.pdf")
    plt.show()

    #-----------------------------

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

def read_database(filename, log):
    db               = dict()
    conn             = sqlite3.connect(filename)
    conn.row_factory = sqlite3.Row
    cur              = conn.cursor()

    db['controllers']      = read_table(cur, 'controllers', log)
    db['lans']             = read_table(cur, 'wlans', log)
    db['aps']              = read_table(cur, 'aps', log)
    db['clients']          = read_table(cur, 'clients', log)
    db['client_sightings'] = read_table(cur, 'client_sightings', log)
    db['ap_sightings']     = read_table(cur, 'ap_sightings', log)

    conn.close()

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

    graph_num_clients(databases, log)

if __name__ == "__main__":
    main()

