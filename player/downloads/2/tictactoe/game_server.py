#!/usr/bin/env python3
"""
Tic-Tac-Toe Game Server - 支援雙人對戰的井字遊戲伺服器
用於 HW3 Game Store 系統
"""

import socket
import sys
import time
import json
import threading
from lpfp import send_frame, recv_frame


class TicTacToeGame:
    """井字遊戲邏輯"""
    
    def __init__(self):
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_turn = 'X'  # X 先手
        self.winner = None
        self.game_over = False
        self.players = {}  # {player_name: 'X' or 'O'}
        self.player_count = 0
    
    def add_player(self, player_name):
        """加入玩家"""
        if len(self.players) >= 2:
            return None
        
        # 檢查是否已存在同名玩家，如果是則加上編號
        original_name = player_name
        counter = 1
        while player_name in self.players:
            player_name = f"{original_name}_{counter}"
            counter += 1
        
        self.player_count += 1
        
        if len(self.players) == 0:
            self.players[player_name] = 'X'
            return 'X', player_name
        else:
            self.players[player_name] = 'O'
            return 'O', player_name
    
    def is_ready(self):
        """檢查是否兩個玩家都已加入"""
        return len(self.players) >= 2
    
    def make_move(self, player_name, row, col):
        """玩家下棋"""
        if self.game_over:
            return {"success": False, "message": "Game is over"}
        
        if player_name not in self.players:
            return {"success": False, "message": "Player not in game"}
        
        mark = self.players[player_name]
        
        if mark != self.current_turn:
            return {"success": False, "message": "Not your turn"}
        
        if row < 0 or row > 2 or col < 0 or col > 2:
            return {"success": False, "message": "Invalid position"}
        
        if self.board[row][col] != '':
            return {"success": False, "message": "Position already taken"}
        
        # 落子
        self.board[row][col] = mark
        
        # 檢查勝負
        if self.check_win(mark):
            self.winner = player_name
            self.game_over = True
            return {"success": True, "message": "You win!", "game_over": True, "winner": player_name}
        
        # 檢查平手
        if self.is_full():
            self.game_over = True
            return {"success": True, "message": "Draw!", "game_over": True, "winner": None}
        
        # 換人
        self.current_turn = 'O' if self.current_turn == 'X' else 'X'
        
        return {"success": True, "message": "Move accepted"}
    
    def check_win(self, mark):
        """檢查是否獲勝"""
        # 檢查行
        for row in self.board:
            if all(cell == mark for cell in row):
                return True
        
        # 檢查列
        for col in range(3):
            if all(self.board[row][col] == mark for row in range(3)):
                return True
        
        # 檢查對角線
        if all(self.board[i][i] == mark for i in range(3)):
            return True
        if all(self.board[i][2-i] == mark for i in range(3)):
            return True
        
        return False
    
    def is_full(self):
        """檢查棋盤是否已滿"""
        return all(self.board[i][j] != '' for i in range(3) for j in range(3))
    
    def get_state(self):
        """獲取遊戲狀態"""
        return {
            "board": self.board,
            "current_turn": self.current_turn,
            "players": self.players,
            "game_over": self.game_over,
            "winner": self.winner,
            "ready": self.is_ready()
        }


class TicTacToeServer:
    """Tic-Tac-Toe 遊戲伺服器"""
    
    def __init__(self, port):
        self.port = port
        self.game = TicTacToeGame()
        self.connections = {}  # {player_name: socket}
        self.running = True
        self.lock = threading.Lock()
    
    def broadcast_state(self):
        """廣播遊戲狀態給所有玩家"""
        state = self.game.get_state()
        message = {
            "type": "GAME_STATE",
            "state": state
        }
        message_bytes = json.dumps(message).encode("utf-8")
        
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
    
    def handle_client(self, conn, addr):
        """處理客戶端連線"""
        player_name = None
        player_mark = None
        
        try:
            while self.running:
                data = recv_frame(conn)
                if not data:
                    break
                
                try:
                    request = json.loads(data)
                    action = request.get("action")
                    
                    if action == "join":
                        req_name = request.get("player_name", f"Player_{addr[1]}")
                        
                        with self.lock:
                            result = self.game.add_player(req_name)
                        
                        if result:
                            player_mark, player_name = result
                            self.connections[player_name] = conn
                            
                            response = {
                                "status": "success",
                                "message": f"Joined as {player_mark}",
                                "player_name": player_name,
                                "mark": player_mark,
                                "state": self.game.get_state()
                            }
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                            
                            print(f"[Server] {player_name} joined as {player_mark}")
                            
                            # 廣播新狀態給所有玩家
                            time.sleep(0.1)  # 短暫延遲確保客戶端準備好
                            self.broadcast_state()
                            
                            # 如果兩人都到了，再廣播一次確保狀態同步
                            if self.game.is_ready():
                                print(f"[Server] Game ready! Both players joined.")
                                time.sleep(0.1)
                                self.broadcast_state()
                        else:
                            response = {
                                "status": "error",
                                "message": "Game is full"
                            }
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                    
                    elif action == "move":
                        row = request.get("row")
                        col = request.get("col")
                        
                        if player_name:
                            with self.lock:
                                result = self.game.make_move(player_name, row, col)
                            
                            response = {
                                "status": "success" if result["success"] else "error",
                                "message": result["message"],
                                "state": self.game.get_state()
                            }
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                            
                            if result["success"]:
                                # 廣播新狀態
                                self.broadcast_state()
                                
                                # 如果遊戲結束，發送結束訊息
                                if result.get("game_over"):
                                    self.send_game_end(result.get("winner"))
                        else:
                            response = {"status": "error", "message": "Not joined"}
                            send_frame(conn, json.dumps(response).encode("utf-8"))
                    
                    elif action == "get_state":
                        response = {
                            "status": "success",
                            "state": self.game.get_state()
                        }
                        send_frame(conn, json.dumps(response).encode("utf-8"))
                    
                    elif action == "quit":
                        break
                    
                    else:
                        response = {"status": "error", "message": "Unknown action"}
                        send_frame(conn, json.dumps(response).encode("utf-8"))
                
                except json.JSONDecodeError:
                    response = {"status": "error", "message": "Invalid JSON"}
                    send_frame(conn, json.dumps(response).encode("utf-8"))
                except Exception as e:
                    print(f"[Server] Error: {e}")
        
        except Exception as e:
            print(f"[Server] Connection error: {e}")
        
        finally:
            if player_name and player_name in self.connections:
                del self.connections[player_name]
            conn.close()
            print(f"[Server] {player_name or 'Unknown'} disconnected")
    
    def send_game_end(self, winner):
        """發送遊戲結束訊息"""
        message = {
            "type": "GAME_END",
            "winner": winner,
            "state": self.game.get_state()
        }
        message_bytes = json.dumps(message).encode("utf-8")
        
        for conn in self.connections.values():
            try:
                send_frame(conn, message_bytes)
            except:
                pass
        
        print(f"[Server] Game ended. Winner: {winner or 'Draw'}")
    
    def start(self):
        """啟動伺服器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind(('0.0.0.0', self.port))
            server_socket.listen(5)
            print(f"[TicTacToe Server] Started on port {self.port}")
            print(f"[TicTacToe Server] Waiting for players...")
            
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    print(f"[TicTacToe Server] Player connected from {addr}")
                    
                    thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    thread.daemon = True
                    thread.start()
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"[Server] Error: {e}")
        
        finally:
            server_socket.close()
            print("[TicTacToe Server] Stopped")


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
    
    server = TicTacToeServer(port)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.running = False


if __name__ == "__main__":
    main()