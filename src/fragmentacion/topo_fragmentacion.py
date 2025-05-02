#!/usr/bin/env python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

class FragmentationTopo(Topo):
    """Topología para demostrar la fragmentación IPv4 con 3 switches"""
    def build(self, **_opts):
        # Crear los 3 switches en línea
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')  # Switch central
        s3 = self.addSwitch('s3')
        
        # Crear los dos hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        
        # Conectar hosts a switches
        self.addLink(h1, s1)
        
        # Agregar pérdida de paquetes (10%) en la conexión entre h2 y s3
        self.addLink(h2, s3, cls=TCLink, loss=10)
        
        # Conectar los switches en línea
        # La interfaz s2-eth1 conecta con s1
        self.addLink(s1, s2)
        
        # La interfaz s2-eth2 conecta con s3
        self.addLink(s2, s3)

def run():
    """Crear y configurar la red"""
    topo = FragmentationTopo()
    
    # Configurar para que funcione sin controlador
    net = Mininet(topo=topo, link=TCLink, switch=OVSSwitch, controller=None)
    net.start()
    
    # Configurar switches para funcionar en modo standalone (sin controlador)
    for switch in net.switches:
        switch.cmd('ovs-vsctl set bridge {} protocols=OpenFlow10,OpenFlow12,OpenFlow13'.format(switch.name))
        switch.cmd('ovs-vsctl set bridge {} fail-mode=standalone'.format(switch.name))
    
    # Reducir el MTU de la interfaz del switch central (s2) que conecta con s3
    # s2-eth2 es la interfaz que conecta s2 con s3
    s2 = net.get('s2')
    s2.cmd('ifconfig s2-eth2 mtu 600')
    
    print("\n*** Topología de red para el ejercicio de fragmentación IPv4 ***")
    print("Configuración:")
    print("- Topología: h1 -- s1 -- s2 -- s3 -- h2")
    print("- MTU de s2-eth2 (interfaz del switch central hacia s3): 600 bytes")
    print("- Pérdida de paquetes en la conexión h2-s3: 10%")
    print("\nComandos sugeridos para probar la fragmentación:")
    print("1. Iniciar servidor iperf en h2:")
    print("   mininet> h2 iperf -s &")
    print("\n2. Para probar TCP (fragmentación y respuesta ante pérdidas):")
    print("   mininet> h1 iperf -c h2 -l 1400")
    print("\n3. Para probar UDP (fragmentación y respuesta ante pérdidas):")
    print("   mininet> h1 iperf -c h2 -l 1400 -u")
    print("\n4. Para capturar el tráfico en una interfaz específica:")
    print("   mininet> h1 wireshark &")
    print("   mininet> h2 wireshark &")
    print("   mininet> xterm s2")
    print("   En la terminal xterm: # wireshark")
    
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    run()