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
sudo mn --custom src/lib/mininet.py --topo mytopo
```

La topología consta de 4 hosts y 1 switch. Los hosts son h1, h2, h3 y h4. El switch es s1.

Hay perdida configuarada entre s1 y h3 de 10% y entre s1 y h4 de 40%.