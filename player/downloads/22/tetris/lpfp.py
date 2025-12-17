# lpfp.py
import struct
import socket

def send_frame(conn, payload: bytes):
    """發送訊框，返回是否成功"""
    try:
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        length = struct.pack("!I", len(payload)) #網路位元加長度
        conn.sendall(length + payload) #長度跟後面的資料憶起送
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        # 連線已斷開
        return False
    except Exception:
        # 其他未預期錯誤
        return False

def recv_frame(conn):
    """接收訊框，失敗返回 None"""
    try:
        header = b''
        while len(header) < 4: #先讀前四byte
            chunk = conn.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
        (length,) = struct.unpack("!I", header)
        
        # 防止過大的數據包（DoS 攻擊）
        if length > 10 * 1024 * 1024:  # 10MB 限制 太常不收
            return None
        
        data = b''
        while len(data) < length: #讀完所有資料
            chunk = conn.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    except socket.timeout:
        # Timeout 不是錯誤，返回 None 讓調用者處理
        return None
    except (ConnectionResetError, OSError):
        # 連線問題
        return None
    except Exception:
        # 其他錯誤
        return None