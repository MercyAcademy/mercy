#!/usr/bin/env python3
"""

Requirements:

    virtualenv venv-network-map --python=python3.8
    . ./venv-network-map/bin/activate
    pip install graphviz
    pip install networkparse
    pip install pyparsing

"""

"""

TO DO:

- Put trunk VLANs on connections
- There's a mixing of "interface" and "port" terminology


"""

import graphviz
import csv
import os
import re

from pprint import pprint
from pprint import pformat
from networkparse import parse
from ipaddress import IPv4Network

dir = "/Users/jsquyres/git/personal/mercy/network-map/Network Switch Configurations/"
mdf = "MDF"
bus = "Business"
con = "Concession"
sci = "Science"
ath = "Athletics"
files = [
    # MDF
    {
        "location" : mdf,
        "type"     : "Cisco",
        "filename" : os.path.join(dir, mdf, "MDF Core 81 1.txt"),
    },
    {
        "location" : mdf,
        "type"     : "Cisco",
        "filename" : os.path.join(dir, mdf, "MDF Phone 81 53.txt"),
    },
    {
        "location" : mdf,
        "type"     : "Cisco",
        "filename" : os.path.join(dir, mdf, "MDF WAP 81 2.txt"),
    },

    {
        "location" : mdf,
        "type"     : "HP",
        "filename" : os.path.join(dir, mdf, "MDF HP 81 50.txt"),
    },
    {
        "location" : mdf,
        "type"     : "HP",
        "filename" : os.path.join(dir, mdf, "MDF HP 81 62.txt"),
    },
    {
        "location" : mdf,
        "type"     : "HP",
        "filename" : os.path.join(dir, mdf, "MDF HP 81 64.txt"),
    },

    # Business
    {
        "location" : bus,
        "type"     : "HP",
        "filename" : os.path.join(dir, bus, "Business Aruba 81 67.txt"),
    },
    {
        "location" : bus,
        "type"     : "Cisco",
        "filename" : os.path.join(dir, bus, "Business Phone 81 54.txt"),
    },

    # Concession
    {
        "location" : con,
        "type"     : "HP",
        "filename" : os.path.join(dir, con, "Concession Aruba 81 69.txt"),
    },
    {
        "location" : con,
        "type"     : "Cisco",
        "filename" : os.path.join(dir, con, "Concession Phone 81 56.txt"),
    },

    # Science
    {
        "location" : sci,
        "type"     : "HP",
        "filename" : os.path.join(dir, sci, "Science HP 81 51.txt"),
    },
    {
        "location" : sci,
        "type"     : "Cisco",
        "filename" : os.path.join(dir, sci, "Science Phone 81 55.txt"),
    },

    # Athletics
    {
        "location" : ath,
        "type"     : "HP",
        "filename" : os.path.join(dir, ath, "Athletics-81-58.txt"),
    },
]

# Configuration variables
config = {
    "show_trunk_vlans"  : True,
}

vlan_colors = [
    "lawngreen",
    "lightblue",
    "lightcyan",
    "orange",
    "beige",
    "darkgreen",
    "royalblue",
    "pink",
    "darkturquoise",
    "violet",
    "chocolate",
    "plum",
    "blue",
    "lightgrey",
    "coral",
    "gold",
]

global_vlan_colors = dict()

#----------------------------------------------------------------------------

def parse_range(range_str):
    ret = list()

    tokens = range_str.split(",")
    for token in tokens:
        if token.find('-') >= 0:
            values = token.split("-")
            # Interfaces will be integers or a letter followed by an integer.
            c = values[0][0]
            if c.isalpha():
                prefix = c
                lower  = int(values[0][1:])
                upper  = int(values[1][1:])
            else:
                prefix = ''
                lower  = int(values[0])
                upper  = int(values[1])

            for i in range(lower, upper + 1):
                ret.append("{prefix}{val}".format(prefix=prefix, val=i))
        else:
            ret.append(token)

    return ret

def netmask_to_prefixlen(netmask):
    return IPv4Network('0.0.0.0/' + netmask).prefixlen

#----------------------------------------------------------------------------

class BaseSwitchConfig:
    def __init__(self):
        self._find_config_hostname()
        print("Setting up {type} switch {h}"
            .format(type=self.type, h=self.hostname))
        self._find_config_vlans()
        self._find_config_port_channels()
        self._find_config_interfaces()

    def __str__(self):
        s = """ == VLANs on {h}
 {vlans}
 == Port channels on {h}
 {port_channels}
 == Interfaces on {h}
 {interfaces}""".format(h=self.hostname,
                    vlans=pformat(self.vlans),
                    port_channels=pformat(self.port_channels),
                    interfaces=pformat(self.interfaces))

        return s

    #------------------------------------------------------------------------

    def get_config(self):
        return self.config

    def get_hostname(self):
        return self.hostname

    def get_type(self):
        return self.type

    def set_location(self, location):
        self.location = location

    def get_location(self):
        return self.location

    def set_graph_name(self, name):
        self.graph_name = name

    def get_graph_name(self):
        return name

    #----------------------------------------------------------------------------

    # This is common to both kinds of switches
    def _find_config_hostname(self):
        hostname = (self.config.filter('hostname .+').one()).split()[1]

        # Sometimes it is surrounded by quotes.  Strip them.
        if hostname[0] == '"' and hostname[-1] == '"':
            hostname = hostname[1 : -1]

        self.hostname = hostname

    def get_vlan_color(self, id):
        id = int(id)
        if id in global_vlan_colors:
            return global_vlan_colors[id]

        # Go reserve a color that isn't already being used
        for color in vlan_colors:
            if color not in global_vlan_colors.values():
                global_vlan_colors[id] = color
                return color

        print("ERROR: Need more colors")
        pprint(global_vlan_colors)
        exit(1)

#----------------------------------------------------------------------------

class CiscoConfig(BaseSwitchConfig):
    def __init__(self, str):
        self.type = "Cisco"
        self.config = parse.ConfigIOS(str)
        super().__init__()

    #------------------------------------------------------------------------

    def _find_config_vlans(self):
        self.vlans = dict()
        lines = self.config.filter('interface Vlan.+')
        for line in lines:
            token = line.split()[1]
            match = re.search('Vlan(\d+)', token)
            id    = int(match.group(1))
            vlan  = {
                "id"          : id,
                "graph_color" : self.get_vlan_color(id),
            }

            try:
                result         = line.children.filter("ip address .+").one().split()
                vlan["ip"]     = result[2]
                netmask        = result[3]
                vlan["prefix"] = netmask_to_prefixlen(netmask)
            except:
                # It's ok if there is no IP address
                pass

            self.vlans[id] = vlan

    #------------------------------------------------------------------------

    def _find_config_port_channels(self):
        self.port_channels = dict()
        lines = self.config.filter('interface Port-channel.+')
        for line in lines:
            token = line.split()[1]
            match = re.search('Port-channel(\d+)', token)
            id    = int(match.group(1))
            pc    = {
                "id" : id,
            }

            for child in line.children:
                tokens = child.split()
                if tokens[0].lower() == 'description':
                    pc['description'] = ' '.join(tokens[1 :])
                elif child.startswith('switchport mode'):
                    pc['mode'] = tokens[2]
                elif child.startswith("switchport trunk allowed vlan"):
                    pc['trunk_vlans'] = parse_range(tokens[4])
                else:
                    # Skip everything else
                    pass

            self.port_channels[id] = pc

    #------------------------------------------------------------------------

    def _find_config_interfaces(self):

        def _get_thing(things, id, need_color=False):
            id = int(id)
            if id not in things:
                things[id] = {
                    "id" : id,
                }
                if need_color:
                    things[id]['graph_color'] = self.get_vlan_color(id)

            return things[id]

        self.interfaces = dict()
        lines = self.config.filter('interface .+')
        for line in lines:
            token = line.split()[1]
            speed = 1000
            match = re.match('GigabitEthernet(.+)', token)
            if not match:
                speed = 10000
                match = re.match("TenGigabitEthernet(.+)", token)
            if not match:
                speed = 100
                match = re.match("FastEthernet(.+)", token)
            if not match:
                continue

            id = match.group(1)

            interface = {
                "id"    : id,
                "speed" : speed,
            }
            for child in line.children:
                tokens = child.split()
                if tokens[0].lower() == 'description':
                    interface['description'] = ' '.join(tokens[1 :])

                elif child.startswith('switchport mode'):
                    interface['mode'] = tokens[2]
                elif child.startswith("switchport trunk allowed vlan"):
                    interface['trunk_vlans'] = list()
                    trunk_vlans = parse_range(tokens[4])
                    for vlan_id in trunk_vlans:
                        vlan = _get_thing(self.vlans, vlan_id, need_color=True)
                        interface['trunk_vlans'].append(vlan)
                elif child.startswith("switchport access vlan"):
                    vlan_id = int(tokens[3])
                    vlan = _get_thing(self.vlans, vlan_id, need_color=True)
                    interface['access_vlan'] = self.vlans[vlan_id]

                elif tokens[0].lower() == "channel-group":
                    channel_id = int(tokens[1])
                    pc = _get_thing(self.port_channels, channel_id)
                    interface['port-channel'] = pc

                else:
                    # Skip everything else
                    pass

                if tokens[0].lower() == "shutdown":
                    interface["shutdown"] = True

            self.interfaces[id] = interface

#----------------------------------------------------------------------------

class HPConfig(BaseSwitchConfig):
    def __init__(self, str):
        self.type = "HP"
        self.config = parse.ConfigIOS(str)
        super().__init__()

    #------------------------------------------------------------------------

    def _find_config_vlans(self):

        def _find_interfaces(line, str):
            try:
                result = line.children.filter(str).one().split()
                return parse_range(result[-1])
            except:
                # It is not an error if there are no children that
                # match this string
                return list()

        self.vlans = dict()
        lines = self.config.filter('vlan .+')
        for line in lines:
            id   = int(line.split()[1])
            vlan = {
                'id'          : id,
                "graph_color" : self.get_vlan_color(id),
            }

            try:
                result         = line.children.filter("ip address .+").one().split()
                vlan["ip"]     = result[2]
                netmask        = result[3]
                vlan["prefix"] = netmask_to_prefixlen(netmask)
            except:
                # It's ok if there is no IP address
                pass

            # Does this vlan have a name?
            # It will be surrounded in quotes
            try:
                result       = line.children.filter("name").one().split()
                vlan['name'] = result[2][1 : -1]
            except:
                pass

            # Find all interface IDs, too
            # (intentionally skipping "no untagged" in VLAN 1 -- see
            # https://community.hpe.com/t5/Switches-Hubs-and-Modems/VLAN-Tagging-confusion/td-p/4715581)
            vlan['tagged']   = _find_interfaces(line, "tagged .*")
            vlan['untagged'] = _find_interfaces(line, "untagged .*")

            self.vlans[id] = vlan

    #------------------------------------------------------------------------

    def _find_config_port_channels(self):
        self.port_channels = dict()

    #------------------------------------------------------------------------

    def _find_config_interfaces(self):
        def _get_interface(interfaces, id):
            sid = str(id)
            if sid not in interfaces:
                interfaces[sid] = {
                    "id" : id,
                }
            return interfaces[sid]

        interfaces = dict()

        # We previously found interfaces on the vlans
        for vlan in self.vlans.values():
            # If it is "untagged", that's an access VLAN on this interface
            for id in vlan['untagged']:
                interface = _get_interface(interfaces, id)
                interface["access_vlan"] = vlan

            # If it is "tagged", that's a trunk VLAN on this interface
            for id in vlan['tagged']:
                interface = _get_interface(interfaces, id)
                key = "trunk_vlans"
                if key not in interface:
                    interface[key] = list()
                interface[key].append(vlan)

        self.interfaces = interfaces

#----------------------------------------------------------------------------

def read_switches():
    switches = dict()
    for entry in files:
        print(f"=== READING SWITCH FILE {entry}")
        with open(entry['filename']) as f:
            # Read the lines into a giant string
            lines = f.readlines()
            str = ''.join(lines).strip()

            # Parse it according to the type
            if entry["type"] == "Cisco":
                switch = CiscoConfig(str)
            elif entry["type"] == "HP":
                switch = HPConfig(str)
            else:
                print("Errror: unknown file type {filename}"
                    .format(filename=entry['filename']))

            switch.set_location(entry['location'])
            switches[switch.get_hostname()] = switch

    return switches

#----------------------------------------------------------------------------

def read_aps():
    aps = dict()

    with open("aps.csv") as csvfile:
        reader = csv.reader(csvfile, dialect='excel')
        first = True
        for row in reader:
            # Skip first row
            # JMS There's probably a better way to do this...?
            if first:
                first = False
                continue

            switch = row[0]
            port   = row[1]
            ap     = row[2]

            # Skip blank rows

            if switch.strip() == '':
                continue

            if switch not in aps:
                aps[switch] = dict()

            aps[switch][port] = ap
            entry = {
                'switch' : switch,
                'port'   : port,
                'ap'     : ap,
            }

    # Output, mainly for debugging
    print("=== APs")
    pprint(aps)

    return aps

#----------------------------------------------------------------------------

def read_neighbors():
    def _linkit(switch_a, port_a, switch_b, port_b, neighbors):
        entry = {
            'source'      : switch_a,
            'source_port' : port_a,
            'peer'        : switch_b,
            'peer_port'   : port_b,
        }
        if switch_a not in neighbors:
            neighbors[switch_a] = dict()
        neighbors[switch_a][port_a] = entry

    neighbors = dict()
    with open("network-neighbors.csv") as csvfile:
        reader = csv.reader(csvfile, dialect='excel')
        first = True
        for row in reader:
            # Skip first row
            # JMS There's probably a better way to do this...?
            if first:
                first = False
                continue

            # Skip blank rows
            if row[0].strip() == '':
                continue

            _linkit(row[0], row[1], row[2], row[3], neighbors)
            _linkit(row[2], row[3], row[0], row[1], neighbors)

    # Output, mainly for debugging
    print("== Neighbors")
    pprint(neighbors)

    return neighbors

#----------------------------------------------------------------------------

def render_switch_interfaces(graph, switch):
    switch_id = switch.get_hostname()

    def _add_interface_node(graph, interface):
        kwargs = {
            "shape" : "square",
        }

        label = str(interface['id'])

        key = 'access_vlan'
        if key in interface:
            kwargs["style"] = "filled"
            kwargs["color"] = interface[key]['graph_color']

        key = 'shutdown'
        if key in interface and interface[key]:
            kwargs["style"] = "filled"
            kwargs["color"] = "red"
            kwargs['shape'] = 'octagon'

        kwargs['label'] = label

        graph.node(name=interface['graph_name'], **kwargs)

    # Make a unique graph name for each interface
    for interface_id, interface in switch.interfaces.items():
        name = "{hostname}-{port}".format(hostname=switch_id,
                                        port=interface_id)
        interface['graph_name'] = name

    # Add a node for each physical port that is not in a port channel
    for interface_id, interface in switch.interfaces.items():
        if 'port-channel' in interface:
            continue
        _add_interface_node(graph, interface)

    # Add a subgraph for each node port channel
    # In that subgraph, include a node for each interface in that
    # port channel.
    for pc_id, pc in switch.port_channels.items():
        pc_graph = None
        for i_id, interface in switch.interfaces.items():
            key = 'port-channel'
            if key not in interface:
                continue
            ipc = interface[key]
            if ipc['id'] != pc_id:
                continue

            # If we get here, this interface is in this port channel
            if pc_graph is None:
                name     = ('cluster_{hostname}_pc_{pc_name}'
                            .format(hostname=switch_id,
                                    pc_name=pc_id))
                body     = [ 'label = ""',
                             'style = "filled"',
                             'color = "lightgrey"' ]
                pc_graph = graphviz.Graph(name=name, body=body)

                pc['graph_name'] = name

            # Add a node for this interface to the port channel subgraph
            pc_graph.node(name=interface['graph_name'],
                        label=interface['id'],
                        shape='square')

        if pc_graph:
            graph.subgraph(pc_graph)

def render_switch_vlans(graph, switch):
    for vlan in switch.vlans.values():
        key = 'ip'
        if key in vlan:
            graph.node(str(vlan[key]),
                        style='filled', color='yellow')

def render_switch(graph, switch):
    hostname     = switch.get_hostname()
    # Need to override the "rounded" style from our location parent
    body         = [ ('label = "{type} {hostname}"'
                        .format(type=switch.get_type(),
                                hostname=hostname)),
                     'style = solid;' ]
    name         = "cluster_{hostname}".format(hostname=hostname)
    switch_graph = graphviz.Graph(body=body, name=name)

    switch.set_graph_name(name)

    # Render each VLAN on this switch
    render_switch_vlans(switch_graph, switch)

    # Render each interface on this switch
    render_switch_interfaces(switch_graph, switch)

    # Output, mainly for debugging purposes
    print(switch)

    graph.subgraph(switch_graph)

def render_locations(graph, switches):
    location_graphs = dict()

    for switch_id, switch in switches.items():
        location = switch.get_location()
        if location not in location_graphs:
            body = [ 'label ="Location: {l}"'.format(l=location),
                     'style = rounded;']
            name = 'cluster_{l}'.format(l=location)
            location_graphs[location] = graphviz.Graph(body=body, name=name)

        render_switch(location_graphs[location], switch)

    for location_graph in location_graphs.values():
        graph.subgraph(location_graph)

def render_aps(graph, switches, aps):
    # For each AP, find the corresponding graph name of the interface
    # to which it is connected
    for switch, ports in aps.items():
        for port, ap in ports.items():
            name = 'ap_{name}'.format(name=ap)
            graph.node(name=name, label=ap, shape='circle')
            port_graph_name = find_switch_interface(switches, switch, port)
            if port_graph_name is None:
                continue

            graph.edge(name, port_graph_name, color='green', style='bold')

def render_vlans(graph):
    # Make a subgraph to show the color code for the vlans
    body = [ 'label = "VLAN colors"' ]
    vgraph = graphviz.Graph(name="cluster_vlans", body=body)
    for vlan, color in global_vlan_colors.items():
        vgraph.node(name=str(vlan), style="filled", color=color,
                    shape="square")

    pprint(global_vlan_colors)

    graph.subgraph(vgraph)

def find_switch_interface(switches, target_switch_name, target_interface_name):
    tsname = target_switch_name.lower()
    tiname = target_interface_name.lower()

    for sname, switch in switches.items():
        if sname.lower() != tsname:
            continue

        for iname, interface in switch.interfaces.items():
            if iname.lower() == tiname:
                # FOUND
                return interface['graph_name']

    print("WARNING: Did not find graph name for switch {s}, interface {i}"
        .format(s=target_switch_name, i=target_interface_name))
    return None

def render_neighbors(graph, switches, neighbors):
    # For each neighbor pair, find the corresponding graph names
    # Note that both A->B and B->A are in neighbors.  Only make one graphiz edge for each pair.
    for source in neighbors:
        for source_port in neighbors[source]:
            entry = neighbors[source][source_port]
            peer  = neighbors[entry['peer']][entry['peer_port']]

            # Did we already render this (in the other direction?)
            if 'rendered' in peer:
                entry['rendered'] = True
                continue

            source_interface = find_switch_interface(switches, source,
                                    source_port)
            peer_interface   = find_switch_interface(switches, entry['peer'],
                                    entry['peer_port'])

            if source_interface is None or peer_interface is None:
                continue

            graph.edge(source_interface, peer_interface, color='blue')
            entry['rendered'] = True

def render(switches, aps, neighbors):
    name  = "mercy"
    graph = graphviz.Graph(name=name, engine="fdp")

    graph.attr("graph", overlap="False")
    graph.attr("graph", splines="polyline")

    render_locations(graph, switches)
    render_vlans(graph)
    render_aps(graph, switches, aps)
    render_neighbors(graph, switches, neighbors)

    graph.save("mercy.dot")
    graph.render("mercy", view=False)

#----------------------------------------------------------------------------
# main
#----------------------------------------------------------------------------

def main():
    switches  = read_switches()
    print("=== DONE READING SWITCHES")
    # JMS skip including the APs for now
    #aps       = read_aps()
    aps       = dict()
    neighbors = read_neighbors()

    render(switches, aps, neighbors)

if __name__ == '__main__':
    main()
