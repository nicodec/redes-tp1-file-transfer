from mininet.topo import Topo
from mininet.link import TCLink


class MyTopo(Topo):
    "Simple topology example."

    def __init__(self):
        Topo.__init__(self)
        # Add hosts and switches
        server = self.addHost('h1')
        cliente1 = self.addHost('h2')
        cliente2 = self.addHost('h3')
        cliente3 = self.addHost('h4')
        switch = self.addSwitch('s1')
        # Add links
        self.addLink(server, switch)
        self.addLink(cliente1, switch, )
        self.addLink(cliente2, switch, cls=TCLink, loss=10)
        self.addLink(cliente3, switch, cls=TCLink, loss=40)


topos = {'mytopo': (lambda: MyTopo())}