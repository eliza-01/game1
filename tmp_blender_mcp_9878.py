import json
import socket
import sys

with open(sys.argv[2], 'r', encoding='utf-8') as handle:
    code = handle.read()
payload = (json.dumps({'type': sys.argv[1], 'params': {'code': code}}) + '\n').encode('utf-8')
with socket.create_connection(('127.0.0.1', 9878), timeout=10) as sock:
    sock.sendall(payload)
    response = sock.recv(4 * 1024 * 1024)
print(response.decode('utf-8'))
