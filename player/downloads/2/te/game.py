#!/usr/bin/env python3
"""
Tic-Tac-Toe Game Client - 井字遊戲客戶端 (CLI 版本)
修復版本：解決輸入阻塞和狀態同步問題
"""

import sys
import json
import threading
import time
import socket
import os
import select
from lpfp import send_frame, recv_frame


def clear_screen():
    """清除螢幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


class TicTacToeClient:
    """井字遊戲客戶端 (CLI)"""
    
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.conn = None
        self.running = True
        self.connected = False
        
        # 遊戲狀態
        self.my_name = None
        self.my_mark = None
        self.state = None
        self.game_over = False
        self.winner = None
        self.message = "Connecting..."
        self.my_turn = False
        self.need_redraw = True
        self.game_ready = False
        
        # 執行緒鎖
        self.lock = threading.Lock()
    
    def connect(self):
        """連接到伺服器"""
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((self.host, self.port))
            self.connected = True
            self.message = "Connected! Joining game..."
            
            # 加入遊戲
            request = {
                "action": "join",
                "player_name": self.username
            }
            send_frame(self.conn, json.dumps(request).encode("utf-8"))
            
            # 接收回應
            data = recv_frame(self.conn)
            if data:
                response = json.loads(data)
                if response.get("status") == "success":
                    self.my_name = response.get("player_name")
                    self.my_mark = response.get("mark")
                    self.state = response.get("state")
                    self.update_status()
                    
                    # 啟動接收執行緒
                    threading.Thread(target=self.listen_server, daemon=True).start()
                    return True
                else:
                    self.message = response.get("message", "Failed to join")
            
            return False
        
        except Exception as e:
            self.message = f"Connection failed: {e}"
            return False
    
    def listen_server(self):
        """接收伺服器訊息"""
        while self.running and self.connected:
            try:
                data = recv_frame(self.conn)
                if not data:
                    with self.lock:
                        self.message = "Disconnected from server"
                        self.connected = False
                        self.need_redraw = True
                    break
                
                msg = json.loads(data)
                msg_type = msg.get("type")
                
                with self.lock:
                    if msg_type == "GAME_STATE":
                        self.state = msg.get("state")
                        self.update_status()
                        self.need_redraw = True
                    
                    elif msg_type == "GAME_END":
                        self.state = msg.get("state")
                        self.winner = msg.get("winner")
                        self.game_over = True
                        if self.winner:
                            if self.winner == self.my_name:
                                self.message = "🎉 YOU WIN! 🎉"
                            else:
                                self.message = f"😢 {self.winner} wins!"
                        else:
                            self.message = "🤝 It's a DRAW!"
                        self.need_redraw = True
                    
                    elif msg.get("status") == "success":
                        self.state = msg.get("state")
                        self.update_status()
                        self.need_redraw = True
                    
                    elif msg.get("status") == "error":
                        self.message = f"❌ {msg.get('message', 'Error')} - Try again!"
                        # 錯誤時恢復輸入權
                        if self.game_ready:
                            # 重新檢查是否該輪到自己
                            self._check_my_turn()
                        self.need_redraw = True
            
            except Exception as e:
                if self.running:
                    with self.lock:
                        self.message = f"Connection error: {e}"
                        self.connected = False
                        self.need_redraw = True
                break
    
    def _check_my_turn(self):
        """檢查是否輪到自己（內部使用，已持有鎖）"""
        if self.state and self.game_ready:
            players = self.state.get("players", {})
            current_turn = self.state.get("current_turn")
            my_mark = players.get(self.my_name)
            self.my_turn = (my_mark == current_turn)
    
    def update_status(self):
        """更新狀態訊息（假設已持有鎖或在主執行緒）"""
        if not self.state:
            return
        
        players = self.state.get("players", {})
        current_turn = self.state.get("current_turn")
        ready = self.state.get("ready", False)
        
        # 更新遊戲準備狀態
        self.game_ready = ready
        
        if not ready or len(players) < 2:
            self.message = f"You are [{self.my_mark}]. Waiting for opponent..."
            self.my_turn = False
        elif self.state.get("game_over"):
            pass  # 保持遊戲結束訊息
        else:
            # 檢查是否輪到自己
            my_mark = players.get(self.my_name)
            self.my_turn = (my_mark == current_turn)
            
            if self.my_turn:
                self.message = ">>> Your turn! Enter row col (e.g., 1 1) <<<"
            else:
                # 找出對手名稱
                opponent = None
                for name in players:
                    if name != self.my_name:
                        opponent = name
                        break
                self.message = f"Waiting for {opponent}..."
    
    def send_move(self, row, col):
        """發送落子"""
        if not self.connected or self.game_over:
            return False
        
        request = {
            "action": "move",
            "row": row,
            "col": col
        }
        
        try:
            send_frame(self.conn, json.dumps(request).encode("utf-8"))
            return True
        except:
            with self.lock:
                self.message = "Failed to send move"
            return False
    
    def draw_board(self):
        """繪製棋盤"""
        clear_screen()
        
        print("=" * 50)
        print("          🎮 Tic-Tac-Toe Online 🎮")
        print("=" * 50)
        
        # 玩家資訊
        if self.state:
            players = self.state.get("players", {})
            current_turn = self.state.get("current_turn", "?")
            
            player_info = []
            for name, mark in players.items():
                indicator = " (you)" if name == self.my_name else ""
                turn_indicator = " ←" if mark == current_turn and self.game_ready else ""
                player_info.append(f"{mark}: {name}{indicator}{turn_indicator}")
            
            if player_info:
                print(f"  Players: {' vs '.join(player_info)}")
            else:
                print(f"  You: {self.my_mark}")
            
            if self.game_ready:
                print(f"  Current Turn: [{current_turn}]")
            else:
                print(f"  Status: Waiting for players...")
        
        print("-" * 50)
        
        # 棋盤
        if self.state:
            board = self.state.get("board", [[''] * 3 for _ in range(3)])
        else:
            board = [[''] * 3 for _ in range(3)]
        
        print("\n       0   1   2")
        print("     +---+---+---+")
        
        for i in range(3):
            row_str = f"  {i}  |"
            for j in range(3):
                cell = board[i][j] if board[i][j] else ' '
                row_str += f" {cell} |"
            print(row_str)
            print("     +---+---+---+")
        
        # 狀態訊息
        print("\n" + "-" * 50)
        print(f"  {self.message}")
        print("-" * 50)
        
        if self.game_over:
            print("\n  Press Enter to exit...")
        elif self.my_turn and self.game_ready:
            print("\n  Enter 'q' to quit")
    
    def run(self):
        """遊戲主迴圈"""
        print("Connecting to server...")
        
        if not self.connect():
            print(f"Error: {self.message}")
            return
        
        self.draw_board()
        
        while self.running:
            # 檢查狀態更新
            with self.lock:
                need_redraw = self.need_redraw
                game_over = self.game_over
                my_turn = self.my_turn
                game_ready = self.game_ready
                connected = self.connected
                
                if need_redraw:
                    self.need_redraw = False
            
            # 重繪畫面
            if need_redraw:
                self.draw_board()
            
            # 連線中斷
            if not connected:
                print("\n  Connection lost. Press Enter to exit...")
                try:
                    input()
                except:
                    pass
                break
            
            # 遊戲結束
            if game_over:
                try:
                    input()  # 等待按 Enter
                except:
                    pass
                break
            
            # 不是自己的回合或遊戲未準備好，等待
            if not my_turn or not game_ready:
                time.sleep(0.2)
                continue
            
            # 輸入
            try:
                user_input = input("\n  Your move (row col): ").strip()
                
                if not user_input:
                    self.need_redraw = True
                    continue
                
                if user_input.lower() == 'q':
                    print("\n  Quitting game...")
                    break
                
                parts = user_input.split()
                if len(parts) != 2:
                    with self.lock:
                        self.message = "Invalid input! Enter: row col (e.g., 1 1)"
                        self.need_redraw = True
                    continue
                
                try:
                    row = int(parts[0])
                    col = int(parts[1])
                except ValueError:
                    with self.lock:
                        self.message = "Invalid input! Use numbers 0-2"
                        self.need_redraw = True
                    continue
                
                if not (0 <= row <= 2 and 0 <= col <= 2):
                    with self.lock:
                        self.message = "Invalid position! Use 0-2"
                        self.need_redraw = True
                    continue
                
                # 發送移動
                self.send_move(row, col)
                
                # 暫時設為非自己回合，等待伺服器回應
                with self.lock:
                    self.my_turn = False
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n\n  Interrupted. Exiting...")
                break
        
        # 清理
        self.running = False
        if self.conn:
            try:
                request = {"action": "quit"}
                send_frame(self.conn, json.dumps(request).encode("utf-8"))
                self.conn.close()
            except:
                pass
        
        print("\n  Goodbye! 👋\n")


def main():
    """主程式"""
    if len(sys.argv) < 3:
        print("Usage: python3 game.py <host> <port> [username]")
        print("Example: python3 game.py localhost 12345 Player1")
        sys.exit(1)
    
    host = sys.argv[1]
    
    try:
        port = int(sys.argv[2])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    
    # 如果沒有提供 username，使用環境變數或預設值
    if len(sys.argv) > 3:
        username = sys.argv[3]
    else:
        username = os.environ.get("GAME_USERNAME", f"Player_{os.getpid()}")
    
    client = TicTacToeClient(host, port, username)
    client.run()


if __name__ == "__main__":
    main()