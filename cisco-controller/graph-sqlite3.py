#!/usr/bin/env python3
#
# brew install libpng freetype pkg-config ffmpeg
#
# Do not install matplotlib from pip3 -- it won't have the Right
# Things for animation.  Instead, build it manually:
#
# git clone git@github.com:matplotlib/matplotlib.git
# cd matplotlib
# python3.7 -mpip install .
#
# pip3 install --user pytz
#

import argparse
import logging
import sqlite3
import pytz
import sys
import os
import re

import matplotlib
import matplotlib.animation as animation
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from matplotlib.ticker import NullFormatter
from datetime import timedelta
from datetime import datetime
from datetime import date
from pprint import pprint
from pprint import pformat

#####################################################################

# Number of clients for the different colors in the scatter plots
green_max  = 35
yellow_max = 45
red_max    = 999

# Values used in computing circle size in the scatter plots
min_val   = 0
max_val   = 200
range_val = max_val - min_val

min_scale_val   = 0
max_scale_val   = 500
range_scale_val = max_scale_val - min_scale_val

wlan_names = [
    'mercy1',
    'Mercy-guest',
    'MercyStudent',
]

#-------------------------------------------------------------------

# Timezone information
local_tz_name = 'America/Louisville'
local_tz = pytz.timezone(local_tz_name)

utc_tz = pytz.utc

# Weekday names
weekday_names = [
    'Mon',
    'Tue',
    'Wed',
    'Thu',
    'Fri',
    'Sat',
    'Sun',
]

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

#####################################################################

def get_color(value):
    if value <= green_max:
        color = 'g'
    elif value <= yellow_max:
        color = 'y'
    else:
        color = 'r'

    return color

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
#     # For APs:
#     'ap_name' : name,
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

    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():

                # Look at each client sighting at this timestamp.
                #
                # Save data both on per-minute and per-hour bases
                for _, client in day_db['client_sightings']['rows'].items():
                    local_dt = client['local_timestamp']
                    ap_id    = client['ap_index']
                    ap_name  = client['ap_name']
                    c_id     = day_db['aps']['rows'][ap_id]['controller_id']

                    def _minute_increment(data, timestamp):
                        data_minute = data['minute']['raw']
                        if not timestamp in data_minute:
                            data_minute[timestamp] = 0
                        data_minute[timestamp] += 1

                    # Increment the "total number of clients" count at
                    # this timestamp.
                    _minute_increment(total, local_dt)

                    # Increment the "number of clients on this AP"
                    # count at this timestamp.
                    if not ap_id in per_ap:
                        per_ap[ap_id] = analyze_create_empty()
                        # Save the name of the AP, too.
                        per_ap[ap_id]['ap_name'] = ap_name
                    _minute_increment(per_ap[ap_id], local_dt)

                    # Increment the "number of clients on this
                    # controller" count at this timestamp.
                    if not c_id in per_controller:
                        per_controller[c_id] = analyze_create_empty()
                    _minute_increment(per_controller[c_id], local_dt)

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
        raw_hour['color'] = get_color(raw_hour['total'])

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

def analyze_databases(databases, first, log):
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
    plt.title("Total number of wifi clients")

    fig.savefig("total-clients-on-all-controllers.pdf")
    #plt.show()
    plt.close(fig)

#--------------------------------------------------------------------

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
    plt.close(fig)

#--------------------------------------------------------------------

def plot_per_ap(per_ap, meta, min_num_clients, log):
    fig, ax = plt.subplots()

    str   = 'ax.{function}'.format(function=meta['function'])
    func  = eval(str)
    title = meta['title']
    field = meta['field']

    #fig, ax = plt.subplots()
    title='Average number of wifi clients per hour on each AP'
    if min_num_clients > 0:
        title += ('(when num clients >= {num}'
                  .format(num=min_num_clients))
    ax.set(xlabel='Days', ylabel='Number of clients',
           title=title)

    for ap_id, a in per_ap.items():
        happy = False
        for y in a['hour']['y']:
            if y >= min_num_clients:
                happy = True
                break

        if not happy:
            continue

        log.info("Ploting average number of clients per hour on AP {name} (when num_clients > {min})"
                 .format(name=a['ap_name'], min=min_num_clients))
        ax.plot(a['hour']['x'], a['hour']['y'],
                label=a['ap_name'])

    plt.legend()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.grid()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")

    fig.savefig("total-clients-on-each-ap-min-clients={min}.pdf"
                .format(min=min_num_clients))
    #plt.show()
    plt.close(fig)

#####################################################################

def load_ap_animation_coordinates(log):
    aps = {
        'AP-Chapel'       : { 'y': 6, 'x': 8,  'shortname' : ' Chapel' },
        'AP-Business'     : { 'y': 6, 'x': 9,  'shortname' : 'Business' },
        'AP123'           : { 'y': 6, 'x': 10, 'shortname' : '   123' },

        'AP104'           : { 'y': 5, 'x': 1,  'shortname' : '   104' },
        'AP103'           : { 'y': 5, 'x': 2,  'shortname' : '   103' },
        'AP-MainOffice-r' : { 'y': 5, 'x': 5,  'shortname' : ' MainOff' },
        'AP102'           : { 'y': 5, 'x': 6,  'shortname' : '   102' },
        'AP101'           : { 'y': 5, 'x': 7,  'shortname' : '   101' },
        'AP-Athletic'     : { 'y': 5, 'x': 10, 'shortname' : 'Athletic' },

        'AP-MediaCenter1' : { 'y': 4, 'x': 1,  'shortname' : '   MC1' },
        'AP-MediaCenter2' : { 'y': 4, 'x': 2,  'shortname' : '   MC2' },
        'AP106'           : { 'y': 4, 'x': 3,  'shortname' : '   106' },
        'AP107'           : { 'y': 4, 'x': 5,  'shortname' : '   107' },
        'AP-Locker'       : { 'y': 4, 'x': 10, 'shortname' : ' Locker' },

        'AP108'           : { 'y': 3, 'x': 1, 'shortname' : '   108' },
        'AP109'           : { 'y': 3, 'x': 2, 'shortname' : '   109' },
        'AP110'           : { 'y': 3, 'x': 3, 'shortname' : '   110' },
        'AP111'           : { 'y': 3, 'x': 4, 'shortname' : '   111' },
        'APSTEM'          : { 'y': 3, 'x': 5, 'shortname' : '   STEM' },
        'AP113'           : { 'y': 3, 'x': 6, 'shortname' : '   113' },
        'AP114'           : { 'y': 3, 'x': 7, 'shortname' : '   114' },

        'AP-Cafe2'        : { 'y': 2, 'x': 8, 'shortname' : '  Cafe2' },

        'AP-Cafe1'        : { 'y': 1, 'x': 8, 'shortname' : '  Cafe1' },
        'AP-SmallGym'     : { 'y': 1, 'x': 9, 'shortname' : '  SmGym' },

        #----------------

        'AP206'           : { 'y' : -1, 'x' : 1, 'shortname' : '   206'},
        'AP205'           : { 'y' : -1, 'x' : 2, 'shortname' : '   205'},
        'AP204'           : { 'y' : -1, 'x' : 3, 'shortname' : '   204'},
        'AP203'           : { 'y' : -1, 'x' : 4, 'shortname' : '   203'},
        'AP202'           : { 'y' : -1, 'x' : 5, 'shortname' : '   202'},
        'AP201'           : { 'y' : -1, 'x' : 6, 'shortname' : '   201'},
        # Is this the conference room?s it not on the mapps that I have.
        'AP-President'    : { 'y' : -1, 'x' : 7, 'shortname' : 'Presdnt'},
        'AP-Gym'          : { 'y' : -1, 'x' : 8, 'shortname' : '   Gym'},

        'AP207'           : { 'y' : -2, 'x' : 2, 'shortname' : '   207'},
        'AP208'           : { 'y' : -2, 'x' : 4, 'shortname' : '   208'},
        'AP-Auditorium-r' : { 'y' : -2, 'x' : 6, 'shortname' : 'Adtorum'},

        'AP210'           : { 'y' : -3, 'x' : 2, 'shortname' : '   210'},
        'AP209'           : { 'y' : -3, 'x' : 4, 'shortname' : '   209'},

        'AP211'           : { 'y' : -4, 'x' : 1, 'shortname' : '   211'},
        'AP212'           : { 'y' : -4, 'x' : 2, 'shortname' : '   212'},
        'AP213'           : { 'y' : -4, 'x' : 3, 'shortname' : '   213'},
        'AP214'           : { 'y' : -4, 'x' : 4, 'shortname' : '   214'},
        'AP215r'          : { 'y' : -4, 'x' : 5, 'shortname' : '   215'},
        'AP216'           : { 'y' : -4, 'x' : 6, 'shortname' : '   216'},
        'AP217'           : { 'y' : -4, 'x' : 7, 'shortname' : '   217'},
        'AP-Dance'        : { 'y' : -4, 'x' : 8, 'shortname' : '  Dance'},

        #----------------

        'AP-Turf-Field'    : { 'y' : -6, 'x' : 1, 'shortname' : '  Turf  '},
        'AP-Softball'      : { 'y' : -6, 'x' : 2, 'shortname' : 'Softball'},
        'AP-Athletic-Bldg' : { 'y' : -6, 'x' : 3, 'shortname' : ' AthBlgd'},
    }

    # These x/y values carefully chosen (in conjunction with the
    # values above) so that we can plot a text value here that changes
    # over the animation (i.e., it's just above the text frame of the
    # plot area).
    timestamp = { 'y' : 7.1, 'x' : 2.8 }

    return aps, timestamp

def plot_scatter_animation_listize(data, coords, log):
    # Key: timestamp
    output = dict()

    for ap in data.values():
        name = ap['ap_name']
        x = coords[name]['x']
        y = coords[name]['y']

        raw = ap['minute']['raw']
        for dt in raw:
            # Scale the value to be a respectible circle size
            pct = raw[dt] / range_val
            scaled_value = min_scale_val + pct * range_scale_val

            # Get an appropriate color
            c = get_color(raw[dt])

            if not dt in output:
                output[dt] = {
                    'timestamp' : dt,
                    'x'         : list(),
                    'y'         : list(),
                    's'         : list(),
                    'c'         : list(),
                    'plot'      : None, # To be filled in later
                }

            output[dt]['x'].append(x)
            output[dt]['y'].append(y)
            output[dt]['s'].append(scaled_value)
            output[dt]['c'].append(c)

    return output

# Calculate the max axis size, because it doesn't change across all the
# plots
def plot_scatter_calculate_axis(coords, log):
    min_x = 999
    max_x = 0
    min_y = 999
    max_y = 0

    for _, coord in coords.items():
        x = coord['x']
        y = coord['y']

        if x > max_x:
            max_x = x
        if x < min_x:
            min_x = x
        if y > max_y:
            max_y = y
        if y < min_y:
            min_y = y

    # Add a little fluff to make sure it's big enough
    min_x -= 1
    max_x += 1
    min_y -= 1
    max_y += 1

    log.debug("Calculated axes for scatter plot: x=[{minx},{maxx}], y=[{miny},{maxy}]"
              .format(minx=min_x, maxx=max_x, miny=min_y, maxy=max_y))

    return [min_x, max_x, min_y, max_y]

def plot_scatter_make_title(dt, dayname=False, hour_min=False, tz=False):
    title = ''

    if dayname:
        title += ('{dayname} '
                  .format(dayname=weekday_names[dt.weekday()]))

    title += ('{year:04d}-{mon:02d}-{day:02d} '
              .format(year=dt.year,
                      mon=dt.month,
                      day=dt.day))

    if hour_min:
        title += ('{hour:02d}:{min:02d} '
                  .format(hour=dt.hour,
                          min=dt.minute))

    if tz:
        title += ' {tz}'.format(tz=local_tz_name)

    return title

def plot_scatter_set_labels(coords):
    for _, coord in coords.items():
        name = coord['shortname']
        x    = coord['x'] - 0.5
        y    = coord['y'] + 0.5

        plt.text(x, y, name)

def plot_scatter_make_plot(item, log):
    # Make the scatter plot for this timestamp
    log.debug("x: {x}, y: {y}, s: {s}"
              .format(x=pformat(item['x']),
                      y=pformat(item['y']),
                      s=pformat(item['s'])))
    plot = plt.scatter(x=item['x'], y=item['y'],
                       s=item['s'], c=item['c'])

    return plot

# The loops for generating scatter plot PDFs and animations are quite
# similar, but slightly different than.  Though trial and error, I
# have determined that I just need two different loops.
#
# 1. Generating PDFs requires a different title for each PDF.  Must
# also call plt.cla() between each plot so that we don't get the union
# of all previous scatter plots on that PDF output.
#
# 2. Generating animations will only use a single title (the animation
# class does not seem to be smart enough to notice the difference in
# titles, it only notices differences in the data area -- or I don't
# know how to make it notice the difference).  And if you call
# plt.cla() between each artist generation, you get a bogus movie.
# Confirmation: per
# https://stackoverflow.com/questions/49158604/matplotlib-animation-update-title-using-artistanimation#49159236,
# it seems you can only have one title per axis.
#
# So just keep this simple and have two different functions/loops for
# generating the scatter plots for PDFs and animations separately.
# Yes, this is wasteful because we generate the scatter plots twice,
# but the logic is far simpler this way.  Cope.

def plot_scatter_write_pdfs(fig, ap_listized_data, coords, log):
    # Setup things that are the same between all PDFs
    axis = plot_scatter_calculate_axis(coords, log)

    # Loop over all the data, and generate a PDF for each scatter
    # plot.
    for dt in sorted(ap_listized_data):
        # Clear the plot so that we don't have output from the
        # previous plot included in this new plot.
        plt.cla()

        # Now put all the metadata back in the plot
        plt.xticks([])
        plt.yticks([])
        plt.axis(axis)
        plot_scatter_set_labels(coords)
        title = plot_scatter_make_title(dt, dayname=True, hour_min=True,
                                        tz=True)
        plt.title(title)

        # Generate the actual scatter plot
        _ = plot_scatter_make_plot(ap_listized_data[dt], log)

        # Write it out to a file
        filename = ('aps-{year:04d}{mon:02d}{day:02d}-{dayname}-{hour:02d}{min:02d}.pdf'
                    .format(year=dt.year,
                            mon=dt.month,
                            day=dt.day,
                            dayname=weekday_names[dt.weekday()],
                            hour=dt.hour,
                            min=dt.minute))

        fig.savefig(filename)
        log.info("Wrote filename: {f}".format(f=filename))

def plot_scatter_write_animations(fig, ap_listized_data, ap_coords,
                                  timestamp_coords, log):

    def _reset_figure():
        # Clear out everything from the previous animation
        plt.cla()
        plt.xticks([])
        plt.yticks([])
        plt.axis(axis)
        plot_scatter_set_labels(ap_coords)

    def _write_movie(fig, artists, dt):
        ani = animation.ArtistAnimation(fig,
                                        artists,
                                        interval=1000,
                                        blit=True)

        filename = ('aps-{year:04d}{mon:02d}{day:02d}-{dayname}.mp4'
                    .format(year=dt.year,
                            mon=dt.month,
                            day=dt.day,
                            dayname=weekday_names[dt.weekday()]))
        ani.save(filename)
        log.info("Wrote movie: {f} ({num} frames)"
                 .format(f=filename, num=len(artists)))

        _reset_figure()

    # Setup things that are the same between all artists (i.e.,
    # frames)
    axis = plot_scatter_calculate_axis(ap_coords, log)
    _reset_figure()

    # Do not make an actual plt.title (i.e., a title on the axis),
    # because those cannot be animated.  Instead, we'll do some
    # trickery below.

    # Loop over all the data, and generate a frame ("artist") for each
    # one.
    dt_current = None
    artists    = list()
    for dt in sorted(ap_listized_data):
        # See if the day has changed.  If so, write out the animation
        # of the previous day *BEFORE* we change the figure for today.
        if (dt_current and dt_current.day != dt.day and len(artists) > 0):
            _write_movie(fig, artists, dt_current)
            artists = list()
            plt.cla()
            plt.xticks([])
            plt.yticks([])
            plt.axis(axis)
            plot_scatter_set_labels(ap_coords)

        title_str = plot_scatter_make_title(dt, dayname=True,
                                            hour_min=True, tz=True)
        title     = plt.text(x=timestamp_coords['x'],
                             y=timestamp_coords['y'],
                             s=title_str)

        # Generate the actual scatter plot
        plot = plot_scatter_make_plot(ap_listized_data[dt], log)
        artists.append([plot, title])
        dt_current = dt

    # Write out the last animation
    if len(artists) > 0:
        _write_movie(fig, artists, dt_current)

def plot_scatter_ap_clients_animation(ap_data, log):
    # Subplots gives us a larger plot area (vs. plt.figure()).
    fig, _ = plt.subplots()
    fig.tight_layout()

    ap_coords, timestamp_coord = load_ap_animation_coordinates(log)
    ap_listized_data = plot_scatter_animation_listize(ap_data,
                                                      ap_coords, log)
    plot_scatter_write_animations(fig, ap_listized_data, ap_coords,
                                  timestamp_coord, log)

#--------------------------------------------------------------------

def plot_scatter_busy_aps(ap_data, min_num_clients,
                          green, yellow, red, log):
    def _get_color(val):
        if val >= red:
            return 'r'
        elif val >= yellow:
            return 'y'
        else:
            return 'g'

    #------------------------------------------------------------

    def _compute(ap_data, min_num_clients, log):
        y        = 0
        output   = dict()
        date_min = None
        date_max = None
        for ap in ap_data.values():
            y       = y + 1
            ap_name = ap['ap_name']
            raw     = ap['minute']['raw']
            log.info("Examining busy information for AP {name}"
                     .format(name=ap_name))

            if not ap_name in output:
                output[ap_name] = dict()

            # Iterate over all the timestamps in the raw data (which
            # will span mall the days).
            for dt, count in raw.items():
                date = dt.date()

                if not date in output[ap_name]:
                    output[ap_name][date] = {
                        'name'  : ap_name,
                        'date'  : date,
                        'x'     : None, # Calculate this later
                        'y'     : y,
                        'count' : 0,
                        'value' : None, # Calculate this later
                        'color' : None, # Calculate this later
                    }

                if date_min is None or date < date_min:
                    date_min = date
                if date_max is None or date > date_max:
                    date_max = date

                if count >= min_num_clients:
                    output[ap_name][date]['count'] += 1

        # Make a ytick list of the correct length.  Note that we have
        # y values start at 1, and the notation below will make an
        # array starting with index 1.  So make the list be (y+1)
        # entries in length.
        ytick_labels = [ None ] * (y + 1)

        # Now that we have final counts, assign circle sizes, colors,
        # and x values.
        for ap_name, ap_item in output.items():
            for date, item in ap_item.items():
                # Scale the value to be a respectible circle size
                pct           = item['count'] / range_val
                scaled_value  = min_scale_val + pct * range_scale_val

                item['value'] = scaled_value
                item['color'] = _get_color(item['count'])
                item['x']     = date
                ytick_labels[item['y']] = item['name']

        return output, date_min, date_max, ytick_labels

    #------------------------------------------------------------

    def _listize(output, log):
        x     = list()
        y     = list()
        size  = list()
        color = list()

        for ap_name, ap_item in output.items():
            for date, item in ap_item.items():
                x.append(item['x'])
                y.append(item['y'])
                size.append(item['value'])
                color.append(item['color'])

        return x, y, size, color

    #------------------------------------------------------------

    # We have lots of text -- make it small...
    plt.rcParams.update({'axes.labelsize' : '6'})
    plt.rcParams.update({'xtick.labelsize' : '6'})
    plt.rcParams.update({'ytick.labelsize' : '6'})

    # Subplots gives us a larger plot area (vs. plt.figure()).
    fig, ax = plt.subplots()
    #fig.tight_layout()

    title = ('How often a given APs have >={num} clients per day\n(green>={g}, yellow>={y}, red>={r})'
             .format(num=min_num_clients, g=green, y=yellow, r=red))
    ax.set(title=title)

    # Run through the data and compute
    output, date_min, date_max, ytick_labels = _compute(ap_data,
                                                        min_num_clients,
                                                        log)

    # Push the axes out just a skosh
    one_day   = timedelta(days=1)
    date_min -= one_day
    date_max += one_day

    # Now re-orient the data into 4 discrete lists: x, y, size, color
    x, y, size, color = _listize(output, log)

    plot = plt.scatter(x=x, y=y, s=size, c=color)

    ax.grid()
    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=3))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
         rotation_mode="anchor")
    ax.get_xaxis().set_minor_locator(matplotlib.ticker.MultipleLocator(1))

    # If we don't set the X axis limits, sometimes Matplotlib picks
    # crazy large limits (i.e., for lots of X values below and above
    # where our data is).
    ax.set_xlim(left=date_min - one_day,
                right=date_max + one_day)

    ax.set_yticklabels(ytick_labels)
    ax.get_yaxis().set_major_locator(matplotlib.ticker.MultipleLocator(1))

    # Need to set the Y axis limits so that our Y tick labels exactly
    # match up.  Note that matplotlib will ignore ytick_label[0]
    # because it is None.  Our first Y value will be at 1, so set the
    # Y limit to be 0.5 (i.e., first major line will be at 1, but
    # there will be a little white space below it).
    ax.set_ylim(0.5, len(ytick_labels) + 0.5)

    fig.savefig('full-ap-frequency.pdf')
    plt.close(fig)

#####################################################################

def analyze_follow_mac(name, mac, databases, first, log):
    for year, year_db in databases.items():
        for month, month_db in year_db.items():
            for day, day_db in month_db.items():

                # Look at each client sighting at this timestamp.
                # Find the MAC of interest
                for _, client in day_db['client_sightings']['rows'].items():
                    if client['mac'] != mac:
                        continue

                    log.info("Found {name}/{mac} at {ts} on AP {ap}"
                             .format(name=name, mac=mac,
                                     ts=client['local_timestamp'],
                                     ap=client['ap_name']))

                    # JMS Do something with this data...

def plot_follow_mac(name, mac, databases, first, log):
    analyze_follow_mac(name, mac, databases, first, log)

    # JMS plot this data...

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
        # sqlite3.Row does not have a .copy() method.
        # So copy the data manually.
        data = dict()
        for fname in field_names:
            data[fname] = row[fname]

        rows[data['id']] = data

    table = {
        'field_names' : field_names,
        'rows'        : rows,
    }

    return table

sqlite_dt_exp = re.compile("(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):")

def discretize_sqlite3_timestamp(timestamp_str, log):
    match  = sqlite_dt_exp.match(timestamp_str)
    if not match:
        log.error("Malformed timestamp ('{ts}') -- skipped"
                  .format(ts=timestamp_str))
        return None, None

    year   = int(match.group(1))
    month  = int(match.group(2))
    day    = int(match.group(3))
    hour   = int(match.group(4))
    minute = analyze_normalize_minute(int(match.group(5)))

    utc_dt   = utc_tz.localize(datetime(year, month, day,
                                        hour, minute))
    local_dt = utc_dt.astimezone(local_tz)

    return utc_dt, local_dt


def normalize_timestamps(db, log):
    # JMS For the moment, we only need to discretize the
    # client_sightings and ap_sightings tables
    #for table in ['controllers', 'wlans', 'aps', 'clients',
    #              'client_sightings', 'ap_sightings']:
    for table in ['client_sightings', 'ap_sightings']:
        for _, row in db[table]['rows'].items():
            ts = row['timestamp']

            utc_dt, local_dt = discretize_sqlite3_timestamp(ts, log)
            row['utc_timestamp']   = utc_dt
            row['local_timestamp'] = local_dt

def normalize_client_sightings(db, log):
    for _, client in db['client_sightings']['rows'].items():
        client_id = client['client_index']
        ap_id     = client['ap_index']
        wlan_id   = client['wlan_index']

        client['mac']       = db['clients']['rows'][client_id]['mac']
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

    # Normalize timestamps
    normalize_timestamps(db, log)

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

        # NOTE: The filename timestamp is in local time (not UTC)
        local_year  = match.group(1)
        local_month = match.group(2)
        local_day   = match.group(3)

        log.info("Reading database {f}..."
                 .format(f=f.path))

        db = read_database(filename=f.path, log=log)

        if not local_year in databases:
            databases[local_year] = dict()
        if not local_month in databases[local_year]:
            databases[local_year][local_month] = dict()

        databases[local_year][local_month][local_day] = db

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

    first = analyze_find_first_date(databases)
    log.debug("Found first date in databases: {dt}"
              .format(dt=first))

    total, per_controller, per_ap = analyze_databases(databases,
                                                      first, log)

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

    a_lot_of_clients = 50

    plot_total_clients(total, continuous, log)
    plot_per_controller(per_controller, step, log)
    plot_per_ap(per_ap, step, min_num_clients=0, log=log)
    plot_per_ap(per_ap, step,
                min_num_clients=a_lot_of_clients, log=log)

    plot_scatter_ap_clients_animation(per_ap, log)
    plot_scatter_busy_aps(per_ap,
                          min_num_clients=a_lot_of_clients,
                          green=5, yellow=10, red=20,
                          log=log)

    macs = {
        'kathryn' : 'c0:b6:58:b4:f4:79',
    }
    for name, mac in macs.items():
        plot_follow_mac(name, mac, databases, first, log)

if __name__ == "__main__":
    main()

