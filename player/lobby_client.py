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
    def __init__(self, host, lobby_port):
        self.host = host
        self.lobby_port = lobby_port
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
            self.sock.settimeout(30.0)  # 設置 30 秒超時
            self.sock.connect((self.host, self.lobby_port))
            
            # === 發送握手 ===
            handshake = {"client_type": "player"}
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
                print("\n💡 提示: 請確認你使用的是 Lobby Port，不是 Developer Port")
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
            # 檢查 socket 是否還連接
            if not self.sock:
                return {"status": "error", "message": "Not connected to server"}
            
            request = {"action": action, "data": data}
            send_frame(self.sock, json.dumps(request).encode('utf-8'))
            
            response_raw = recv_frame(self.sock)
            if response_raw:
                return json.loads(response_raw.decode('utf-8'))
            else:
                return {"status": "error", "message": "No response from server"}
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            return {"status": "error", "message": f"Connection lost: {e}"}
        except socket.timeout:
            return {"status": "error", "message": "Request timeout"}
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
        
        # 通過 Lobby Server 註冊
        response = self.send_request("register", {
            "username": username,
            "password": password
        })
        
        if response["status"] == "success":
            print(f"✅ 註冊成功！")
            input("按 Enter 繼續...")
            return False
        else:
            print(f"❌ 註冊失敗: {response.get('message', 'Unknown error')}")
            input("按 Enter 繼續...")
            return False
    
    def login(self):
        """登入"""
        print("\n🔐 玩家登入")
        username = self.get_input("帳號")
        password = self.get_input("密碼")
        
        # 通過 Lobby Server 登入
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
            
            menu_title = f"玩家大廳 - {self.username}"
            if self.current_room:
                menu_title += f" [房間: {self.current_room}]"
            
            if self.username == "Guest":
                options = [
                    "遊戲商城",
                    "離開"
                ]
                self.show_menu(menu_title, options)
                choice = self.get_input("請選擇")
                
                if choice == "1":
                    self.game_store_menu()
                elif choice == "2":
                    self.running = False
                else:
                    print("❌ 無效的選項")
                    input("按 Enter 繼續...")
            else:
                # 根據是否在房間顯示不同選項
                if self.current_room:
                    options = [
                        "遊戲商城",
                        "房間功能",
                        "查看線上玩家",
                        "登出"
                    ]
                else:
                    options = [
                        "遊戲商城",
                        "房間大廳",
                        "查看線上玩家",
                        "登出"
                    ]
                
                self.show_menu(menu_title, options)
                choice = self.get_input("請選擇")
                
                if choice == "1":
                    self.game_store_menu()
                elif choice == "2":
                    if self.current_room:
                        self.room_menu()
                    else:
                        self.room_lobby_menu()
                elif choice == "3":
                    self.list_online_players()
                elif choice == "4":
                    self.running = False
                    print("👋 登出成功")
                    break
                else:
                    print("❌ 無效的選項")
                    input("按 Enter 繼續...")
    
    def game_store_menu(self):
        """遊戲商城子選單"""
        while True:
            self.clear_screen()
            
            options = [
                "瀏覽所有遊戲",
                "下載/更新遊戲",
                "我的遊戲",
                "撰寫評論",
                "返回"
            ]
            
            self.show_menu("🎮 遊戲商城", options)
            choice = self.get_input("請選擇")
            
            if choice == "1":
                self.browse_games()
            elif choice == "2":
                self.download_game()
            elif choice == "3":
                self.my_games()
            elif choice == "4":
                self.write_review()
            elif choice == "5":
                break
            else:
                print("❌ 無效的選項")
                input("按 Enter 繼續...")
    
    def room_lobby_menu(self):
        """房間大廳子選單（未在房間時）"""
        while True:
            self.clear_screen()
            
            options = [
                "查看所有房間",
                "建立房間",
                "加入房間",
                "返回"
            ]
            
            self.show_menu("🏠 房間大廳", options)
            choice = self.get_input("請選擇")
            
            if choice == "1":
                self.list_rooms()
            elif choice == "2":
                self.create_room()
                if self.current_room:
                    # 建立房間後進入房間選單
                    self.room_menu()
                    break
            elif choice == "3":
                self.join_room()
                if self.current_room:
                    # 加入房間後進入房間選單
                    self.room_menu()
                    break
            elif choice == "4":
                break
            else:
                print("❌ 無效的選項")
                input("按 Enter 繼續...")
    
    def room_menu(self):
        """房間功能子選單（已在房間時）"""
        while self.current_room:
            self.clear_screen()
            
            # 取得房間狀態
            response = self.send_request("get_room_status", {"room_id": self.current_room})
            
            is_host = False
            room_status = "unknown"
            room_data = None
            
            if response and response.get("status") == "success":
                room_data = response["data"]
                is_host = room_data.get("is_host", False)
                room_status = room_data.get("status", "unknown")
                players = room_data.get("players", [])
                game_name = room_data.get("game_name", "?")
                
                # 顯示房間資訊
                status_text = {"waiting": "⏳ 等待中", "playing": "🎮 遊戲中"}
                print(f"\n🚪 房間: {self.current_room}")
                print(f"   遊戲: {game_name} | 狀態: {status_text.get(room_status, room_status)}")
                print(f"   玩家: {', '.join(players)}")
                if is_host:
                    print("   👑 你是房主")
                print()
            elif response and response.get("status") == "error":
                if "not found" in response.get("message", "").lower():
                    print("\n⚠️  房間已被解散")
                    self.current_room = None
                    input("\n按 Enter 繼續...")
                    return
            
            # 根據身份和狀態顯示選項
            if is_host:
                if room_status == "playing":
                    options = [
                        "查看房間狀態",
                        "重置房間",
                        "離開房間",
                        "返回主選單"
                    ]
                else:
                    options = [
                        "查看房間狀態",
                        "啟動遊戲",
                        "離開房間",
                        "返回主選單"
                    ]
            else:
                if room_status == "playing":
                    options = [
                        "查看房間狀態",
                        "加入遊戲",
                        "離開房間",
                        "返回主選單"
                    ]
                else:
                    options = [
                        "查看房間狀態",
                        "等待房主啟動",
                        "離開房間",
                        "返回主選單"
                    ]
            
            self.show_menu("房間功能", options)
            choice = self.get_input("請選擇")
            
            if choice == "1":
                self.check_room_status()
            elif choice == "2":
                if is_host:
                    if room_status == "playing":
                        self.reset_room()
                    else:
                        self.start_game()
                else:
                    if room_status == "playing" and room_data and room_data.get("server_port"):
                        self._launch_game_client(room_data)
                    else:
                        print("⏳ 請等待房主啟動遊戲...")
                        input("\n按 Enter 繼續...")
            elif choice == "3":
                confirm = self.get_input("確定要離開房間嗎? (y/n)", required=False) or "n"
                if confirm.lower() in ["yes", "y"]:
                    response = self.send_request("leave_room", {"room_id": self.current_room})
                    if response["status"] == "success":
                        print("✅ 已離開房間")
                        self.current_room = None
                    else:
                        print(f"❌ 離開失敗: {response.get('message', '')}")
                    input("\n按 Enter 繼續...")
                    break
            elif choice == "4":
                break  # 返回主選單但保持在房間
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
        
        # 先取得遊戲列表
        response = self.send_request("list_games", {})
        
        if response["status"] != "success":
            print(f"❌ 無法取得遊戲列表: {response.get('message', '')}")
            input("\n按 Enter 繼續...")
            return
        
        games = response["data"]["games"]
        
        if not games:
            print("  目前沒有任何遊戲")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示遊戲列表
        print(f"\n可用遊戲 (共 {len(games)} 款):\n")
        for i, game in enumerate(games, 1):
            print(f"  {i}. {game['game_name']} (v{game['version']})")
            print(f"     {game['game_type']} | 最多 {game['max_players']} 人 | 評分: {game['average_rating']:.1f}/5.0")
            print()
        
        print("  0. 取消")
        
        # 選擇遊戲
        while True:
            choice = self.get_input("\n請選擇要查看的遊戲 (輸入數字或名稱)")
            
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
                # 當作遊戲名稱處理
                game_names = [g['game_name'] for g in games]
                if choice in game_names:
                    game_name = choice
                    break
                else:
                    print(f"❌ 找不到遊戲「{choice}」，請輸入正確的數字或名稱")
        
        # 取得遊戲詳情
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
        
        # 先取得遊戲列表
        response = self.send_request("list_games", {})
        
        if response["status"] != "success":
            print(f"❌ 無法取得遊戲列表: {response.get('message', '')}")
            input("\n按 Enter 繼續...")
            return
        
        games = response["data"]["games"]
        
        if not games:
            print("  目前沒有任何遊戲")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示遊戲列表
        print(f"\n可用遊戲 (共 {len(games)} 款):\n")
        for i, game in enumerate(games, 1):
            print(f"  {i}. {game['game_name']} (v{game['version']})")
            print(f"     {game['game_type']} | 最多 {game['max_players']} 人 | 評分: {game['average_rating']:.1f}/5.0")
            print(f"     {game['description']}")
            print()
        
        print("  0. 取消")
        
        # 選擇遊戲
        while True:
            choice = self.get_input(f"請選擇 (0-{len(games)})", required=False)
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
        
        print(f"\n⏳ 下載中...")
        
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
            input("\n按 Enter 繼續...")
            return
        
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
        
        # 提供刪除選項
        print("="*50)
        print("  D. 刪除遊戲")
        print("  0. 返回")
        print("="*50)
        
        choice = self.get_input("\n請選擇").strip().lower()
        
        if choice == 'd':
            self.delete_game(games, player_dir)
        elif choice == '0':
            return
        else:
            print("❌ 無效的選項")
            input("按 Enter 繼續...")
    
    def delete_game(self, games, player_dir):
        """刪除已下載的遊戲"""
        print("\n🗑️  刪除遊戲")
        print("\n已下載的遊戲:")
        for i, game_name in enumerate(games, 1):
            print(f"  {i}. {game_name}")
        print(f"  0. 取消")
        
        while True:
            choice = self.get_input("\n請選擇要刪除的遊戲 (輸入數字)")
            
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(games):
                    game_name = games[choice_num - 1]
                    break
                else:
                    print(f"❌ 請輸入 0-{len(games)}")
            except ValueError:
                print("❌ 請輸入有效的數字")
        
        # 確認刪除
        confirm = self.get_input(f"\n確定要刪除「{game_name}」嗎？(y/n)").strip().lower()
        
        if confirm == 'y':
            import shutil
            game_dir = os.path.join(player_dir, game_name)
            try:
                shutil.rmtree(game_dir)
                print(f"\n✅ 已成功刪除「{game_name}」")
            except Exception as e:
                print(f"\n❌ 刪除失敗: {e}")
        else:
            print("\n已取消刪除")
        
        input("\n按 Enter 繼續...")
    
    def write_review(self):
        """撰寫遊戲評論"""
        print("\n✍️  撰寫遊戲評論")
        
        # 先檢查玩家已下載的遊戲
        player_dir = os.path.join(self.downloads_dir, self.username)
        
        if not os.path.exists(player_dir):
            print("❌ 你還沒有下載任何遊戲，無法撰寫評論")
            input("\n按 Enter 繼續...")
            return
        
        games = [d for d in os.listdir(player_dir) if os.path.isdir(os.path.join(player_dir, d))]
        
        if not games:
            print("❌ 你還沒有下載任何遊戲，無法撰寫評論")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示已下載的遊戲列表
        print(f"\n你已下載的遊戲:")
        for i, game_name in enumerate(games, 1):
            print(f"  {i}. {game_name}")
        print(f"  0. 取消")
        
        # 選擇遊戲（支援數字或名稱）
        while True:
            choice = self.get_input("\n請選擇要評論的遊戲 (輸入數字或名稱)")
            
            # 嘗試作為數字處理
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(games):
                    game_name = games[choice_num - 1]
                    break
                else:
                    print(f"❌ 請輸入 0-{len(games)}")
                    continue
            except ValueError:
                # 作為遊戲名稱處理
                if choice in games:
                    game_name = choice
                    break
                else:
                    print(f"❌ 你尚未下載「{choice}」，請輸入正確的數字或遊戲名稱")
                    continue
        
        # 輸入評分
        while True:
            rating_str = self.get_input("評分 (1-5)")
            try:
                rating = int(rating_str)
                if 1 <= rating <= 5:
                    break
                else:
                    print("❌ 評分必須在 1 到 5 之間")
            except ValueError:
                print("❌ 請輸入有效的數字")
        
        # 輸入評論內容
        comment = self.get_input("評論內容 (可留空)", required=False)
        
        # 送出評論
        response = self.send_request("submit_review", {
            "game_name": game_name,
            "rating": rating,
            "comment": comment
        })
        
        if response["status"] == "success":
            print(f"\n✅ {response['message']}")
        else:
            print(f"\n❌ {response.get('message', '評論失敗')}")
        
        input("\n按 Enter 繼續...")
    
    def view_reviews(self, game_name):
        """查看遊戲評論"""
        response = self.send_request("get_reviews", {"game_name": game_name})
        
        if response["status"] == "success":
            data = response["data"]
            reviews = data.get("reviews", [])
            avg_rating = data.get("average_rating", 0)
            total_reviews = data.get("total_reviews", 0)
            
            print(f"\n{'='*60}")
            print(f"  遊戲: {game_name}")
            print(f"  平均評分: {avg_rating:.1f}/5.0 ({total_reviews} 則評論)")
            
            if reviews:
                print(f"\n  評論列表:")
                for review in reviews:
                    print(f"\n  ⭐ {review['rating']}/5 - {review['player']}")
                    if review.get('comment'):
                        print(f"     {review['comment']}")
                    if review.get('timestamp'):
                        print(f"     時間: {review['timestamp']}")
            else:
                print("\n  目前還沒有評論")
            
            print(f"{'='*60}")
        else:
            print(f"❌ 取得評論失敗: {response.get('message', '')}")
    
    def list_rooms(self):
        """查看所有房間"""
        print("\n🏠 房間列表")
        
        # 取得已下載的遊戲清單
        player_dir = os.path.join(self.downloads_dir, self.username)
        
        if os.path.exists(player_dir):
            downloaded_games = [d for d in os.listdir(player_dir) if os.path.isdir(os.path.join(player_dir, d))]
        else:
            downloaded_games = []
        
        response = self.send_request("list_rooms", {})
        
        if response["status"] == "success":
            rooms = response["data"]["rooms"]
            
            if not rooms:
                print("  目前沒有任何房間")
            else:
                print(f"\n  共 {len(rooms)} 個房間:\n")
                for i, room in enumerate(rooms, 1):
                    status_icon = "🎮" if room["status"] == "playing" else "⏳"
                    
                    # 檢查是否已下載遊戲
                    game_status = "✅" if room['game_name'] in downloaded_games else "❌ 未下載"
                    
                    print(f"  {i}. {status_icon} {room['room_id']}")
                    print(f"     遊戲: {room['game_name']} (v{room.get('version', '?')}) {game_status}")
                    print(f"     房主: {room['host']}")
                    print(f"     玩家: {room['current_players']}/{room['max_players']}")
                    print(f"     狀態: {room['status']}")
                    print()
        else:
            print(f"❌ 取得房間列表失敗: {response.get('message', '')}")
        
        input("\n按 Enter 返回...")
    
    def list_online_players(self):
        """查看線上玩家"""
        print("\n👥 線上玩家")
        print("⏳ 載入中...")
        
        response = self.send_request("list_online_players", {})
        
        if response["status"] == "success":
            data = response["data"]
            players = data["players"]
            total = data["total_online"]
            
            self.clear_screen()
            print("\n" + "=" * 60)
            print(f"  👥 線上玩家 (共 {total} 人)")
            print("=" * 60)
            
            if not players:
                print("\n  目前沒有其他玩家在線上")
            else:
                # 分類顯示
                playing = [p for p in players if p["status"] == "playing"]
                in_room = [p for p in players if p["status"] == "in_room"]
                idle = [p for p in players if p["status"] == "idle"]
                
                if playing:
                    print(f"\n  🎮 遊戲中 ({len(playing)} 人)")
                    print("  " + "-" * 40)
                    for p in playing:
                        host_icon = "👑" if p.get("is_host") else "  "
                        print(f"    {host_icon} {p['username']}")
                        print(f"       正在玩: {p.get('game_name', '?')} ({p.get('room_id', '?')})")
                
                if in_room:
                    print(f"\n  🚪 在房間等待中 ({len(in_room)} 人)")
                    print("  " + "-" * 40)
                    for p in in_room:
                        host_icon = "👑" if p.get("is_host") else "  "
                        print(f"    {host_icon} {p['username']}")
                        print(f"       房間: {p.get('room_id', '?')} ({p.get('game_name', '?')})")
                
                if idle:
                    print(f"\n  💤 在大廳 ({len(idle)} 人)")
                    print("  " + "-" * 40)
                    for p in idle:
                        me_indicator = " (你)" if p['username'] == self.username else ""
                        print(f"       {p['username']}{me_indicator}")
            
            print("\n" + "=" * 60)
            print("  👑 = 房主")
            print("=" * 60)
        else:
            print(f"❌ 取得玩家列表失敗: {response.get('message', '')}")
        
        input("\n按 Enter 返回...")
    
    def create_room(self):
        """建立房間"""
        print("\n🏗️  建立房間")
        
        # 檢查是否已在房間
        if self.current_room:
            print("❌ 你已經在房間內了！")
            print(f"   當前房間: {self.current_room}")
            print("   請先離開房間（選項 9）才能建立新房間")
            input("\n按 Enter 繼續...")
            return
        
        # 取得已下載的遊戲
        player_dir = os.path.join(self.downloads_dir, self.username)
        
        if not os.path.exists(player_dir):
            print("❌ 你還沒有下載任何遊戲")
            print("請先下載遊戲（選項 3）")
            input("\n按 Enter 繼續...")
            return
        
        games = [d for d in os.listdir(player_dir) if os.path.isdir(os.path.join(player_dir, d))]
        
        if not games:
            print("❌ 你還沒有下載任何遊戲")
            print("請先下載遊戲（選項 3）")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示遊戲列表
        print(f"\n你的遊戲 (共 {len(games)} 款):\n")
        for i, game_name in enumerate(games, 1):
            game_dir = os.path.join(player_dir, game_name)
            version_file = os.path.join(game_dir, ".version")
            
            if os.path.exists(version_file):
                with open(version_file) as f:
                    version = f.read().strip()
            else:
                version = "unknown"
            
            print(f"  {i}. {game_name} (v{version})")
        
        print("  0. 取消")
        
        # 選擇遊戲
        while True:
            choice = self.get_input(f"請選擇 (0-{len(games)})", required=False)
            if not choice:
                continue
            
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(games):
                    game_name = games[choice_num - 1]
                    break
                else:
                    print(f"❌ 請輸入 0-{len(games)}")
            except ValueError:
                print("❌ 請輸入數字")
        
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
        
        # 檢查是否已在房間
        if self.current_room:
            print("❌ 你已經在房間內了！")
            print(f"   當前房間: {self.current_room}")
            print("   請先離開房間（選項 9）才能加入其他房間")
            input("\n按 Enter 繼續...")
            return
        
        # 取得已下載的遊戲清單及版本
        player_dir = os.path.join(self.downloads_dir, self.username)
        
        if not os.path.exists(player_dir):
            downloaded_games = {}
        else:
            downloaded_games = {}
            for d in os.listdir(player_dir):
                game_path = os.path.join(player_dir, d)
                if os.path.isdir(game_path):
                    # 讀取版本資訊
                    version_file = os.path.join(game_path, ".version")
                    if os.path.exists(version_file):
                        try:
                            with open(version_file, "r") as f:
                                version = f.read().strip()
                        except:
                            version = "unknown"
                    else:
                        version = "unknown"
                    downloaded_games[d] = version
        
        if not downloaded_games:
            print("❌ 你還沒有下載任何遊戲")
            print("請先下載遊戲（選項 3）才能加入房間")
            input("\n按 Enter 繼續...")
            return
        
        # 取得房間列表
        response = self.send_request("list_rooms", {})
        
        if response["status"] != "success":
            print(f"❌ 無法取得房間列表: {response.get('message', '')}")
            input("\n按 Enter 繼續...")
            return
        
        rooms = response["data"]["rooms"]
        
        # 過濾並分類房間
        available_rooms = []      # 遊戲已下載且版本匹配
        version_mismatch = []     # 遊戲已下載但版本不匹配
        not_downloaded = []       # 遊戲未下載
        
        for room in rooms:
            if room["status"] == "playing":
                continue
            
            game_name = room["game_name"]
            room_version = room.get("version", "unknown")
            
            if game_name in downloaded_games:
                local_version = downloaded_games[game_name]
                if local_version == room_version or local_version == "unknown" or room_version == "unknown":
                    available_rooms.append(room)
                else:
                    room["local_version"] = local_version
                    version_mismatch.append(room)
            else:
                not_downloaded.append(room)
        
        if not available_rooms:
            print("  目前沒有可加入的房間")
            
            # 顯示版本不匹配的房間
            if version_mismatch:
                print("\n  ⚠️  以下房間版本不匹配（需要更新遊戲）:")
                for r in version_mismatch:
                    print(f"    - {r['room_id']}: {r['game_name']}")
                    print(f"      房間版本: {r.get('version', '?')} | 你的版本: {r['local_version']}")
            
            # 顯示未下載的房間
            if not_downloaded:
                print("\n  ⚠️  以下房間的遊戲你還沒下載:")
                for r in not_downloaded:
                    print(f"    - {r['room_id']}: {r['game_name']} (v{r.get('version', '?')})")
            
            input("\n按 Enter 繼續...")
            return
        
        # 顯示可加入的房間列表
        print(f"\n可加入的房間 (共 {len(available_rooms)} 個):\n")
        for i, room in enumerate(available_rooms, 1):
            game_name = room['game_name']
            room_version = room.get('version', 'unknown')
            local_version = downloaded_games.get(game_name, 'unknown')
            
            print(f"  {i}. {room['room_id']}")
            print(f"     遊戲: {game_name} (v{room_version})")
            if local_version == room_version:
                print(f"     版本: ✅ 匹配")
            else:
                print(f"     版本: ✅ 已下載 (v{local_version})")
            print(f"     房主: {room['host']}")
            print(f"     玩家: {room['current_players']}/{room['max_players']}")
            print()
        
        # 提示版本不匹配的房間
        if version_mismatch:
            print(f"  ⚠️  另有 {len(version_mismatch)} 個房間版本不匹配")
        
        print("  0. 取消")
        
        # 選擇房間
        while True:
            choice = self.get_input(f"請選擇 (0-{len(available_rooms)})", required=False)
            if not choice:
                continue
            
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(available_rooms):
                    selected_room = available_rooms[choice_num - 1]
                    room_id = selected_room['room_id']
                    game_name = selected_room['game_name']
                    local_version = downloaded_games.get(game_name, "unknown")
                    break
                else:
                    print(f"❌ 請輸入 0-{len(available_rooms)}")
            except ValueError:
                print("❌ 請輸入數字")
        
        # 加入房間時傳送版本資訊
        response = self.send_request("join_room", {
            "room_id": room_id,
            "version": local_version
        })
        
        if response["status"] == "success":
            data = response["data"]
            self.current_room = room_id
            
            print(f"✅ 加入房間成功！")
            print(f"   房間 ID: {data['room_id']}")
            print(f"   遊戲: {data['game_name']} (v{data.get('version', '?')})")
            print(f"   玩家: {', '.join(data['players'])}")
        else:
            print(f"❌ 加入房間失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    
    def check_room_status(self):
        """查詢房間狀態"""
        print("\n🔍 查詢房間狀態")
        print("⏳ 更新中...")
        
        response = self.send_request("get_room_status", {"room_id": self.current_room})
        
        if not response:
            print("❌ 查詢失敗: 無法連接到 Server")
            print("💡 請檢查網路連線或重新登入")
            input("\n按 Enter 繼續...")
            return
        
        if response.get("status") == "success":
            data = response["data"]
            
            print("\n" + "="*60)
            print(f"📍 房間 ID: {data['room_id']}")
            print("="*60)
            
            print(f"\n🎮 遊戲資訊:")
            print(f"   名稱: {data['game_name']}")
            print(f"   版本: {data['version']}")
            print(f"   最多玩家: {data['max_players']}")
            
            print(f"\n👥 玩家列表 ({data['current_players']}/{data['max_players']}):")
            for i, player in enumerate(data['players'], 1):
                if player == data['host']:
                    print(f"   {i}. {player} 👑 (房主)")
                elif player == self.username:
                    print(f"   {i}. {player} (你)")
                else:
                    print(f"   {i}. {player}")
            
            print(f"\n📊 房間狀態:")
            status_text = {
                "waiting": "⏳ 等待中",
                "playing": "🎮 遊戲中",
                "finished": "✅ 已結束"
            }
            print(f"   {status_text.get(data['status'], data['status'])}")
            
            if data['is_host']:
                print(f"\n💡 你是房主，可以啟動遊戲")
            else:
                print(f"\n💡 等待房主啟動遊戲")

            # 檢查遊戲是否已啟動
            if data.get('status') == 'playing' and data.get('server_port'):
                print(f"\n🎮 遊戲已啟動！")
                print(f"   Game Server: {self.host}:{data['server_port']}")
                
                # 只有非房主才顯示加入遊戲提示
                if not data['is_host']:
                    join = self.get_input("\n是否加入遊戲? (yes/no)", required=False) or "no"
                    
                    if join.lower() in ["yes", "y"]:
                        self._launch_game_client(data)
                else:
                    print("\n💡 你是房主，可以選擇「重置房間」來重新開始遊戲")
            
            print("="*60)
        else:
            print(f"❌ 查詢失敗: {response.get('message', 'Unknown error')}")
            
            # 檢查是否是連線問題
            if "No response" in response.get('message', ''):
                print("\n💡 可能的原因:")
                print("   - Server 連線中斷")
                print("   - 網路問題")
                print("   建議: 返回主選單並重新登入")
        
        input("\n按 Enter 繼續...")
    
    def reset_room(self):
        """重置房間狀態（房主專用）"""
        print("\n🔄 重置房間")
        
        confirm = self.get_input("確定要重置房間嗎？這會結束當前遊戲 (yes/no)", required=False) or "no"
        if confirm.lower() not in ["yes", "y"]:
            print("已取消")
            input("\n按 Enter 繼續...")
            return
        
        response = self.send_request("reset_room", {"room_id": self.current_room})
        
        if response["status"] == "success":
            print("✅ 房間已重置，可以重新啟動遊戲")
        else:
            print(f"❌ 重置失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def _launch_game_client(self, room_data):
        """啟動遊戲客戶端（阻塞式）"""
        config = room_data.get("config", {})
        start_cmd = config.get("start_command", "")
        
        if not start_cmd:
            print("⚠️  此遊戲沒有自動啟動命令")
            input("\n按 Enter 繼續...")
            return
        
        game_name = room_data['game_name']
        player_dir = os.path.join(self.downloads_dir, self.username)
        game_dir = os.path.join(player_dir, game_name)
        
        if not os.path.exists(game_dir):
            print(f"❌ 找不到遊戲檔案: {game_dir}")
            print(f"請先下載遊戲")
            input("\n按 Enter 繼續...")
            return
        
        server_host = self.host
        server_port = room_data['server_port']
        start_cmd = start_cmd.replace("{host}", server_host)
        start_cmd = start_cmd.replace("{port}", str(server_port))
        start_cmd = start_cmd.replace("{username}", self.username)
        
        print(f"\n啟動命令: {start_cmd}")
        print(f"工作目錄: {game_dir}")
        
        try:
            # 使用阻塞式執行
            print("\n" + "="*50)
            print("遊戲執行中，請在遊戲視窗操作...")
            print("="*50 + "\n")
            
            import subprocess
            result = subprocess.run(
                start_cmd,
                shell=True,
                cwd=game_dir
            )
            
            print("\n" + "="*50)
            print("遊戲已結束")
            print("="*50)
            print(f"\n你仍在房間 {self.current_room} 中")
            print("可以選擇：")
            print("  - 等待房主再次啟動遊戲")
            print("  - 離開房間")
            
        except Exception as e:
            print(f"❌ 啟動失敗: {e}")
        
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
            
            # 取得 Game Server 資訊
            # 使用連接 Lobby Server 的 host，因為 Game Server 也在同一台機器上
            server_host = data.get("server_host", self.host)
            server_port = data.get("server_port")
            
            if server_port:
                print(f"   Game Server: {server_host}:{server_port}")
            
            # 取得啟動命令
            config = data.get("config", {})
            start_cmd = config.get("start_command", "")
            
            if start_cmd:
                # 找到遊戲檔案位置
                game_name = data['game_name']
                player_dir = os.path.join(self.downloads_dir, self.username)
                game_dir = os.path.join(player_dir, game_name)
                
                if os.path.exists(game_dir):
                    # 替換 {host} 和 {port}
                    if server_port:
                        start_cmd = start_cmd.replace("{host}", server_host)
                        start_cmd = start_cmd.replace("{port}", str(server_port))
                    
                    # 加入玩家名稱
                    start_cmd = start_cmd.replace("{username}", self.username)
                    
                    print(f"\n啟動命令: {start_cmd}")
                    print(f"工作目錄: {game_dir}")
                    
                    # 詢問是否自動啟動
                    auto = self.get_input("是否自動啟動遊戲? (yes/no)", required=False) or "no"
                    
                    if auto.lower() in ["yes", "y"]:
                        try:
                            # 在遊戲目錄下執行啟動命令（阻塞式）
                            print("\n" + "="*50)
                            print("遊戲執行中，請在遊戲視窗操作...")
                            print("="*50 + "\n")
                            
                            # 使用 subprocess.run 阻塞直到遊戲結束
                            result = subprocess.run(
                                start_cmd,
                                shell=True,
                                cwd=game_dir
                            )
                            
                            print("\n" + "="*50)
                            print("遊戲已結束")
                            print("="*50)
                            
                            # 遊戲結束後保持在房間內
                            print(f"\n👑 你是房主，仍在房間 {self.current_room} 中")
                            print("\n可以選擇：")
                            print("  1. 再次啟動遊戲（選項 2）")
                            print("  2. 離開房間解散（選項 3）")
                            print("  3. 返回主選單等待（選項 0）")
                        except Exception as e:
                            print(f"❌ 啟動失敗: {e}")
                            print(f"\n請手動執行:")
                            print(f"  cd {game_dir}")
                            print(f"  {start_cmd}")
                            # 啟動失敗，保留在房間內
                    else:
                        print(f"\n請手動執行:")
                        print(f"  cd {game_dir}")
                        print(f"  {start_cmd}")
                        # 用戶選擇手動啟動，保留在房間內
                else:
                    print(f"\n❌ 找不到遊戲檔案: {game_dir}")
                    print(f"請先下載遊戲")
                    # 找不到遊戲，保留在房間內
            else:
                print("\n⚠️  此遊戲沒有自動啟動命令")
                print("請查看遊戲目錄手動啟動")
                # 沒有啟動命令，保留在房間內
        else:
            print(f"❌ 啟動遊戲失敗: {response.get('message', '')}")
            # 啟動失敗，保留在房間內
        
        input("\n按 Enter 繼續...")
    
    def run(self):
        """主程式流程"""
        # 1. 連線到 Lobby Server
        if not self.connect():
            return
        
        # 2. 登入/註冊
        if not self.login_menu():
            print("👋 再見！")
            return
        
        # 3. 進入主選單
        self.main_menu()
        
        # 4. 關閉連線
        if self.sock:
            self.sock.close()
        
        print("👋 再見！")


# 在 lobby_client.py 的 LobbyClient 類別中加入以下函數

    def delete_downloaded_game(self):
        """刪除已下載的遊戲"""
        print("\n🗑️  刪除遊戲")
        print("=" * 60)
        
        # 確認下載目錄
        player_dir = os.path.join(self.downloads_dir, self.username)
        
        if not os.path.exists(player_dir):
            print("❌ 你還沒有下載任何遊戲")
            input("\n按 Enter 繼續...")
            return
        
        # 列出已下載的遊戲
        games = []
        try:
            for game_name in os.listdir(player_dir):
                game_path = os.path.join(player_dir, game_name)
                if os.path.isdir(game_path):
                    # 計算目錄大小
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(game_path):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            try:
                                total_size += os.path.getsize(filepath)
                            except:
                                pass
                    
                    size_mb = round(total_size / (1024 * 1024), 2)
                    games.append((game_name, size_mb, game_path))
        except Exception as e:
            print(f"❌ 無法讀取遊戲目錄: {e}")
            input("\n按 Enter 繼續...")
            return
        
        if not games:
            print("❌ 你還沒有下載任何遊戲")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示遊戲列表
        print(f"\n已下載的遊戲 (共 {len(games)} 款):\n")
        total_size = sum(size for _, size, _ in games)
        
        for i, (game_name, size, _) in enumerate(games, 1):
            print(f"  {i}. {game_name}")
            print(f"     大小: {size} MB")
            print()
        
        print(f"  總計: {total_size:.2f} MB")
        print("\n  0. 取消")
        
        # 選擇要刪除的遊戲
        while True:
            choice = self.get_input(f"請選擇要刪除的遊戲 (0-{len(games)})", required=False)
            if not choice:
                continue
            
            try:
                idx = int(choice)
                if idx == 0:
                    return
                if 1 <= idx <= len(games):
                    game_name, size, game_path = games[idx - 1]
                    break
                else:
                    print(f"❌ 請輸入 0-{len(games)}")
            except ValueError:
                print("❌ 請輸入數字")
        
        # 確認刪除
        print(f"\n⚠️  刪除確認")
        print(f"   遊戲名稱: {game_name}")
        print(f"   檔案大小: {size} MB")
        print(f"   刪除後可釋放: {size} MB 空間")
        print()
        
        confirm = self.get_input("確定要刪除嗎？輸入 'yes' 確認", required=False)
        
        if confirm.lower() != "yes":
            print("\n❌ 已取消刪除")
            input("\n按 Enter 繼續...")
            return
        
        # 執行刪除
        try:
            import shutil
            shutil.rmtree(game_path)
            print(f"\n✅ 遊戲 '{game_name}' 已成功刪除")
            print(f"   已釋放 {size} MB 空間")
        except Exception as e:
            print(f"\n❌ 刪除失敗: {e}")
        
        input("\n按 Enter 繼續...")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 lobby_client.py <host> <lobby_port>")
        print("\n提示: 從檔案讀取 port")
        
        # 嘗試從檔案讀取
        if os.path.exists(".lobby_port"):
            with open(".lobby_port") as f:
                lobby_port = int(f.read().strip())
            host = "localhost"
        else:
            print("\n❌ 找不到 .lobby_port 檔案")
            print("請先執行 python3 start_servers.py 啟動 Server")
            sys.exit(1)
    else:
        host = sys.argv[1]
        lobby_port = int(sys.argv[2])
    
    client = LobbyClient(host, lobby_port)
    client.run()


if __name__ == "__main__":
    main()