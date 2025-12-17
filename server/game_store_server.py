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
# 取得腳本所在目錄（使用絕對路徑）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEVELOPER_PORT = 0  # Developer Server Port
LOBBY_PORT = 0      # Lobby Server Port

# 資料目錄（使用絕對路徑）
GAMES_DIR = os.path.join(SCRIPT_DIR, "uploaded_games")
DATA_DIR = os.path.join(SCRIPT_DIR, "game_store_data")
GAME_METADATA_FILE = os.path.join(DATA_DIR, "games_metadata.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
PLAYERS_FILE = os.path.join(SCRIPT_DIR, "players.json")

os.makedirs(GAMES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

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


def handle_developer_register(data):
    """處理開發者註冊"""
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return {"status": "error", "message": "Missing credentials"}
    
    # 向 DB Server 註冊
    try:
        db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        db_sock.connect((DB_HOST, DB_PORT))
        
        request = {
            "collection": "Developer",
            "action": "create",
            "data": {"name": username, "password": password}
        }
        
        send_frame(db_sock, json.dumps(request).encode('utf-8'))
        response_raw = recv_frame(db_sock)
        db_sock.close()
        
        if response_raw:
            response = json.loads(response_raw.decode('utf-8'))
            if response["status"] == "success":
                print(f"[Developer] Developer {username} registered")
            return response
        else:
            return {"status": "error", "message": "DB connection failed"}
    
    except Exception as e:
        print(f"[Developer] Register error: {e}")
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
    
    # 強制要求 start_command
    start_command = config.get("start_command", "").strip()
    if not start_command:
        return {"status": "error", "message": "start_command is required in config"}
    
    # 驗證 start_command 格式（必須包含佔位符）
    if "{host}" not in start_command or "{port}" not in start_command:
        return {"status": "error", "message": "start_command must include {host} and {port} placeholders"}
    
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
        
        # 檢查遊戲狀態
        if games_metadata[game_name]["status"] != "active":
            return {"status": "error", "message": "Cannot update inactive game. Please re-upload the game instead."}
        
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
        
        if not save_json_file(GAME_METADATA_FILE, games_metadata):
            return {"status": "error", "message": "Failed to update metadata"}
    
    # 刪除所有正在運行此遊戲的房間（類似下架遊戲的處理）
    removed_rooms = []
    with rooms_lock:
        rooms_to_delete = []
        
        # 找出所有使用此遊戲的房間
        for room_id, room in rooms.items():
            if room["game_name"] == game_name:
                rooms_to_delete.append((room_id, room.copy()))
        
        # 刪除房間並停止遊戲 Server
        for room_id, room in rooms_to_delete:
            if "game_server_pid" in room:
                try:
                    import signal
                    os.killpg(os.getpgid(room["game_server_pid"]), signal.SIGTERM)
                    print(f"🛑 Game Server stopped for room {room_id} (game update)")
                except Exception as e:
                    print(f"⚠️ Failed to stop game server: {e}")
            
            del rooms[room_id]
            removed_rooms.append({
                "room_id": room_id,
                "players": room["players"],
                "status": room["status"]
            })
    
    message = f"Game updated to version {new_version}"
    if removed_rooms:
        message += f" and {len(removed_rooms)} room(s) deleted"
    
    return {
        "status": "success",
        "message": message,
        "data": {
            "game_name": game_name,
            "new_version": new_version,
            "removed_rooms": removed_rooms
        }
    }


def handle_remove_game(data, developer_name):
    """處理遊戲下架（完全刪除）並移除相關房間"""
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
        
        # 完全刪除遊戲（從 metadata 移除）
        del games_metadata[game_name]
        
        # 刪除遊戲檔案
        game_dir = os.path.join(GAMES_DIR, game_name)
        try:
            if os.path.exists(game_dir):
                import shutil
                shutil.rmtree(game_dir)
        except Exception as e:
            print(f"[Warning] Failed to delete game files: {e}")
            # 繼續執行，即使檔案刪除失敗
        
        if not save_json_file(GAME_METADATA_FILE, games_metadata):
            return {"status": "error", "message": "Failed to remove game"}
    
    # 刪除該遊戲的所有房間（在 games_lock 外部執行，避免死鎖）
    removed_rooms = []
    with rooms_lock:
        rooms_to_delete = []
        
        # 找出所有該遊戲的房間
        for room_id, room in rooms.items():
            if room["game_name"] == game_name:
                rooms_to_delete.append((room_id, room.copy()))
        
        # 刪除房間並停止遊戲 server
        for room_id, room in rooms_to_delete:
            # 停止 Game Server（如果有）
            if "game_server_pid" in room:
                try:
                    import signal
                    os.killpg(os.getpgid(room["game_server_pid"]), signal.SIGTERM)
                    print(f"🛑 Game Server stopped for room {room_id} (PID: {room['game_server_pid']})")
                except Exception as e:
                    print(f"⚠️  Failed to stop game server for room {room_id}: {e}")
            
            # 刪除房間
            del rooms[room_id]
            removed_rooms.append({
                "room_id": room_id,
                "players": room["players"],
                "status": room["status"]
            })
            print(f"[Store] 🗑️  Room {room_id} deleted (game '{game_name}' removed)")
    
    # 返回結果
    result_message = f"Game '{game_name}' completely removed"
    if removed_rooms:
        result_message += f" and {len(removed_rooms)} room(s) deleted"
    
    return {
        "status": "success",
        "message": result_message,
        "data": {
            "game_name": game_name,
            "removed_rooms": removed_rooms
        }
    }


def handle_list_my_games(developer_name):
    """列出開發者的所有遊戲（只顯示 active）"""
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        my_games = []
        for game_name, info in games_metadata.items():
            # 只列出屬於該開發者且狀態為 active 的遊戲
            if info["developer"] == developer_name and info["status"] == "active":
                my_games.append({
                    "game_name": game_name,
                    "version": info["version"],
                    "game_type": info.get("game_type", "Unknown"),
                    "status": info["status"],
                    "download_count": info["download_count"],
                    "average_rating": info["average_rating"],
                    "review_count": info.get("review_count", 0),  # 新增
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
    player_version = data.get("version")  # 玩家的遊戲版本

    if not game_name:
        return {"status": "error", "message": "Missing game_name"}

    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})

        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}

        game_info = games_metadata[game_name]

        if game_info["status"] != "active":
            return {"status": "error", "message": "Game is not available"}

        # 驗證版本
        server_version = game_info.get("version", "1.0.0")
        if player_version and player_version != server_version:
            return {
                "status": "error",
                "message": f"版本不匹配！你的版本: {player_version}，最新版本: {server_version}。請先更新遊戲。"
            }

    with rooms_lock:
        room_id = generate_room_id()

        rooms[room_id] = {
            "room_id": room_id,
            "game_name": game_name,
            "version": server_version,  # 使用伺服器驗證後的版本
            "host": player_name,
            "players": [player_name],
            "ready_players": [],  # 準備就緒的玩家列表
            "max_players": game_info["max_players"],
            "status": "waiting",  # waiting / ready_check / playing / finished
            "created_at": time.time(),
            "game_server_port": None
        }

        return {
            "status": "success",
            "message": "Room created",
            "data": {
                "room_id": room_id,
                "game_name": game_name,
                "version": server_version,  # 回傳版本資訊
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
                    "version": room.get("version", "unknown"),  # 加入版本
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


def handle_list_online_players():
    """列出所有線上玩家及其狀態"""
    player_list = []
    
    with online_players_lock:
        online_usernames = set(online_players.keys())
    
    with rooms_lock:
        # 建立玩家到房間的映射
        player_room_map = {}  # {player_name: room_info}
        for room_id, room in rooms.items():
            if room["status"] != "finished":
                for player in room["players"]:
                    player_room_map[player] = {
                        "room_id": room_id,
                        "game_name": room["game_name"],
                        "room_status": room["status"],
                        "is_host": player == room["host"]
                    }
    
    # 組合玩家資訊
    for username in online_usernames:
        player_info = {
            "username": username,
            "status": "online"  # 預設狀態
        }
        
        if username in player_room_map:
            room_info = player_room_map[username]
            player_info["room_id"] = room_info["room_id"]
            player_info["game_name"] = room_info["game_name"]
            player_info["is_host"] = room_info["is_host"]
            
            if room_info["room_status"] == "playing":
                player_info["status"] = "playing"
            else:
                player_info["status"] = "in_room"
        else:
            player_info["status"] = "idle"  # 在大廳閒置
    
        player_list.append(player_info)
    
    # 按狀態排序：playing > in_room > idle
    status_order = {"playing": 0, "in_room": 1, "idle": 2}
    player_list.sort(key=lambda x: (status_order.get(x["status"], 3), x["username"]))
    
    return {
        "status": "success",
        "data": {
            "players": player_list,
            "total_online": len(player_list)
        }
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
        
        # 如果狀態是 playing，檢查 Game Server 是否還在運行
        if room.get("status") == "playing":
            game_process = room.get("game_server_process")
            game_server_pid = room.get("game_server_pid")
            
            should_reset = False
            reset_reason = ""
            
            if game_process:
                # 使用 poll() 檢查進程是否結束
                return_code = game_process.poll()
                if return_code is not None:
                    if return_code == 0:
                        reset_reason = "Game ended normally"
                    elif return_code == -2:
                        reset_reason = "Game interrupted (Ctrl+C)"
                    elif return_code == -15:
                        reset_reason = "Game terminated"
                    else:
                        reset_reason = f"Game ended (exit code: {return_code})"
                    should_reset = True
            elif game_server_pid:
                # 備用：用 os.kill 檢查
                try:
                    os.kill(game_server_pid, 0)
                except OSError:
                    reset_reason = f"Game Server (PID: {game_server_pid}) not running"
                    should_reset = True
            else:
                # 沒有 process 也沒有 PID 但狀態是 playing
                reset_reason = "No Game Server info"
                should_reset = True
            
            if should_reset:
                print(f"[Lobby] 🔄 Auto-reset room {room_id}: {reset_reason}")
                room["status"] = "waiting"
                room["game_server_pid"] = None
                room["game_server_port"] = None
                room["game_server_process"] = None
        
        # 準備基本房間資訊
        room_data = {
            "room_id": room_id,
            "game_name": room.get("game_name", "Unknown"),
            "version": room.get("version", "1.0.0"),
            "host": room.get("host", ""),
            "players": room.get("players", []),
            "current_players": len(room.get("players", [])),
            "max_players": room.get("max_players", 2),
            "status": room.get("status", "unknown"),
            "is_host": (player_name == room.get("host"))
        }
        
        # 如果在準備確認階段，加入準備狀態
        if room.get("status") == "ready_check":
            room_data["ready_players"] = room.get("ready_players", [])
            room_data["waiting_for"] = [p for p in room["players"] if p not in room.get("ready_players", [])]
            room_data["is_ready"] = player_name in room.get("ready_players", [])
        
        # 如果遊戲已啟動，加入遊戲伺服器資訊
        if room.get("status") == "playing":
            # 取得遊戲配置
            game_name = room.get("game_name")
            with games_lock:
                games_metadata = load_json_file(GAME_METADATA_FILE, {})
                if game_name in games_metadata:
                    room_data["config"] = games_metadata[game_name].get("config", {})
            
            room_data["server_port"] = room.get("game_server_port")
        
        return {
            "status": "success",
            "data": room_data
        }


def handle_join_room(data, player_name):
    """加入房間"""
    room_id = data.get("room_id")
    player_version = data.get("version")  # 玩家的遊戲版本
    
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
        
        # 檢查版本是否匹配
        room_version = room.get("version", "unknown")
        if player_version and player_version != room_version:
            return {
                "status": "error", 
                "message": f"版本不匹配！房間版本: {room_version}, 你的版本: {player_version}。請更新遊戲。"
            }
        
        room["players"].append(player_name)
        
        return {
            "status": "success",
            "message": "Joined room",
            "data": {
                "room_id": room_id,
                "game_name": room["game_name"],
                "version": room_version,
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
        
        is_host = (player_name == room["host"])
        
        # 移除玩家
        room["players"].remove(player_name)
        
        # 如果房主離開，解散房間
        if is_host:
            # 記錄剩餘玩家
            remaining_players = room["players"].copy()
            
            # 停止 Game Server（如果有）
            if "game_server_pid" in room:
                try:
                    import signal
                    os.killpg(os.getpgid(room["game_server_pid"]), signal.SIGTERM)
                    print(f"🛑 Game Server stopped (PID: {room['game_server_pid']})")
                except Exception as e:
                    print(f"⚠️ Failed to stop game server: {e}")
            
            # 刪除房間
            del rooms[room_id]
            
            print(f"[Lobby] 🏠 Room {room_id} disbanded (host {player_name} left)")
            if remaining_players:
                print(f"[Lobby] ⚠️  {len(remaining_players)} player(s) were in room: {', '.join(remaining_players)}")
            
            return {
                "status": "success",
                "message": "Room disbanded (host left)",
                "data": {
                    "room_id": room_id,
                    "disbanded": True,
                    "remaining_players": remaining_players
                }
            }
        
        # 如果房間空了，也刪除房間
        if not room["players"]:
            del rooms[room_id]
            print(f"[Lobby] 🏠 Room {room_id} deleted (empty)")
            return {
                "status": "success",
                "message": "Left room (room deleted)",
                "data": {
                    "room_id": room_id,
                    "disbanded": True
                }
            }
        
        return {
            "status": "success",
            "message": "Left room",
            "data": {
                "room_id": room_id,
                "disbanded": False,
                "remaining_players": len(room["players"])
            }
        }


def handle_start_game(data, player_name, client_ip=None):
    """啟動遊戲（房主專用）- 啟動 Game Server 並等待其他玩家加入"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if player_name != room["host"]:
            return {"status": "error", "message": "Only host can start game"}
        
        if room["status"] == "playing":
            return {"status": "error", "message": "Game already started"}
        
        if len(room["players"]) < 2:
            return {"status": "error", "message": "Need at least 2 players"}
        
        # 啟動 Game Server
        game_name = room["game_name"]
        game_dir = os.path.join(GAMES_DIR, game_name)
        
        with games_lock:
            games_metadata = load_json_file(GAME_METADATA_FILE, {})
            if game_name not in games_metadata:
                return {"status": "error", "message": "Game not found"}
            
            version = games_metadata[game_name]["version"]
            config = games_metadata[game_name].get("config", {})
        
        game_version_dir = os.path.join(game_dir, version)
        
        if not os.path.exists(game_version_dir):
            return {"status": "error", "message": "Game files not found"}
        
        server_command = config.get("server_command")
        
        if not server_command:
            # 沒有 server_command，純客戶端遊戲
            room["status"] = "playing"
            return {
                "status": "success",
                "message": "Game started (no server needed)",
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
            
            game_server_port = random.randint(20000, 30000)
            
            # 獲取當前房間的玩家數量
            num_players = len(room["players"])
            
            if "{port}" in server_command:
                cmd = server_command.replace("{port}", str(game_server_port))
            else:
                cmd = f"{server_command} {game_server_port}"
            
            # ⭐ 加上玩家數量參數
            cmd = f"{cmd} --players {num_players}"
            
            print(f"[Lobby] Starting Game Server...")
            print(f"[Lobby] Command: {cmd}")
            print(f"[Lobby] Players: {num_players}")
            
            log_file = open(f"/tmp/game_server_{game_server_port}.log", "w")
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=game_version_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            import time
            time.sleep(0.5)
            
            if process.poll() is not None:
                return {"status": "error", "message": "Game Server failed to start"}
            
            # 更新房間狀態
            room["game_server_pid"] = process.pid
            room["game_server_port"] = game_server_port
            room["game_server_process"] = process  # 保存 process 對象
            room["status"] = "playing"
            
            print(f"✅ Game Server started on port {game_server_port} (PID: {process.pid})")
            
            # 啟動監控線程，當 Game Server 結束時自動重置房間
            def monitor_game_server(proc, rid):
                """監控遊戲伺服器進程，結束時自動重置房間"""
                try:
                    # 等待 Game Server 結束（會阻塞直到進程結束）
                    return_code = proc.wait()
                    
                    if return_code == 0:
                        print(f"[Lobby] ✅ Game Server (PID: {proc.pid}) ended normally")
                    elif return_code == -2:  # SIGINT (Ctrl+C)
                        print(f"[Lobby] ⚠️  Game Server (PID: {proc.pid}) interrupted by Ctrl+C")
                    elif return_code == -15:  # SIGTERM
                        print(f"[Lobby] ⚠️  Game Server (PID: {proc.pid}) terminated")
                    else:
                        print(f"[Lobby] ⚠️  Game Server (PID: {proc.pid}) ended with code {return_code}")
                        
                except Exception as e:
                    print(f"[Lobby] ⚠️  Monitor exception for PID {proc.pid}: {e}")
                
                # 自動重置房間狀態
                try:
                    with rooms_lock:
                        if rid in rooms:
                            r = rooms[rid]
                            old_status = r["status"]
                            r["status"] = "waiting"
                            r["game_server_pid"] = None
                            r["game_server_port"] = None
                            r["game_server_process"] = None
                            print(f"[Lobby] 🔄 Room {rid} reset: '{old_status}' → 'waiting'")
                        else:
                            print(f"[Lobby] ⚠️  Room {rid} no longer exists, cannot reset")
                except Exception as e:
                    print(f"[Lobby] ❌ Error resetting room {rid}: {e}")
            
            import threading
            monitor_thread = threading.Thread(
                target=monitor_game_server,
                args=(process, room_id),
                daemon=True
            )
            monitor_thread.start()
            
            # ⭐ 不回傳 server_host，讓客戶端用它連線 Game Store Server 的地址
            # 因為 Game Server 和 Game Store Server 在同一台機器
            
            return {
                "status": "success",
                "message": "Game server started! Connect now.",
                "data": {
                    "room_id": room_id,
                    "game_name": game_name,
                    "version": version,
                    "players": room["players"],
                    "config": config,
                    "server_port": game_server_port
                }
            }
            
        except Exception as e:
            import traceback
            print(f"[Lobby] ❌ Exception: {traceback.format_exc()}")
            return {"status": "error", "message": f"Failed to start: {str(e)}"}


def handle_player_ready(data, player_name):
    """玩家準備就緒"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if player_name not in room["players"]:
            return {"status": "error", "message": "Not in room"}
        
        if room["status"] != "ready_check":
            return {"status": "error", "message": "Not in ready check phase"}
        
        if player_name in room["ready_players"]:
            return {"status": "error", "message": "Already ready"}
        
        # 標記為準備就緒
        room["ready_players"].append(player_name)
        
        print(f"[Lobby] Room {room_id}: {player_name} is ready ({len(room['ready_players'])}/{len(room['players'])})")
        
        # 檢查是否所有人都準備好了
        if len(room["ready_players"]) == len(room["players"]):
            # 所有人都準備好，自動啟動遊戲
            print(f"[Lobby] Room {room_id}: All players ready! Starting game...")
            return _actually_start_game(room_id, room)
        
        return {
            "status": "success",
            "message": "You are ready",
            "data": {
                "room_id": room_id,
                "ready_players": room["ready_players"],
                "total_players": len(room["players"]),
                "waiting_for": [p for p in room["players"] if p not in room["ready_players"]],
                "all_ready": False
            }
        }


def handle_cancel_ready_check(data, player_name):
    """取消準備確認（房主專用）"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if player_name != room["host"]:
            return {"status": "error", "message": "Only host can cancel"}
        
        if room["status"] != "ready_check":
            return {"status": "error", "message": "Not in ready check phase"}
        
        # 取消準備確認
        room["status"] = "waiting"
        room["ready_players"] = []
        
        print(f"[Lobby] Room {room_id}: Ready check cancelled by host")
        
        return {
            "status": "success",
            "message": "Ready check cancelled",
            "data": {"room_id": room_id}
        }


def _actually_start_game(room_id, room):
    """實際啟動遊戲（內部函數，已持有 rooms_lock）"""
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
        # 如果沒有 server_command，表示是純 Client 遊戲
        room["status"] = "playing"
        return {
            "status": "success",
            "message": "Game started (no server needed)",
            "data": {
                "room_id": room_id,
                "game_name": game_name,
                "version": version,
                "players": room["players"],
                "config": config,
                "server_port": None,
                "all_ready": True,
                "game_started": True
            }
        }
    
    # 啟動 Game Server
    try:
        import subprocess
        import random
        
        # 分配動態 Port
        game_server_port = random.randint(20000, 30000)
        
        # 獲取當前房間的玩家數量
        num_players = len(room["players"])
        
        # 準備啟動命令
        if "{port}" in server_command:
            cmd = server_command.replace("{port}", str(game_server_port))
        else:
            cmd = f"{server_command} {game_server_port}"
        
        # ⭐ 加上玩家數量參數
        cmd = f"{cmd} --players {num_players}"
        
        print(f"[Lobby] Starting Game Server...")
        print(f"[Lobby] Working directory: {game_version_dir}")
        print(f"[Lobby] Command: {cmd}")
        print(f"[Lobby] Players: {num_players}")
        
        # 在遊戲目錄下啟動 Server
        log_file = open(f"/tmp/game_server_{game_server_port}.log", "w")
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=game_version_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        print(f"[Lobby] Game Server output: /tmp/game_server_{game_server_port}.log")
        
        # 等待一下確認進程啟動
        import time
        time.sleep(0.5)
        
        # 檢查進程是否還活著
        if process.poll() is not None:
            # 進程已經結束了
            stdout, stderr = process.communicate()
            error_msg = stderr.decode('utf-8') if stderr else stdout.decode('utf-8') if stdout else "Unknown error"
            print(f"[Lobby] ❌ Game Server failed to start!")
            print(f"[Lobby] Error: {error_msg}")
            room["status"] = "waiting"
            room["ready_players"] = []
            return {
                "status": "error",
                "message": f"Game Server failed to start: {error_msg[:200]}"
            }
        
        # 儲存 process 資訊
        room["game_server_pid"] = process.pid
        room["game_server_port"] = game_server_port
        room["game_server_process"] = process  # 保存 process 對象
        room["status"] = "playing"
        
        print(f"✅ Game Server started: {game_name} on port {game_server_port} (PID: {process.pid})")
        
        # 啟動監控線程，當 Game Server 結束時自動重置房間
        def monitor_game_server(proc, rid):
            """監控遊戲伺服器進程，結束時自動重置房間"""
            try:
                # 等待 Game Server 結束（會阻塞直到進程結束）
                return_code = proc.wait()
                
                if return_code == 0:
                    print(f"[Lobby] ✅ Game Server (PID: {proc.pid}) ended normally")
                elif return_code == -2:  # SIGINT (Ctrl+C)
                    print(f"[Lobby] ⚠️  Game Server (PID: {proc.pid}) interrupted by Ctrl+C")
                elif return_code == -15:  # SIGTERM
                    print(f"[Lobby] ⚠️  Game Server (PID: {proc.pid}) terminated")
                else:
                    print(f"[Lobby] ⚠️  Game Server (PID: {proc.pid}) ended with code {return_code}")
                    
            except Exception as e:
                print(f"[Lobby] ⚠️  Monitor exception for PID {proc.pid}: {e}")
            
            # 自動重置房間狀態
            try:
                with rooms_lock:
                    if rid in rooms:
                        r = rooms[rid]
                        old_status = r["status"]
                        r["status"] = "waiting"
                        r["game_server_pid"] = None
                        r["game_server_port"] = None
                        r["game_server_process"] = None
                        print(f"[Lobby] 🔄 Room {rid} reset: '{old_status}' → 'waiting'")
                    else:
                        print(f"[Lobby] ⚠️  Room {rid} no longer exists, cannot reset")
            except Exception as e:
                print(f"[Lobby] ❌ Error resetting room {rid}: {e}")
        
        import threading
        monitor_thread = threading.Thread(
            target=monitor_game_server, 
            args=(process, room_id),
            daemon=True
        )
        monitor_thread.start()
        
        # ⭐ 不回傳 server_host，讓客戶端用它連線 Game Store Server 的地址
        
        return {
            "status": "success",
            "message": "Game server started! Connect now.",
            "data": {
                "room_id": room_id,
                "game_name": game_name,
                "version": version,
                "players": room["players"],
                "config": config,
                "server_port": game_server_port
            }
        }
        
    except Exception as e:
        import traceback
        print(f"[Lobby] ❌ Exception starting game server:")
        print(traceback.format_exc())
        room["status"] = "waiting"
        room["ready_players"] = []
        return {
            "status": "error",
            "message": f"Failed to start game server: {str(e)}"
        }


def handle_reset_room(data, player_name):
    """重置房間狀態（只有房主可以重置，用於遊戲結束後重新開始）"""
    room_id = data.get("room_id")
    
    if not room_id:
        return {"status": "error", "message": "Missing room_id"}
    
    with rooms_lock:
        if room_id not in rooms:
            return {"status": "error", "message": "Room not found"}
        
        room = rooms[room_id]
        
        if player_name != room["host"]:
            return {"status": "error", "message": "Only host can reset room"}
        
        # 如果有遊戲伺服器在運行，先停止它
        if room.get("game_server_pid"):
            try:
                import signal
                os.kill(room["game_server_pid"], signal.SIGTERM)
                print(f"[Lobby] Stopped game server PID {room['game_server_pid']}")
            except:
                pass  # 進程可能已經結束
        
        # 重置房間狀態
        room["status"] = "waiting"
        room["game_server_pid"] = None
        room["game_server_port"] = None
        
        print(f"[Lobby] Room {room_id} reset to waiting by {player_name}")
        
        return {
            "status": "success",
            "message": "Room reset to waiting",
            "data": {
                "room_id": room_id,
                "status": room["status"],
                "players": room["players"]
            }
        }


# ==================== Lobby/Player 相關功能 ====================


# ==================== 評論相關功能 ====================



def handle_get_reviews(data, player_name):
    """獲取遊戲評論"""
    game_name = data.get("game_name")
    
    if not game_name:
        return {"status": "error", "message": "Missing game_name"}
    
    # 載入評論數據
    reviews = load_json_file(REVIEWS_FILE, {})
    game_reviews = reviews.get(game_name, [])
    
    # 計算平均評分
    if game_reviews:
        avg_rating = sum(r["rating"] for r in game_reviews) / len(game_reviews)
    else:
        avg_rating = 0
    
    return {
        "status": "success",
        "data": {
            "game_name": game_name,
            "reviews": game_reviews,
            "total_reviews": len(game_reviews),
            "average_rating": round(avg_rating, 1)
        }
    }


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


def handle_download_game(data, player_name):
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
            
            # 記錄玩家下載歷史（新增）
            with online_players_lock:
                players = load_json_file(PLAYERS_FILE, {})
                
                # ⭐ 如果玩家不存在，自動創建
                if player_name not in players:
                    players[player_name] = {
                        "downloaded_games": []
                    }
                    print(f"[Download] 創建新玩家記錄: {player_name}")
                
                if "downloaded_games" not in players[player_name]:
                    players[player_name]["downloaded_games"] = []
                
                # 避免重複記錄
                if game_name not in players[player_name]["downloaded_games"]:
                    players[player_name]["downloaded_games"].append(game_name)
                    save_json_file(PLAYERS_FILE, players)
                    print(f"[Download] 記錄玩家 {player_name} 下載遊戲 {game_name}")
                else:
                    print(f"[Download] 玩家 {player_name} 已下載過 {game_name}（重新下載）")
            
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
    
    # 檢查遊戲是否存在且狀態為 active
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        if game_name not in games_metadata:
            return {"status": "error", "message": "Game not found"}
        
        # 檢查遊戲狀態（已下架的遊戲不能評論）
        if games_metadata[game_name]["status"] != "active":
            return {"status": "error", "message": "Cannot review inactive game"}
    
    # 檢查玩家是否下載過這個遊戲
    with online_players_lock:
        players = load_json_file(PLAYERS_FILE, {})
        if player_name not in players:
            return {"status": "error", "message": "Player not found"}
        
        player_games = players[player_name].get("downloaded_games", [])
        if game_name not in player_games:
            return {"status": "error", "message": "You must download the game before reviewing"}
    
    with reviews_lock:
        # 載入現有評論
        reviews = load_json_file(REVIEWS_FILE, {})
        print(f"[Review] 載入評論檔案: {REVIEWS_FILE}")
        print(f"[Review] 現有評論數: {len(reviews.get(game_name, []))}")
        
        if game_name not in reviews:
            reviews[game_name] = []
        
        # 檢查是否已評論過（同一玩家只能有一則評論）
        existing_review_index = None
        for i, review in enumerate(reviews[game_name]):
            if review["player"] == player_name:
                existing_review_index = i
                break
        
        # 建立新評論
        new_review = {
            "player": player_name,
            "rating": rating,
            "comment": comment,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if existing_review_index is not None:
            # 更新現有評論（同一玩家的舊評論被替換）
            reviews[game_name][existing_review_index] = new_review
            message = "Review updated successfully"
            print(f"[Review] 更新玩家 {player_name} 的評論")
        else:
            # 新增評論
            reviews[game_name].append(new_review)
            message = "Review submitted successfully"
            print(f"[Review] 新增玩家 {player_name} 的評論")
        
        print(f"[Review] 儲存後評論數: {len(reviews[game_name])}")
        
        # 先保存評論文件
        if not save_json_file(REVIEWS_FILE, reviews):
            print(f"[Review] 評論儲存失敗!")
            return {"status": "error", "message": "Failed to save review"}
        
        print(f"[Review] 評論已儲存到 {REVIEWS_FILE}")
    
    # 在 reviews_lock 外更新遊戲評分（避免嵌套鎖）
    with games_lock:
        games_metadata = load_json_file(GAME_METADATA_FILE, {})
        
        if game_name in games_metadata:
            # 重新計算平均分數
            all_ratings = [r["rating"] for r in reviews[game_name]]
            avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0.0
            
            old_rating = games_metadata[game_name].get("average_rating", 0.0)
            old_count = games_metadata[game_name].get("review_count", 0)
            
            games_metadata[game_name]["average_rating"] = round(avg_rating, 2)
            games_metadata[game_name]["review_count"] = len(all_ratings)
            
            print(f"[Review] 更新遊戲 '{game_name}' 評分:")
            print(f"[Review]   舊評分: {old_rating:.2f} ({old_count} 則)")
            print(f"[Review]   新評分: {avg_rating:.2f} ({len(all_ratings)} 則)")
            
            if not save_json_file(GAME_METADATA_FILE, games_metadata):
                print(f"[Review] ⚠️  警告: 遊戲評分更新失敗!")
                # 不返回錯誤，因為評論已經保存成功
            else:
                print(f"[Review] ✅ 遊戲評分已更新")
        else:
            print(f"[Review] ⚠️  警告: 遊戲 '{game_name}' 不存在於 metadata")
    
    return {
        "status": "success",
        "message": message
    }



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
                
                # 註冊
                elif action == "register":
                    response = handle_developer_register(data)
                
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
                
                # 初始化 response
                response = {"status": "error", "message": "Action not handled"}
                
                try:
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
                        response = handle_download_game(data, player_name)
                    
                    elif action == "submit_review":
                        response = handle_submit_review(data, player_name)
                    
                    # 房間相關操作
                    elif action == "create_room":
                        response = handle_create_room(data, player_name)
                    
                    elif action == "list_rooms":
                        response = handle_list_rooms()
                    
                    elif action == "list_online_players":
                        response = handle_list_online_players()
                    
                    elif action == "get_room_status":
                        response = handle_get_room_status(data, player_name)
                    
                    elif action == "get_reviews":
                        response = handle_get_reviews(data, player_name)
                    
                    elif action == "join_room":
                        response = handle_join_room(data, player_name)
                    
                    elif action == "leave_room":
                        response = handle_leave_room(data, player_name)
                    
                    elif action == "start_game":
                        response = handle_start_game(data, player_name, addr[0])
                    
                    elif action == "player_ready":
                        response = handle_player_ready(data, player_name)
                    
                    elif action == "cancel_ready_check":
                        response = handle_cancel_ready_check(data, player_name)
                    
                    elif action == "reset_room":
                        response = handle_reset_room(data, player_name)
                    
                    # 檢查是否為 Developer action（錯誤連線）
                    elif action in ["upload_game", "update_game", "remove_game", "list_my_games"]:
                        response = {
                            "status": "error", 
                            "message": "❌ 這是 Lobby Server（玩家用）！請使用 Developer Port 連線。"
                        }
                    
                    else:
                        response = {"status": "error", "message": f"Unknown action: {action}"}
                
                except Exception as e:
                    # 處理 action 時出錯，回傳錯誤但不斷線
                    import traceback
                    print(f"[Lobby] ❌ Error handling action '{action}': {e}")
                    print(traceback.format_exc())
                    response = {
                        "status": "error",
                        "message": f"Server error while handling {action}: {str(e)}"
                    }
                
                # 回傳 response
                send_frame(conn, json.dumps(response).encode('utf-8'))
            
            except json.JSONDecodeError:
                response = {"status": "error", "message": "Invalid JSON"}
                send_frame(conn, json.dumps(response).encode('utf-8'))
    
    except ConnectionResetError:
        print(f"[Lobby] Connection reset by {addr} (client closed)")
    
    except BrokenPipeError:
        print(f"[Lobby] Broken pipe with {addr} (client closed)")
    
    except Exception as e:
        print(f"[Lobby] Error with {addr}: {e}")
    
    finally:
        # 玩家斷線清理
        if player_name:
            print(f"[Lobby] Cleaning up for disconnected player: {player_name}")
            
            # 1. 檢查玩家是否在房間中，自動離開
            player_room = None
            with online_players_lock:
                for room_id, room in list(rooms.items()):
                    if player_name in room.get("players", []):
                        player_room = room_id
                        break
            
            if player_room:
                print(f"[Lobby] Player {player_name} was in room {player_room}, auto-leaving...")
                # 呼叫離開房間的邏輯
                leave_result = handle_leave_room({"room_id": player_room}, player_name)
                print(f"[Lobby] Auto-leave result: {leave_result.get('message', '')}")
            
            # 2. 移除線上玩家記錄
            with online_players_lock:
                if player_name in online_players:
                    del online_players[player_name]
                    print(f"[Lobby] Player {player_name} removed from online list")
        
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