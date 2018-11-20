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
    first = None
    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():
                dt = datetime(int(year), int(month), int(day))

                if not first:
                    first = dt
                elif dt < first:
                    first = dt

    log.debug("Found first: {dt}".format(dt=first))

    # Now plot them all relative to the first date
    xaxis       = dict()
    total       = dict()
    controllers = dict()
    aps         = dict()
    exp         = re.compile("(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):")
    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():
                for _, client in day_db['client_sightings']['rows'].items():
                    # We take samples at 15 minute intervals, but it
                    # takes a few seconds to insert all the data into
                    # the database.  So all the clients seen at a
                    # given time may not have exactly the same
                    # timestamp.  For simplicity, just drop the
                    # seconds off the sqlite3 timestamp -- that's
                    # "good enough".
                    ts = client['timestamp']
                    match = exp.match(ts)
                    if not match:
                        log.error("Malformed timestamp ('{ts}') -- skipped"
                                  .format(ts=ts))
                        continue

                    year   = int(match.group(1))
                    month  = int(match.group(2))
                    day    = int(match.group(3))
                    hour   = int(match.group(4))
                    minute = int(match.group(5))

                    ap_id         = client['ap_index']
                    controller_id = day_db['aps']['rows'][ap_id]['controller_id']

                    dt = datetime(year, month, day, hour, minute)
                    ts = dt.timestamp()

                    xaxis[ts] = dt

                    if not ts in total:
                        total[ts] = 0
                        
                    if not ap_id in aps:
                        aps[ap_id] = dict()
                    if not ts in aps[ap_id]:
                        aps[ap_id][ts] = 0
                        
                    if not controller_id in controllers:
                        controllers[controller_id] = dict()
                    if not ts in controllers[controller_id]:
                        controllers[controller_id][ts] = 0

                    # Add one to the counts
                    total      [ts]                += 1
                    aps        [ap_id][ts]         += 1
                    controllers[controller_id][ts] += 1

    # Convert the data into ordered lists
    x             = list()
    y_total       = list()
    sorted_xaxis  = sorted(xaxis)

    y_controllers = dict()
    for c_id in controllers:
        y_controllers[c_id] = list()

    y_aps         = dict()
    for ap_id in aps:
        y_aps[ap_id] = list()

    for ts in sorted_xaxis:
        x.append(xaxis[ts])
        y_total.append(total[ts])

        for c_id in controllers:
            if ts in controllers[c_id]:
                y_controllers[c_id].append(controllers[c_id][ts])

        for ap_id in aps:
            if ts in aps[ap_id]:
                y_aps[ap_id].append(aps[ap_id][ts])

    # Plot totals
    fig, ax = plt.subplots()
    ax.set(xlabel='Days', ylabel='Number of clients',
           title='Total number of wifi clients')

    log.info("Plotting total number of clients on all controllers")
    ax.plot(x, y_total, label='Total clients')

    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-all-controllers.pdf")
    #plt.show()

    # Plot clients on each controller
    fig, ax = plt.subplots()
    ax.set(xlabel='Days', ylabel='Number of clients',
           title='Number of wifi clients on each controller')

    for c_id in controllers:
        log.info("Ploting number of clients on controller {id}".format(id=c_id))
        log.info("Len of X: {lx}, Len of Y: {ly}"
                 .format(lx=len(x), ly=len(y_controllers[c_id])))
        continue
        ax.plot(x, y_controllers[c_id], label='Clients on controller {id}'.format(id=c_id))

    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-each-controller.pdf")
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

