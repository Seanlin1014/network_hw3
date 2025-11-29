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
    
    def __init__(self, port):
        self.port = port
        self.games = {}  # {player_name: ServerTetrisGame}
        self.connections = {}  # {player_name: socket}
        self.game_seed = int(time.time())
        self.running = True
        self.broadcast_interval = 0.1  # 每0.1秒廣播一次狀態
        self.player_counter = 0  # 玩家計數器，用於生成唯一ID
        self.game_start_time = None  # 遊戲開始時間
        
    
    def broadcast_game_state(self):
        """定期廣播遊戲狀態給所有玩家"""
        while self.running:
            try:
                time.sleep(self.broadcast_interval)
                
                if len(self.games) < 2:
                    # 等待兩個玩家都加入
                    continue
                
                # 記錄遊戲開始時間
                if self.game_start_time is None:
                    self.game_start_time = time.time()
                    print(f"[Server] Game started with {len(self.games)} players!")
                
                # 收集所有玩家的狀態
                states = {}
                for player_name, game in self.games.items():
                    game.auto_drop()  # 自動下落
                    states[player_name] = game.get_state()
                
                print(f"[Broadcast] Sending game state to {len(self.connections)} players")
                
                # 廣播給所有連接的玩家
                message = {
                    "type": "GAME_STATE",
                    "states": states
                }
                message_bytes = json.dumps(message).encode("utf-8")
                
                # 發送給所有玩家
                dead_connections = []
                for player_name, conn in list(self.connections.items()):
                    try:
                        send_frame(conn, message_bytes)
                    except:
                        dead_connections.append(player_name)
                
                # 清理斷線的玩家
                for player_name in dead_connections:
                    if player_name in self.connections:
                        del self.connections[player_name]
                    if player_name in self.games:
                        del self.games[player_name]
                
                # 檢查遊戲結束條件（遊戲開始3秒後才檢查）
                if len(self.games) >= 2 and self.game_start_time:
                    elapsed = time.time() - self.game_start_time
                    if elapsed >= 3.0:  # 給玩家3秒反應時間
                        for player_name, game in self.games.items():
                            # 檢查是否有玩家完成遊戲（清除1行）或遊戲結束
                            if game.lines_cleared >= 1 or game.game_over:
                                print(f"[Server] Game ending: {player_name} - lines={game.lines_cleared}, game_over={game.game_over}")
                                self.end_game()
                                return
                            
            except Exception as e:
                import traceback
                print(f"[Broadcast] Error: {e}")
                traceback.print_exc()
    
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
        
        self.running = False
        print(f"[Server] Game ended. Winner: {winner}")

    def handle_client(self, conn, addr):
        """處理客戶端連線"""
        player_name = None
        
        try:
            while self.running:
                # 接收請求
                data = recv_frame(conn)
                if not data:
                    break
                
                try:
                    request = json.loads(data)
                    action = request.get("action")
                    
                    if action == "join":
                        # 生成唯一的玩家名稱
                        self.player_counter += 1
                        player_name = f"Player{self.player_counter}"
                        print(f"[Server] Player joined as: {player_name}")
                        self.games[player_name] = ServerTetrisGame(player_name, self.game_seed)
                        self.connections[player_name] = conn
                        response = {
                            "status": "success",
                            "message": "Joined game",
                            "seed": self.game_seed,
                            "state": self.games[player_name].get_state()
                        }
                        send_frame(conn, json.dumps(response).encode("utf-8"))
                        
                    elif action == "input":
                        key = request.get("key")
                        if player_name and player_name in self.games:
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
                            game.auto_drop()  # 自動下落
                            response = {
                                "status": "success",
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
            if player_name:
                self.games.pop(player_name, None)
                self.connections.pop(player_name, None)
            conn.close()
            print(f"[Server] Player disconnected")
    
    def start(self):
        """啟動伺服器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 啟動廣播線程
        broadcast_thread = threading.Thread(target=self.broadcast_game_state, daemon=True)
        broadcast_thread.start()
        print("[Tetris Server] Game state broadcast started")
        
        try:
            server_socket.bind(('0.0.0.0', self.port))
            server_socket.listen(5)
            print(f"[Tetris Server] Started on port {self.port}")
            print(f"[Tetris Server] Waiting for players...")
            
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    print(f"[Tetris Server] Player connected from {addr}")
                    
                    # 每個玩家一個執行緒
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True
                    thread.start()
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error accepting connection: {e}")
        
        finally:
            server_socket.close()
            print("[Tetris Server] Stopped")


def main():
    """主程式"""
    if len(sys.argv) != 2:
        print("Usage: python3 server_game.py <port>")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    
    server = TetrisGameServer(port)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.running = False


if __name__ == "__main__":
    main()