""" Mininet-WiFi: A simple networking testbed for Wireless OpenFlow/SDWN!
    author: Ramon Fontes (ramonrf@dca.fee.unicamp.br)"""

import os
from subprocess import (check_output as co)

from mininet.log import info


class Cleanup():
    "Wrapper for cleanup()"

    @classmethod
    def cleanup_mac802154(cls):
        """Clean up junk which might be left over from old runs;
           do fast stuff before slow dp and link removal!"""
        try:
            info("*** Removing mac802154_hwsim module and Configurations\n")
            co("lsmod | grep mac802154_hwsim", shell=True)
            os.system('rmmod mac802154_hwsim')
        except:
            pass

cleanup_mac802154 = Cleanup.cleanup_mac802154
