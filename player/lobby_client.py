#!/usr/bin/env python3
# lobby_client.py - 玩家大廳客戶端（選單式介面）

import socket
import json
import os
import sys
import base64
import zipfile
import io
import subprocess
from lpfp import send_frame, recv_frame

class LobbyClient:
    def __init__(self, host, lobby_port, db_port):
        self.host = host
        self.lobby_port = lobby_port
        self.db_port = db_port
        self.username = None
        self.running = True
        self.downloads_dir = "downloads"
        self.current_room = None
        
        # 建立下載目錄
        os.makedirs(self.downloads_dir, exist_ok=True)
    
    def connect(self):
        """連線到 Lobby Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.lobby_port))
            return True
        except Exception as e:
            print(f"❌ 連線失敗: {e}")
            return False
    
    def send_request(self, action, data):
        """發送請求"""
        try:
            request = {"action": action, "data": data}
            send_frame(self.sock, json.dumps(request).encode('utf-8'))
            
            response_raw = recv_frame(self.sock)
            if response_raw:
                return json.loads(response_raw.decode('utf-8'))
            else:
                return {"status": "error", "message": "No response from server"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def clear_screen(self):
        """清除螢幕"""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def show_menu(self, title, options):
        """顯示選單"""
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print("="*60)
    
    def get_input(self, prompt, required=True):
        """取得使用者輸入"""
        while True:
            value = input(f"{prompt}: ").strip()
            if value or not required:
                return value
            print("❌ 此欄位必填，請重新輸入")
    
    def login_menu(self):
        """登入/註冊選單"""
        while True:
            self.clear_screen()
            self.show_menu("Game Store - 玩家大廳", [
                "登入 (Login)",
                "註冊 (Register)",
                "訪客模式 (Guest - 瀏覽遊戲)",
                "離開 (Exit)"
            ])
            
            choice = self.get_input("請選擇")
            
            if choice == "1":
                if self.login():
                    return True
            elif choice == "2":
                if self.register():
                    return True
            elif choice == "3":
                self.username = "Guest"
                return True
            elif choice == "4":
                return False
            else:
                print("❌ 無效的選項")
                input("按 Enter 繼續...")
    
    def register(self):
        """註冊玩家帳號"""
        print("\n📝 註冊玩家帳號")
        username = self.get_input("帳號名稱")
        password = self.get_input("密碼")
        
        try:
            db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            db_sock.connect((self.host, self.db_port))
            
            request = {
                "collection": "Player",
                "action": "create",
                "data": {"name": username, "password": password}
            }
            
            send_frame(db_sock, json.dumps(request).encode('utf-8'))
            response = json.loads(recv_frame(db_sock).decode('utf-8'))
            db_sock.close()
            
            if response["status"] == "success":
                print(f"✅ 註冊成功！")
                input("按 Enter 繼續...")
                return False
            else:
                print(f"❌ 註冊失敗: {response.get('message', 'Unknown error')}")
                input("按 Enter 繼續...")
                return False
        
        except Exception as e:
            print(f"❌ 註冊失敗: {e}")
            input("按 Enter 繼續...")
            return False
    
    def login(self):
        """登入"""
        print("\n🔐 玩家登入")
        username = self.get_input("帳號")
        password = self.get_input("密碼")
        
        # 向 DB Server 驗證
        try:
            db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            db_sock.connect((self.host, self.db_port))
            
            request = {
                "collection": "Player",
                "action": "query",
                "data": {"type": "login", "name": username, "password": password}
            }
            
            send_frame(db_sock, json.dumps(request).encode('utf-8'))
            response = json.loads(recv_frame(db_sock).decode('utf-8'))
            db_sock.close()
            
            if response["status"] == "success":
                self.username = username
                print(f"✅ 登入成功！歡迎, {username}")
                input("按 Enter 繼續...")
                return True
            else:
                print(f"❌ 登入失敗: {response.get('message', 'Unknown error')}")
                input("按 Enter 繼續...")
                return False
        
        except Exception as e:
            print(f"❌ 登入失敗: {e}")
            input("按 Enter 繼續...")
            return False
    
    def main_menu(self):
        """主選單"""
        while self.running:
            self.clear_screen()
            
            menu_title = f"玩家大廳 - {self.username}"
            if self.current_room:
                menu_title += f" [房間: {self.current_room}]"
            
            if self.username == "Guest":
                options = [
                    "瀏覽遊戲商城",
                    "查看遊戲詳情",
                    "離開"
                ]
            else:
                options = [
                    "瀏覽遊戲商城",
                    "查看遊戲詳情",
                    "下載/更新遊戲",
                    "我的遊戲",
                    "---房間功能---",
                    "查看所有房間",
                    "建立房間",
                    "加入房間",
                    "離開房間" if self.current_room else "(目前不在房間)",
                    "登出"
                ]
            
            self.show_menu(menu_title, options)
            choice = self.get_input("請選擇")
            
            if self.username == "Guest":
                if choice == "1":
                    self.browse_games()
                elif choice == "2":
                    self.view_game_details()
                elif choice == "3":
                    self.running = False
                else:
                    print("❌ 無效的選項")
                    input("按 Enter 繼續...")
            else:
                if choice == "1":
                    self.browse_games()
                elif choice == "2":
                    self.view_game_details()
                elif choice == "3":
                    self.download_game()
                elif choice == "4":
                    self.my_games()
                elif choice == "6":
                    self.list_rooms()
                elif choice == "7":
                    self.create_room()
                elif choice == "8":
                    self.join_room()
                elif choice == "9":
                    if self.current_room:
                        self.leave_room()
                    else:
                        print("❌ 你目前不在任何房間")
                        input("按 Enter 繼續...")
                elif choice == "10":
                    self.running = False
                    print("👋 登出成功")
                    break
                else:
                    print("❌ 無效的選項")
                    input("按 Enter 繼續...")
    
    def browse_games(self):
        """瀏覽遊戲"""
        print("\n🎮 遊戲商城")
        
        response = self.send_request("list_games", {})
        
        if response["status"] == "success":
            games = response["data"]["games"]
            
            if not games:
                print("  目前沒有任何遊戲")
            else:
                print(f"\n  共 {len(games)} 款遊戲:\n")
                for i, game in enumerate(games, 1):
                    print(f"  {i}. {game['game_name']} (v{game['version']})")
                    print(f"     開發者: {game['developer']}")
                    print(f"     類型: {game['game_type']} | 最多 {game['max_players']} 人")
                    print(f"     評分: {game['average_rating']:.1f}/5.0 ({game['review_count']} 則評論)")
                    print(f"     下載: {game['download_count']} 次")
                    print(f"     {game['description']}")
                    print()
        else:
            print(f"❌ 取得遊戲列表失敗: {response.get('message', '')}")
        
        input("\n按 Enter 返回...")
    
    def view_game_details(self):
        """查看遊戲詳情"""
        print("\n🔍 遊戲詳情")
        
        game_name = self.get_input("遊戲名稱")
        
        response = self.send_request("get_game_info", {"game_name": game_name})
        
        if response["status"] == "success":
            info = response["data"]["game_info"]
            reviews = response["data"]["reviews"]
            
            print(f"\n{'='*60}")
            print(f"  遊戲名稱: {info['game_name']}")
            print(f"  開發者: {info['developer']}")
            print(f"  版本: {info['version']}")
            print(f"  類型: {info['game_type']}")
            print(f"  最多玩家: {info['max_players']}")
            print(f"  評分: {info['average_rating']:.1f}/5.0")
            print(f"  下載次數: {info['download_count']}")
            print(f"\n  簡介:")
            print(f"  {info['description']}")
            
            if reviews:
                print(f"\n  最新評論:")
                for review in reviews[-5:]:
                    print(f"    ⭐ {review['rating']}/5 - {review['player']}")
                    print(f"       {review['comment']}")
            
            print(f"{'='*60}")
        else:
            print(f"❌ 取得遊戲詳情失敗: {response.get('message', '')}")
        
        input("\n按 Enter 返回...")
    
    def download_game(self):
        """下載遊戲"""
        print("\n📥 下載遊戲")
        
        game_name = self.get_input("遊戲名稱")
        
        print("\n⏳ 下載中...")
        
        response = self.send_request("download_game", {"game_name": game_name})
        
        if response["status"] == "success":
            data = response["data"]
            version = data["version"]
            game_files_b64 = data["game_files"]
            
            # 儲存到本地
            player_dir = os.path.join(self.downloads_dir, self.username)
            game_dir = os.path.join(player_dir, game_name)
            os.makedirs(game_dir, exist_ok=True)
            
            # 解碼並解壓縮
            game_files = base64.b64decode(game_files_b64)
            
            zip_buffer = io.BytesIO(game_files)
            with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                zip_ref.extractall(game_dir)
            
            # 儲存版本資訊
            version_file = os.path.join(game_dir, ".version")
            with open(version_file, 'w') as f:
                f.write(version)
            
            # 儲存配置
            config_file = os.path.join(game_dir, ".config.json")
            with open(config_file, 'w') as f:
                json.dump(data.get("config", {}), f, indent=2)
            
            print(f"✅ 下載成功！")
            print(f"   版本: {version}")
            print(f"   位置: {game_dir}")
        else:
            print(f"❌ 下載失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def my_games(self):
        """我的遊戲"""
        print("\n📚 我的遊戲")
        
        player_dir = os.path.join(self.downloads_dir, self.username)
        
        if not os.path.exists(player_dir):
            print("  你還沒有下載任何遊戲")
            input("\n按 Enter 繼續...")
            return
        
        games = [d for d in os.listdir(player_dir) if os.path.isdir(os.path.join(player_dir, d))]
        
        if not games:
            print("  你還沒有下載任何遊戲")
        else:
            print(f"\n  共 {len(games)} 款遊戲:\n")
            for i, game_name in enumerate(games, 1):
                game_dir = os.path.join(player_dir, game_name)
                version_file = os.path.join(game_dir, ".version")
                
                if os.path.exists(version_file):
                    with open(version_file) as f:
                        version = f.read().strip()
                else:
                    version = "unknown"
                
                print(f"  {i}. {game_name} (v{version})")
                print(f"     位置: {game_dir}")
                print()
        
        input("\n按 Enter 繼續...")
    
    def list_rooms(self):
        """查看所有房間"""
        print("\n🏠 房間列表")
        
        response = self.send_request("list_rooms", {})
        
        if response["status"] == "success":
            rooms = response["data"]["rooms"]
            
            if not rooms:
                print("  目前沒有任何房間")
            else:
                print(f"\n  共 {len(rooms)} 個房間:\n")
                for i, room in enumerate(rooms, 1):
                    status_icon = "🎮" if room["status"] == "playing" else "⏳"
                    print(f"  {i}. {status_icon} {room['room_id']}")
                    print(f"     遊戲: {room['game_name']}")
                    print(f"     房主: {room['host']}")
                    print(f"     玩家: {room['current_players']}/{room['max_players']}")
                    print(f"     狀態: {room['status']}")
                    print()
        else:
            print(f"❌ 取得房間列表失敗: {response.get('message', '')}")
        
        input("\n按 Enter 返回...")
    
    def create_room(self):
        """建立房間"""
        print("\n🏗️  建立房間")
        
        game_name = self.get_input("遊戲名稱")
        
        response = self.send_request("create_room", {"game_name": game_name})
        
        if response["status"] == "success":
            data = response["data"]
            self.current_room = data["room_id"]
            
            print(f"✅ 房間建立成功！")
            print(f"   房間 ID: {data['room_id']}")
            print(f"   遊戲: {data['game_name']}")
            print(f"   最多玩家: {data['max_players']}")
            print(f"\n你可以:")
            print(f"  - 等待其他玩家加入")
            print(f"  - 當人數足夠時，在主選單選擇「離開房間」來啟動遊戲")
        else:
            print(f"❌ 建立房間失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def join_room(self):
        """加入房間"""
        print("\n🚪 加入房間")
        
        room_id = self.get_input("房間 ID")
        
        response = self.send_request("join_room", {"room_id": room_id})
        
        if response["status"] == "success":
            data = response["data"]
            self.current_room = room_id
            
            print(f"✅ 加入房間成功！")
            print(f"   房間 ID: {data['room_id']}")
            print(f"   遊戲: {data['game_name']}")
            print(f"   玩家: {', '.join(data['players'])}")
        else:
            print(f"❌ 加入房間失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def leave_room(self):
        """離開房間"""
        print(f"\n🚪 離開房間 {self.current_room}")
        
        # 如果是房主，詢問是否要啟動遊戲
        print("\n選項:")
        print("  1. 啟動遊戲（房主專用）")
        print("  2. 離開房間")
        
        choice = self.get_input("請選擇")
        
        if choice == "1":
            self.start_game()
        else:
            response = self.send_request("leave_room", {"room_id": self.current_room})
            
            if response["status"] == "success":
                print(f"✅ {response.get('message', '')}")
                self.current_room = None
            else:
                print(f"❌ 離開房間失敗: {response.get('message', '')}")
            
            input("\n按 Enter 繼續...")
    
    def start_game(self):
        """啟動遊戲"""
        print("\n🎮 啟動遊戲")
        
        response = self.send_request("start_game", {"room_id": self.current_room})
        
        if response["status"] == "success":
            data = response["data"]
            
            print(f"✅ 遊戲啟動中！")
            print(f"   遊戲: {data['game_name']}")
            print(f"   版本: {data['version']}")
            print(f"   玩家: {', '.join(data['players'])}")
            
            # 取得啟動命令
            config = data.get("config", {})
            start_cmd = config.get("start_command", "")
            
            if start_cmd:
                # 找到遊戲檔案位置
                game_name = data['game_name']
                player_dir = os.path.join(self.downloads_dir, self.username)
                game_dir = os.path.join(player_dir, game_name)
                
                if os.path.exists(game_dir):
                    print(f"\n啟動命令: {start_cmd}")
                    print(f"工作目錄: {game_dir}")
                    
                    # 詢問是否自動啟動
                    auto = self.get_input("是否自動啟動遊戲? (yes/no)")
                    
                    if auto.lower() == "yes":
                        try:
                            # 在遊戲目錄下執行啟動命令
                            os.chdir(game_dir)
                            subprocess.Popen(start_cmd.split())
                            print("✅ 遊戲已啟動！")
                        except Exception as e:
                            print(f"❌ 啟動失敗: {e}")
                            print(f"\n請手動執行:")
                            print(f"  cd {game_dir}")
                            print(f"  {start_cmd}")
                else:
                    print(f"\n❌ 找不到遊戲檔案: {game_dir}")
                    print(f"請先下載遊戲")
            else:
                print("\n⚠️  此遊戲沒有自動啟動命令")
                print("請查看遊戲目錄手動啟動")
            
            self.current_room = None
        else:
            print(f"❌ 啟動遊戲失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def run(self):
        """執行 Client"""
        self.clear_screen()
        print("\n" + "="*60)
        print("  🎮 Game Store - Lobby Client")
        print("="*60)
        
        if not self.connect():
            return
        
        print("✅ 已連線到 Lobby Server")
        
        if self.login_menu():
            self.main_menu()
        
        self.sock.close()
        print("\n👋 再見！")


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 lobby_client.py <host> <lobby_port> <db_port>")
        print("\n提示: 從檔案讀取 port")
        
        # 嘗試從檔案讀取
        if os.path.exists(".lobby_port") and os.path.exists(".db_port"):
            with open(".lobby_port") as f:
                lobby_port = int(f.read().strip())
            with open(".db_port") as f:
                db_port = int(f.read().strip())
            host = "localhost"
        else:
            print("\n❌ 找不到 .lobby_port 或 .db_port 檔案")
            print("請先執行 ./start_game_store.sh 啟動 Server")
            sys.exit(1)
    else:
        host = sys.argv[1]
        lobby_port = int(sys.argv[2])
        db_port = int(sys.argv[3])
    
    client = LobbyClient(host, lobby_port, db_port)
    client.run()


if __name__ == "__main__":
    main()
