"""
    Mininet-WiFi: A simple networking testbed for Wireless OpenFlow/SDWN!
author: Ramon Fontes (ramonrf@dca.fee.unicamp.br)
"""

import re
import numpy as np
from scipy.spatial.distance import pdist

from mininet.log import info, debug
from mininet.util import Python3, getincrementaldecoder, moveIntf
from mininet.node import Node
from mininet.moduledeps import pathCheck
from mn_iot.mac80211.propagationModels import propagationModel
from mn_iot.mac80211.wmediumdConnector import w_cst, wmediumd_mode


class Node_mac802154(Node):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""

    portBase = 0  # Nodes always start with eth0/port0, even in OF 1.0

    def __init__(self, name, inNamespace=True, **params):
        """name: name of node
           inNamespace: in network namespace?
           privateDirs: list of private directory strings or tuples
           params: Node parameters (see config() for details)"""

        # Make sure class actually works
        self.checkSetup()

        self.name = params.get('name', name)
        self.privateDirs = params.get('privateDirs', [])
        self.inNamespace = params.get('inNamespace', inNamespace)

        # Python 3 complains if we don't wait for shell exit
        self.waitExited = params.get('waitExited', Python3)

        # Stash configuration parameters for future reference
        self.params = params

        self.intfs = {}  # dict of port numbers to interfaces
        self.ports = {}  # dict of interfaces to port numbers
        self.wpanports = -1  # dict of wif interfaces to port numbers
        self.nameToIntf = {}  # dict of interface names to Intfs

        self.func = []
        self.isStationary = True
        self.edge = []

        # Make pylint happy
        (self.shell, self.execed, self.pid, self.stdin, self.stdout,
         self.lastPid, self.lastCmd, self.pollOut) = (
             None, None, None, None, None, None, None, None)
        self.waiting = False
        self.readbuf = ''

        # Incremental decoder for buffered reading
        self.decoder = getincrementaldecoder()

        # Start command interpreter shell
        self.master, self.slave = None, None  # pylint
        self.startShell()
        self.mountPrivateDirs()

    # File descriptor to node mapping support
    # Class variables and methods
    inToNode = {}  # mapping of input fds to nodes
    outToNode = {}  # mapping of output fds to nodes

    def plot(self, position):
        self.params['position'] = position.split(',')
        self.params['range'] = [0]
        self.plotted = True

    def unmountPrivateDirs(self):
        "mount private directories"
        for directory in self.privateDirs:
            if isinstance(directory, tuple):
                self.cmd('umount ', directory[0])
            else:
                self.cmd('umount ', directory)

    def cleanup(self):
        "Help python collect its garbage."
        # We used to do this, but it slows us down:
        # Intfs may end up in root NS
        # for intfName in self.intfNames():
        # if self.name in intfName:
        # quietRun( 'ip link del ' + intfName )
        self.shell = None

    def newWpanPort(self):
        "Return the next port number to allocate."
        self.wpanports += 1
        return self.wpanports

    def newPort(self):
        "Return the next port number to allocate."
        if len(self.ports) > 0:
            return max(self.ports.values()) + 1
        return self.portBase

    def addIntf(self, intf, port=None, moveIntfFn=moveIntf):
        """Add an interface.
           intf: interface
           port: port number (optional, typically OpenFlow port number)
           moveIntfFn: function to move interface (optional)"""
        if port is None:
            port = self.newPort()
        self.intfs[port] = intf
        self.ports[intf] = port
        self.nameToIntf[intf.name] = intf
        debug('\n')
        debug('added intf %s (%d) to node %s\n' % (
            intf, port, self.name))
        if (not isinstance(self, Sixlowpan)):
            if self.inNamespace:
                debug('moving', intf, 'into namespace for', self.name, '\n')
                moveIntfFn(intf.name, self)

    def getMAC(self, iface):
        "get Mac Address of any Interface"
        try:
            _macMatchRegex = re.compile(r'..:..:..:..:..:..:..:..')
            debug('getting mac address from %s\n' % iface)
            macaddr = str(self.pexec('ip addr show %s' % iface))
            mac = _macMatchRegex.findall(macaddr)
            debug('%s\n' % mac[0])
            return mac[0]
        except:
            info('Please run sudo mn -c.\n')

    def connectionsTo(self, node):
        "Return [ intf1, intf2... ] for all intfs that connect self to node."
        # We could optimize this if it is important
        connections = []
        for intf in self.intfList():
            link = intf.link
            if link and link.intf2 != None and link.intf2 != 'wireless':
                node1, node2 = link.intf1.node, link.intf2.node
                if node1 == self and node2 == node:
                    connections += [ (intf, link.intf2) ]
                elif node1 == node and node2 == self:
                    connections += [ (intf, link.intf1) ]
        return connections

    # Convenience and configuration methods
    def setMAC(self, mac, intf=None):
        """Set the MAC address for an interface.
           intf: intf or intf name
           mac: MAC address as string"""
        return self.intf(intf).setMAC(mac)

    def setIP(self, ip, prefixLen=64, intf=None, **kwargs):
        """Set the IP address for an interface.
           intf: intf or intf name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs
           kwargs: any additional arguments for intf.setIP"""
        if intf in self.params['wif']:
            wif = int(intf[-1:])
            self.params['wif_ip'][wif] = ip

        return self.intf(intf).setIP(ip, prefixLen, **kwargs)

    def __repr__(self):
        "More informative string representation"
        intfs = (','.join([ '%s:%s' % (i.name, i.IP())
                            for i in self.intfList() ]))
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid)

    def __str__(self):
        "Abbreviated string representation"
        return self.name

    # Automatic class setup support
    isSetup = False

    @classmethod
    def setup(cls):
        "Make sure our class dependencies are available"
        pathCheck('mnexec', 'ip addr', moduleName='Mininet')

    def get_distance_to(self, dst):
        """Get the distance between two nodes
        :param self: source node
        :param dst: destination node"""

        pos_src = self.params['position']
        pos_dst = dst.params['position']
        points = np.array([(pos_src[0], pos_src[1], pos_src[2]),
                           (pos_dst[0], pos_dst[1], pos_dst[2])])
        dist = pdist(points)
        return round(dist,2)

    def get_rssi(self, node=None, wif=0, dist=0):
        value = propagationModel(self, node, dist, wif)
        return float(value.rssi)

    def set_lqi(self, dst, lqi):
        self.params['lqi'][dst] = lqi
        dst.params['lqi'][self] = lqi

    def setPosition(self, pos):
        "Set Position"
        pos = pos.split(',')
        self.params['position'] = float(pos[0]), float(pos[1]), float(pos[2])
        self.updateGraph()

        if wmediumd_mode.mode == w_cst.INTERFERENCE_MODE:
            self.set_pos_wmediumd(self.params['position'])
        self.configLinks()

    def configLinks(self):
        "Applies channel params and handover"
        from mn_iot.mac802154.mobility import Mobility
        Mobility.configLinks(self)

    def updateGraph(self):
        "Update the Graph"
        from mn_iot.mac80211.plot import plot2d, plot3d
        cls = plot2d
        if plot3d.is3d:
            cls = plot3d
        if cls.fig_exists():
            cls.updateCircleRadius(self)
            cls.updateLine(self)
            cls.update(self)
            cls.pause()


class Sixlowpan(Node_mac802154):
    "A sixLoWPan is simply a Node"
    pass