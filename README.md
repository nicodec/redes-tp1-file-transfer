# redes-tp1-file-transfer
En `/redes-tp1-file-transfer` ejecutar lo siguiente:

## Stop & Wait
- Servidor:
```
python3 src/start_server.py -H localhost -p 8888 -r udp_saw -s src/server/files/udp_saw
```

- Cliente de download:
```
python3 src/download.py -H localhost -p 8888 -d src/client/files -n prueba.txt -r udp_saw
```

- Cliente de upload:
```
python3 src/upload.py -H localhost -p 8888 -s src/client/files -n img-5mb.jpg -r udp_saw
```

---

## Selective Repeat
- Servidor:
```
python3 src/start_server.py -H localhost -p 8888 -r udp_sr -s src/server/files/udp_sr
```

- Cliente de download:
```
python3 src/download.py -H localhost -p 8888 -d src/client/files -n img-4mb.jpg -r udp_sr
```

- Cliente de upload:
```
python3 src/upload.py -H localhost -p 8888 -s src/client/files -n img-3mb.jpg -r udp_sr
```

## Mininet
Para correr mininet con la topología ya configurada:

```
sudo mn --custom src/mininet.py --topo mytopo
```

La topología consta de 4 hosts y 1 switch. Los hosts son h1, h2, h3 y h4. El switch es s1.

Hay perdida configuarada entre s1 y h3 de 10% y entre s1 y h4 de 40%.

## Anexo: Fragmentacion IPv4
Esto lanza una red con dos hosts (h1, h2) conectados por 3 switches, con:

Reducción del MTU a 600 bytes en la interfaz final.

Un 10% de pérdida de paquetes en el enlace hacia h2.

Desactivación de Path MTU Discovery para forzar fragmentación.

- Para correr la topologia:
```
sudo python3 src/fragmentacion/topo_fragmentacion.py
```

- Una vez dentro del CLI de Mininet, correr (esto inicia un servidor iperf en h2, escuchando por tráfico UDP/TCP):
```
mininet> h2 iperf -s &
```

- Luego correr (esto envía paquetes UDP de 1400 bytes desde h1 a h2 durante 5 segundos):
```
mininet> h1 iperf -c h2 -l 1400 -u -t 5
```

Flags:
- `c h2`: cliente apunta a h2

- `l 1400`: tamaño del datagrama UDP = 1400 bytes

- `u`: usa UDP

- `t 5`: duración de la prueba = 5 segundos

Extra: Esto genera tráfico TCP, que sí retransmite fragmentos perdidos.
```
mininet> h1 iperf -c h2 -t 5
```