#!/usr/bin/python

'This example creates a simple network topology with 3 nodes'

from mininet.log import setLogLevel, info
from mn_iot.wifi.cli import CLI_wifi
from mn_iot.wifi.net import Mininet_wifi
from mn_iot.mac802154.link import mac802154Link
from mn_iot.wifi.link import wmediumd
from mn_iot.wifi.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    node1 = net.add6lowpan('node1', ip='2001::1/64', position='10,50,0')
    node2 = net.add6lowpan('node2', ip='2001::2/64', position='10,100,0')
    node3 = net.add6lowpan('node3', ip='2001::3/64', position='10,150,0')

    info("*** Configuring nodes\n")
    net.configureWifiNodes()

    info("*** Associating Nodes\n")
    net.addLink(node1, cls=mac802154Link, panid='0xbeef')
    net.addLink(node2, cls=mac802154Link, panid='0xbeef')
    net.addLink(node3, cls=mac802154Link, panid='0xbeef')

    info("*** Starting network\n")
    net.build()

    info("*** Running CLI\n")
    CLI_wifi(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
