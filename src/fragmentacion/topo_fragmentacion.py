from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel


class SimpleFragmentationTopo(Topo):
    def build(self):
        # Hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        # Enlaces normales
        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(s2, s3, cls=TCLink, loss=10)  # acá agregamos pérdida
        self.addLink(s3, h2)


def run():
    topo = SimpleFragmentationTopo()
    net = Mininet(topo=topo, link=TCLink)
    net.start()

    h1, h2 = net.get('h1'), net.get('h2')

    # Reducir MTU en una interfaz del switch intermedio (s2-s3)
    h1.cmd("ip link set h1-eth0 mtu 1500")
    h2.cmd("ip link set h2-eth0 mtu 600")  # MTU baja del lado receptor

    # Desactivar Path MTU Discovery (para forzar fragmentación)
    h1.cmd("sysctl -w net.ipv4.ip_no_pmtu_disc=1")
    h2.cmd("sysctl -w net.ipv4.ip_no_pmtu_disc=1")

    print("Topología lista. Ejecutá los comandos iperf dentro del CLI.")
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
