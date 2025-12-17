#!/usr/bin/env python3
"""
Number Bomb Game Client - 使用 Tic-Tac-Toe 的成功模式
"""

import socket
import threading
import json
import sys
import time
import os
from lpfp import send_frame, recv_frame


def clear_screen():
    """清除螢幕"""
    print('\033[2J\033[H', end='', flush=True)


class NumberBombClient:
    """數字炸彈遊戲客戶端"""
    
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.conn = None
        self.running = True
        self.connected = False
        
        # 遊戲狀態
        self.my_name = None
        self.state = None
        self.game_over = False
        self.game_started = False
        self.my_turn = False
        self.message = "Connecting..."
        self.need_redraw = True
        
        # 執行緒鎖
        self.lock = threading.Lock()
    
    def get_player_number(self, player_name):
        """取得玩家編號"""
        if not self.state:
            return "?"
        players = self.state.get("players", [])
        try:
            return players.index(player_name) + 1
        except:
            return "?"
    
    def connect(self):
        """連接到伺服器"""
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((self.host, self.port))
            self.connected = True
            
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
                    self.state = response.get("state")
                    self.message = "Connected! Waiting for game..."
                    
                    # 啟動接收執行緒
                    threading.Thread(target=self.listen_server, daemon=True).start()
                    return True
                else:
                    error_msg = response.get("message", "Failed to join")
                    print(f"\n❌ {error_msg}")
                    return False
            
            print("\n❌ 伺服器無回應")
            return False
            
        except Exception as e:
            print(f"\n❌ 連線失敗: {e}")
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
                    if msg_type == "STATE_UPDATE":
                        self.state = msg.get("state")
                        
                        if self.state.get("game_started") and not self.game_started:
                            self.game_started = True
                            self.message = "💣 遊戲開始！💣"
                        
                        self.update_status()
                        self.need_redraw = True
                    
                    elif msg_type == "GAME_UPDATE":
                        player = msg.get("player")
                        guess = msg.get("guess")
                        result = msg.get("result")
                        self.state = msg.get("state")
                        
                        player_num = self.get_player_number(player)
                        
                        if result.get("hit_bomb"):
                            self.message = f"💥 Player {player_num} 踩到炸彈了！"
                        else:
                            new_range = result.get("new_range", [])
                            self.message = f"Player {player_num} 猜了 {guess} - 範圍: {new_range[0]} ~ {new_range[1]}"
                        
                        self.update_status()
                        self.need_redraw = True
                    
                    elif msg_type == "GAME_END":
                        self.game_over = True
                        loser = msg.get("loser")
                        bomb = msg.get("bomb")
                        
                        loser_num = self.get_player_number(loser)
                        
                        if loser == self.my_name:
                            self.message = f"😭 你輸了！炸彈是 {bomb}"
                        else:
                            self.message = f"🎉 你贏了！Player {loser_num} 踩到炸彈 {bomb}"
                        
                        self.need_redraw = True
                    
                    elif msg_type == "GAME_ABORT":
                        self.game_over = True
                        abort_msg = msg.get("message", "遊戲已中斷")
                        self.message = f"⚠️ {abort_msg}"
                        self.need_redraw = True
            
            except Exception as e:
                if self.running:
                    with self.lock:
                        self.message = f"Connection error: {e}"
                        self.connected = False
                        self.need_redraw = True
                break
    
    def update_status(self):
        """更新狀態訊息（假設已持有鎖）"""
        if not self.state:
            return
        
        if not self.game_started:
            players = self.state.get("players", [])
            self.message = f"Waiting for players... ({len(players)} connected)"
            self.my_turn = False
            return
        
        current_player = self.state.get("current_player")
        self.my_turn = (current_player == self.my_name)
        
        if self.my_turn:
            game_range = self.state.get("range", [0, 0])
            self.message = f"👉 輪到你了！範圍: {game_range[0]} ~ {game_range[1]}"
        else:
            waiting_num = self.get_player_number(current_player)
            self.message = f"⏳ 等待 Player {waiting_num}..."
    
    def send_guess(self, number):
        """發送猜測"""
        if not self.connected or self.game_over:
            return False
        
        request = {
            "action": "guess",
            "number": number
        }
        
        try:
            send_frame(self.conn, json.dumps(request).encode("utf-8"))
            return True
        except:
            with self.lock:
                self.message = "Failed to send guess"
            return False
    
    def draw_screen(self):
        """繪製遊戲畫面"""
        clear_screen()
        
        print("=" * 50)
        print("          💣 Number Bomb Game 💣")
        print("=" * 50)
        
        # 玩家資訊
        if self.state:
            players = self.state.get("players", [])
            game_range = self.state.get("range", [0, 0])
            
            player_list = ", ".join([f"Player {i+1}" for i in range(len(players))])
            print(f"  Players: {player_list}")
            
            if self.game_started:
                print(f"  Range: {game_range[0]} ~ {game_range[1]}")
        
        print("-" * 50)
        
        # 狀態訊息
        print(f"\n  {self.message}")
        print("\n" + "-" * 50)
        
        if self.game_over:
            print("\n  Press Enter to exit...")
        elif self.my_turn and self.game_started:
            game_range = self.state.get("range", [0, 0])
            print(f"\n  Enter your guess ({game_range[0]} ~ {game_range[1]}): ", end='', flush=True)
    
    def run(self):
        """遊戲主迴圈"""
        print("Connecting to server...")
        
        if not self.connect():
            time.sleep(1)
            return
        
        self.draw_screen()
        
        while self.running:
            # 檢查狀態更新
            with self.lock:
                need_redraw = self.need_redraw
                game_over = self.game_over
                my_turn = self.my_turn
                game_started = self.game_started
                connected = self.connected
                
                if need_redraw:
                    self.need_redraw = False
            
            # 重繪畫面
            if need_redraw:
                self.draw_screen()
            
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
                    input()
                except:
                    pass
                break
            
            # 不是自己的回合或遊戲未開始，等待
            if not my_turn or not game_started:
                time.sleep(0.05)  # 50ms 快速響應
                continue
            
            # 輸入
            try:
                user_input = input().strip()
                
                if not user_input:
                    with self.lock:
                        self.need_redraw = True
                    continue
                
                if user_input.lower() == 'q':
                    print("\n  Quitting game...")
                    break
                
                try:
                    guess = int(user_input)
                except ValueError:
                    with self.lock:
                        self.message = "❌ 請輸入有效的數字"
                        self.need_redraw = True
                    continue
                
                game_range = self.state.get("range", [0, 0])
                if guess < game_range[0] or guess > game_range[1]:
                    with self.lock:
                        self.message = f"❌ 數字必須在 {game_range[0]} ~ {game_range[1]} 之間"
                        self.need_redraw = True
                    continue
                
                # ⭐ 樂觀更新：立即顯示
                with self.lock:
                    self.message = f"你猜了 {guess}，等待結果..."
                    self.my_turn = False  # 暫時設為非自己回合
                
                self.draw_screen()
                
                # 發送猜測
                self.send_guess(guess)
                
            except EOFError:
                print("\n\n  Exiting...")
                break
            except KeyboardInterrupt:
                print("\n\n  Quitting game...")
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
        print("Usage: python3 game.py <host> <port>")
        sys.exit(1)
    
    host = sys.argv[1]
    
    try:
        port = int(sys.argv[2])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    
    # 玩家名稱
    import random
    username = f"Player{random.randint(1, 999)}"
    
    client = NumberBombClient(host, port, username)
    client.run()


if __name__ == "__main__":
    main()