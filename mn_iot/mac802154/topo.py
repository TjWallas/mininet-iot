#!/usr/bin/env python
"""@package topo

Wireless Network topology creation.

@author Ramon Fontes (ramonrf@dca.fee.unicamp.br)

This package includes code to represent network topologies.
"""

from mininet.util import irange, naturalSeq
from mininet.topo import Topo
from mn_iot.mac802154.link import SixLowpan


class MultiGraph( object ):
    "Utility class to track nodes and edges - replaces networkx.MultiGraph"

    def __init__( self ):
        self.node = {}
        self.edge = {}

    def add_node( self, node, attr_dict=None, **attrs):
        """Add node to graph
           attr_dict: attribute dict (optional)
           attrs: more attributes (optional)
           warning: updates attr_dict with attrs"""
        attr_dict = {} if attr_dict is None else attr_dict
        attr_dict.update( attrs )
        self.node[ node ] = attr_dict

    def add_edge( self, src, key=None, attr_dict=None, **attrs ):
        """Add edge to graph
           key: optional key
           attr_dict: optional attribute dict
           attrs: more attributes
           warning: udpates attr_dict with attrs"""
        attr_dict = {} if attr_dict is None else attr_dict
        attr_dict.update( attrs )
        self.node.setdefault( src, {} )
        self.edge.setdefault( src, {} )
        self.edge[ src ].setdefault( src, {} )
        entry = self.edge[ src ][ src ] = self.edge[ src ][ src ]
        # If no key, pick next ordinal number
        if key is None:
            keys = [ k for k in entry.keys() if isinstance( k, int ) ]
            key = max( [ 0 ] + keys ) + 1
        entry[ key ] = attr_dict
        return key

    def nodes( self, data=False):
        """Return list of graph nodes
           data: return list of ( node, attrs)"""
        return self.node.items() if data else self.node.keys()

    def edges_iter( self, data=False, keys=False ):
        "Iterator: return graph edges, optionally with data and keys"
        for src, entry in self.edge.items():
            for dst, entrykeys in entry.items():
                if src > dst:
                    # Skip duplicate edges
                    continue
                for k, attrs in entrykeys.items():
                    if data:
                        if keys:
                            yield( src, dst, k, attrs )
                        else:
                            yield( src, dst, attrs )
                    else:
                        if keys:
                            yield( src, dst, k )
                        else:
                            yield( src, dst )

    def edges( self, data=False, keys=False ):
        "Return list of graph edges"
        return list( self.edges_iter( data=data, keys=keys ) )

    def __getitem__( self, node ):
        "Return link dict for given src node"
        return self.edge[ node ]

    def __len__( self ):
        "Return the number of nodes"
        return len( self.node )

    def convertTo( self, cls, data=False, keys=False ):
        """Convert to a new object of networkx.MultiGraph-like class cls
           data: include node and edge data
           keys: include edge keys as well as edge data"""
        g = cls()
        g.add_nodes_from( self.nodes( data=data ) )
        g.add_edges_from( self.edges( data=( data or keys ), keys=keys ) )
        return g


class Topo_sixlowpan(Topo):
    "Data center network representation for structured multi-trees."

    def __init__(self, *args, **params):
        """Topo object.
           Optional named parameters:
           hinfo: default host options
           sopts: default switch options
           lopts: default link options
           calls build()"""
        self.g = MultiGraph()
        self.hopts = params.pop('hopts', {})
        self.sopts = params.pop('sopts', {})
        self.lopts = params.pop('lopts', {})
        # ports[src][dst][sport] is port on dst that connects to src
        self.ports = {}
        self.build(*args, **params)

    def build(self, *args, **params):
        "Override this method to build your topology."
        pass

    def addNode(self, name, **opts):
        """Add Node to graph.
           name: name
           opts: node options
           returns: node name"""
        self.g.add_node(name, **opts)
        return name

    def addSensor(self, name, **opts):
        """Convenience method: Add host to graph.
           name: host name
           opts: host options
           returns: host name"""
        if not opts and self.hopts:
            opts = self.hopts
        return self.addNode(name, **opts)

    # This legacy port management mechanism is clunky and will probably
    # be removed at some point.

    def iterLinks(self, withKeys=False, withInfo=False):
        """Return links (iterator)
           withKeys: return link keys
           withInfo: return link info
           returns: list of ( src, dst [,key, info ] )"""
        for _src, _dst, key, info in self.g.edges_iter(data=True, keys=True):
            node1 = info['node1']
            if withKeys:
                if withInfo:
                    yield (node1, key, info)
                else:
                    yield (node1, key)
            else:
                if withInfo:
                    yield (node1, info)
                else:
                    yield (node1)

    def links(self, sort=False, withKeys=False, withInfo=False):
        """Return links
           sort: sort links alphabetically, preserving (src, dst) order
           withKeys: return link keys
           withInfo: return link info
           returns: list of ( src, dst [,key, info ] )"""
        links = list(self.iterLinks(withKeys, withInfo))
        if not sort:
            return links
        # Ignore info when sorting
        tupleSize = 3 if withKeys else 2
        return sorted(links, key=(lambda l: naturalSeq(l[:tupleSize])))

    def addPort(self, src, sport=None):
        """Generate port mapping for new edge.
            src: source switch name
            dst: destination switch name"""
        # Initialize if necessary
        ports = self.ports
        ports.setdefault(src, {})
        # New port: number of outlinks + base
        if sport is None:
            src_base = 0
            sport = len(ports[ src ]) + src_base
        ports[ src ][ sport ] = (src, sport)
        return sport

    def nodes( self, sort=True ):
        "Return nodes in graph"
        if sort:
            return self.sorted( self.g.nodes() )
        else:
            return self.g.nodes()

    def sensors( self, sort=True ):
        """Return stations.
           sort: sort stations alphabetically
           returns: list of stations"""
        return [ n for n in self.nodes( sort )  ]

    def addLink(self, node1, node2=None, port1=None, port2=None,
                key=None, **opts):
        """node1, node2: nodes to link together
           port1, port2: ports (optional)
           opts: link options (optional)
           returns: link info key"""
        if not opts and self.lopts:
            opts = self.lopts
        port1 = self.addPort(node1, port1)
        opts = dict(opts)
        opts.update(node1=node1, port1=port1)
        self.g.add_edge(node1, key, opts)
        return key


# Our idiom defines additional parameters in build(param...)
# pylint: disable=arguments-differ

class Single6lowpanTopo(Topo_sixlowpan):
    "Single k sensors."
    def build(self, k=2, **_opts):
        "k: number of sensors"
        self.k = k
        for s in irange(1, k):
            sensor = self.addSensor('sensor%s' % s)
            self.addLink(sensor, cls=SixLowpan, panid='0xbeef')


class Minimal6lowpanTopo(Single6lowpanTopo):
    "Minimal 6lowpan topology with two sensors"
    def build(self):
        return Single6lowpanTopo.build(self, k=1)


# pylint: enable=arguments-differ
