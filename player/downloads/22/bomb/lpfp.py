#!/usr/bin/env python3
"""
Length-Prefixed Framed Protocol (LPFP)
用於網路通訊的簡單訊框協議
"""

def send_frame(sock, data):
    """發送一個訊框"""
    length = len(data)
    sock.sendall(length.to_bytes(4, byteorder='big') + data)

def recv_frame(sock):
    """接收一個訊框"""
    length_bytes = sock.recv(4)
    if not length_bytes or len(length_bytes) < 4:
        return None
    
    length = int.from_bytes(length_bytes, byteorder='big')
    data = b''
    
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            return None
        data += chunk
    
    return data
