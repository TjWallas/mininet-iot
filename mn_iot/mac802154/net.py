"""
    Mininet-WiFi: A simple networking testbed for Wireless OpenFlow/SDWN!
    author: Ramon Fontes (ramonrf@dca.fee.unicamp.br)"""


import os
import socket
import re
from sys import version_info as py_version_info
from threading import Thread as thread

from time import sleep
from itertools import chain, groupby
from six import string_types

from mn_wifi.net import Mininet_wifi
from mn_wifi.node import Station, Car, AP, OVSKernelAP
from mn_wifi.link import TCWirelessLink, mesh, physicalMesh, adhoc, \
    ITSLink, wifiDirectLink, physicalWifiDirectLink, _4address, wmediumd
from mn_wifi.wmediumdConnector import snr, error_prob, interference
from mn_wifi.plot import plot2d, plot3d, plotGraph
from mn_wifi.mobility import mobility as mob, tracked as trackedMob
from mn_wifi.clean import Cleanup as cleanup_mnwifi
from mn_wifi.propagationModels import propagationModel
from mn_wifi.energy import Energy

from mininet.term import cleanUpScreens, makeTerms
from mininet.util import (numCores, macColonHex, waitListening)
from mininet.link import Intf, TCLink, TCULink
from mininet.log import info, error, debug, output
from mininet.node import (Host, OVSKernelSwitch,
                          DefaultController)

from mn_iot.mac802154.clean import Cleanup as cleanup_mniot
from mn_iot.mac802154.mobility import Mobility as mobSensor
from mn_iot.mac802154.util import ipAdd6, netParse
from mn_iot.mac802154.node import Sixlowpan
from mn_iot.mac802154.module import module
from mn_iot.mac802154.link import SixLowpan as SixLowpanLink

VERSION = "1.0"


class Mininet_iot(Mininet_wifi):

    def __init__(self, topo=None, switch=OVSKernelSwitch,
                 accessPoint=OVSKernelAP, host=Host, station=Station,
                 car=Car, sensor=Sixlowpan, controller=DefaultController,
                 link=TCWirelessLink, intf=Intf, build=True, xterms=False,
                 cleanup=False, ipBase='2001:0:0:0:0:0:0:0/64', inNamespace=False,
                 autoSetMacs=False, autoStaticArp=False, autoPinCpus=False,
                 listenPort=None, waitConnected=False, ssid="new-ssid",
                 mode="g", channel=1, wmediumd_mode=snr,
                 fading_coefficient=0, autoAssociation=True,
                 allAutoAssociation=True, driver='nl80211',
                 autoSetPositions=False, configureWiFiDirect=False,
                 configure4addr=False, noise_threshold=-91, cca_threshold=-90,
                 disable_tcp_checksum=False, ifb=False,
                 bridge=False, plot=False, plot3d=False, docker=False,
                 container='mininet-iot', ssh_user='alpha', sixlp=False,
                 set_socket_ip=None, set_socket_port=12345):

        self.topo = topo
        self.switch = switch
        self.host = host
        self.station = station
        self.sensor = sensor
        self.accessPoint = accessPoint
        self.car = car
        self.controller = controller
        self.sixlp = sixlp
        self.link = link
        self.intf = intf
        self.cleanup = cleanup
        self.ipBase = '2001:0:0:0:0:0:0:0/64'
        self.inNamespace = False
        self.autoSetMacs = False
        self.autoStaticArp = False
        self.autoPinCpus = False
        self.listenPort = None
        self.waitConnected = False
        self.autoSetPositions = False
        self.built = False
        self.wmediumd_started = False
        self.mob_check = False
        self.isVanet = False
        self.alt_module = None
        self.draw = False
        self.ppm_is_set = False
        self.isReplaying = False
        self.docker = docker
        self.container = container
        self.ssh_user = ssh_user
        self.ifb = ifb  # Support to Intermediate Functional Block (IFB) Devices
        self.driver = driver
        self.bridge = bridge
        self.set_socket_ip = set_socket_ip
        self.set_socket_port = set_socket_port
        self.init_plot = plot
        self.init_plot3d = plot3d
        self.waitConn = waitConnected
        self.xterms = xterms
        self.autoSetMacs = autoSetMacs
        self.autoSetPositions = autoSetPositions
        self.autoStaticArp = autoStaticArp
        self.autoPinCpus = autoPinCpus
        self.configureWiFiDirect = configureWiFiDirect
        self.configure4addr = configure4addr
        self.wmediumd_mode = wmediumd_mode
        self.fading_coefficient = fading_coefficient
        self.noise_threshold = noise_threshold
        self.cca_threshold = cca_threshold
        self.autoAssociation = autoAssociation  # does not include mobility
        self.allAutoAssociation = allAutoAssociation  # includes mobility
        self.ipBaseNum, self.prefixLen = netParse(self.ipBase)
        self.nextPosition = 1
        self.disable_tcp_checksum = disable_tcp_checksum
        self.inNamespace = inNamespace
        self.plot = plot2d
        self.numCores = numCores()
        self.nextIP = 1  # start for address allocation
        self.nextCore = 0  # next core for pinning hosts to CPUs
        self.nameToNode = {}  # name to Node (Host/Switch) objects
        self.mob_param = {}
        self.links = []
        self.aps = []
        self.controllers = []
        self.hosts = []
        self.cars = []
        self.switches = []
        self.stations = []
        self.sensors = []
        self.sixLP = []
        self.terms = []  # list of spawned xterm processes
        self.n_wifs = 0
        self.roads = 0
        self.connections = {}
        self.seed = 1
        self.n_radios = 0
        self.min_v = 1
        self.max_v = 10
        self.min_x = 0
        self.min_y = 0
        self.min_z = 0
        self.max_x = 100
        self.max_y = 100
        self.max_z = 0
        self.conn = {}
        self.wlinks = []
        Mininet_iot.init()  # Initialize Mininet-IoT if necessary

        if self.set_socket_ip:
            self.server()

        if autoSetPositions and link == wmediumd:
            self.wmediumd_mode = interference

        if not allAutoAssociation:
            self.autoAssociation = False
            mob.allAutoAssociation = False

        self.built = False
        if topo and build:
            self.build()

    def server(self):
        thread(target=self.start_socket).start()

    def start_socket(self):
        host = self.set_socket_ip
        port, cleanup_mnwifi.socket_port = self.set_socket_port, self.set_socket_port

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)

        while True:
            conn, addr = s.accept()
            try:
                thread(target=self.get_socket_data, args=(conn, addr)).start()
            except:
                print("Thread did not start.\n")

    def get_socket_data(self, conn, addr):
        while True:
            try:
                data = conn.recv(1024).decode('utf-8').split('.')
                if data[0] == 'set':
                    node = self.getNodeByName(data[1])
                    if len(data) < 4:
                        data = 'usage: set.node.method.value'
                    else:
                        if hasattr(node, data[2]):
                            method_to_call = getattr(node, data[2])
                            method_to_call(data[3])
                            data = 'command accepted!'
                        else:
                            data = 'unrecognized method!'
                elif data[0] == 'get':
                    node = self.getNodeByName(data[1])
                    if len(data) < 3:
                        data = 'usage: get.node.param'
                    else:
                        data = node.params[data[2]]
                else:
                    data = 'unrecognized option %s:' % data[0]
                conn.send(str(data).encode('utf-8'))
                break
            except:
                conn.close()

    def addParameters(self, node, node_mode='managed', **params):
        """adds parameters to wireless nodes
        node: node
        autoSetMacs: set MAC addrs automatically like IP addresses
        params: parameters
        defaults: Default IP and MAC addresses
        node_mode: if interface is running in managed or master mode"""
        node.params['wlan'] = []
        node.params['range'] = []
        node.wpanPhyID = []

        wifs = self.count6LoWPANIfaces(**params)

        for wif in range(wifs):
            self.addParamsToNode(node)
            if node_mode == 'managed':
                self.appendAssociatedTo(node)
                self.add_ip_param(node, wifs, **params)
            self.add_mac_param(node, wifs, **params)
            node.params['range'].append(100)
            node.params['wlan'].append(node.name + '-wpan' + str(wif))
            node.params.pop("wifs", None)

        # position
        if 'position' in params:
            pos = params['position']
            if isinstance(pos, string_types):
                pos = pos.split(',')
            self.pos_to_array(node, pos)
        else:
            if 'position' in node.params:
                pos = node.params['position']
                self.pos_to_array(node, pos)

        array_ = ['antennaGain', 'antennaHeight', 'txpower',
                  'channel', 'mode', 'freq']
        for param in array_:
            node.params[param] = []
            if param in params:
                if isinstance(params[param], int):
                    params[param] = str(params[param])
                list = params[param].split(',')
                for value in list:
                    if param == 'mode' or param == 'channel':
                        node.params[param].append(value)
                    else:
                        node.params[param].append(float(value))
                len_ = len(node.params[param])
                if len != params['wifs']:
                    for _ in range(params['wifs'] - len_):
                        node.params[param].append(value)
            else:
                params['wifs'] = 1
                for _ in range(params['wifs']):
                    if param == 'antennaGain':
                        value = 5.0
                    if param == 'antennaHeight':
                        value = 1.0
                    if param == 'txpower':
                        value = 14
                    if param == 'channel':
                        value = 1
                    if param == 'mode':
                        value = 'g'
                    if param == 'freq':
                        value = 2.412
                    node.params[param].append(value)
            node.params['lqi'] = {}

    def add_mac_param(self, node, wifs, autoSetMacs=False, **params):
        "Add IP Param"
        node.params['mac'] = []
        if 'mac' in params:
            ip_list = params['mac'].split(',')
            for ip in ip_list:
                node.params['mac'].append(ip)
            if len(ip_list) != len(node.params['wlan']):
                for ip_list in range(len(ip_list),
                                     len(node.params['wlan'])):
                    node.params['mac'].append('')
        elif autoSetMacs:
            for n in range(wifs):
                node.params['mac'].append('')
                node.params['mac'][n] = params['mac']
        else:
            for _ in range(wifs):
                node.params['mac'].append('')

    def add_ip_param(self, node, wifs, autoSetMacs=False, **params):
        "Add IP Param"
        node.params['wlan_ip'] = []
        if 'wlan_ip' in params:
            ip_list = params['wlan_ip'].split(',')
            for ip in ip_list:
                node.params['wlan_ip'].append(ip)
            if len(ip_list) != len(node.params['wlan']):
                for ip_list in range(len(ip_list),
                                     len(node.params['wlan'])):
                    node.params['wlan_ip'].append('0/0')
        elif autoSetMacs:
            for n in range(wifs):
                node.params['wlan_ip'].append('0/0')
                node.params['wlan_ip'][n] = params['wlan_ip']
        else:
            for _ in range(wifs):
                node.params['wlan_ip'].append('')

    def pos_to_array(self, node, pos):
        if isinstance(pos, string_types):
            pos = pos.split(',')
        node.params['position'] = [float(pos[0]),
                                   float(pos[1]),
                                   float(pos[2])]

    def appendAssociatedTo(self, node):
        "Add associatedTo param"
        node.params['associatedTo'].append('')

    def configureMacAddr(self, node):
        """Configure Mac Address

        :param node: node"""
        for wlan in range(0, len(node.params['wlan'])):
            iface = node.params['wlan'][wlan]
            if node.params['mac'][wlan] == '':
                node.params['mac'][wlan] = node.getMAC(iface)
            else:
                mac = node.params['mac'][wlan]
                node.setMAC(mac, iface)

    def addSensor(self, name, cls=None, **params):
        """Add Sensor node.
           name: name of station to add
           cls: custom 6LoWPAN class/constructor (optional)
           params: parameters for 6LoWPAN
           returns: added station"""
        # Default IP and MAC addresses
        defaults = {'wlan_ip': ipAdd6(self.nextIP,
                                     ipBaseNum=self.ipBaseNum,
                                     prefixLen=self.prefixLen) +
                          '/%s' % self.prefixLen
                   }
        if 'ip' in params:
            params['wlan_ip'] = params['ip']
        defaults.update(params)

        if self.autoSetPositions:
            defaults['position'] = ('%s,0,0' % self.nextPosition)
        if self.autoSetMacs:
            defaults['mac'] = macColonHex(self.nextIP)
        if self.autoPinCpus:
            defaults['cores'] = self.nextCore
            self.nextCore = (self.nextCore + 1) % self.numCores
        self.nextIP += 1
        self.nextPosition += 1

        if not cls:
            cls = self.sensor
        node = cls(name, **defaults)

        self.addParameters(node, defaults, **params)

        self.sensors.append(node)
        self.nameToNode[name] = node

        return node

    # BL: We now have four ways to look up nodes
    # This may (should?) be cleaned up in the future.
    def getNodeByName(self, *args):
        "Return node(s) with given name(s)"
        if len(args) is 1:
            return self.nameToNode[args[0]]
        return [self.nameToNode[n] for n in args]

    def get(self, *args):
        "Convenience alias for getNodeByName"
        return self.getNodeByName(*args)

    # Even more convenient syntax for node lookup and iteration
    def __getitem__(self, key):
        "net[ name ] operator: Return node with given name"
        return self.nameToNode[key]

    def __delitem__(self, key):
        "del net[ name ] operator - delete node with given name"
        self.delNode(self.nameToNode[key])

    def __contains__(self, item):
        "returns True if net contains named node"
        return item in self.nameToNode

    def keys(self):
        "return a list of all node names or net's keys"
        return list(self)

    def values(self):
        "return a list of all nodes or net's values"
        return [self[name] for name in self]

    def items(self):
        "return (key,value) tuple list for every node in net"
        return zip(self.keys(), self.values())

    def buildFrom6lowpanTopo(self, topo=None):
        """Build mininet-iot from a topology object
           At the end of this function, everything should be connected
           and up."""
        info('*** Adding nodes:\n')
        for sensorName in topo.sensors():
            if sensorName:
                self.addSensor(sensorName, **topo.nodeInfo(sensorName))
                info(sensorName + ' ')

        info('\n*** Configuring 6lowpan nodes...\n')
        self.configureWifiNodes()

        info('\n*** Adding link(s):\n')
        for srcName, params in topo.links(
                sort=True, withInfo=True):
            self.addLink(**params)
            info('(%s) ' % (srcName))
        info('\n')

    def addLink(self, node1, node2=None, port1=None, port2=None,
                cls=None, **params):
        """"Add a link from node1 to node2
            node1: source node (or name)
            node2: dest node (or name)
            port1: source port (optional)
            port2: dest port (optional)
            cls: link class (optional)
            params: additional link params (optional)
            returns: link object"""
        # Accept node objects or names
        node1 = node1 if not isinstance(node1, string_types) else self[node1]
        node2 = node2 if not isinstance(node2, string_types) else self[node2]
        options = dict(params)

        self.conn.setdefault('src', [])
        self.conn.setdefault('dst', [])
        self.conn.setdefault('ls', [])

        cls = self.link if cls is None else cls

        modes = [mesh, physicalMesh, adhoc, ITSLink,
                 wifiDirectLink, physicalWifiDirectLink]
        if cls in modes:
            cls(node=node1, **params)
        elif cls == SixLowpanLink:
            link = cls(node=node1, port=port1, **params)
            self.links.append(link)
            return link
        elif cls == _4address:
            if 'position' in node1.params and 'position' in node2.params:
                self.conn['src'].append(node1)
                self.conn['dst'].append(node2)
                self.conn['ls'].append('--')

            if node1 not in self.aps:
                self.aps.append(node1)
            elif node2 not in self.aps:
                self.aps.append(node2)

            if self.wmediumd_mode == interference:
                link = cls(node1, node2, port1, port2)
                self.links.append(link)
                return link
            else:
                dist = node1.get_distance_to(node2)
                if dist <= node1.params['range'][0]:
                    link = cls(node1, node2)
                    self.links.append(link)
                    return link
        elif ((node1 in (self.stations or self.cars) and node2 in self.aps)
              or (node2 in (self.stations or self.cars) and node1 in self.aps)) and \
                'link' not in options:
            self.infraAssociation(node1, node2, port1, port2, cls, **params)
        elif 'wifi' in params:
            self.infraAssociation(node1, node2, port1, port2, cls, **params)
        else:
            if 'link' in options:
                options.pop('link', None)

            if 'position' in node1.params and 'position' in node2.params:
                self.conn['src'].append(node1)
                self.conn['dst'].append(node2)
                self.conn['ls'].append('-')
            # Port is optional
            if port1 is not None:
                options.setdefault('port1', port1)
            if port2 is not None:
                options.setdefault('port2', port2)

            # Set default MAC - this should probably be in Link
            options.setdefault('addr1', self.randMac())
            options.setdefault('addr2', self.randMac())

            if not cls or cls == wmediumd or cls == TCWirelessLink:
                cls = TCLink
            if self.disable_tcp_checksum:
                cls = TCULink

            cls = self.link if cls is None else cls
            link = cls(node1, node2, **options)
            self.links.append(link)
            return link

    def startTerms(self):
        "Start a terminal for each node."
        if 'DISPLAY' not in os.environ:
            error("Error starting terms: Cannot connect to display\n")
            return
        info("*** Running terms on %s\n" % os.environ['DISPLAY'])
        cleanUpScreens()
        self.terms += makeTerms(self.controllers, 'controller')
        self.terms += makeTerms(self.switches, 'switch')
        self.terms += makeTerms(self.hosts, 'host')
        self.terms += makeTerms(self.stations, 'station')
        self.terms += makeTerms(self.aps, 'ap')
        self.terms += makeTerms(self.sensors, 'sixLP')

    def checkDimension(self, nodes):
        try:
            for node in nodes:
                if hasattr(node, 'coord'):
                    node.params['position'] = node.coord[0].split(',')
            plotGraph(min_x=self.min_x, min_y=self.min_y, min_z=self.min_z,
                      max_x=self.max_x, max_y=self.max_y, max_z=self.max_z,
                      nodes=nodes, conn=self.conn)
            if not issubclass(self.plot, plot3d):
                self.plot.pause()
        except:
            info('Something went wrong with the GUI.\n')
            self.draw = False

    def plotCheck(self, plotNodes):
        "Check which nodes will be plotted"
        nodes = self.stations + self.aps + plotNodes + self.cars + \
                self.sensors
        self.checkDimension(nodes)

    def plot_dynamic(self):
        "Check which nodes will be plotted dynamically at runtime"
        nodes = self.stations + self.aps + self.cars + \
                self.sensors
        self.checkDimension(nodes)

        while True:
            for node in nodes:
                intf = node.params['wlan'][0]
                node.params['range'][0] = node.getRange(intf=intf)
                if self.draw:
                    if not issubclass(self.plot, plot3d):
                        self.plot.updateCircleRadius(node)
                    self.plot.update(node)
            self.plot.pause()
            sleep(0.5)

    def plotGraph(self, **kwargs):
        "Plots Graph"
        self.draw = True
        for key in kwargs:
            setattr(self, key, kwargs[key])
        if 'max_z' in kwargs and kwargs['max_z'] != 0:
            self.plot = plot3d
        cleanup_mnwifi.plot = self.plot

    def check_if_mob(self):
        if self.mob_param:
            if 'model' in self.mob_param or self.isVanet or self.nroads != 0:
                self.mob_param['nodes'] = self.getMobileNodes()
                self.start_mobility(**self.mob_param)
            else:
                self.mob_param['plotNodes'] = self.plot_nodes()
                trackedMob(**self.mob_param)
            self.mob_check = True
        else:
            if self.draw and not self.isReplaying:
                plotNodes = self.plot_nodes()
                self.plotCheck(plotNodes)

    def build(self):
        "Build mininet-wifi."
        if self.topo:
            if self.sixlp:
                self.buildFrom6lowpanTopo(self.topo)
            else:
                self.buildFromWirelessTopo(self.topo)
                if self.init_plot or self.init_plot3d:
                    max_z = 0
                    if self.init_plot3d:
                        max_z = len(self.stations) * 100
                    self.plotGraph(max_x=(len(self.stations) * 100),
                                   max_y=(len(self.stations) * 100),
                                   max_z=max_z)
        else:
            if not mob.stations:
                for node in self.stations:
                    if 'position' in node.params:
                        mob.stations.append(node)
            if self.sensors and not mobSensor.sensors:
                for node in self.sensors:
                    if 'position' in node.params:
                        mobSensor.sensors.append(node)

        if not self.wmediumd_started:
            self.init_wmediumd()

        if self.inNamespace:
            self.configureControlNetwork()
        info('*** Configuring nodes\n')
        self.configHosts()
        if self.xterms:
            self.startTerms()
        if self.autoStaticArp:
            self.staticArp()

        for node in self.stations:
            for wif in range(0, len(node.params['wlan'])):
                if not isinstance(node, AP) and node.func[0] != 'ap' and \
                        node.func[wif] != 'mesh' and \
                        node.func[wif] != 'adhoc' and \
                        node.func[wif] != 'wifiDirect':
                    if isinstance(node, Station):
                        node.params['range'][wif] = \
                            int(node.params['range'][wif]) / 5

        if self.allAutoAssociation:
            if self.autoAssociation and not self.configureWiFiDirect:
                self.auto_association()
        if not self.mob_check:
            self.check_if_mob()

        nodes = self.stations + self.aps + self.cars + self.sensors
        battery_nodes = []
        for node in nodes:
            if 'battery' in node.params:
                battery_nodes.append(node)
        if battery_nodes:
            Energy(battery_nodes)

        self.built = True

    def __iter__(self):
        "return iterator over node names"
        for node in chain(self.hosts, self.switches, self.controllers,
                          self.stations, self.cars, self.aps, self.sensors):
            yield node.name

    def __len__(self):
        "returns number of nodes in net"
        return (len(self.hosts) + len(self.switches) +
                len(self.controllers) + len(self.stations) +
                len(self.cars) + len(self.aps) +
                len(self.sensors))

    def stop(self):
        'Stop Mininet-WiFi'
        self.stopGraphParams()
        info('*** Stopping %i controllers\n' % len(self.controllers))
        for controller in self.controllers:
            info(controller.name + ' ')
            controller.stop()
        info('\n')
        if self.terms:
            info('*** Stopping %i terms\n' % len(self.terms))
            self.stopXterms()
        info('*** Stopping %i links\n' % len(self.links))
        for link in self.links:
            info('.')
            link.stop()
        info('\n')
        info('*** Stopping switches/access points\n')
        stopped = {}
        nodesL2 = self.switches + self.aps
        if py_version_info < (3, 0):
            for swclass, switches in groupby(
                    sorted(nodesL2, key=type), type):
                switches = tuple(switches)
                if hasattr(swclass, 'batchShutdown'):
                    success = swclass.batchShutdown(switches)
                    stopped.update({s: s for s in success})
        else:
            for swclass, switches in groupby(
                    sorted(nodesL2, key=lambda x: str(type(x))), type):
                switches = tuple(switches)
                if hasattr(swclass, 'batchShutdown'):
                    success = swclass.batchShutdown(switches)
                    stopped.update({s: s for s in success})
        for switch in nodesL2:
            info(switch.name + ' ')
            if switch not in stopped:
                switch.stop()
            switch.terminate()
        info('\n')
        info('*** Stopping nodes\n')
        nodes = self.hosts + self.stations + self.sensors
        for node in nodes:
            info(node.name + ' ')
            node.terminate()
        info('\n')
        self.closeMininetIoT()
        info('\n*** Done\n')

    def start(self):
        "Start controller and switches."
        if not self.built:
            self.build()

        if not self.mob_check:
            self.check_if_mob()

        if not self.sixlp:
            info('*** Starting controller(s)\n')
            for controller in self.controllers:
                info(controller.name + ' ')
                controller.start()
            info('\n')

            info('*** Starting switches and/or access points\n')
            nodesL2 = self.switches + self.aps
            for nodeL2 in nodesL2:
                info(nodeL2.name + ' ')
                nodeL2.start(self.controllers)

            started = {}
            if py_version_info < (3, 0):
                for swclass, switches in groupby(
                        sorted(nodesL2, key=type), type):
                    switches = tuple(switches)
                    if hasattr(swclass, 'batchStartup'):
                        success = swclass.batchStartup(switches)
                        started.update({s: s for s in success})
            else:
                for swclass, switches in groupby(
                        sorted(nodesL2, key=lambda x: str(type(x))), type):
                    switches = tuple(switches)
                    if hasattr(swclass, 'batchStartup'):
                        success = swclass.batchStartup(switches)
                        started.update({s: s for s in success})
        info('\n')
        if self.waitConn:
            self.waitConnected()

    def configureWmediumd(self):
        "Configure Wmediumd"
        if self.autoSetPositions:
            self.wmediumd_mode = interference
        self.wmediumd_mode()

        if not self.configureWiFiDirect and not self.configure4addr and \
                self.wmediumd_mode != error_prob:
            wmediumd(self.fading_coefficient, self.noise_threshold,
                     self.stations, self.aps, self.cars, self.sensors,
                     propagationModel, self.wmediumdMac)

    def init_wmediumd(self):
        if (
                self.configure4addr or self.configureWiFiDirect or
                self.wmediumd_mode == error_prob) and self.link == wmediumd:
            wmediumd(self.fading_coefficient, self.noise_threshold,
                     self.stations, self.aps, self.cars, self.sensors,
                     propagationModel, self.wmediumdMac)
            for sta in self.stations:
                if self.wmediumd_mode != error_prob:
                    sta.set_pos_wmediumd(sta.params['position'])
            for sta in self.stations:
                if sta in self.aps:
                    self.stations.remove(sta)
        self.wmediumd_started = True

    @staticmethod
    def _parsePing(pingOutput):
        "Parse ping output and return packets sent, received."
        # Check for downed link
        if 'connect: Network is unreachable' in pingOutput:
            return 1, 0
        r = r'(\d+) packets transmitted, (\d+)( packets)? received'
        m = re.search(r, pingOutput)
        if m is None:
            error('*** Error: could not parse ping output: %s\n' %
                  pingOutput)
            return 1, 0
        sent, received = int(m.group(1)), int(m.group(2))
        return sent, received

    @classmethod
    def ping6(self, hosts=None, timeout=None):
        """Ping6 between all specified hosts.
           hosts: list of hosts
           timeout: time to wait for a response, as string
           returns: ploss packet loss percentage"""
        # should we check if running?
        packets = 0
        lost = 0
        ploss = None
        if not hosts:
            hosts = self.sensors
            output('*** Ping: testing ping reachability\n')
        for node in hosts:
            output('%s -> ' % node.name)
            for dest in hosts:
                if node != dest:
                    opts = ''
                    if timeout:
                        opts = '-W %s' % timeout
                    if dest.intfs:
                        result = node.cmdPrint('ping6 -c1 %s %s'
                                               % (opts, dest.IP()))
                        sent, received = self._parsePing(result)
                    else:
                        sent, received = 0, 0
                    packets += sent
                    if received > sent:
                        error('*** Error: received too many packets')
                        error('%s' % result)
                        node.cmdPrint('route')
                        exit(1)
                    lost += sent - received
                    output(('%s ' % dest.name) if received else 'X ')
            output('\n')
        if packets > 0:
            ploss = 100.0 * lost / packets
            received = packets - lost
            output("*** Results: %i%% dropped (%d/%d received)\n" %
                   (ploss, received, packets))
        else:
            ploss = 0
            output("*** Warning: No packets sent\n")
        return ploss

    @staticmethod
    def _parseFull(pingOutput):
        "Parse ping output and return all data."
        errorTuple = (1, 0, 0, 0, 0, 0)
        # Check for downed link
        r = r'[uU]nreachable'
        m = re.search(r, pingOutput)
        if m is not None:
            return errorTuple
        r = r'(\d+) packets transmitted, (\d+)( packets)? received'
        m = re.search(r, pingOutput)
        if m is None:
            error('*** Error: could not parse ping output: %s\n' %
                  pingOutput)
            return errorTuple
        sent, received = int(m.group(1)), int(m.group(2))
        r = r'rtt min/avg/max/mdev = '
        r += r'(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms'
        m = re.search(r, pingOutput)
        if m is None:
            if received is 0:
                return errorTuple
            error('*** Error: could not parse ping output: %s\n' %
                  pingOutput)
            return errorTuple
        rttmin = float(m.group(1))
        rttavg = float(m.group(2))
        rttmax = float(m.group(3))
        rttdev = float(m.group(4))
        return sent, received, rttmin, rttavg, rttmax, rttdev

    def pingFull(self, hosts=None, timeout=None):
        """Ping between all specified hosts and return all data.
           hosts: list of hosts
           timeout: time to wait for a response, as string
           returns: all ping data; see function body."""
        # should we check if running?
        # Each value is a tuple: (src, dsd, [all ping outputs])
        all_outputs = []
        if not hosts:
            hosts = self.hosts
            output('*** Ping: testing ping reachability\n')
        for node in hosts:
            output('%s -> ' % node.name)
            for dest in hosts:
                if node != dest:
                    opts = ''
                    if timeout:
                        opts = '-W %s' % timeout
                    result = node.cmd('ping -c1 %s %s' % (opts, dest.IP()))
                    outputs = self._parsePingFull(result)
                    sent, received, rttmin, rttavg, rttmax, rttdev = outputs
                    all_outputs.append((node, dest, outputs))
                    output(('%s ' % dest.name) if received else 'X ')
            output('\n')
        output("*** Results: \n")
        for outputs in all_outputs:
            src, dest, ping_outputs = outputs
            sent, received, rttmin, rttavg, rttmax, rttdev = ping_outputs
            output(" %s->%s: %s/%s, " % (src, dest, sent, received))
            output("rtt min/avg/max/mdev %0.3f/%0.3f/%0.3f/%0.3f ms\n" %
                   (rttmin, rttavg, rttmax, rttdev))
        return all_outputs

    def pingAll(self, timeout=None):
        """Ping between all hosts.
           returns: ploss packet loss percentage"""
        return self.ping6(timeout=timeout)

    @staticmethod
    def _parseIperf(iperfOutput):
        """Parse iperf output and return bandwidth.
           iperfOutput: string
           returns: result string"""
        r = r'([\d\.]+ \w+/sec)'
        m = re.findall(r, iperfOutput)
        if m:
            return m[-1]
        else:
            # was: raise Exception(...)
            error('could not parse iperf output: ' + iperfOutput)
            return ''

    def iperf(self, hosts=None, l4Type='TCP', udpBw='10M', fmt=None,
              seconds=5, port=5001):
        """Run iperf between two hosts.
           hosts: list of hosts; if None, uses first and last hosts
           l4Type: string, one of [ TCP, UDP ]
           udpBw: bandwidth target for UDP test
           fmt: iperf format argument if any
           seconds: iperf time to transmit
           port: iperf port
           returns: two-element array of [ server, client ] speeds
           note: send() is buffered, so client rate can be much higher than
           the actual transmission rate; on an unloaded system, server
           rate should be much closer to the actual receive rate"""
        sleep(2)
        nodes = self.sensors
        hosts = hosts or [nodes[0], nodes[-1]]
        assert len(hosts) is 2
        client, server = hosts
        output('*** Iperf: testing', l4Type, 'bandwidth between',
               client, 'and', server, '\n')
        server.cmd('killall -9 iperf')
        iperfArgs = 'iperf -p %d ' % port
        bwArgs = ''
        if l4Type is 'UDP':
            iperfArgs += '-u '
            bwArgs = '-b ' + udpBw + ' '
        elif l4Type != 'TCP':
            raise Exception('Unexpected l4 type: %s' % l4Type)
        if fmt:
            iperfArgs += '-f %s ' % fmt
        server.sendCmd(iperfArgs + '-s')
        if l4Type is 'TCP':
            if not waitListening(client, server.IP(), port):
                raise Exception('Could not connect to iperf on port %d'
                                % port)
        cliout = client.cmd(iperfArgs + '-t %d -c ' % seconds +
                            server.IP() + ' ' + bwArgs)
        debug('Client output: %s\n' % cliout)
        servout = ''
        # We want the last *b/sec from the iperf server output
        # for TCP, there are two of them because of waitListening
        count = 2 if l4Type is 'TCP' else 1
        while len(re.findall('/sec', servout)) < count:
            servout += server.monitor(timeoutms=5000)
        server.sendInt()
        servout += server.waitOutput()
        debug('Server output: %s\n' % servout)
        result = [self._parseIperf(servout), self._parseIperf(cliout)]
        if l4Type is 'UDP':
            result.insert(0, udpBw)
        output('*** Results: %s\n' % result)
        return result

    @classmethod
    def closeMininetIoT(self):
        "Close Mininet-WiFi"
        cleanup_mniot()

    def addParamsToNode(self, node):
        "Add func and wpanPhyID"
        node.func.append('none')
        node.wpanPhyID.append(0)

    def count6LoWPANIfaces(self, **params):
        "Count the number of virtual 6LoWPAN interfaces"
        if 'wifs' in params:
            self.n_wifs += int(params['wifs'])
            wifs = int(params['wifs'])
        else:
            wifs = 1
            self.n_wifs += 1
        return wifs

    def kill_fakelb(self):
        "Kill fakelb"
        module.fakelb()
        sleep(0.1)

    def configureIface(self, node, wlan):
        intf = module.wlan_list[0]
        module.wlan_list.pop(0)
        node.renameIface(intf, node.params['wlan'][wlan])

    def closeMininetWiFi(self):
        "Close Mininet-WiFi"
        module.stop()


class MininetWithControlIOTNet(Mininet_iot):
    """Control network support:
       Create an explicit control network. Currently this is only
       used/usable with the user datapath.
       Notes:
       1. If the controller and switches are in the same (e.g. root)
          namespace, they can just use the loopback connection.
       2. If we can get unix domain sockets to work, we can use them
          instead of an explicit control network.
       3. Instead of routing, we could bridge or use 'in-band' control.
       4. Even if we dispense with this in general, it could still be
          useful for people who wish to simulate a separate control
          network (since real networks may need one!)
       5. Basically nobody ever used this code, so it has been moved
          into its own class.
       6. Ultimately we may wish to extend this to allow us to create a
          control network which every node's control interface is
          attached to."""

    def configureControlNetwork(self):
        "Configure control network."
        self.configureRoutedControlNetwork()

    # We still need to figure out the right way to pass
    # in the control network location.

    def configureRoutedControlNetwork(self, ip='192.168.123.1',
                                      prefixLen=16):
        """Configure a routed control network on controller and switches.
           For use with the user datapath only right now."""
        controller = self.controllers[0]
        info(controller.name + ' <->')
        cip = ip
        snum = ipParse(ip)
        nodesL2 = self.switches + self.aps
        for nodeL2 in nodesL2:
            info(' ' + nodeL2.name)
            if self.link == wmediumd:
                link = Link(nodeL2, controller, port1=0)
            else:
                self.link = Link
                link = self.link(nodeL2, controller, port1=0)
            sintf, cintf = link.intf1, link.intf2
            nodeL2.controlIntf = sintf
            snum += 1
            while snum & 0xff in [0, 255]:
                snum += 1
            sip = ipStr(snum)
            cintf.setIP(cip, prefixLen)
            sintf.setIP(sip, prefixLen)
            controller.setHostRoute(sip, cintf)
            nodeL2.setHostRoute(cip, sintf)
        info('\n')
        info('*** Testing control network\n')
        while not cintf.isUp():
            info('*** Waiting for', cintf, 'to come up\n')
            sleep(1)
        for nodeL2 in nodesL2:
            while not sintf.isUp():
                info('*** Waiting for', sintf, 'to come up\n')
                sleep(1)
            if self.ping(hosts=[nodeL2, controller]) != 0:
                error('*** Error: control network test failed\n')
                exit(1)
        info('\n')