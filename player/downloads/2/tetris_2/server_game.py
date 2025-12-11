#!/usr/bin/env python3
"""
Tetris Game Server - 支援多人對戰的俄羅斯方塊遊戲伺服器
用於 HW3 Game Store 系統
"""

import socket
import sys
import time
import json
import random
import threading
from lpfp import send_frame, recv_frame

# 遊戲常數
ROWS, COLS = 20, 10

TETROMINOS = {
    'I': [[1, 1, 1, 1]],
    'O': [[1, 1], [1, 1]],
    'T': [[0, 1, 0], [1, 1, 1]],
    'S': [[0, 1, 1], [1, 1, 0]],
    'Z': [[1, 1, 0], [0, 1, 1]],
    'J': [[1, 0, 0], [1, 1, 1]],
    'L': [[0, 0, 1], [1, 1, 1]]
}


class ServerTetrisGame:
    """伺服器端的俄羅斯方塊遊戲邏輯"""
    
    def __init__(self, player_name, seed):
        self.player_name = player_name
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.score = 0
        self.lines_cleared = 0
        self.game_over = False
        self.last_update = time.time()
        self.drop_interval = 0.5
        self.last_input_time = 0
        self.input_cooldown = 0.05
        
        random.seed(seed)
        self.spawn_piece()
    
    def spawn_piece(self):
        """生成新方塊"""
        shape_name = random.choice(list(TETROMINOS.keys()))
        shape = TETROMINOS[shape_name]
        self.falling = {
            'shape': shape,
            'name': shape_name,
            'x': COLS // 2 - len(shape[0]) // 2,
            'y': 0
        }
        
        if self.collide(self.falling):
            self.game_over = True
    
    def collide(self, piece, offset_x=0, offset_y=0):
        """檢測碰撞"""
        for y, row in enumerate(piece['shape']):
            for x, cell in enumerate(row):
                if cell:
                    new_x = piece['x'] + x + offset_x
                    new_y = piece['y'] + y + offset_y
                    
                    if new_x < 0 or new_x >= COLS or new_y >= ROWS:
                        return True
                    if new_y >= 0 and self.board[new_y][new_x]:
                        return True
        return False
    
    def lock_piece(self):
        """鎖定方塊到棋盤"""
        for y, row in enumerate(self.falling['shape']):
            for x, cell in enumerate(row):
                if cell:
                    board_y = self.falling['y'] + y
                    board_x = self.falling['x'] + x
                    if board_y >= 0:
                        self.board[board_y][board_x] = 1
        
        lines = self.clear_lines()
        self.score += lines * 100
        self.spawn_piece()
    
    def clear_lines(self):
        """清除完整的行"""
        lines = 0
        y = ROWS - 1
        while y >= 0:
            if all(self.board[y]):
                del self.board[y]
                self.board.insert(0, [0] * COLS)
                lines += 1
                self.lines_cleared += 1
            else:
                y -= 1
        return lines
    
    def move_left(self):
        """向左移動"""
        if not self.collide(self.falling, offset_x=-1):
            self.falling['x'] -= 1
            return True
        return False
    
    def move_right(self):
        """向右移動"""
        if not self.collide(self.falling, offset_x=1):
            self.falling['x'] += 1
            return True
        return False
    
    def rotate(self):
        """旋轉方塊"""
        old_shape = self.falling['shape']
        self.falling['shape'] = list(zip(*old_shape[::-1]))
        
        if self.collide(self.falling):
            self.falling['shape'] = old_shape
            return False
        return True
    
    def soft_drop(self):
        """軟降（加速下落）"""
        self.falling['y'] += 1
        if self.collide(self.falling):
            self.falling['y'] -= 1
            self.lock_piece()
            return False
        return True
    
    def hard_drop(self):
        """硬降（直接落到底）"""
        while not self.collide(self.falling, offset_y=1):
            self.falling['y'] += 1
        self.lock_piece()
    
    def auto_drop(self):
        """自動下落"""
        now = time.time()
        if now - self.last_update >= self.drop_interval:
            self.falling['y'] += 1
            if self.collide(self.falling):
                self.falling['y'] -= 1
                self.lock_piece()
            self.last_update = now
            return True
        return False
    
    def handle_input(self, key):
        """處理玩家輸入"""
        if self.game_over:
            return False
        
        now = time.time()
        if now - self.last_input_time < self.input_cooldown:
            return False
        self.last_input_time = now
        
        if key == "LEFT":
            return self.move_left()
        elif key == "RIGHT":
            return self.move_right()
        elif key == "ROTATE":
            return self.rotate()
        elif key == "DOWN":
            return self.soft_drop()
        elif key == "HARD_DROP":
            self.hard_drop()
            return True
        return False
    
    def get_state(self):
        """獲取遊戲狀態"""
        return {
            'board': self.board,
            'falling': self.falling,
            'score': self.score,
            'lines': self.lines_cleared,
            'game_over': self.game_over
        }


class TetrisGameServer:
    """Tetris 遊戲伺服器"""
    
    def __init__(self, port, expected_players=2):
        self.port = port
        self.expected_players = expected_players
        self.games = {}  # {player_name: ServerTetrisGame}
        self.connections = {}  # {player_name: socket}
        self.game_seed = int(time.time())
        self.running = True
        self.game_started = False  # 遊戲是否已經開始
        self.broadcast_interval = 0.1
        self.player_counter = 0
        self.lock = threading.Lock()
        
        print(f"[Tetris Server] Game seed: {self.game_seed}")
        print(f"[Tetris Server] Waiting for {expected_players} players to connect")
        
    
    def broadcast_game_state(self):
        """定期廣播遊戲狀態給所有玩家"""
        while self.running:
            try:
                time.sleep(self.broadcast_interval)
                
                with self.lock:
                    current_players = len(self.games)
                
                # 檢查是否所有玩家都已連線
                if not self.game_started:
                    if current_players >= self.expected_players:
                        print(f"[Server] All {self.expected_players} players connected! Starting game...")
                        self.game_started = True
                        
                        # 發送遊戲開始訊息
                        start_message = {
                            "type": "GAME_START",
                            "message": "All players connected! Game starting!",
                            "players": list(self.games.keys())
                        }
                        start_bytes = json.dumps(start_message).encode("utf-8")
                        for conn in self.connections.values():
                            try:
                                send_frame(conn, start_bytes)
                            except:
                                pass
                    else:
                        # 發送等待訊息
                        waiting_message = {
                            "type": "WAITING",
                            "current_players": current_players,
                            "expected_players": self.expected_players,
                            "players": list(self.games.keys())
                        }
                        waiting_bytes = json.dumps(waiting_message).encode("utf-8")
                        for conn in self.connections.values():
                            try:
                                send_frame(conn, waiting_bytes)
                            except:
                                pass
                        continue
                
                # 遊戲已開始，正常廣播狀態
                if current_players < 2:
                    continue
                
                # 收集所有玩家的狀態
                states = {}
                with self.lock:
                    for player_name, game in self.games.items():
                        game.auto_drop()
                        states[player_name] = game.get_state()
                
                # 廣播給所有連接的玩家
                message = {
                    "type": "GAME_STATE",
                    "states": states
                }
                message_bytes = json.dumps(message).encode("utf-8")
                
                dead_connections = []
                for player_name, conn in list(self.connections.items()):
                    try:
                        send_frame(conn, message_bytes)
                    except:
                        dead_connections.append(player_name)
                
                for player_name in dead_connections:
                    with self.lock:
                        if player_name in self.connections:
                            del self.connections[player_name]
                        if player_name in self.games:
                            del self.games[player_name]
                
                # 檢查遊戲結束條件
                if self.game_started and len(self.games) >= 2:
                    for player_name, game in self.games.items():
                        if game.lines_cleared >= 1 or game.game_over:
                            self.end_game()
                            return
                            
            except Exception as e:
                print(f"[Broadcast] Error: {e}")
    
    def end_game(self):
        """結束遊戲並發送結果"""
        if len(self.games) < 2:
            return
        
        # 找出勝者
        players = list(self.games.keys())
        game1 = self.games[players[0]]
        game2 = self.games[players[1]]
        
        if game1.lines_cleared >= 1 and game2.lines_cleared < 1:
            winner = players[0]
        elif game2.lines_cleared >= 1 and game1.lines_cleared < 1:
            winner = players[1]
        elif game1.game_over and not game2.game_over:
            winner = players[1]
        elif game2.game_over and not game1.game_over:
            winner = players[0]
        else:
            # 平手或同時完成，比較分數
            winner = players[0] if game1.score >= game2.score else players[1]
        
        # 發送遊戲結束訊息
        results = [
            {"player": players[0], "score": game1.score, "lines": game1.lines_cleared},
            {"player": players[1], "score": game2.score, "lines": game2.lines_cleared}
        ]
        
        end_message = {
            "type": "GAME_END",
            "winner": winner,
            "results": results
        }
        end_message_bytes = json.dumps(end_message).encode("utf-8")
        
        for conn in self.connections.values():
            try:
                send_frame(conn, end_message_bytes)
            except:
                pass
        
        print(f"[Server] Game ended. Winner: {winner}")
        print(f"[Server] Shutting down in 2 seconds...")
        
        # 等待客戶端接收結果
        time.sleep(2)
        
        # 關閉所有連線
        for conn in self.connections.values():
            try:
                conn.close()
            except:
                pass
        
        # 停止伺服器
        self.running = False
        print(f"[Server] Server stopped.")

    def handle_client(self, conn, addr):
        """處理客戶端連線"""
        player_name = None
        
        try:
            while self.running:
                data = recv_frame(conn)
                if not data:
                    break
                
                try:
                    request = json.loads(data)
                    action = request.get("action")
                    
                    if action == "join":
                        with self.lock:
                            self.player_counter += 1
                            player_name = f"Player{self.player_counter}"
                            print(f"[Server] Player joined as: {player_name} (seed: {self.game_seed})")
                            self.games[player_name] = ServerTetrisGame(player_name, self.game_seed)
                            self.connections[player_name] = conn
                            current_count = len(self.games)
                        
                        response = {
                            "status": "success",
                            "message": "Joined game",
                            "player_name": player_name,
                            "seed": self.game_seed,
                            "current_players": current_count,
                            "expected_players": self.expected_players,
                            "state": self.games[player_name].get_state()
                        }
                        send_frame(conn, json.dumps(response).encode("utf-8"))
                        
                        print(f"[Server] Players: {current_count}/{self.expected_players}")
                        
                    elif action == "input":
                        key = request.get("key")
                        if player_name and player_name in self.games and self.game_started:
                            game = self.games[player_name]
                            game.handle_input(key)
                            response = {
                                "status": "success",
                                "state": game.get_state()
                            }
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                    
                    elif action == "get_state":
                        if player_name and player_name in self.games:
                            game = self.games[player_name]
                            if self.game_started:
                                game.auto_drop()
                            response = {
                                "status": "success",
                                "game_started": self.game_started,
                                "state": game.get_state()
                            }
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                    
                    elif action == "quit":
                        break
                    
                    else:
                        send_frame(conn, json.dumps({"status": "error", "message": "Unknown action"}).encode("utf-8"))
                
                except json.JSONDecodeError:
                    send_frame(conn, json.dumps({"status": "error", "message": "Invalid JSON"}).encode("utf-8"))
                except Exception as e:
                    print(f"Error handling request: {e}")
                    send_frame(conn, json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        
        except Exception as e:
            print(f"Connection error: {e}")
        
        finally:
            with self.lock:
                if player_name:
                    self.games.pop(player_name, None)
                    self.connections.pop(player_name, None)
            conn.close()
            print(f"[Server] Player {player_name} disconnected")
    
    def start(self):
        """啟動伺服器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)  # 設置 timeout 以便檢查 running 狀態
        
        # 啟動廣播線程
        broadcast_thread = threading.Thread(target=self.broadcast_game_state, daemon=True)
        broadcast_thread.start()
        print("[Tetris Server] Game state broadcast started")
        
        try:
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            print(f"[Tetris Server] Started on port {self.port}")
            print(f"[Tetris Server] Waiting for players...")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    print(f"[Tetris Server] Player connected from {addr}")
                    
                    # 每個玩家一個執行緒
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True
                    thread.start()
                
                except socket.timeout:
                    # timeout 時檢查 running 狀態
                    continue
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")
        
        finally:
            self.server_socket.close()
            print("[Tetris Server] Stopped")


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
            except ValueError:
                pass
    
    print(f"[Tetris Server] Starting with {expected_players} expected players")
    server = TetrisGameServer(port, expected_players)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.running = False


if __name__ == "__main__":
    main()