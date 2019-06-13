![](https://github.com/ramonfontes/miscellaneous/blob/master/mininet-iot/mininet-iot-logo.png)

### About Mininet-IoT

### What is Mininet-IoT?
Mininet-IoT emulates a complete network of nodes and links on a single machine. To create a sample two-host, one-switch network, just run:

`sudo mn`

To create a sample two-stations, one-ap network, just run:


`sudo mn --wifi`

To create a sample two-sixlowpan-nodes, just run:


`sudo mn --sixlowpan`  

##### Note: Since mac802154_hwsim is only supported from Kernel version 4.18, you may want to consider to run Mininet-IoT from this Kernel version.

