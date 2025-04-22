# redes-tp1-file-transfer
En `/redes-tp1-file-transfer` ejecutar lo siguiente:

## Stop & Wait
- Servidor:
```
python3 src/start_server.py -H localhost -p 3333 -r udp_saw -s src/server/files/udp_saw
```

- Cliente de download:
```
python3 src/download.py -H localhost -p 3333 -d src/client/files -n prueba.txt -r udp_saw
```

- Cliente de upload:
```
```
python3 src/upload.py -H localhost -p 3333 -s src/client/files -n img-5mb.jpg -r udp_saw
---

## Selective Repeat
- Servidor:
```
```

- Cliente de download:
```
```

- Cliente de upload:
```
```