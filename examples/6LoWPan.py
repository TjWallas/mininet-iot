#!/usr/bin/python

'This example creates a simple network topology with 3 sensors'

from mininet.log import setLogLevel, info
from mn_iot.wifi.cli import CLI_wifi
from mn_iot.wifi.net import Mininet_wifi
from mn_iot.mac802154.link import SixLowpan
#from mn_iot.wifi.link import wmediumd
#from mn_iot.wifi.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Mininet_wifi() #link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    sensor1 = net.addSensor('sensor1', ip='2001::1/64', position='10,50,0')
    sensor2 = net.addSensor('sensor2', ip='2001::2/64', position='10,100,0')
    sensor3 = net.addSensor('sensor3', ip='2001::3/64', position='10,150,0')

    info("*** Configuring nodes\n")
    net.configureWifiNodes()

    info("*** Associating Nodes\n")
    net.addLink(sensor1, cls=SixLowpan, panid='0xbeef')
    net.addLink(sensor2, cls=SixLowpan, panid='0xbeef')
    net.addLink(sensor3, cls=SixLowpan, panid='0xbeef')

    info("*** Starting network\n")
    net.build()

    info("*** Running CLI\n")
    CLI_wifi(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
