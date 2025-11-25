#!/usr/bin/env python3
# db_server_extended.py - 擴充的資料庫伺服器
"""
Extended Database Server - 支援多種帳號類型

Collections:
- Developer: {name, passwordHash, createdAt, lastLoginAt, games[]}
- Player: {name, passwordHash, createdAt, lastLoginAt, playHistory[]}

Protocol: Length-Prefixed Framing Protocol + JSON
"""

import socket
import threading
import json
import time
import os
import hashlib
from lpfp import send_frame, recv_frame

# 資料存儲路徑
DATA_DIR = "db_data"
DEVELOPERS_FILE = os.path.join(DATA_DIR, "developers.json")
PLAYERS_FILE = os.path.join(DATA_DIR, "players.json")

# 全局鎖
lock = threading.Lock()

# 確保數據目錄存在
os.makedirs(DATA_DIR, exist_ok=True)


# ==================== 數據加載與保存 ====================

def load_json(filepath, default=None):
    """安全加載 JSON 文件"""
    if default is None:
        default = {}
    
    if not os.path.exists(filepath):
        return default
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[DB] Error loading {filepath}: {e}")
        backup = f"{filepath}.corrupted.{int(time.time())}"
        try:
            os.rename(filepath, backup)
            print(f"[DB] Corrupted file backed up to: {backup}")
        except:
            pass
        return default


def save_json(filepath, data):
    """原子性保存 JSON 文件"""
    try:
        temp_file = filepath + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, filepath)
        return True
    except Exception as e:
        print(f"[DB] Error saving {filepath}: {e}")
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        return False


def hash_password(password):
    """密碼雜湊"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ==================== Developer Collection ====================

def developer_create(data):
    """創建開發者帳號"""
    name = data.get("name")
    password = data.get("password")
    
    if not name or not password:
        return {"status": "error", "message": "Missing name or password"}
    
    with lock:
        developers = load_json(DEVELOPERS_FILE, {})
        
        if name in developers:
            return {"status": "error", "message": "Developer already exists"}
        
        developers[name] = {
            "name": name,
            "passwordHash": hash_password(password),
            "createdAt": time.time(),
            "lastLoginAt": None,
            "games": []  # 開發者上架的遊戲列表
        }
        
        if save_json(DEVELOPERS_FILE, developers):
            return {"status": "success", "message": "Developer created", "data": {"name": name}}
        else:
            return {"status": "error", "message": "Failed to save developer"}


def developer_query(data):
    """查詢開發者 - 支持登入驗證"""
    action_type = data.get("type")
    
    if action_type == "login":
        name = data.get("name")
        password = data.get("password")
        
        if not name or not password:
            return {"status": "error", "message": "Missing credentials"}
        
        with lock:
            developers = load_json(DEVELOPERS_FILE, {})
            
            if name not in developers:
                return {"status": "error", "message": "Developer not found"}
            
            if developers[name]["passwordHash"] != hash_password(password):
                return {"status": "error", "message": "Wrong password"}
            
            # 更新最後登入時間
            developers[name]["lastLoginAt"] = time.time()
            save_json(DEVELOPERS_FILE, developers)
            
            return {"status": "success", "message": "Login success", "data": {"name": name}}
    
    elif action_type == "list_all":
        with lock:
            developers = load_json(DEVELOPERS_FILE, {})
            dev_list = []
            for name, info in developers.items():
                dev_list.append({
                    "name": name,
                    "createdAt": info.get("createdAt"),
                    "games_count": len(info.get("games", []))
                })
            return {"status": "success", "data": dev_list}
    
    else:
        return {"status": "error", "message": "Unknown query type"}


# ==================== Player Collection ====================

def player_create(data):
    """創建玩家帳號"""
    name = data.get("name")
    password = data.get("password")
    
    if not name or not password:
        return {"status": "error", "message": "Missing name or password"}
    
    with lock:
        players = load_json(PLAYERS_FILE, {})
        
        if name in players:
            return {"status": "error", "message": "Player already exists"}
        
        players[name] = {
            "name": name,
            "passwordHash": hash_password(password),
            "createdAt": time.time(),
            "lastLoginAt": None,
            "playHistory": []  # 遊玩歷史
        }
        
        if save_json(PLAYERS_FILE, players):
            return {"status": "success", "message": "Player created", "data": {"name": name}}
        else:
            return {"status": "error", "message": "Failed to save player"}


def player_query(data):
    """查詢玩家 - 支持登入驗證"""
    action_type = data.get("type")
    
    if action_type == "login":
        name = data.get("name")
        password = data.get("password")
        
        if not name or not password:
            return {"status": "error", "message": "Missing credentials"}
        
        with lock:
            players = load_json(PLAYERS_FILE, {})
            
            if name not in players:
                return {"status": "error", "message": "Player not found"}
            
            if players[name]["passwordHash"] != hash_password(password):
                return {"status": "error", "message": "Wrong password"}
            
            # 更新最後登入時間
            players[name]["lastLoginAt"] = time.time()
            save_json(PLAYERS_FILE, players)
            
            return {"status": "success", "message": "Login success", "data": {"name": name}}
    
    elif action_type == "list_all":
        with lock:
            players = load_json(PLAYERS_FILE, {})
            player_list = []
            for name, info in players.items():
                player_list.append({
                    "name": name,
                    "createdAt": info.get("createdAt"),
                    "lastLoginAt": info.get("lastLoginAt")
                })
            return {"status": "success", "data": player_list}
    
    else:
        return {"status": "error", "message": "Unknown query type"}


# ==================== 請求路由 ====================

def handle_request(request):
    """處理客戶端請求"""
    try:
        collection = request.get("collection")
        action = request.get("action")
        data = request.get("data", {})
        
        if collection == "Developer":
            if action == "create":
                return developer_create(data)
            elif action == "query":
                return developer_query(data)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        
        elif collection == "Player":
            if action == "create":
                return player_create(data)
            elif action == "query":
                return player_query(data)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        
        else:
            return {"status": "error", "message": f"Unknown collection: {collection}"}
    
    except Exception as e:
        print(f"[DB] Error handling request: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Internal error: {str(e)}"}


# ==================== 客戶端處理 ====================

def handle_client(conn, addr):
    """處理單個客戶端連線"""
    print(f"[DB] Connected from {addr}")
    
    try:
        while True:
            raw = recv_frame(conn)
            if not raw:
                break
            
            try:
                request = json.loads(raw.decode('utf-8'))
                print(f"[DB] Request from {addr}: {request.get('collection')}.{request.get('action')}")
            except json.JSONDecodeError:
                response = {"status": "error", "message": "Invalid JSON"}
                send_frame(conn, json.dumps(response).encode('utf-8'))
                continue
            
            response = handle_request(request)
            send_frame(conn, json.dumps(response).encode('utf-8'))
    
    except Exception as e:
        print(f"[DB] Error with {addr}: {e}")
    
    finally:
        conn.close()
        print(f"[DB] Disconnected from {addr}")


# ==================== 主程式 ====================

def main():
    import sys
    
    HOST = "0.0.0.0"
    
    if len(sys.argv) > 1:
        try:
            PORT = int(sys.argv[1])
        except ValueError:
            print(f"[DB Server] Invalid port: {sys.argv[1]}")
            sys.exit(1)
    else:
        PORT = 0  # 自動分配端口
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        actual_port = server_socket.getsockname()[1]
    except OSError as e:
        print(f"[DB Server] Error binding to port {PORT}: {e}")
        sys.exit(1)
    
    server_socket.listen(5)
    
    print("\n" + "="*60)
    print(f"[DB Server] Started successfully!")
    print(f"[DB Server] Listening on {HOST}:{actual_port}")
    print("="*60)
    print(f"\n⚠️  IMPORTANT: DB Server Port = {actual_port}")
    print(f"\nWhen starting Game Store Server, use:")
    print(f"  python3 game_store_server.py {actual_port}")
    print("\n" + "="*60)
    print("[DB Server] Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            client_thread.start()
    
    except KeyboardInterrupt:
        print("\n[DB Server] Shutting down...")
    
    finally:
        server_socket.close()
        print("[DB Server] Stopped")


if __name__ == "__main__":
    main()
