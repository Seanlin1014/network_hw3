#!/usr/bin/env python3
# developer_client.py - 開發者客戶端（選單式介面）

import socket
import json
import os
import sys
import zipfile
import io
import base64
from lpfp import send_frame, recv_frame

class DeveloperClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.username = None
        self.running = True
    
    def connect(self):
        """連線到 Developer Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
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
            self.show_menu("Developer Portal - 開發者入口", [
                "登入 (Login)",
                "註冊 (Register)",
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
                return False
            else:
                print("❌ 無效的選項")
                input("按 Enter 繼續...")
    
    def register(self):
        """註冊開發者帳號"""
        print("\n📝 註冊開發者帳號")
        username = self.get_input("帳號名稱")
        password = self.get_input("密碼")
        
        # 向 DB Server 註冊
        try:
            db_host = self.host
            db_port = int(input("DB Server Port: ").strip())
            
            db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            db_sock.connect((db_host, db_port))
            
            request = {
                "collection": "Developer",
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
        print("\n🔐 開發者登入")
        username = self.get_input("帳號")
        password = self.get_input("密碼")
        
        response = self.send_request("login", {
            "username": username,
            "password": password
        })
        
        if response["status"] == "success":
            self.username = username
            print(f"✅ 登入成功！歡迎, {username}")
            input("按 Enter 繼續...")
            return True
        else:
            print(f"❌ 登入失敗: {response.get('message', 'Unknown error')}")
            input("按 Enter 繼續...")
            return False
    
    def main_menu(self):
        """主選單"""
        while self.running:
            self.clear_screen()
            self.show_menu(f"開發者主選單 - {self.username}", [
                "查看我的遊戲",
                "上架新遊戲",
                "更新遊戲",
                "下架遊戲",
                "登出"
            ])
            
            choice = self.get_input("請選擇")
            
            if choice == "1":
                self.list_my_games()
            elif choice == "2":
                self.upload_game()
            elif choice == "3":
                self.update_game()
            elif choice == "4":
                self.remove_game()
            elif choice == "5":
                self.running = False
                print("👋 登出成功")
                break
            else:
                print("❌ 無效的選項")
                input("按 Enter 繼續...")
    
    def list_my_games(self):
        """列出我的遊戲"""
        print("\n📋 我的遊戲列表")
        
        response = self.send_request("list_my_games", {})
        
        if response["status"] == "success":
            games = response["data"]["games"]
            
            if not games:
                print("  目前沒有任何遊戲")
            else:
                print(f"\n  共 {len(games)} 款遊戲:\n")
                for i, game in enumerate(games, 1):
                    status_icon = "✅" if game["status"] == "active" else "❌"
                    print(f"  {i}. {status_icon} {game['game_name']}")
                    print(f"     版本: {game['version']}")
                    print(f"     狀態: {game['status']}")
                    print(f"     下載次數: {game['download_count']}")
                    print(f"     評分: {game['average_rating']:.1f}/5.0")
                    print()
        else:
            print(f"❌ 取得遊戲列表失敗: {response.get('message', '')}")
        
        input("\n按 Enter 返回...")
    
    def pack_game_directory(self, game_dir):
        """打包遊戲目錄成 ZIP"""
        if not os.path.exists(game_dir):
            return None
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(game_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, game_dir)
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        return base64.b64encode(zip_buffer.read()).decode('utf-8')
    
    def upload_game(self):
        """上架新遊戲"""
        print("\n📤 上架新遊戲")
        
        game_name = self.get_input("遊戲名稱")
        
        print("\n遊戲類型:")
        print("  1. CLI (命令列介面)")
        print("  2. GUI (圖形介面)")
        print("  3. Multiplayer (多人遊戲)")
        game_type_choice = self.get_input("選擇類型 (1-3)")
        game_type_map = {"1": "CLI", "2": "GUI", "3": "Multiplayer"}
        game_type = game_type_map.get(game_type_choice, "CLI")
        
        description = self.get_input("遊戲簡介")
        max_players = int(self.get_input("最大玩家數", required=False) or "2")
        version = self.get_input("版本號 (預設 1.0.0)", required=False) or "1.0.0"
        
        # 遊戲檔案路徑
        game_dir = self.get_input("遊戲檔案目錄路徑")
        
        print("\n📦 正在打包遊戲檔案...")
        game_files = self.pack_game_directory(game_dir)
        
        if not game_files:
            print(f"❌ 無法讀取遊戲目錄: {game_dir}")
            input("按 Enter 繼續...")
            return
        
        print(f"✅ 打包完成，大小: {len(game_files)} bytes (base64)")
        
        # 設定檔
        start_cmd = self.get_input("啟動命令 (例: python3 game_client.py)", required=False)
        server_cmd = self.get_input("伺服器命令 (例: python3 game_server.py)", required=False)
        
        config = {}
        if start_cmd:
            config["start_command"] = start_cmd
        if server_cmd:
            config["server_command"] = server_cmd
        
        print("\n⏳ 上傳中...")
        
        response = self.send_request("upload_game", {
            "game_name": game_name,
            "game_type": game_type,
            "description": description,
            "max_players": max_players,
            "version": version,
            "game_files": game_files,
            "config": config
        })
        
        if response["status"] == "success":
            print(f"✅ 上架成功！")
            print(f"   遊戲 ID: {response['data']['game_id']}")
            print(f"   版本: {response['data']['version']}")
        else:
            print(f"❌ 上架失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def update_game(self):
        """更新遊戲"""
        print("\n🔄 更新遊戲")
        
        game_name = self.get_input("要更新的遊戲名稱")
        new_version = self.get_input("新版本號")
        update_notes = self.get_input("更新說明", required=False)
        
        game_dir = self.get_input("新版本遊戲檔案目錄")
        
        print("\n📦 正在打包遊戲檔案...")
        game_files = self.pack_game_directory(game_dir)
        
        if not game_files:
            print(f"❌ 無法讀取遊戲目錄: {game_dir}")
            input("按 Enter 繼續...")
            return
        
        print(f"✅ 打包完成")
        print("\n⏳ 上傳中...")
        
        response = self.send_request("update_game", {
            "game_name": game_name,
            "version": new_version,
            "game_files": game_files,
            "update_notes": update_notes
        })
        
        if response["status"] == "success":
            print(f"✅ 更新成功！")
            print(f"   新版本: {response['data']['new_version']}")
        else:
            print(f"❌ 更新失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def remove_game(self):
        """下架遊戲"""
        print("\n🗑️  下架遊戲")
        
        game_name = self.get_input("要下架的遊戲名稱")
        
        confirm = self.get_input(f"確定要下架 '{game_name}' 嗎? (yes/no)")
        
        if confirm.lower() != "yes":
            print("❌ 已取消")
            input("按 Enter 繼續...")
            return
        
        response = self.send_request("remove_game", {
            "game_name": game_name
        })
        
        if response["status"] == "success":
            print(f"✅ 下架成功！")
        else:
            print(f"❌ 下架失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def run(self):
        """執行 Client"""
        self.clear_screen()
        print("\n" + "="*60)
        print("  🎮 Game Store - Developer Client")
        print("="*60)
        
        if not self.connect():
            return
        
        print("✅ 已連線到 Developer Server")
        
        if self.login_menu():
            self.main_menu()
        
        self.sock.close()
        print("\n👋 再見！")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 developer_client.py <host> <dev_port>")
        print("\n提示: 從 .dev_port 檔案讀取 port")
        
        # 嘗試從檔案讀取
        if os.path.exists(".dev_port"):
            with open(".dev_port") as f:
                port = int(f.read().strip())
            host = "localhost"
        else:
            print("\n❌ 找不到 .dev_port 檔案")
            print("請先執行 ./start_game_store.sh 啟動 Server")
            sys.exit(1)
    else:
        host = sys.argv[1]
        port = int(sys.argv[2])
    
    client = DeveloperClient(host, port)
    client.run()


if __name__ == "__main__":
    main()
