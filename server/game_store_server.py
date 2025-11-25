#!/usr/bin/env python3
# game_store_server.py - 遊戲商店伺服器（整合 Developer 和 Lobby 功能）

"""
Game Store Server - 統一的遊戲商店伺服器
支援：
1. Developer 功能：遊戲上架、更新、下架
2. Lobby 功能：玩家瀏覽、下載、房間管理
3. 遊戲評分與留言
"""

import socket
import threading
import json
import time
import os
import sys
import shutil
import base64
from lpfp import send_frame, recv_frame

# ==================== 設定 ====================

HOST = "0.0.0.0"
DEVELOPER_PORT = 0  # Developer Server Port
LOBBY_PORT = 0      # Lobby Server Port

# 資料目錄
GAMES_DIR = "uploaded_games"  # 上架遊戲儲存目錄
GAME_METADATA_FILE = "game_store_data/games_metadata.json"
REVIEWS_FILE = "game_store_data/reviews.json"

os.makedirs(GAMES_DIR, exist_ok=True)
os.makedirs("game_store_data", exist_ok=True)

# 全局鎖
games_lock = threading.Lock()
reviews_lock = threading.Lock()

# 線上玩家追蹤（防止重複登入）
online_players = {}  # {username: (conn, addr)}
online_players_lock = threading.Lock()

# 資料庫連線資訊
DB_HOST = "localhost"
DB_PORT = None  # 從命令列參數設定


# ==================== 資料載入與保存 ====================

def load_json_file(filepath, default=None):
    """安全載入 JSON 檔案"""
    if default is None:
        default = {}
    
    if not os.path.exists(filepath):
        return default
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Store] Error loading {filepath}: {e}")
        return default


def save_json_file(filepath, data):
    """原子性保存 JSON 檔案"""
    try:
        temp_file = filepath + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, filepath)
        return True
    except Exception as e:
        print(f"[Store] Error saving {filepath}: {e}")
        return False


# ==================== Developer 相關功能 ====================

def handle_developer_login(data):
    """處理開發者登入（驗證 developer 帳號）"""
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return {"status": "error", "message": "Missing credentials"}
    
    # 向 DB Server 驗證（需要檢查是否為 developer 帳號）
    try:
        db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        db_sock.connect((DB_HOST, DB_PORT))
        
        request = {
            "collection": "Developer",
            "action": "query",
            "data": {"type": "login", "name": username, "password": password}
        }
        
        send_frame(db_sock, json.dumps(request).encode('utf-8'))
        response_raw = recv_frame(db_sock)
        db_sock.close()
        
        if response_raw:
            response = json.loads(response_raw.decode('utf-8'))
            return response
        else:
            return {"status": "error", "message": "DB connection failed"}
    
    except Exception as e:
        print(f"[Developer] Login error: {e}")
        return {"status": "error", "message": str(e)}


def handle_upload_game(data, developer_name):
    """處理遊戲上架"""
    game_name = data.get("game_name")
    game_type = data.get("game_type")  # CLI / GUI / Multiplayer
    description = data.get("description", "")
    max_players = data.get("max_players", 2)
    version = data.get("version", "1.0.0")
    game_files_b64 = data.get("game_files")  # Base64 encoded zip file
    config = data.get("config", {})  # 遊戲設定（啟動命令等）
    
    if not all([game_name, game_type, game_files_b64]):
        return {"status": "error", "message": "Missing required fields"}
    
    with games_lock:
        # 載入遊戲 metadata
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        # 檢查遊戲是否已存在
        if game_name in games_metadata:
            return {"status": "error", "message": "Game already exists. Use update instead."}
        
        # 建立遊戲目錄
        game_dir = os.path.join(GAMES_DIR, game_name, version)
        os.makedirs(game_dir, exist_ok=True)
        
        # 儲存遊戲檔案
        try:
            game_files = base64.b64decode(game_files_b64)
            zip_path = os.path.join(game_dir, "game.zip")
            with open(zip_path, 'wb') as f:
                f.write(game_files)
            
            # 解壓縮
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(game_dir)
            
            # 刪除 zip 檔
            os.remove(zip_path)
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to save game files: {str(e)}"}
        
        # 儲存 metadata
        game_id = f"{game_name}_{int(time.time())}"
        games_metadata[game_name] = {
            "game_id": game_id,
            "game_name": game_name,
            "developer": developer_name,
            "game_type": game_type,
            "description": description,
            "max_players": max_players,
            "version": version,
            "created_at": time.time(),
            "updated_at": time.time(),
            "status": "active",  # active / inactive
            "config": config,
            "download_count": 0,
            "average_rating": 0.0,
            "review_count": 0
        }
        
        if save_json_file(GAME_METADATA_FILE, games_metadata):
            return {
                "status": "success",
                "message": "Game uploaded successfully",
                "data": {"game_id": game_id, "game_name": game_name, "version": version}
            }
        else:
            return {"status": "error", "message": "Failed to save metadata"}


def handle_update_game(data, developer_name):
    """處理遊戲更新"""
    game_name = data.get("game_name")
    new_version = data.get("version")
    game_files_b64 = data.get("game_files")
    update_notes = data.get("update_notes", "")
    
    if not all([game_name, new_version, game_files_b64]):
        return {"status": "error", "message": "Missing required fields"}
    
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        # 檢查遊戲是否存在
        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}
        
        # 檢查權限
        if games_metadata[game_name]["developer"] != developer_name:
            return {"status": "error", "message": "Permission denied"}
        
        # 建立新版本目錄
        game_dir = os.path.join(GAMES_DIR, game_name, new_version)
        os.makedirs(game_dir, exist_ok=True)
        
        # 儲存新版本檔案
        try:
            game_files = base64.b64decode(game_files_b64)
            zip_path = os.path.join(game_dir, "game.zip")
            with open(zip_path, 'wb') as f:
                f.write(game_files)
            
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(game_dir)
            
            os.remove(zip_path)
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to save game files: {str(e)}"}
        
        # 更新 metadata
        games_metadata[game_name]["version"] = new_version
        games_metadata[game_name]["updated_at"] = time.time()
        games_metadata[game_name]["update_notes"] = update_notes
        
        if save_json_file(GAME_METADATA_FILE, games_metadata):
            return {
                "status": "success",
                "message": "Game updated successfully",
                "data": {"game_name": game_name, "new_version": new_version}
            }
        else:
            return {"status": "error", "message": "Failed to update metadata"}


def handle_remove_game(data, developer_name):
    """處理遊戲下架"""
    game_name = data.get("game_name")
    
    if not game_name:
        return {"status": "error", "message": "Missing game_name"}
    
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}
        
        # 檢查權限
        if games_metadata[game_name]["developer"] != developer_name:
            return {"status": "error", "message": "Permission denied"}
        
        # 標記為 inactive（不實際刪除檔案）
        games_metadata[game_name]["status"] = "inactive"
        games_metadata[game_name]["removed_at"] = time.time()
        
        if save_json_file(GAME_METADATA_FILE, games_metadata):
            return {
                "status": "success",
                "message": "Game removed successfully",
                "data": {"game_name": game_name}
            }
        else:
            return {"status": "error", "message": "Failed to remove game"}


def handle_list_my_games(developer_name):
    """列出開發者的所有遊戲"""
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        my_games = []
        for game_name, info in games_metadata.items():
            if info["developer"] == developer_name:
                my_games.append({
                    "game_name": game_name,
                    "version": info["version"],
                    "status": info["status"],
                    "download_count": info["download_count"],
                    "average_rating": info["average_rating"],
                    "created_at": info["created_at"],
                    "updated_at": info["updated_at"]
                })
        
        return {
            "status": "success",
            "data": {"games": my_games}
        }


# ==================== 房間管理 ====================

# 全局房間資料
rooms = {}  # {room_id: {room_info}}
room_id_counter = 1
rooms_lock = threading.Lock()

# 遊戲 Server 進程管理
game_servers = {}  # {room_id: process}
game_servers_lock = threading.Lock()


def generate_room_id():
    """產生唯一的房間 ID"""
    global room_id_counter
    room_id = f"ROOM_{room_id_counter:04d}"
    room_id_counter += 1
    return room_id


def handle_create_room(data, player_name):
    """建立遊戲房間"""
    game_name = data.get("game_name")
    
    if not game_name:
        return {"status": "error", "message": "Missing game_name"}
    
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}
        
        game_info = games_metadata[game_name]
        
        if game_info["status"] != "active":
            return {"status": "error", "message": "Game is not available"}
    
    with rooms_lock:
        room_id = generate_room_id()
        
        rooms[room_id] = {
            "room_id": room_id,
            "game_name": game_name,
            "version": game_info["version"],  # ← 新增：加入版本資訊
            "host": player_name,
            "players": [player_name],
            "max_players": game_info["max_players"],
            "status": "waiting",
            "created_at": time.time(),
            "game_server_port": None
        }
        
        return {
            "status": "success",
            "message": "Room created",
            "data": {
                "room_id": room_id,
                "game_name": game_name,
                "max_players": game_info["max_players"]
            }
        }


def handle_list_rooms():
    """列出所有房間"""
    with rooms_lock:
        room_list = []
        for room_id, room in rooms.items():
            if room["status"] != "finished":
                room_list.append({
                    "room_id": room_id,
                    "game_name": room["game_name"],
                    "host": room["host"],
                    "players": room["players"],
                    "current_players": len(room["players"]),
                    "max_players": room["max_players"],
                    "status": room["status"]
                })
        
        return {
            "status": "success",
            "data": {"rooms": room_list}
        }


def handle_get_room_status(data, player_name):
    """查詢房間狀態（即時更新）"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found or has been closed"}
        
        room = rooms[room_id]
        
        # 檢查玩家是否在房間內
        if player_name not in room["players"]:
            return {"status": "error", "message": "You are not in this room"}
        
        # 安全地獲取 version，如果沒有則從 metadata 中獲取
        version = room.get("version", "1.0.0")
        if not version or version == "1.0.0":
            # 嘗試從 game metadata 獲取最新版本
            try:
                with games_lock:
                    games_metadata = load_json_file(GAME_METADATA_FILE, {})
                    if room["game_name"] in games_metadata:
                        version = games_metadata[room["game_name"]]["version"]
            except:
                version = "1.0.0"
        
        return {
            "status": "success",
            "data": {
                "room_id": room_id,
                "game_name": room["game_name"],
                "version": version,
                "host": room["host"],
                "players": room["players"],
                "current_players": len(room["players"]),
                "max_players": room["max_players"],
                "status": room["status"],
                "is_host": (player_name == room["host"])
            }
        }


def handle_join_room(data, player_name):
    """加入房間"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if room["status"] != "waiting":
            return {"status": "error", "message": "Room is not accepting players"}
        
        if player_name in room["players"]:
            return {"status": "error", "message": "Already in room"}
        
        if len(room["players"]) >= room["max_players"]:
            return {"status": "error", "message": "Room is full"}
        
        room["players"].append(player_name)
        
        return {
            "status": "success",
            "message": "Joined room",
            "data": {
                "room_id": room_id,
                "game_name": room["game_name"],
                "players": room["players"]
            }
        }


def handle_leave_room(data, player_name):
    """離開房間"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if player_name not in room["players"]:
            return {"status": "error", "message": "Not in room"}
        
        room["players"].remove(player_name)
        
        # 如果房主離開，解散房間
        if player_name == room["host"]:
            # 停止 Game Server（如果有）
            if "game_server_pid" in room:
                try:
                    import signal
                    os.killpg(os.getpgid(room["game_server_pid"]), signal.SIGTERM)
                    print(f"🛑 Game Server stopped (PID: {room['game_server_pid']})")
                except Exception as e:
                    print(f"⚠️ Failed to stop game server: {e}")
            
            del rooms[room_id]
            return {
                "status": "success",
                "message": "Room disbanded (host left)"
            }
        
        return {
            "status": "success",
            "message": "Left room"
        }


def handle_start_game(data, player_name):
    """啟動遊戲（只有房主可以啟動）"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if player_name != room["host"]:
            return {"status": "error", "message": "Only host can start game"}
        
        if room["status"] != "waiting":
            return {"status": "error", "message": "Game already started"}
        
        if len(room["players"]) < 2:
            return {"status": "error", "message": "Need at least 2 players"}
        
        # 啟動遊戲 Server
        game_name = room["game_name"]
        game_dir = os.path.join(GAMES_DIR, game_name)
        
        # 尋找最新版本
        with games_lock:
            games_metadata = load_json_file(GAME_METADATA_FILE, {})
            if game_name not in games_metadata:
                return {"status": "error", "message": "Game not found"}
            
            version = games_metadata[game_name]["version"]
            config = games_metadata[game_name].get("config", {})
        
        game_version_dir = os.path.join(game_dir, version)
        
        if not os.path.exists(game_version_dir):
            return {"status": "error", "message": "Game files not found"}
        
        # 真正啟動 Game Server
        server_command = config.get("server_command")
        
        if not server_command:
            # 如果沒有 server_command，表示是純 Client 遊戲（如單機遊戲）
            room["status"] = "playing"
            return {
                "status": "success",
                "message": "Game starting (no server needed)",
                "data": {
                    "room_id": room_id,
                    "game_name": game_name,
                    "version": version,
                    "players": room["players"],
                    "config": config,
                    "server_port": None
                }
            }
        
        # 啟動 Game Server
        try:
            import subprocess
            import random
            
            # 分配動態 Port
            game_server_port = random.randint(20000, 30000)
            
            # 準備啟動命令
            if "{port}" in server_command:
                cmd = server_command.replace("{port}", str(game_server_port))
            else:
                cmd = f"{server_command} {game_server_port}"
            
            # 在遊戲目錄下啟動 Server
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=game_version_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # 儲存 process 資訊
            room["game_server_pid"] = process.pid
            room["game_server_port"] = game_server_port
            room["status"] = "playing"
            
            print(f"✅ Game Server started: {game_name} on port {game_server_port} (PID: {process.pid})")
            
            return {
                "status": "success",
                "message": "Game server started",
                "data": {
                    "room_id": room_id,
                    "game_name": game_name,
                    "version": version,
                    "players": room["players"],
                    "config": config,
                    "server_host": "localhost",
                    "server_port": game_server_port
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to start game server: {str(e)}"
            }


# ==================== Lobby/Player 相關功能 ====================

def handle_list_games():
    """列出所有可用遊戲"""
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        active_games = []
        for game_name, info in games_metadata.items():
            if info["status"] == "active":
                active_games.append({
                    "game_name": game_name,
                    "developer": info["developer"],
                    "game_type": info["game_type"],
                    "description": info["description"],
                    "max_players": info["max_players"],
                    "version": info["version"],
                    "average_rating": info["average_rating"],
                    "review_count": info["review_count"],
                    "download_count": info["download_count"]
                })
        
        return {
            "status": "success",
            "data": {"games": active_games}
        }


def handle_get_game_info(data):
    """取得遊戲詳細資訊"""
    game_name = data.get("game_name")
    
    if not game_name:
        return {"status": "error", "message": "Missing game_name"}
    
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}
        
        game_info = games_metadata[game_name].copy()
        
        # 取得評論
        reviews = load_json_file(REVIEWS_FILE, {})
        game_reviews = reviews.get(game_name, [])
        
        return {
            "status": "success",
            "data": {
                "game_info": game_info,
                "reviews": game_reviews[-10:]  # 最新 10 則評論
            }
        }


def handle_download_game(data):
    """處理遊戲下載請求"""
    game_name = data.get("game_name")
    
    if not game_name:
        return {"status": "error", "message": "Missing game_name"}
    
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}
        
        game_info = games_metadata[game_name]
        
        if game_info["status"] != "active":
            return {"status": "error", "message": "Game is not available"}
        
        version = game_info["version"]
        game_dir = os.path.join(GAMES_DIR, game_name, version)
        
        if not os.path.exists(game_dir):
            return {"status": "error", "message": "Game files not found"}
        
        # 打包遊戲檔案
        try:
            import zipfile
            import io
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(game_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, game_dir)
                        zip_file.write(file_path, arcname)
            
            zip_buffer.seek(0)
            game_files_b64 = base64.b64encode(zip_buffer.read()).decode('utf-8')
            
            # 更新下載次數
            games_metadata[game_name]["download_count"] += 1
            save_json_file(GAME_METADATA_FILE, games_metadata)
            
            return {
                "status": "success",
                "data": {
                    "game_name": game_name,
                    "version": version,
                    "game_files": game_files_b64,
                    "config": game_info.get("config", {})
                }
            }
        
        except Exception as e:
            return {"status": "error", "message": f"Failed to pack game: {str(e)}"}


def handle_submit_review(data, player_name):
    """處理遊戲評分與留言"""
    game_name = data.get("game_name")
    rating = data.get("rating")  # 1-5
    comment = data.get("comment", "")
    
    if not game_name or rating is None:
        return {"status": "error", "message": "Missing required fields"}
    
    if not (1 <= rating <= 5):
        return {"status": "error", "message": "Rating must be between 1 and 5"}
    
    with reviews_lock:
        reviews = load_json_file(REVIEWS_FILE, {})
        
        if game_name not in reviews:
            reviews[game_name] = []
        
        # 檢查是否已評論過
        for review in reviews[game_name]:
            if review["player"] == player_name:
                return {"status": "error", "message": "You have already reviewed this game"}
        
        # 新增評論
        reviews[game_name].append({
            "player": player_name,
            "rating": rating,
            "comment": comment,
            "timestamp": time.time()
        })
        
        # 更新遊戲評分
        with games_lock:
            games_metadata = load_json_file(GAME_METADATA_FILE, {})
            
            if game_name in games_metadata:
                all_ratings = [r["rating"] for r in reviews[game_name]]
                avg_rating = sum(all_ratings) / len(all_ratings)
                
                games_metadata[game_name]["average_rating"] = round(avg_rating, 2)
                games_metadata[game_name]["review_count"] = len(all_ratings)
                
                save_json_file(GAME_METADATA_FILE, games_metadata)
        
        if save_json_file(REVIEWS_FILE, reviews):
            return {
                "status": "success",
                "message": "Review submitted successfully"
            }
        else:
            return {"status": "error", "message": "Failed to save review"}


# ==================== Developer Client 處理 ====================

def handle_developer_client(conn, addr):
    """處理 Developer Client 連線"""
    print(f"[Developer] Connected from {addr}")
    developer_name = None
    
    try:
        # === 握手驗證 ===
        # 等待 Client 發送身份標識
        raw = recv_frame(conn)
        if not raw:
            print(f"[Developer] No handshake from {addr}")
            conn.close()
            return
        
        try:
            handshake = json.loads(raw.decode('utf-8'))
            client_type = handshake.get("client_type")
            
            # 檢查身份
            if client_type != "developer":
                error_msg = {
                    "status": "error",
                    "message": "❌ 這是 Developer Server！你連到了錯誤的 Port。\n請使用 Developer Client 連線，或改用 Lobby Port。"
                }
                send_frame(conn, json.dumps(error_msg).encode('utf-8'))
                print(f"[Developer] Wrong client type '{client_type}' from {addr}, closing connection")
                conn.close()
                return
            
            # 發送確認
            handshake_response = {
                "status": "success",
                "message": "Connected to Developer Server",
                "server_type": "developer"
            }
            send_frame(conn, json.dumps(handshake_response).encode('utf-8'))
            print(f"[Developer] Handshake successful with {addr}")
        
        except json.JSONDecodeError:
            print(f"[Developer] Invalid handshake from {addr}")
            conn.close()
            return
        # === 握手驗證結束 ===
        
        while True:
            raw = recv_frame(conn)
            if not raw:
                break
            
            try:
                request = json.loads(raw.decode('utf-8'))
                action = request.get("action")
                data = request.get("data", {})
                
                print(f"[Developer] Request from {addr}: {action}")
                
                # 登入
                if action == "login":
                    response = handle_developer_login(data)
                    if response["status"] == "success":
                        developer_name = data.get("username")
                
                # 需要登入的操作
                elif not developer_name:
                    response = {"status": "error", "message": "Please login first"}
                
                elif action == "upload_game":
                    response = handle_upload_game(data, developer_name)
                
                elif action == "update_game":
                    response = handle_update_game(data, developer_name)
                
                elif action == "remove_game":
                    response = handle_remove_game(data, developer_name)
                
                elif action == "list_my_games":
                    response = handle_list_my_games(developer_name)
                
                # 檢查是否為 Player action（錯誤連線）
                elif action in ["register", "list_games", "download_game", "create_room", 
                              "join_room", "leave_room", "start_game", "get_room_status", "list_rooms"]:
                    response = {
                        "status": "error", 
                        "message": "❌ 這是 Developer Server！請使用 Lobby Port 連線。"
                    }
                
                else:
                    response = {"status": "error", "message": f"Unknown action: {action}"}
                
                send_frame(conn, json.dumps(response).encode('utf-8'))
            
            except json.JSONDecodeError:
                response = {"status": "error", "message": "Invalid JSON"}
                send_frame(conn, json.dumps(response).encode('utf-8'))
    
    except Exception as e:
        print(f"[Developer] Error with {addr}: {e}")
    
    finally:
        conn.close()
        print(f"[Developer] Disconnected from {addr}")


# ==================== Lobby Client 處理 ====================

def handle_lobby_client(conn, addr):
    """處理 Lobby Client 連線"""
    print(f"[Lobby] Connected from {addr}")
    player_name = None
    
    try:
        # === 握手驗證 ===
        # 等待 Client 發送身份標識
        raw = recv_frame(conn)
        if not raw:
            print(f"[Lobby] No handshake from {addr}")
            conn.close()
            return
        
        try:
            handshake = json.loads(raw.decode('utf-8'))
            client_type = handshake.get("client_type")
            
            # 檢查身份
            if client_type != "player":
                error_msg = {
                    "status": "error",
                    "message": "❌ 這是 Lobby Server（玩家用）！你連到了錯誤的 Port。\n請使用 Player Client 連線，或改用 Developer Port。"
                }
                send_frame(conn, json.dumps(error_msg).encode('utf-8'))
                print(f"[Lobby] Wrong client type '{client_type}' from {addr}, closing connection")
                conn.close()
                return
            
            # 發送確認
            handshake_response = {
                "status": "success",
                "message": "Connected to Lobby Server",
                "server_type": "lobby"
            }
            send_frame(conn, json.dumps(handshake_response).encode('utf-8'))
            print(f"[Lobby] Handshake successful with {addr}")
        
        except json.JSONDecodeError:
            print(f"[Lobby] Invalid handshake from {addr}")
            conn.close()
            return
        # === 握手驗證結束 ===
        
        while True:
            raw = recv_frame(conn)
            if not raw:
                break
            
            try:
                request = json.loads(raw.decode('utf-8'))
                action = request.get("action")
                data = request.get("data", {})
                
                print(f"[Lobby] Request from {addr}: {action}")
                
                # 不需登入的操作
                if action == "list_games":
                    response = handle_list_games()
                
                elif action == "get_game_info":
                    response = handle_get_game_info(data)
                
                # 註冊和登入
                elif action == "register":
                    username = data.get("username")
                    password = data.get("password")
                    
                    if not username or not password:
                        response = {"status": "error", "message": "Missing username or password"}
                    else:
                        try:
                            # 連線到 DB Server 註冊
                            db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            db_sock.connect(("localhost", DB_PORT))
                            
                            db_request = {
                                "collection": "Player",
                                "action": "create",
                                "data": {"name": username, "password": password}
                            }
                            
                            send_frame(db_sock, json.dumps(db_request).encode('utf-8'))
                            db_response = json.loads(recv_frame(db_sock).decode('utf-8'))
                            db_sock.close()
                            
                            response = db_response
                            if response["status"] == "success":
                                print(f"[Lobby] Player {username} registered from {addr}")
                        
                        except Exception as e:
                            response = {"status": "error", "message": f"Register failed: {str(e)}"}
                
                elif action == "login":
                    username = data.get("username")
                    password = data.get("password")
                    
                    if not username or not password:
                        response = {"status": "error", "message": "Missing username or password"}
                    else:
                        try:
                            # 連線到 DB Server 驗證
                            db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            db_sock.connect(("localhost", DB_PORT))
                            
                            db_request = {
                                "collection": "Player",
                                "action": "query",
                                "data": {
                                    "type": "login",
                                    "name": username,
                                    "password": password
                                }
                            }
                            
                            send_frame(db_sock, json.dumps(db_request).encode('utf-8'))
                            db_response = json.loads(recv_frame(db_sock).decode('utf-8'))
                            db_sock.close()
                            
                            if db_response["status"] == "success":
                                # 檢查是否已經登入
                                with online_players_lock:
                                    if username in online_players:
                                        response = {"status": "error", "message": "此帳號已在其他地方登入"}
                                        print(f"[Lobby] Login rejected: {username} already online")
                                    else:
                                        # 記錄線上玩家
                                        online_players[username] = (conn, addr)
                                        player_name = username
                                        response = {"status": "success", "message": "Login successful"}
                                        print(f"[Lobby] Player {username} logged in from {addr}")
                            else:
                                response = {"status": "error", "message": "Invalid username or password"}
                        
                        except Exception as e:
                            response = {"status": "error", "message": f"Login failed: {str(e)}"}
                
                elif not player_name:
                    response = {"status": "error", "message": "Please login first"}
                
                elif action == "download_game":
                    response = handle_download_game(data)
                
                elif action == "submit_review":
                    response = handle_submit_review(data, player_name)
                
                # 房間相關操作
                elif action == "create_room":
                    response = handle_create_room(data, player_name)
                
                elif action == "list_rooms":
                    response = handle_list_rooms()
                
                elif action == "get_room_status":
                    response = handle_get_room_status(data, player_name)
                
                elif action == "join_room":
                    response = handle_join_room(data, player_name)
                
                elif action == "leave_room":
                    response = handle_leave_room(data, player_name)
                
                elif action == "start_game":
                    response = handle_start_game(data, player_name)
                
                # 檢查是否為 Developer action（錯誤連線）
                elif action in ["upload_game", "update_game", "remove_game", "list_my_games"]:
                    response = {
                        "status": "error", 
                        "message": "❌ 這是 Lobby Server（玩家用）！請使用 Developer Port 連線。"
                    }
                
                else:
                    response = {"status": "error", "message": f"Unknown action: {action}"}
                
                print(f"[Lobby] Response to {addr}: {response.get('status')}")
                send_frame(conn, json.dumps(response).encode('utf-8'))
            except json.JSONDecodeError as e:
                print(f"[Lobby] JSON decode error from {addr}: {e}")
                response = {"status": "error", "message": "Invalid JSON"}
                send_frame(conn, json.dumps(response).encode('utf-8'))

            except Exception as e:
                # 新增：捕獲並記錄所有異常
                print(f"[Lobby] Error processing request from {addr}: {e}")
                import traceback
                traceback.print_exc()
                response = {"status": "error", "message": f"Internal error: {str(e)}"}
                send_frame(conn, json.dumps(response).encode('utf-8'))
    
    except Exception as e:
        print(f"[Lobby] Error with {addr}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 移除線上玩家記錄
        if player_name:
            with online_players_lock:
                if player_name in online_players:
                    del online_players[player_name]
                    print(f"[Lobby] Player {player_name} logged out")
        
        conn.close()
        print(f"[Lobby] Disconnected from {addr}")


# ==================== 主程式 ====================

def start_developer_server():
    """啟動 Developer Server"""
    global DEVELOPER_PORT
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, 0))
    DEVELOPER_PORT = server_socket.getsockname()[1]
    server_socket.listen(5)
    
    print(f"[Developer Server] Listening on {HOST}:{DEVELOPER_PORT}")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_developer_client,
                args=(conn, addr),
                daemon=True
            )
            client_thread.start()
    except:
        pass
    finally:
        server_socket.close()


def start_lobby_server():
    """啟動 Lobby Server"""
    global LOBBY_PORT
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, 0))
    LOBBY_PORT = server_socket.getsockname()[1]
    server_socket.listen(5)
    
    print(f"[Lobby Server] Listening on {HOST}:{LOBBY_PORT}")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_lobby_client,
                args=(conn, addr),
                daemon=True
            )
            client_thread.start()
    except:
        pass
    finally:
        server_socket.close()


def main():
    global DB_PORT
    
    if len(sys.argv) < 2:
        print("Usage: python3 game_store_server.py <DB_PORT>")
        sys.exit(1)
    
    try:
        DB_PORT = int(sys.argv[1])
    except ValueError:
        print("Error: DB_PORT must be an integer")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("Game Store Server Starting...")
    print("="*60)
    
    # 啟動兩個 Server
    dev_thread = threading.Thread(target=start_developer_server, daemon=True)
    lobby_thread = threading.Thread(target=start_lobby_server, daemon=True)
    
    dev_thread.start()
    lobby_thread.start()
    
    # 等待 ports 被分配
    time.sleep(0.5)
    
    print("\n" + "="*60)
    print("Game Store Server Started Successfully!")
    print("="*60)
    print(f"\n🎮 Developer Server Port: {DEVELOPER_PORT}")
    print(f"🎯 Lobby Server Port: {LOBBY_PORT}")
    print(f"💾 DB Server Port: {DB_PORT}")
    print("\n" + "="*60)
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Game Store] Shutting down...")


if __name__ == "__main__":
    main()