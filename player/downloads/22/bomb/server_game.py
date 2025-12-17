#!/usr/bin/env python3
"""
Number Bomb Game Server - 數字炸彈遊戲伺服器
支援 3-8 人多人對戰
"""

import socket
import sys
import time
import json
import threading
import random
from lpfp import send_frame, recv_frame


class NumberBombGame:
    """數字炸彈遊戲邏輯"""
    
    def __init__(self, min_players=2, max_players=8):
        self.min_players = min_players
        self.max_players = max_players
        self.players = []  # 玩家列表（按加入順序）
        self.current_player_index = 0
        self.bomb_number = None
        self.range_min = 1
        self.range_max = 99
        self.game_started = False
        self.game_over = False
        self.loser = None
        self.guess_history = []  # 猜測歷史
        
    def add_player(self, player_name):
        """加入玩家"""
        if len(self.players) >= self.max_players:
            return None
            
        # 檢查重複名稱
        original_name = player_name
        counter = 1
        while player_name in self.players:
            player_name = f"{original_name}_{counter}"
            counter += 1
        
        self.players.append(player_name)
        return player_name
    
    def can_start(self):
        """檢查是否可以開始遊戲"""
        return len(self.players) >= self.min_players
    
    def start_game(self):
        """開始遊戲"""
        if not self.can_start():
            return False
        
        self.bomb_number = random.randint(self.range_min + 1, self.range_max - 1)
        self.game_started = True
        self.current_player_index = 0
        print(f"[Game] 遊戲開始！炸彈數字: {self.bomb_number} (保密)")
        return True
    
    def get_current_player(self):
        """取得當前玩家"""
        if not self.game_started or self.game_over:
            return None
        return self.players[self.current_player_index]
    
    def make_guess(self, player_name, guess):
        """玩家猜數字"""
        if not self.game_started:
            return {"success": False, "message": "Game not started"}
        
        if self.game_over:
            return {"success": False, "message": "Game is over"}
        
        current_player = self.get_current_player()
        if player_name != current_player:
            return {"success": False, "message": "Not your turn"}
        
        # 檢查範圍
        if guess < self.range_min or guess > self.range_max:
            return {
                "success": False,
                "message": f"Number must be between {self.range_min} and {self.range_max}"
            }
        
        # 檢查是否踩到炸彈
        if guess == self.bomb_number:
            self.game_over = True
            self.loser = player_name
            self.guess_history.append({
                "player": player_name,
                "guess": guess,
                "result": "hit_bomb"
            })
            return {
                "success": True,
                "hit_bomb": True,
                "bomb": self.bomb_number,
                "loser": player_name
            }
        
        # 更新範圍
        old_range = (self.range_min, self.range_max)
        if guess < self.bomb_number:
            self.range_min = guess
        else:
            self.range_max = guess
        
        self.guess_history.append({
            "player": player_name,
            "guess": guess,
            "result": "safe",
            "new_range": [self.range_min, self.range_max]
        })
        
        # 輪到下一個玩家
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        
        return {
            "success": True,
            "hit_bomb": False,
            "new_range": [self.range_min, self.range_max]
        }
    
    def get_state(self):
        """取得遊戲狀態"""
        return {
            "players": self.players,
            "current_player": self.get_current_player(),
            "range": [self.range_min, self.range_max],
            "game_started": self.game_started,
            "game_over": self.game_over,
            "guess_history": self.guess_history[-5:]  # 只返回最近5次猜測
        }


class NumberBombServer:
    """數字炸彈遊戲伺服器"""
    
    def __init__(self, port, expected_players=2):
        self.port = port
        self.expected_players = max(2, min(8, expected_players))  # 限制 2-8 人
        self.game = NumberBombGame(min_players=self.expected_players, max_players=8)
        self.connections = {}  # {player_name: conn}
        self.running = True
        self.lock = threading.Lock()
        
    def broadcast(self, message, exclude_player=None):
        """廣播訊息給所有玩家"""
        message_bytes = json.dumps(message).encode("utf-8")
        
        with self.lock:
            for player_name, conn in list(self.connections.items()):
                if player_name != exclude_player:
                    try:
                        send_frame(conn, message_bytes)
                    except:
                        pass
    
    def broadcast_state(self):
        """廣播當前遊戲狀態給所有玩家"""
        state_msg = {
            "type": "STATE_UPDATE",
            "state": self.game.get_state()
        }
        self.broadcast(state_msg)
    
    def handle_client(self, conn, addr):
        """處理客戶端連線"""
        player_name = None
        
        try:
            print(f"[Server] Client connected from {addr}")
            
            # 等待加入請求
            data = recv_frame(conn)
            if not data:
                return
            
            request = json.loads(data)
            action = request.get("action")
            
            if action == "join":
                requested_name = request.get("player_name", f"Player_{len(self.game.players)+1}")
                
                with self.lock:
                    # 檢查遊戲是否已滿
                    if len(self.game.players) >= self.game.max_players:
                        response = {
                            "status": "error",
                            "message": "Game is full"
                        }
                        send_frame(conn, json.dumps(response).encode("utf-8"))
                        return
                    
                    # 加入玩家
                    player_name = self.game.add_player(requested_name)
                    if not player_name:
                        response = {
                            "status": "error",
                            "message": "Failed to join"
                        }
                        send_frame(conn, json.dumps(response).encode("utf-8"))
                        return
                    
                    self.connections[player_name] = conn
                    print(f"[Server] {player_name} joined ({len(self.game.players)}/{self.expected_players})")
                
                # 發送成功回應
                response = {
                    "status": "success",
                    "player_name": player_name,
                    "state": self.game.get_state()
                }
                send_frame(conn, json.dumps(response).encode("utf-8"))
                
                # ⭐ 如果人數足夠，直接開始遊戲
                with self.lock:
                    current_count = len(self.game.players)
                    min_needed = self.game.min_players
                    
                    print(f"[Server] Current: {current_count}, Need: {min_needed}, Expected: {self.expected_players}")
                    
                    if self.game.can_start() and not self.game.game_started:
                        self.game.start_game()
                        print(f"[Server] Game started with {current_count} players!")
                
                # 廣播最新狀態給所有玩家（包括遊戲是否已開始）
                time.sleep(0.1)  # 短暫延遲確保客戶端準備好
                self.broadcast_state()
            
            # 處理遊戲中的請求
            while self.running:
                data = recv_frame(conn)
                if not data:
                    break
                
                try:
                    request = json.loads(data)
                    action = request.get("action")
                    
                    if action == "guess":
                        guess = request.get("number")
                        
                        if not isinstance(guess, int):
                            response = {"status": "error", "message": "Invalid number"}
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                            continue
                        
                        with self.lock:
                            result = self.game.make_guess(player_name, guess)
                        
                        if result["success"]:
                            # 發送確認給猜測者
                            response = {"status": "success"}
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                            
                            # 廣播遊戲更新
                            if result.get("hit_bomb"):
                                # 遊戲結束
                                self.broadcast({
                                    "type": "GAME_END",
                                    "loser": result["loser"],
                                    "bomb": result["bomb"],
                                    "state": self.game.get_state()
                                })
                                
                                # 3秒後關閉伺服器
                                def shutdown():
                                    import time
                                    time.sleep(3)
                                    print("[Server] Game finished, shutting down...")
                                    self.running = False
                                
                                threading.Thread(target=shutdown, daemon=True).start()
                            else:
                                # 繼續遊戲
                                self.broadcast({
                                    "type": "GAME_UPDATE",
                                    "player": player_name,
                                    "guess": guess,
                                    "result": result,
                                    "state": self.game.get_state()
                                })
                        else:
                            response = {"status": "error", "message": result["message"]}
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                    
                    elif action == "quit":
                        print(f"[Server] {player_name} quit")
                        break
                    
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"[Server] Error handling request: {e}")
                    break
        
        except Exception as e:
            print(f"[Server] Connection error: {e}")
        
        finally:
            if player_name:
                with self.lock:
                    if player_name in self.connections:
                        del self.connections[player_name]
                    
                    # ⭐ 如果遊戲進行中有玩家離開，通知所有人遊戲結束
                    if self.game.game_started and not self.game.game_over:
                        print(f"[Server] {player_name} disconnected during game - ending game")
                        self.game.game_over = True
                        
                        # 廣播遊戲結束
                        self.broadcast({
                            "type": "GAME_ABORT",
                            "message": f"{player_name} 離開了遊戲",
                            "disconnected_player": player_name
                        })
                        
                        # 關閉伺服器
                        self.running = False
                    else:
                        print(f"[Server] {player_name} disconnected")
            conn.close()
    
    def start_game(self):
        """開始遊戲"""
        with self.lock:
            if self.game.start_game():
                # 廣播遊戲開始
                self.broadcast({
                    "type": "GAME_START",
                    "state": self.game.get_state()
                })
    
    def start(self):
        """啟動伺服器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.settimeout(1.0)  # 設置 timeout 以便定期檢查 running 狀態
        
        try:
            server_socket.bind(('0.0.0.0', self.port))
            server_socket.listen(10)
            print(f"[Number Bomb Server] Started on port {self.port}")
            print(f"[Number Bomb Server] ⭐⭐⭐ EXPECTING {self.expected_players} PLAYERS ⭐⭐⭐")
            print(f"[Number Bomb Server] Min to start: {self.game.min_players}, Max: {self.game.max_players}")
            sys.stdout.flush()
            
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True
                    thread.start()
                
                except socket.timeout:
                    # Timeout 是正常的，繼續循環以檢查 running 狀態
                    continue
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    if self.running:  # 只在還在運行時才印錯誤
                        print(f"[Server] Error: {e}")
        
        finally:
            server_socket.close()
            print("[Number Bomb Server] Stopped")


def main():
    """主程式"""
    if len(sys.argv) < 2:
        print("Usage: python3 server_game.py <port> [--players N]")
        sys.exit(1)

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)

    # 解析 --players 參數
    expected_players = 2  # 預設 2 人
    for i, arg in enumerate(sys.argv):
        if arg == "--players" and i + 1 < len(sys.argv):
            try:
                expected_players = int(sys.argv[i + 1])
                expected_players = max(2, min(8, expected_players))  # 限制 2-8 人
            except ValueError:
                pass

    print(f"[Number Bomb Server] Starting (expects {expected_players} players)")
    server = NumberBombServer(port, expected_players)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.running = False


if __name__ == "__main__":
    main()