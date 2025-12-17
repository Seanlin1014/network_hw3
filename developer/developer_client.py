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
            
            # === 發送握手 ===
            handshake = {"client_type": "developer"}
            send_frame(self.sock, json.dumps(handshake).encode('utf-8'))
            
            # 等待握手回應
            response_raw = recv_frame(self.sock)
            if not response_raw:
                print("❌ 連線失敗: Server 無回應")
                self.sock.close()
                return False
            
            response = json.loads(response_raw.decode('utf-8'))
            
            if response["status"] != "success":
                print(f"\n❌ 連線錯誤!\n")
                print(response.get("message", "Unknown error"))
                print("\n💡 提示: 請確認你使用的是 Developer Port，不是 Lobby Port")
                self.sock.close()
                return False
            
            print(f"✅ 已連線到 {response.get('server_type', 'Unknown')} Server")
            # === 握手完成 ===
            
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
        """取得使用者輸入，自動轉換全形括號為半形"""
        while True:
            value = input(f"{prompt}: ").strip()
            
            # 自動轉換全形括號為半形
            if value:
                value = value.replace('｛', '{').replace('｝', '}')
                value = value.replace('（', '(').replace('）', ')')
            
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
        
        # 向 Server 註冊（不再直接連 DB）
        try:
            request = {
                "action": "register",
                "data": {
                    "username": username,
                    "password": password
                }
            }
            
            send_frame(self.sock, json.dumps(request).encode('utf-8'))
            response = json.loads(recv_frame(self.sock).decode('utf-8'))
            
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
                    print(f"     類型: {game.get('game_type', 'Unknown')}")
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
        print("💡 提示: 在任何輸入處按 Ctrl+C 或輸入 'q' 可以取消上架\n")
        
        try:
            # 遊戲名稱驗證
            while True:
                game_name = self.get_input("遊戲名稱")
                if game_name.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                if len(game_name) < 2:
                    print("❌ 遊戲名稱至少需要 2 個字元")
                    continue
                if len(game_name) > 50:
                    print("❌ 遊戲名稱不能超過 50 個字元")
                    continue
                # 檢查是否只包含空白
                if game_name.strip() == "":
                    print("❌ 遊戲名稱不能只包含空白")
                    continue
                break
            
            print("\n遊戲類型:")
            print("  1. CLI (命令列介面)")
            print("  2. GUI (圖形介面)")
            print("  3. Multiplayer (多人遊戲)")
            
            # 遊戲類型驗證
            while True:
                game_type_choice = self.get_input("選擇類型 (1-3)")
                if game_type_choice.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                if game_type_choice in ["1", "2", "3"]:
                    game_type_map = {"1": "CLI", "2": "GUI", "3": "Multiplayer"}
                    game_type = game_type_map[game_type_choice]
                    break
                else:
                    print("❌ 請輸入 1, 2 或 3")
            
            # 遊戲簡介驗證
            while True:
                description = self.get_input("遊戲簡介")
                if description.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                if len(description) < 5:
                    print("❌ 遊戲簡介至少需要 5 個字元")
                    continue
                if description.strip() == "":
                    print("❌ 遊戲簡介不能只包含空白")
                    continue
                break
            
            # 最大玩家數驗證
            while True:
                max_players_input = self.get_input("最大玩家數", required=False) or "2"
                if max_players_input.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                try:
                    max_players = int(max_players_input)
                    if 1 <= max_players <= 100:
                        break
                    print("❌ 玩家數必須在 1-100 之間")
                except ValueError:
                    print("❌ 請輸入有效的數字")
            
            # 版本號驗證
            while True:
                version = self.get_input("版本號 (預設 1.0.0)", required=False) or "1.0.0"
                if version.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                parts = version.split('.')
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    break
                print("❌ 版本號格式錯誤，應為 x.x.x（例如 1.0.0）")
            
            # 遊戲檔案路徑驗證
            while True:
                game_dir = self.get_input("遊戲檔案目錄路徑")
                if game_dir.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                
                # 展開 ~ 為完整路徑
                game_dir = os.path.expanduser(game_dir)
                
                # 驗證目錄
                if not os.path.exists(game_dir):
                    print(f"❌ 目錄不存在: {game_dir}")
                    continue
                
                if not os.path.isdir(game_dir):
                    print(f"❌ 這不是一個目錄: {game_dir}")
                    continue
                
                if not os.listdir(game_dir):
                    print(f"❌ 目錄是空的: {game_dir}")
                    continue
                
                break
            
            print(f"\n遊戲檔案目錄路徑: {game_dir}")
            print("\n📦 正在打包遊戲檔案...")
            game_files = self.pack_game_directory(game_dir)
            
            if not game_files:
                print(f"❌ 無法讀取遊戲目錄: {game_dir}")
                input("按 Enter 繼續...")
                return
            
            print(f"✅ 打包完成，大小: {len(game_files)} bytes (base64)")
            
            # 設定檔 - 啟動命令（強制要求）
            print("\n⚙️  遊戲配置")
            print("提示: 啟動命令範例")
            print("  Python: python3 game.py {host} {port}")
            print("  C++: ./playerA {host} {port}")
            print("\n⚠️  啟動命令為必填項目！")
            
            start_cmd = None
            while True:
                start_cmd = self.get_input("啟動命令 (Client)")
                if start_cmd.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                
                if not start_cmd or start_cmd.strip() == "":
                    print("❌ 啟動命令為必填項目，不能為空")
                    continue
                
                # 檢查是否包含 {host} 和 {port}
                has_host = "{host}" in start_cmd
                has_port = "{port}" in start_cmd
                
                if not has_host or not has_port:
                    print("❌ 啟動命令必須包含 {host} 和 {port} 占位符")
                    print(f"   偵測到: {{host}}={has_host}, {{port}}={has_port}")
                    print(f"   你輸入的: {repr(start_cmd)}")
                    print("   正確範例: python3 game.py {host} {port}")
                    print("   提示: 請使用半形括號 {} 而非全形括號 ｛｝")
                    continue
                
                break
            
            # Server 命令（選填）
            print("\n提示: Server 命令範例")
            print("  Python: python3 server_game.py {port}")
            print("  C++: ./lobby_server {port}")
            print("💡 如果沒有 Server，可以直接按 Enter 跳過")
            
            server_cmd = None
            while True:
                server_cmd = self.get_input("伺服器命令 (選填)", required=False)
                if server_cmd and server_cmd.lower() == 'q':
                    print("❌ 已取消上架")
                    input("\n按 Enter 繼續...")
                    return
                
                if not server_cmd or server_cmd.strip() == "":
                    print("ℹ️  此遊戲沒有 Server（純 Client 遊戲）")
                    server_cmd = None
                    break
                
                # 檢查是否包含 {port}
                has_port = "{port}" in server_cmd
                
                if not has_port:
                    print("❌ Server 命令必須包含 {port} 占位符")
                    print(f"   偵測到: {{port}}={has_port}")
                    print(f"   你輸入的: {repr(server_cmd)}")
                    print("   正確範例: python3 server_game.py {port}")
                    print("   提示: 請使用半形括號 {} 而非全形括號 ｛｝")
                    continue
                
                break
            
            # 編譯命令（選填）
            compile_cmd = self.get_input("編譯命令 (C++ 遊戲才需要，例如: make)", required=False)
            if compile_cmd and compile_cmd.lower() == 'q':
                print("❌ 已取消上架")
                input("\n按 Enter 繼續...")
                return
            
            config = {
                "start_command": start_cmd  # 啟動命令為必填
            }
            if server_cmd:
                config["server_command"] = server_cmd
            if compile_cmd and compile_cmd.strip():
                config["compile"] = compile_cmd
            
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
        
        except KeyboardInterrupt:
            print("\n\n❌ 已取消上架")
            input("\n按 Enter 繼續...")
            return
    
    def update_game(self):
        """更新遊戲"""
        print("\n🔄 更新遊戲")
        print("💡 提示: 在任何輸入處按 Ctrl+C 或輸入 'q' 可以取消更新\n")
        
        try:
            # 1. 先取得遊戲列表
            response = self.send_request("list_my_games", {})
            
            if response["status"] != "success":
                print(f"❌ 無法取得遊戲列表: {response.get('message', '')}")
                input("\n按 Enter 繼續...")
                return
            
            games = response["data"]["games"]
            
            if not games:
                print("  你還沒有上架任何遊戲")
                input("\n按 Enter 繼續...")
                return
            
            # 2. 顯示可更新的遊戲列表（只顯示 active 的）
            active_games = [g for g in games if g["status"] == "active"]
            
            if not active_games:
                print("  沒有可更新的遊戲（所有遊戲都已下架）")
                input("\n按 Enter 繼續...")
                return
            
            print(f"\n可更新的遊戲 (共 {len(active_games)} 款):\n")
            for i, game in enumerate(active_games, 1):
                print(f"  {i}. {game['game_name']} (v{game['version']})")
                
                game_type = game.get('game_type', 'Unknown')
                download_count = game.get('download_count', 0)
                average_rating = game.get('average_rating', 0.0)
                
                print(f"     {game_type} | 下載: {download_count} 次 | 評分: {average_rating:.1f}/5.0")
                print()
            
            print("  0. 取消")
            
            # 3. 選擇遊戲
            while True:
                choice = self.get_input(f"請選擇要更新的遊戲 (0-{len(active_games)})", required=False)
                if not choice:
                    continue
                
                if choice.lower() == 'q':
                    print("❌ 已取消更新")
                    input("\n按 Enter 繼續...")
                    return
                
                try:
                    idx = int(choice)
                    if idx == 0:
                        print("❌ 已取消更新")
                        input("\n按 Enter 繼續...")
                        return
                    if 1 <= idx <= len(active_games):
                        game_name = active_games[idx - 1]["game_name"]
                        current_version = active_games[idx - 1]["version"]
                        break
                    else:
                        print(f"❌ 請輸入 0-{len(active_games)}")
                except ValueError:
                    print("❌ 請輸入數字")
            
            print(f"\n選擇的遊戲: {game_name} (當前版本: {current_version})")
            
            # 4. 輸入新版本號
            while True:
                new_version = self.get_input("新版本號")
                if new_version.lower() == 'q':
                    print("❌ 已取消更新")
                    input("\n按 Enter 繼續...")
                    return
                
                parts = new_version.split('.')
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    break
                print("❌ 版本號格式錯誤，應為 x.x.x（例如 1.0.1）")
            
            # 5. 輸入更新說明
            update_notes = self.get_input("更新說明", required=False)
            if update_notes and update_notes.lower() == 'q':
                print("❌ 已取消更新")
                input("\n按 Enter 繼續...")
                return
            
            # 6. 輸入遊戲目錄
            while True:
                game_dir = self.get_input("新版本遊戲檔案目錄")
                if game_dir.lower() == 'q':
                    print("❌ 已取消更新")
                    input("\n按 Enter 繼續...")
                    return
                
                # 展開 ~ 為完整路徑
                game_dir = os.path.expanduser(game_dir)
                
                # 驗證目錄
                if not os.path.exists(game_dir):
                    print(f"❌ 目錄不存在: {game_dir}")
                    continue
                
                if not os.path.isdir(game_dir):
                    print(f"❌ 這不是一個目錄: {game_dir}")
                    continue
                
                if not os.listdir(game_dir):
                    print(f"❌ 目錄是空的: {game_dir}")
                    continue
                
                break
            
            # 7. 打包遊戲檔案
            print("\n📦 正在打包遊戲檔案...")
            game_files = self.pack_game_directory(game_dir)
            
            if not game_files:
                print(f"❌ 無法讀取遊戲目錄: {game_dir}")
                input("按 Enter 繼續...")
                return
            
            print(f"✅ 打包完成")
            
            # 8. 確認更新
            print(f"\n確認更新資訊:")
            print(f"  遊戲名稱: {game_name}")
            print(f"  當前版本: {current_version}")
            print(f"  新版本: {new_version}")
            print(f"  更新說明: {update_notes or '無'}")
            print(f"  ⚠️  更新後，所有正在運行此遊戲的房間將被關閉！")
            
            confirm = self.get_input("\n確定要更新嗎？ (yes/no)", required=False)
            if confirm and confirm.lower() == 'q':
                print("❌ 已取消更新")
                input("\n按 Enter 繼續...")
                return
            
            if confirm.lower() != "yes":
                print("❌ 已取消更新")
                input("按 Enter 繼續...")
                return
            
            # 9. 上傳更新
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
                
                # 顯示被刪除的房間資訊（如果有）
                removed_rooms = response.get('data', {}).get('removed_rooms', [])
                if removed_rooms:
                    print(f"\n   已刪除 {len(removed_rooms)} 個運行中的房間:")
                    for room in removed_rooms:
                        print(f"      - 房間 {room['room_id']}: {len(room['players'])} 位玩家")
            else:
                print(f"❌ 更新失敗: {response.get('message', '')}")
            
            input("\n按 Enter 繼續...")
        
        except KeyboardInterrupt:
            print("\n\n❌ 已取消更新")
            input("\n按 Enter 繼續...")
            return
    
    def remove_game(self):
        """下架遊戲"""
        print("\n🗑️  下架遊戲")
        
        # 先取得遊戲列表
        response = self.send_request("list_my_games", {})
        
        if response["status"] != "success":
            print(f"❌ 無法取得遊戲列表: {response.get('message', '')}")
            input("\n按 Enter 繼續...")
            return
        
        games = response["data"]["games"]
        
        if not games:
            print("  你還沒有上架任何遊戲")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示遊戲列表
        print(f"\n你的遊戲 (共 {len(games)} 款):\n")
        for i, game in enumerate(games, 1):
            status_icon = "✅" if game["status"] == "active" else "❌"
            print(f"  {i}. {status_icon} {game['game_name']} (v{game['version']})")
            
            # 使用 .get() 防止 KeyError
            game_type = game.get('game_type', 'Unknown')
            download_count = game.get('download_count', 0)
            average_rating = game.get('average_rating', 0.0)
            
            print(f"     {game_type} | 下載: {download_count} 次 | 評分: {average_rating:.1f}/5.0")
            print()
        
        print("  0. 取消")
        
        # 選擇遊戲
        while True:
            choice = self.get_input(f"請選擇要下架的遊戲 (0-{len(games)})", required=False)
            if not choice:
                continue
            
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(games):
                    game_name = games[choice_num - 1]['game_name']
                    break
                else:
                    print(f"❌ 請輸入 0-{len(games)}")
            except ValueError:
                print("❌ 請輸入數字")
        
        # 顯示下架影響
        print(f"\n⚠️  下架影響:")
        print(f"  • 遊戲將從商城完全移除")
        print(f"  • 玩家無法再下載此遊戲")
        print(f"  • 無法建立新的遊戲房間")
        print(f"  • 該遊戲的所有房間將被立即刪除")
        print(f"  • 正在遊玩的玩家會被強制結束遊戲")
        print(f"  • 所有遊戲檔案將被永久刪除")
        print(f"  • 此操作無法復原！")
        
        # 確認
        confirm = self.get_input(f"\n確定要永久下架 '{game_name}' 嗎? (yes/no)", required=False) or "no"
        
        if confirm.lower() not in ["yes", "y"]:
            print("❌ 已取消")
            input("按 Enter 繼續...")
            return
        
        response = self.send_request("remove_game", {
            "game_name": game_name
        })
        
        if response["status"] == "success":
            print(f"\n✅ 下架成功！")
            
            # 顯示詳細結果
            data = response.get("data", {})
            removed_rooms = data.get("removed_rooms", [])
            
            if removed_rooms:
                print(f"\n📊 刪除了 {len(removed_rooms)} 個房間:")
                for room_info in removed_rooms:
                    room_id = room_info.get("room_id")
                    players = room_info.get("players", [])
                    status = room_info.get("status", "unknown")
                    print(f"  • 房間 {room_id} (狀態: {status}, 玩家: {len(players)} 人)")
                    if players:
                        print(f"    玩家: {', '.join(players)}")
            else:
                print(f"  沒有需要刪除的房間")
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