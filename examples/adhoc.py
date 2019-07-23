#!/usr/bin/python

"""This example shows how to work in adhoc mode

sta1 <---> sta2 <---> sta3"""

import sys

from mininet.log import setLogLevel, info
from mn_iot.mac80211.link import wmediumd, adhoc
from mn_iot.mac80211.cli import CLI_wifi
from mn_iot.mac80211.net import Mininet_wifi
from mn_iot.mac80211.wmediumdConnector import interference


def topology(autoTxPower):
    "Create a network."
    net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    if autoTxPower:
        sta1 = net.addStation('sta1', position='10,10,0', range=100)
        sta2 = net.addStation('sta2', position='50,10,0', range=100)
        sta3 = net.addStation('sta3', position='90,10,0', range=100)
    else:
        sta1 = net.addStation('sta1', ipv6='fe80::1',
                              position='10,10,0')
        sta2 = net.addStation('sta2', ipv6='fe80::2',
                              position='50,10,0')
        sta3 = net.addStation('sta3', ipv6='fe80::3',
                              position='90,10,0')

    net.setPropagationModel(model="logDistance", exp=4)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info("*** Creating links\n")
    # MANET routing protocols supported by proto: babel, batman and olsr
    net.addLink(sta1, cls=adhoc, ssid='adhocNet',  # proto='olsr',
                mode='g', channel=5, ht_cap='HT40+')
    net.addLink(sta2, cls=adhoc, ssid='adhocNet',  # proto='olsr',
                mode='g', channel=5)
    net.addLink(sta3, cls=adhoc, ssid='adhocNet',  # proto='olsr',
                mode='g', channel=5, ht_cap='HT40+')

    info("*** Starting network\n")
    net.build()

    #info("*** Addressing...\n")
    #sta1.setIPv6('2001::1/64', intf="sta1-wlan0")
    #sta2.setIPv6('2001::2/64', intf="sta2-wlan0")
    #sta3.setIPv6('2001::3/64', intf="sta3-wlan0")

    info("*** Running CLI\n")
    CLI_wifi(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    autoTxPower = True if '-a' in sys.argv else False
    topology(autoTxPower)
