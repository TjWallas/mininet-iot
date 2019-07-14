# author: Ramon Fontes (ramonrf@dca.fee.unicamp.br)

import glob
import os
import subprocess
import logging
from mininet.log import debug, info
from sys import version_info as py_version_info


class module(object):
    "wireless module"

    externally_managed = False
    devices_created_dynamically = False

    def __init__(self, sixLP, n_wpans):
        self.start(sixLP, n_wpans)

    def start(self, nodes, n_radios, alt_module='', **params):
        """Starts environment

        :param nodes: list of wireless nodes
        :param n_radios: number of wifi radios
        :param alt_module: dir of a mac802154 alternative module
        :param **params: ifb -  Intermediate Functional Block device"""
        wm = subprocess.call(['which', 'iwpan'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if wm == 0:
            self.load_module(n_radios, alt_module)  # Initatilize WiFi Module
            n = 0
            for node in nodes:
                for wif in range(0, len(node.params['wif'])):
                    n += 1
                    if n > 2:
                        os.system('wpan-hwsim add >/dev/null 2>&1')
            phys = self.get_virtual_wpan()  # Get Phy Interfaces
            self.assign_iface(nodes, phys, **params)  # iface assign
        else:
            info('*** iwpan will be used, but it is not installed.\n' \
                 '*** Please install iwpan with sudo util/install.sh -6.\n')
            exit(1)

    def load_module(self, n_radios, alt_module=''):
        """ Load WiFi Module 
        
        :param n_radios: number of radios
        :param alt_module: dir of a mac802154 alternative module"""
        debug('Loading %s virtual interfaces\n' % n_radios)
        if not self.externally_managed:
            if alt_module:
                os.system('insmod %s' % alt_module)
            else:
                os.system('modprobe mac802154_hwsim')

    @classmethod
    def kill_mac802154(cls):
        'Kill mac802154'
        info("*** Killing mac802154_hwsim\n")
        os.system('rmmod mac802154_hwsim')

    @classmethod
    def stop(cls):
        'Stop wireless Module'
        if glob.glob("*.apconf"):
            os.system('rm *.apconf')
        if glob.glob("*.staconf"):
            os.system('rm *.staconf')
        if glob.glob("*wifiDirect.conf"):
            os.system('rm *wifiDirect.conf')
        if glob.glob("*.nodeParams"):
            os.system('rm *.nodeParams')

        try:
            (subprocess.check_output("lsmod | grep ifb", shell=True))
            os.system('rmmod ifb')
        except:
            pass

        try:
            confnames = "mn%d_" % os.getpid()
            os.system('pkill -f \'wpa_supplicant -B -Dnl80211 -c%s\''
                      % confnames)
        except:
            pass

        try:
            pidfiles = "mn%d_" % os.getpid()
            os.system('pkill -f \'wpa_supplicant -B -Dnl80211 -P %s\''
                      % pidfiles)
        except:
            pass

        cls.kill_mac802154()

    def get_virtual_wpan(self):
        'Gets the list of virtual wifs that already exist'
        cmd = "iwpan dev 2>&1 | grep " \
              "Interface | awk '{print $2}'"
        if py_version_info < (3, 0):
            wifs = subprocess.check_output\
                (cmd, shell=True).split("\n")
        else:
            wifs = subprocess.check_output\
                (cmd, shell=True).decode('utf-8').split("\n")
        wifs.pop()
        wif_list = sorted(wifs)
        wif_list.sort(key=len, reverse=False)
        return wif_list

    def getPhy(self):
        'Gets the list of virtual wifs that already exist'
        cmd = "iwpan dev | grep phy | " \
              "sed -ne 's/phy#\([0-9]\)/\\1/p'"

        if py_version_info < (3, 0):
            phy = subprocess.check_output\
                (cmd, shell=True).split("\n")
        else:
            phy = subprocess.check_output\
                (cmd, shell=True).decode('utf-8').split("\n")

        phy = sorted(phy)
        phy.pop(0)
        return phy

    def assign_iface(self, nodes, phys, **params):
        """Assign virtual interfaces for all nodes
        
        :param nodes: list of wireless nodes
        :param phys: list of phys
        :param **params: ifb -  Intermediate Functional Block device"""
        log_filename = '/tmp/mininetiot-802154hwsim.log'
        self.logging_to_file("%s" % log_filename)

        try:
            debug("\n*** Configuring interfaces with appropriated network"
                  "-namespaces...\n")
            phy = self.getPhy()
            wif_list = self.get_virtual_wpan()
            wpanPhyID = 0
            for node in nodes:
                for wif in range(0, len(node.params['wif'])):
                    node.wpanPhyID[wif] = wpanPhyID
                    wpanPhyID += 1
                    os.system('iwpan phy phy%s set netns %s' % (phy[0], node.pid))
                    node.cmd('ip link set %s down' % wif_list[0])
                    node.cmd('ip link set %s name %s'
                             % (wif_list[0], node.params['wif'][wif]))
                    wif_list.pop(0)
                    phy.pop(0)
        except:
            logging.exception("Warning:")
            info("Warning! Error when loading mac802154_hwsim. "
                 "Please run sudo 'mn -c' before running your code.\n")
            info("Further information available at %s.\n" % log_filename)
            exit(1)

    def logging_to_file(self, filename):
        logging.basicConfig(filename=filename,
                            filemode='a',
                            level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                           )
