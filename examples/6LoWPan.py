#!/usr/bin/python

'This example creates a simple network topology with 3 sensors'
import os
import sys

from mininet.log import setLogLevel, info
from mn_iot.wifi.cli import CLI_wifi
from mn_iot.wifi.net import Mininet_wifi
from mn_iot.mac802154.link import SixLowpan
#from mn_iot.wifi.link import wmediumd
#from mn_iot.wifi.wmediumdConnector import interference


def topology(mob):
    "Create a network."
    net = Mininet_wifi() #link=wmediumd, wmediumd_mode=interference)

    info("*** Creating nodes\n")
    if mob:
        sensor1 = net.addSensor('sensor1', ip='2001::1/64')
        sensor2 = net.addSensor('sensor2', ip='2001::2/64')
        sensor3 = net.addSensor('sensor3', ip='2001::3/64',
                                position='10,150,0')
    else:
        sensor1 = net.addSensor('sensor1', ip='2001::1/64',
                                position='10,50,0')
        sensor2 = net.addSensor('sensor2', ip='2001::2/64',
                                position='10,100,0')
        sensor3 = net.addSensor('sensor3', ip='2001::3/64',
                                position='10,150,0')

    info("*** Configuring nodes\n")
    net.configureWifiNodes()

    info("*** Associating Nodes\n")
    net.addLink(sensor1, cls=SixLowpan, panid='0xbeef')
    net.addLink(sensor2, cls=SixLowpan, panid='0xbeef')
    net.addLink(sensor3, cls=SixLowpan, panid='0xbeef')

    net.plotGraph(max_x=200, max_y=200)

    if mob:
        net.startMobility(time=0, repetitions=1)
        net.mobility(sensor1, 'start', time=1, position='40.0,30.0,0.0')
        net.mobility(sensor2, 'start', time=2, position='40.0,40.0,0.0')
        net.mobility(sensor1, 'stop', time=12, position='175.0,25.0,0.0')
        net.mobility(sensor2, 'stop', time=22, position='55.0,31.0,0.0')
        net.stopMobility(time=23)

    info("*** Starting network\n")
    net.build()

    if not mob:
        os.system('wpan-hwsim edge add 1 2')
        os.system('wpan-hwsim edge add 2 1')
        os.system('wpan-hwsim edge lqi 1 2 30')
        os.system('wpan-hwsim edge lqi 2 1 30')

    info("*** Running CLI\n")
    CLI_wifi(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    mob = True if '-m' in sys.argv else False
    topology(mob)
