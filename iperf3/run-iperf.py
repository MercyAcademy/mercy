#!/usr/bin/env python3
#
# pip3 install iperf3
# pip3 install sqlite3
#

import os
import iperf3
import sqlite3
import datetime
import argparse
import logging

iperf_dest = "192.168.101.10"

# JMS Do I want to login to the controller and find the WAP that I am
# currently connected to?

default_user = 'user'
default_password = 'password'

now = datetime.datetime.now()
default_sqlite_db = ('iperf3-results-{y}-{m}-{d}.sqlite3'
                     .format(y=now.year, m=now.month, d=now.day))

#--------------------------------------------------------------

def setup_cli():
    parser = argparse.ArgumentParser(description='Analyze Cisco wireless controller stats')
    parser.add_argument('--user',
                        default=default_user,
                        help='Username for controller login')
    parser.add_argument('--password',
                        default=default_password,
                        help='Password for controller login')

    parser.add_argument('--db',
                        default=default_sqlite_db,
                        help='SQLite3 database filename to store results')

    parser.add_argument('--debug',
                        action='store_true',
                        help='Enable extra output for debugging')
    parser.add_argument('--fake',
                        action='store_true',
                        help='Do not actually try to talk to controllers')

    args = parser.parse_args()

    return args

#---------------------------------------------------------------

def setup_logging(args):
    log = logging.getLogger('GithubPRwaiter')
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

################################################################

def db_connect(filename, log):
    # Use the sqlite3.Row factory so that we can get field names
    log.debug("Connecting to database: {db}".format(db=filename))
    conn             = sqlite3.connect(filename)
    conn.row_factory = sqlite3.Row
    cur              = conn.cursor()

    return cur

#---------------------------------------------------------------

def db_disconnect(cur):
    cur.connection.close()

#---------------------------------------------------------------

# SQL table schemas
def db_get_schemas():
    schemas = {
        'data' : '''
CREATE TABLE data (
       id integer primary key autoincrement,
       timestamp datetime default current_timestamp,

       sent_megabits float,
       received_megabits float
)
''',
    }

    return schemas

#---------------------------------------------------------------

# Go through all the schemas.  If the table does not already exist in
# the database, create it.
def db_create_tables(cur, schemas, log):
    for name, schema in schemas.items():
        sql = ("SELECT name FROM sqlite_master WHERE type='table' AND name='{name}'"
                 .format(name=name))
        log.debug("Executing SQL table check: {sql}".format(sql=sql))
        cur.execute(sql)
        result = cur.fetchone()

        if result:
            log.debug("Table {name} exists in database; no need to create it"
                      .format(name=name))
        else:
            log.debug("Table {name} does not exist in database; creating it"
                      .format(name=name))
            log.debug("Executing SQL table creation: {table}"
                      .format(table=name))
            cur.execute(schema)

    cur.connection.commit()

################################################################

def run_iperf(log):
    client = iperf3.Client()
    client.duration = 5
    client.server_hostname = iperf_dest
    result = client.run()

    log.info("Sent Mbps: {m}".format(m=result.sent_Mbps))
    log.info("Recv Mbps: {m}".format(m=result.received_Mbps))

    return result.sent_Mbps, result.received_Mbps

#---------------------------------------------------------------

def save_results(cur, sent, received, log):
    sql = "INSERT INTO data (sent_megabits, received_megabits) VALUES (?,?)"
    values = [ sent, received ]
    log.debug("SQL: {sql}, values: {values}"
              .format(sql=sql, values=values))

    cur.execute(sql, values)
    cur.connection.commit()

################################################################

def main():
    args = setup_cli()
    log  = setup_logging(args)

    # Connect to the database
    cur = db_connect(filename=args.db, log=log)

    # Create DB tables if they don't exist
    schemas = db_get_schemas()
    db_create_tables(cur=cur, schemas=schemas, log=log)

    sent, received = run_iperf(log)
    save_results(cur, sent, received, log)

    # Close out the database
    db_disconnect(cur)

if __name__ == "__main__":
    main()
