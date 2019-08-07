# author: Ramon Fontes (ramonrf@dca.fee.unicamp.br)

import re
import os


class adhocProtocols(object):
    def __init__(self, protocol, node, wif=0):
        eval(protocol)(node, wif)


class batman(object):
    def __init__(self, node, wif=0):
        self.load_module(node)
        self.add_iface(node, wif)
        self.set_link_up(node, wif)

    def add_iface(self, node, wif=0):
        iface = node.params['wif'][wif]
        node.cmd('batctl if add %s' % iface)

    def set_link_up(self, node, wif=0):
        node.cmd('ip link set up dev bat%s' % wif)
        self.setIP(node, wif)

    def setIP(self, node, wif):
        nums = re.findall(r'\d+', node.name)
        id = hex(int(nums[0]))[2:]
        node.cmd('ip addr add 192.168.123.%s/24 '
                 'dev bat%s' % (id, wif))

    def load_module(self, node):
        node.cmd('modprobe batman-adv')


class olsr(object):
    def __init__(self, node, wif=0):
        node.cmd('olsrd -i %s -d 0' % node.params['wif'][wif])


class babel(object):
    def __init__(self, node, wlan=0):
        pid = os.getpid()
        node.cmd("babeld %s -I mn_%s_%s.staconf &" %
                 (node.params['wlan'][wlan], node, pid))
