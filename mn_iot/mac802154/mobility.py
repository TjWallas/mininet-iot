
import os
import re
from time import sleep

from threading import Thread as thread
from mininet.log import debug, info
from mn_iot.mac80211.plot import plot2d, plot3d, plotGraph
from mn_iot.mac80211.mobility import mobility


class Mobility(object):

    sensors = []
    mobileNodes = []
    thread_ = ''
    wmediumd_mode = None
    dist = 0
    noise = 0
    equationLoss = '(dist * 2) / 1000'
    equationDelay = '(dist / 10) + 1'
    equationLatency = '(dist / 10)/2'
    equationBw = ' * (1.01 ** -dist)'

    #def __init__(self, src):
    #    self.get_edge(src)

    @classmethod
    def get_edge(self, src):
        nedges = 0
        lat = 0
        loss = 0
        bw = 0
        for dst in self.sensors:
            if src != dst:
                dist = src.get_distance_to(dst)
                id_src, id_dst = self.get_node_id(src, dst)
                if dist > src.params['range'][0]:
                    if dst in src.edge:
                        self.handle_edge(id_src, id_dst)
                        src.edge.remove(dst)
                        dst.edge.remove(src)
                    src.set_lqi(dst, 0)
                    dst.set_lqi(src, 0)
                else:
                    if dst not in src.edge:
                        self.handle_edge(id_src, id_dst, act='add')
                        src.edge.append(dst)
                        dst.edge.append(src)
                    lqi = int(self.get_rssi(src, dst, dist))
                    self.set_lqi(id_src, id_dst, lqi)
                    src.set_lqi(dst, lqi)
                    dst.set_lqi(src, lqi)
                    nedges += 1

                if self.sensors.index(dst) == (len(self.sensors)-1) or \
                                self.sensors.index(src) == (len(self.sensors)-1):
                    lat = (self.getLatency(dist)+lat)/nedges
                    loss = (self.getLoss(dist)+loss)/nedges
                    bw = (self.getBW(dist=dist)+bw)/nedges

        if nedges:
            self.config_tc(src, 0, bw, loss, lat)

    @classmethod
    def getDelay(cls, dist):
        return eval(cls.equationDelay)

    @classmethod
    def getLatency(cls, dist):
        return eval(cls.equationLatency)

    @classmethod
    def getLoss(cls, dist):
        return eval(cls.equationLoss)

    @classmethod
    def getBW(cls, dist=0):
        custombw = 2
        rate = eval(str(custombw) + cls.equationBw)

        if rate <= 0.0:
            rate = 0.1
        return rate

    @classmethod
    def config_tc(cls, node, wif, bw, loss, latency):
        """config_tc
        :param node: node
        :param wif: wif ID
        :param bw: bandwidth (mbps)
        :param loss: loss (%)
        :param latency: latency (ms)"""
        iface = node.params['wif'][wif]
        cls.tc(node, iface, bw, loss, latency)

    @classmethod
    def tc(cls, node, iface, bw, loss, latency):
        cmd = "tc qdisc replace dev %s root handle 2: netem " % iface
        rate = "rate %.4fmbit " % bw
        cmd += rate
        if latency > 0.1:
            latency = "latency %.2fms " % latency
            cmd += latency
        if loss > 0.1:
            loss = "loss %.1f%% " % loss
            cmd += loss
        print cmd
        node.pexec(cmd)

    @classmethod
    def get_node_id(self, src, dst):
        id_src = int(re.findall(r'\d+', src.name)[0]) - 1
        id_dst = int(re.findall(r'\d+', dst.name)[0]) - 1
        return id_src, id_dst

    @classmethod
    def handle_edge(self, src, dst, act='del'):
        os.system('wpan-hwsim edge %s %s %s >/dev/null 2>&1' % (act, src, dst))
        os.system('wpan-hwsim edge %s %s %s >/dev/null 2>&1' % (act, dst, src))

    @classmethod
    def get_rssi(self, src, dst, dist):
        rssi = src.get_rssi(dst, 0, dist)
        lqi = 100 + rssi
        return lqi

    @classmethod
    def set_lqi(self, src, dst, lqi):
        os.system('wpan-hwsim edge lqi %s %s %s' % (src, dst, lqi))
        os.system('wpan-hwsim edge lqi %s %s %s' % (dst, src, lqi))

    @classmethod
    def stop(cls, **kwargs):
        debug('Starting mobility thread...\n')
        cls.thread_ = thread(target=tracked, kwargs=(kwargs))
        cls.thread_.daemon = True
        cls.thread_._keep_alive = True
        cls.thread_.start()
        cls.set_wifi_params()

    @classmethod
    def set_wifi_params(cls):
        "Opens a thread for wifi parameters"
        thread_ = thread(name='wifiParameters', target=cls.parameters)
        thread_.daemon = True
        thread_.start()

    @classmethod
    def parameters(cls):
        "Applies channel params and handover"
        mobileNodes = list(set(cls.mobileNodes))
        while Mobility.thread_._keep_alive:
            cls.configureLinks(mobileNodes)

    @classmethod
    def configureLinks(cls, nodes):
        for node in nodes:
            for wif in range(len(node.params['wif'])):
                cls.get_edge(node)
        sleep(0.0001)

    @classmethod
    def configLinks(cls, node=None):
        "Applies channel params and handover"
        nodes = []
        nodes.append(node)
        cls.configureLinks(nodes)


class tracked(thread):
    "Used when the position of each node is previously defined"

    def __init__(self, **kwargs):
        super(tracked, self).__init__()
        self.kwargs = kwargs
        self.configure(**kwargs)
        self.plot = ''

    def configure(self, **kwargs):

        Mobility.sensors = kwargs['sensors']
        nodes = Mobility.sensors
        plot = plot2d

        stationaryNodes = []
        for node in nodes:
            if 'position' in node.params and 'initPos' not in node.params:
                stationaryNodes.append(node)
            if 'initPos' in node.params:
                node.params['position'] = node.params['initPos']
                Mobility.mobileNodes.append(node)

        kwargs['nodes'] = Mobility.mobileNodes + stationaryNodes
        try:
            if kwargs['DRAW']:
                plotGraph(**kwargs)
                if kwargs['max_z'] != 0:
                    plot = plot3d
        except:
            info('Warning: running without GUI.\n')
            kwargs['DRAW'] = False

        for node in nodes:
            if hasattr(node, 'coord'):
                self.create_coordinate(node)
                node.points = []
                for coord_ in node.coord_:
                    self.get_line(node, float(coord_[0].split(',')[0]),
                                 float(coord_[0].split(',')[1]),
                                 float(coord_[0].split(',')[2]),
                                 float(coord_[1].split(',')[0]),
                                 float(coord_[1].split(',')[1]),
                                 float(coord_[1].split(',')[2]))
        self.run(plot, **kwargs)

    def run(self, plot, **kwargs):
        from time import time

        for rep in range(kwargs['repetitions']):
            Mobility.thread_._keep_alive = True
            t1 = time()
            i = 1
            if 'reverse' in kwargs and kwargs['reverse'] == True:
                for node in Mobility.mobileNodes:
                    if rep%2 == 1:
                        fin_ = node.params['finPos']
                        node.params['finPos'] = node.params['initPos']
                        node.params['initPos'] = fin_
                    elif rep%2 == 0 and rep > 0:
                        fin_ = node.params['finPos']
                        node.params['finPos'] = node.params['initPos']
                        node.params['initPos'] = fin_
            for node in Mobility.mobileNodes:
                node.time = node.startTime
                mobility.calculate_diff_time(node)
            while Mobility.thread_._keep_alive:
                t2 = time()
                if (t2 - t1) > kwargs['final_time']:
                    Mobility.thread_._keep_alive = False
                if (t2 - t1) >= kwargs['init_time']:
                    if t2 - t1 >= i:
                        for node in Mobility.mobileNodes:
                            if (t2 - t1) >= node.startTime and node.time <= node.endTime:
                                if hasattr(node, 'coord'):
                                    mobility.calculate_diff_time(node)
                                    self.set_pos(node,
                                                 node.points[node.time * node.moveFac])
                                    if node.time == node.endTime:
                                        self.set_pos(node,
                                                     node.points[len(node.points) - 1])
                                else:
                                    self.set_pos(node, self.move_node(node))
                                node.time += 1
                            if kwargs['DRAW']:
                                plot.update(node)
                                if kwargs['max_z'] == 0:
                                    plot2d.updateCircleRadius(node)
                        plot.pause()
                        i += 1

    def set_pos(self, node, pos):
        node.params['position'] = pos
        if Mobility.wmediumd_mode == 3 and Mobility.thread_._keep_alive:
            node.set_pos_wmediumd(pos)

    def move_node(cls, node):
        x = round(node.params['position'][0], 2) + round(node.moveFac[0], 2)
        y = round(node.params['position'][1], 2) + round(node.moveFac[1], 2)
        z = round(node.params['position'][2], 2) + round(node.moveFac[2], 2)
        return [x, y, z]

    def create_coordinate(cls, node):
        node.coord_ = []
        init_pos = node.params['initPos']
        fin_pos = node.params['finPos']
        if not hasattr(node, 'coord'):
            coord1 = '%s,%s,%s' % (init_pos[0], init_pos[1], init_pos[2])
            coord2 = '%s,%s,%s' % (fin_pos[0], fin_pos[1], fin_pos[2])
            node.coord_.append([coord1, coord2])
        else:
            for idx in range(len(node.coord) - 1):
                node.coord_.append([node.coord[idx], node.coord[idx + 1]])

    def get_line(self, node, x1, y1, z1, x2, y2, z2):
        points = []
        issteep = abs(y2 - y1) > abs(x2 - x1)
        if issteep:
            x1, y1 = y1, x1
            x2, y2 = y2, x2
        rev = False
        if x1 > x2:
            x1, x2 = x2, x1
            y1, y2 = y2, y1
            rev = True
        deltax = x2 - x1
        deltay = abs(y2 - y1)
        error = int(deltax / 2)
        y = y1
        ystep = None
        if y1 < y2:
            ystep = 1
        else:
            ystep = -1

        for x in range(int(x1), int(x2) + 1):
            if issteep:
                points.append((y, x, 0))
            else:
                points.append((x, y, 0))
            error -= deltay
            if error < 0:
                y += ystep
                error += deltax
        # Reverse the list if the coordinates were reversed
        if rev:
            points.reverse()
        node.points = node.points + points