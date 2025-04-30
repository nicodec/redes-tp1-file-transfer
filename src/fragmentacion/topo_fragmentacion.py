from typing import Any, cast
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Node
from mininet.topo import Topo
from mininet.link import TCLink


class SimpleFragmentationTopo(Topo):
    def build(self, **_opts):
        # Switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        # Hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')

        # Conexiones
        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(s2, s3, cls=TCLink, loss=10)
        self.addLink(s3, h2)


def run():
    topo = SimpleFragmentationTopo()
    net = Mininet(topo=topo, link=TCLink, controller=None)
    net.start()

    h1 = cast(Node, net.get('h1'))
    h2 = cast(Node, net.get('h2'))

    # MTU default en h1 (1500), bajo en h2 (600)
    h1.cmd("ip link set h1-eth0 mtu 1500")
    h2.cmd("ip link set h2-eth0 mtu 600")

    # Desactivar Path MTU Discovery para forzar fragmentación
    h1.cmd("sysctl -w net.ipv4.ip_no_pmtu_disc=1")
    h2.cmd("sysctl -w net.ipv4.ip_no_pmtu_disc=1")

    # Desactivar probing TCP para que no evite la fragmentación
    h1.cmd("sysctl -w net.ipv4.tcp_mtu_probing=0")
    h2.cmd("sysctl -w net.ipv4.tcp_mtu_probing=0")

    print("Topología levantada. Ejecutá los comandos iperf desde el CLI.")
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
