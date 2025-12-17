#!/usr/bin/env python3
# lobby_client.py - 玩家大廳客戶端（選單式介面）

import socket
import json
import os
import sys
import time
import base64
import zipfile
import io
import subprocess
import threading
import select
from lpfp import send_frame, recv_frame

class LobbyClient:
    def __init__(self, host, lobby_port):
        self.host = host
        self.lobby_port = lobby_port
        self.username = None
        self.running = True
        # 使用絕對路徑，基於程式所在目錄
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.downloads_dir = os.path.join(script_dir, "downloads")
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
                "瀏覽/下載遊戲",
                "查看詳情/評論",
                "我的遊戲",
                "撰寫評論",
                "返回"
            ]
            
            self.show_menu("🎮 遊戲商城", options)
            choice = self.get_input("請選擇")
            
            if choice == "1":
                self.browse_and_download()
            elif choice == "2":
                self.view_game_details()
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
        """房間功能子選單（已在房間時）- 後台自動更新"""
        last_room_data = None
        need_redraw = True
        room_data_lock = threading.Lock()
        current_room_data = {"data": None, "changed": False}
        polling_active = True
        
        # ⭐ 先獲取一次初始狀態
        initial_response = self.send_request("get_room_status", {"room_id": self.current_room})
        if initial_response and initial_response.get("status") == "success":
            current_room_data["data"] = initial_response["data"]
            current_room_data["changed"] = True
        elif initial_response and initial_response.get("status") == "error":
            if "not found" in initial_response.get("message", "").lower():
                print("\n⚠️  房間不存在")
                self.current_room = None
                input("\n按 Enter 繼續...")
                return
        
        def poll_room_status():
            """後台輪詢房間狀態"""
            nonlocal current_room_data, polling_active
            while polling_active and self.current_room:
                try:
                    response = self.send_request("get_room_status", {"room_id": self.current_room})
                    if response and response.get("status") == "success":
                        with room_data_lock:
                            new_data = response["data"]
                            # 檢查是否有變化
                            if new_data != current_room_data["data"]:
                                current_room_data["data"] = new_data
                                current_room_data["changed"] = True
                    elif response and response.get("status") == "error":
                        if "not found" in response.get("message", "").lower():
                            with room_data_lock:
                                current_room_data["data"] = None
                                current_room_data["changed"] = True
                    time.sleep(2)  # 每 2 秒輪詢一次
                except:
                    pass
        
        # 啟動後台輪詢線程
        poll_thread = threading.Thread(target=poll_room_status, daemon=True)
        poll_thread.start()
        
        try:
            while self.current_room:
                # 檢查是否有變化
                with room_data_lock:
                    if current_room_data["changed"]:
                        need_redraw = True
                        current_room_data["changed"] = False
                    room_data = current_room_data["data"]
                
                # ⭐ 房間被解散（但不是初始狀態）
                if room_data is None and last_room_data is not None:
                    self.clear_screen()
                    print("\n⚠️  房間已被解散")
                    self.current_room = None
                    input("\n按 Enter 繼續...")
                    break
                
                # ⭐ 如果還沒有數據，等待輪詢
                if room_data is None:
                    time.sleep(0.1)
                    continue
                
                # ⭐ 更新 last_room_data 用於判斷
                if room_data:
                    last_room_data = room_data.copy() if isinstance(room_data, dict) else room_data
                
                # 需要重繪
                if need_redraw:
                    self.clear_screen()
                    
                    is_host = room_data.get("is_host", False)
                    room_status = room_data.get("status", "unknown")
                    players = room_data.get("players", [])
                    game_name = room_data.get("game_name", "?")
                    
                    # 顯示房間資訊
                    status_text = {
                        "waiting": "⏳ 等待中", 
                        "playing": "🎮 遊戲中"
                    }
                    print(f"\n🚪 房間: {self.current_room}")
                    print(f"   遊戲: {game_name} | 狀態: {status_text.get(room_status, room_status)}")
                    print(f"   玩家: {', '.join(players)}")
                    if is_host:
                        print("   👑 你是房主")
                    
                    # 如果遊戲中，顯示 Game Server 資訊
                    if room_status == "playing" and room_data.get("server_port"):
                        print(f"   🎮 Game Server: {self.host}:{room_data['server_port']}")
                    
                    print()
                    
                    # 根據身份和狀態顯示選項
                    if room_status == "playing":
                        # 遊戲進行中 - 自動啟動遊戲
                        if room_data.get("server_port"):
                            print("\n🎮 遊戲進行中，正在連線...")
                            polling_active = False  # 停止輪詢
                            self._launch_game_client(room_data, auto_start=True)
                            polling_active = True  # 恢復輪詢
                            
                            # ⭐ 遊戲結束後立即刷新房間狀態
                            response = self.send_request("get_room_status", {"room_id": self.current_room})
                            if response and response.get("status") == "success":
                                with room_data_lock:
                                    current_room_data["data"] = response["data"]
                                    current_room_data["changed"] = True
                            
                            need_redraw = True  # 遊戲結束後重繪
                            continue
                        else:
                            print("⚠️  找不到 Game Server 資訊，可能遊戲已結束")
                            print("💡 請稍等，房間狀態將自動更新")
                            input("\n按 Enter 繼續...")
                            need_redraw = True
                            continue
                    else:
                        # waiting 狀態 - 顯示選單
                        if is_host:
                            options = [
                                "刷新房間狀態",
                                "啟動遊戲",
                                "離開房間",
                                "返回主選單"
                            ]
                        else:
                            options = [
                                "刷新房間狀態",
                                "等待房主啟動",
                                "離開房間",
                                "返回主選單"
                            ]
                        
                        self.show_menu("房間功能", options)
                        print("請選擇 (房間狀態自動更新中): ", end='', flush=True)
                    
                    need_redraw = False
                
                # 使用 select 實現帶超時的輸入
                ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                
                if ready:
                    choice = sys.stdin.readline().strip()
                    
                    if choice == "1":
                        need_redraw = True
                    elif choice == "2":
                        with room_data_lock:
                            is_host = room_data.get("is_host", False)
                        
                        if is_host:
                            polling_active = False  # 暫停輪詢
                            self.start_game()
                            polling_active = True  # 恢復輪詢
                            need_redraw = True
                        else:
                            # 非房主等待時，後台輪詢會自動檢測遊戲啟動
                            print("\n⏳ 等待房主啟動遊戲...")
                            print("   (後台自動檢測中，按任意鍵+Enter 取消)\n")
                            
                            # 等待遊戲啟動或用戶取消
                            while True:
                                with room_data_lock:
                                    current_status = room_data.get("status", "unknown") if room_data else "unknown"
                                
                                if current_status == "playing":
                                    print("\n✅ 遊戲已啟動！")
                                    need_redraw = True
                                    break
                                
                                # 檢查用戶是否要取消
                                ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                                if ready:
                                    sys.stdin.readline()  # 清除輸入
                                    print("\n已取消等待")
                                    need_redraw = True
                                    break
                                
                                print(".", end="", flush=True)
                    elif choice == "3":
                        confirm = self.get_input("確定要離開房間嗎? (y/n)", required=False) or "n"
                        if confirm.lower() in ["yes", "y"]:
                            polling_active = False  # 停止輪詢
                            response = self.send_request("leave_room", {"room_id": self.current_room})
                            if response["status"] == "success":
                                print("✅ 已離開房間")
                                self.current_room = None
                            else:
                                print(f"❌ 離開失敗: {response.get('message', '')}")
                                polling_active = True  # 恢復輪詢
                        need_redraw = True
                    elif choice == "4":
                        polling_active = False  # 停止輪詢
                        return
                    else:
                        need_redraw = True
        finally:
            polling_active = False  # 確保線程停止
            poll_thread.join(timeout=3)
    
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
    
    def browse_and_download(self):
        """瀏覽並下載遊戲（整合功能）"""
        print("\n🎮 瀏覽/下載遊戲")
        
        # 取得已下載的遊戲及版本
        player_dir = os.path.join(self.downloads_dir, self.username)
        downloaded = {}
        if os.path.exists(player_dir):
            for d in os.listdir(player_dir):
                game_path = os.path.join(player_dir, d)
                if os.path.isdir(game_path):
                    version_file = os.path.join(game_path, ".version")
                    if os.path.exists(version_file):
                        with open(version_file) as f:
                            downloaded[d] = f.read().strip()
                    else:
                        downloaded[d] = "unknown"
        
        # 取得遊戲列表
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
        
        # 顯示遊戲列表（含下載狀態）
        print(f"\n可用遊戲 (共 {len(games)} 款):\n")
        for i, game in enumerate(games, 1):
            game_name = game['game_name']
            server_ver = game['version']
            
            # 檢查下載狀態
            if game_name in downloaded:
                local_ver = downloaded[game_name]
                if local_ver == server_ver:
                    status = "✅ 已下載"
                else:
                    status = f"⬆️ 可更新 (本地: v{local_ver})"
            else:
                status = "📥 未下載"
            
            print(f"  {i}. {game_name} (v{server_ver}) {status}")
            print(f"     {game['game_type']} | {game['max_players']}人 | ⭐{game['average_rating']:.1f}")
            print(f"     {game['description']}")
            print()
        
        print("  0. 返回")
        
        # 選擇遊戲
        while True:
            choice = self.get_input(f"請選擇要下載的遊戲 (0-{len(games)})", required=False)
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
        
        if response["status"] != "success":
            print(f"❌ 取得遊戲詳情失敗: {response.get('message', '')}")
            input("\n按 Enter 返回...")
            return
        
        info = response["data"]["game_info"]
        reviews = response["data"].get("reviews", [])
        
        # 顯示遊戲詳情並進入評論子選單
        self._show_game_details_menu(info, reviews)
    
    def _show_game_details_menu(self, info, reviews):
        """遊戲詳情與評論子選單"""
        import sys
        
        while True:
            self.clear_screen()
            
            # 顯示遊戲基本資訊
            print("=" * 60)
            print(f"  🎮 {info['game_name']} (v{info['version']})")
            print("=" * 60)
            print(f"  開發者: {info['developer']}")
            print(f"  類型: {info['game_type']} | 最多 {info['max_players']} 人")
            print(f"  下載次數: {info['download_count']}")
            print(f"\n  📝 簡介: {info['description']}")
            
            # 評分統計
            print(f"\n  " + "-" * 40)
            if reviews:
                avg = info['average_rating']
                total = len(reviews)
                
                # 計算各星級數量
                star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
                for r in reviews:
                    rating = r.get('rating', 0)
                    if rating in star_counts:
                        star_counts[rating] += 1
                
                print(f"  ⭐ 評分: {avg:.1f}/5.0 ({total} 則評論)\n")
                
                # 顯示評分分佈條（使用 # 和 - 代替特殊字元）
                for star in [5, 4, 3, 2, 1]:
                    count = star_counts[star]
                    pct = (count / total * 100) if total > 0 else 0
                    bar_len = int(pct / 5)  # 最長 20 格
                    bar = "#" * bar_len + "-" * (20 - bar_len)
                    print(f"  {star}星 [{bar}] {count:2d} ({pct:5.1f}%)")
            else:
                print(f"  ⭐ 尚無評論")
            
            print(f"  " + "-" * 40)
            
            # 選項
            print(f"\n  1. 查看所有評論 ({len(reviews)} 則)")
            print(f"  2. 按評分篩選")
            print(f"  3. 最新評論")
            print(f"  4. 最舊評論")
            print(f"  0. 返回")
            
            # 強制刷新輸出
            sys.stdout.flush()
            
            choice = self.get_input("\n請選擇").strip()
            
            if choice == "1":
                self._show_reviews(reviews, "所有評論")
            elif choice == "2":
                self._filter_reviews_by_rating(reviews)
            elif choice == "3":
                self._show_reviews(reviews[-10:], "最新 10 則評論", reverse=True)
            elif choice == "4":
                self._show_reviews(reviews[:10], "最早 10 則評論")
            elif choice == "0":
                break
            else:
                print("❌ 無效的選項")
                input("按 Enter 繼續...")
    
    def _show_reviews(self, reviews, title, reverse=False):
        """顯示評論列表"""
        import sys
        
        self.clear_screen()
        print(f"\n📋 {title}")
        print("=" * 60)
        
        if not reviews:
            print("\n  尚無評論")
            input("\n按 Enter 返回...")
            return
        
        display_reviews = list(reversed(reviews)) if reverse else reviews
        
        for i, review in enumerate(display_reviews, 1):
            rating = review.get('rating', 0)
            stars = "*" * rating + "." * (5 - rating)
            player = review.get('player', '匿名')
            comment = review.get('comment', '')
            timestamp = review.get('timestamp', '')
            
            # 格式化時間
            time_str = ""
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = str(timestamp)[:16] if len(str(timestamp)) > 16 else str(timestamp)
            
            print(f"\n  {i}. [{stars}] {rating}/5 星")
            print(f"     玩家: {player}")
            if time_str:
                print(f"     時間: {time_str}")
            print(f"     評論: {comment}")
            print(f"     " + "-" * 35)
            
            sys.stdout.flush()
            
            # 每 5 則暫停一次
            if i % 5 == 0 and i < len(display_reviews):
                cont = self.get_input(f"\n  已顯示 {i}/{len(display_reviews)} 則，Enter 繼續，q 返回").strip().lower()
                if cont == 'q':
                    return
        
        print(f"\n  共 {len(display_reviews)} 則評論")
        input("\n按 Enter 返回...")
    
    def _filter_reviews_by_rating(self, reviews):
        """按評分篩選評論"""
        import sys
        
        self.clear_screen()
        print("\n🔍 按評分篩選")
        print("=" * 60)
        
        if not reviews:
            print("\n  尚無評論")
            input("\n按 Enter 返回...")
            return
        
        # 計算各星級數量
        star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for r in reviews:
            rating = r.get('rating', 0)
            if rating in star_counts:
                star_counts[rating] += 1
        
        print("\n  選擇要查看的評分:")
        print(f"  1. [*****] 5星評論 ({star_counts[5]} 則)")
        print(f"  2. [****.] 4星評論 ({star_counts[4]} 則)")
        print(f"  3. [***..] 3星評論 ({star_counts[3]} 則)")
        print(f"  4. [**...] 2星評論 ({star_counts[2]} 則)")
        print(f"  5. [*....] 1星評論 ({star_counts[1]} 則)")
        print(f"  0. 返回")
        
        sys.stdout.flush()
        
        choice = self.get_input("\n請選擇").strip()
        
        rating_map = {"1": 5, "2": 4, "3": 3, "4": 2, "5": 1}
        
        if choice in rating_map:
            target_rating = rating_map[choice]
            filtered = [r for r in reviews if r.get('rating') == target_rating]
            self._show_reviews(filtered, f"{target_rating} 星評論")
        elif choice == "0":
            return
        else:
            print("❌ 無效的選項")
            input("按 Enter 繼續...")
    
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
        import shutil
        
        # 顯示下載目錄位置
        print(f"\n📁 下載目錄: {os.path.abspath(player_dir)}")
        
        # 重新掃描確認目前有哪些遊戲
        if not os.path.exists(player_dir):
            print(f"\n❌ 玩家目錄不存在: {player_dir}")
            input("\n按 Enter 繼續...")
            return
        
        current_games = [d for d in os.listdir(player_dir) if os.path.isdir(os.path.join(player_dir, d))]
        
        if not current_games:
            print("\n❌ 目前沒有任何已下載的遊戲可刪除")
            input("\n按 Enter 繼續...")
            return
        
        print("\n🗑️  刪除遊戲")
        print("\n已下載的遊戲:")
        for i, game_name in enumerate(current_games, 1):
            game_dir = os.path.join(player_dir, game_name)
            version_file = os.path.join(game_dir, ".version")
            if os.path.exists(version_file):
                with open(version_file) as f:
                    version = f.read().strip()
            else:
                version = "unknown"
            print(f"  {i}. {game_name} (v{version})")
            print(f"     路徑: {game_dir}")
        print(f"  0. 取消")
        
        while True:
            choice = self.get_input("\n請選擇要刪除的遊戲 (輸入數字)")
            
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(current_games):
                    game_name = current_games[choice_num - 1]
                    break
                else:
                    print(f"❌ 請輸入 0-{len(current_games)}")
            except ValueError:
                print("❌ 請輸入有效的數字")
        
        game_dir = os.path.join(player_dir, game_name)
        abs_game_dir = os.path.abspath(game_dir)
        
        # 確認檔案存在
        if not os.path.exists(game_dir):
            print(f"\n❌ 找不到遊戲資料夾: {abs_game_dir}")
            input("\n按 Enter 繼續...")
            return
        
        # 顯示要刪除的完整路徑
        print(f"\n將刪除: {abs_game_dir}")
        
        # 確認刪除
        confirm = self.get_input(f"確定要刪除「{game_name}」嗎？(y/n)").strip().lower()
        
        if confirm == 'y':
            try:
                shutil.rmtree(game_dir)
                
                # 驗證是否成功刪除
                if os.path.exists(game_dir):
                    print(f"\n❌ 刪除失敗：資料夾仍然存在")
                    print(f"   路徑: {abs_game_dir}")
                else:
                    print(f"\n✅ 已成功刪除「{game_name}」")
                    print(f"   已刪除: {abs_game_dir}")
                    
                    # 顯示剩餘遊戲數量
                    remaining = [d for d in os.listdir(player_dir) if os.path.isdir(os.path.join(player_dir, d))]
                    if remaining:
                        print(f"   剩餘 {len(remaining)} 款遊戲: {', '.join(remaining)}")
                    else:
                        print(f"   已無任何下載的遊戲")
            except PermissionError:
                print(f"\n❌ 刪除失敗：權限不足，可能遊戲正在執行中")
                print(f"   路徑: {abs_game_dir}")
            except Exception as e:
                print(f"\n❌ 刪除失敗: {e}")
                print(f"   路徑: {abs_game_dir}")
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

        # 取得已下載的遊戲及版本
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

        # 獲取本地遊戲版本
        local_versions = {}
        for game_name in games:
            game_dir = os.path.join(player_dir, game_name)
            version_file = os.path.join(game_dir, ".version")

            if os.path.exists(version_file):
                with open(version_file) as f:
                    local_versions[game_name] = f.read().strip()
            else:
                local_versions[game_name] = "unknown"

        # 取得伺服器上的遊戲列表（含最新版本）
        response = self.send_request("list_games", {})

        if response["status"] != "success":
            print(f"❌ 無法取得遊戲列表: {response.get('message', '')}")
            input("\n按 Enter 繼續...")
            return

        server_games = {g['game_name']: g['version'] for g in response["data"]["games"]}

        # 分類遊戲：版本一致 vs 需要更新
        up_to_date_games = []
        outdated_games = []

        for game_name in games:
            local_ver = local_versions.get(game_name, "unknown")
            server_ver = server_games.get(game_name, "unknown")

            if local_ver == server_ver:
                up_to_date_games.append((game_name, local_ver))
            else:
                outdated_games.append((game_name, local_ver, server_ver))

        # 顯示遊戲列表
        print(f"\n✅ 可建立房間的遊戲 (版本最新):\n")
        if up_to_date_games:
            for i, (game_name, version) in enumerate(up_to_date_games, 1):
                print(f"  {i}. {game_name} (v{version})")
        else:
            print("  (無)")

        if outdated_games:
            print(f"\n⚠️  需要更新的遊戲 (無法建立房間):\n")
            for game_name, local_ver, server_ver in outdated_games:
                print(f"  ❌ {game_name}")
                print(f"     你的版本: v{local_ver} → 最新版本: v{server_ver}")
                # 檢查遊戲是否已下架
                if server_ver in ["vunknown", "unknown"]:
                    print(f"     此遊戲已下架")
                else:
                    print(f"     請先到「遊戲商城 → 瀏覽/下載遊戲」更新")

        if not up_to_date_games:
            print("\n❌ 你沒有版本最新的遊戲，無法建立房間")
            print("請先更新遊戲到最新版本")
            input("\n按 Enter 繼續...")
            return

        print("  0. 取消")

        # 選擇遊戲
        while True:
            choice = self.get_input(f"請選擇 (0-{len(up_to_date_games)})", required=False)
            if not choice:
                continue

            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return
                if 1 <= choice_num <= len(up_to_date_games):
                    game_name, local_version = up_to_date_games[choice_num - 1]
                    break
                else:
                    print(f"❌ 請輸入 0-{len(up_to_date_games)}")
            except ValueError:
                print("❌ 請輸入數字")

        # 建立房間時傳送版本資訊
        response = self.send_request("create_room", {
            "game_name": game_name,
            "version": local_version
        })

        if response["status"] == "success":
            data = response["data"]
            self.current_room = data["room_id"]

            print(f"✅ 房間建立成功！")
            print(f"   房間 ID: {data['room_id']}")
            print(f"   遊戲: {data['game_name']} (v{data.get('version', '?')})")
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
                    # 檢查遊戲是否已下架
                    if r.get('version') in ["vunknown", "unknown"]:
                        print(f"      此遊戲已下架")
            
            # 顯示未下載的房間
            if not_downloaded:
                print("\n  ⚠️  以下房間的遊戲你還沒下載:")
                for r in not_downloaded:
                    room_ver = r.get('version', '?')
                    # 檢查遊戲是否已下架
                    if room_ver in ["vunknown", "unknown"]:
                        print(f"    - {r['room_id']}: {r['game_name']} (v{room_ver}) - 此遊戲已下架")
                    else:
                        print(f"    - {r['room_id']}: {r['game_name']} (v{room_ver})")
            
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
                # 顯示準備狀態
                ready_mark = ""
                if data.get('status') == 'ready_check':
                    ready_players = data.get('ready_players', [])
                    ready_mark = " ✅" if player in ready_players else " ⏳"
                
                if player == data['host']:
                    print(f"   {i}. {player} 👑 (房主){ready_mark}")
                elif player == self.username:
                    print(f"   {i}. {player} (你){ready_mark}")
                else:
                    print(f"   {i}. {player}{ready_mark}")
            
            print(f"\n📊 房間狀態:")
            status_text = {
                "waiting": "⏳ 等待中",
                "ready_check": "🔔 準備確認中",
                "playing": "🎮 遊戲中",
                "finished": "✅ 已結束"
            }
            print(f"   {status_text.get(data['status'], data['status'])}")
            
            # 根據狀態顯示不同提示
            if data['status'] == 'waiting':
                if data['is_host']:
                    print(f"\n💡 你是房主，可以發起準備確認")
                else:
                    print(f"\n💡 等待房主發起準備確認")
            
            elif data['status'] == 'ready_check':
                ready_players = data.get('ready_players', [])
                waiting_for = data.get('waiting_for', [])
                print(f"\n   ✅ 已準備 ({len(ready_players)}): {', '.join(ready_players)}")
                print(f"   ⏳ 等待中 ({len(waiting_for)}): {', '.join(waiting_for)}")
                
                if data['is_host']:
                    print(f"\n💡 等待所有玩家準備就緒...")
                else:
                    if data.get('is_ready'):
                        print(f"\n💡 你已準備就緒，等待其他玩家")
                    else:
                        print(f"\n💡 請選擇「準備就緒」確認參加")
            
            elif data.get('status') == 'playing' and data.get('server_port'):
                print(f"\n🎮 遊戲已啟動！")
                print(f"   Game Server: {self.host}:{data['server_port']}")
                
                if data['is_host']:
                    print("\n💡 你是房主，可以選擇「重置房間」來重新開始遊戲")
                else:
                    print("\n💡 遊戲進行中，返回房間功能即可自動加入")
            
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
    
    def _launch_game_client(self, room_data, auto_start=True):
        """啟動遊戲客戶端（阻塞式）
        
        Args:
            room_data: 房間資料
            auto_start: 是否自動啟動（False 時顯示手動命令）
        """
        import subprocess
        import sys
        
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
        
        # ⭐ 使用伺服器回傳的 server_host，如果沒有才用 self.host
        server_host = room_data.get('server_host', self.host)
        server_port = room_data['server_port']
        start_cmd = start_cmd.replace("{host}", server_host)
        start_cmd = start_cmd.replace("{port}", str(server_port))
        start_cmd = start_cmd.replace("{username}", self.username)
        
        print(f"\n🎮 啟動遊戲")
        print(f"   遊戲: {game_name}")
        print(f"   伺服器: {server_host}:{server_port}")
        print(f"   命令: {start_cmd}")
        print(f"   目錄: {game_dir}")
        
        if not auto_start:
            print(f"\n手動啟動命令:")
            print(f"  cd {game_dir}")
            print(f"  {start_cmd}")
            input("\n按 Enter 繼續...")
            return
        
        print("\n" + "="*50)
        print("遊戲啟動中...")
        print("="*50 + "\n")
        sys.stdout.flush()
        
        try:
            # 使用 Popen 以便更好地控制進程
            process = subprocess.Popen(
                start_cmd,
                shell=True,
                cwd=game_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # 即時輸出遊戲的訊息
            while True:
                output = process.stdout.readline()
                if output:
                    print(output, end='')
                    sys.stdout.flush()
                
                # 檢查進程是否結束
                ret = process.poll()
                if ret is not None:
                    # 讀取剩餘輸出
                    remaining = process.stdout.read()
                    if remaining:
                        print(remaining, end='')
                    break
            
            print("\n" + "="*50)
            print("🎮 遊戲已結束")
            print("="*50)
            
            # ⭐ 等待並刷新房間狀態（給監控線程時間重置）
            if self.current_room:
                print("\n⏳ 等待房間重置...")
                max_retries = 5
                for i in range(max_retries):
                    time.sleep(1)  # 每次等待 1 秒
                    response = self.send_request("get_room_status", {"room_id": self.current_room})
                    if response.get("status") == "success":
                        room_status = response["data"].get("status", "unknown")
                        if room_status == "waiting":
                            print(f"✅ 房間已自動重置為等待狀態")
                            print(f"   房主可以重新啟動遊戲")
                            break
                        else:
                            print(f"   [{i+1}/{max_retries}] 房間狀態: {room_status}")
                    else:
                        print(f"   [{i+1}/{max_retries}] 無法取得房間狀態")
                else:
                    # 超時仍未重置
                    print(f"⚠️  房間狀態尚未更新，可能需要稍等")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  遊戲被中斷 (Ctrl+C)")
            if 'process' in locals() and process.poll() is None:
                print("   正在終止遊戲進程...")
                process.terminate()
                try:
                    process.wait(timeout=2)
                except:
                    process.kill()
            
            # ⭐ 等待並刷新房間狀態（給監控線程時間重置）
            if self.current_room:
                print("\n⏳ 等待房間重置...")
                max_retries = 3
                for i in range(max_retries):
                    time.sleep(1)
                    try:
                        response = self.send_request("get_room_status", {"room_id": self.current_room})
                        if response.get("status") == "success":
                            room_status = response["data"].get("status", "unknown")
                            if room_status == "waiting":
                                print(f"✅ 房間已重置為等待狀態")
                                break
                            else:
                                print(f"   [{i+1}/{max_retries}] 房間狀態: {room_status}")
                    except:
                        pass
            
            print("\n返回選單...")
            return
            
        except Exception as e:
            print(f"\n❌ 啟動失敗: {e}")
        
        input("\n按 Enter 返回選單...")
    
    def start_game(self):
        """啟動遊戲（房主專用）- 啟動 Game Server 並自動連線等待其他玩家"""
        print("\n🎮 啟動遊戲")
        
        response = self.send_request("start_game", {"room_id": self.current_room})
        
        if response["status"] == "success":
            data = response["data"]
            
            print(f"✅ Game Server 已啟動！")
            print(f"   遊戲: {data['game_name']}")
            print(f"   版本: {data['version']}")
            print(f"   玩家: {', '.join(data['players'])}")
            
            server_port = data.get("server_port")
            if server_port:
                print(f"   Game Server: {self.host}:{server_port}")
            
            print(f"\n💡 等待其他玩家加入...")
            print(f"   請通知其他玩家選擇「加入遊戲」")
            
            # 房主自動連線到遊戲
            try:
                self._launch_game_client(data, auto_start=True)
            except KeyboardInterrupt:
                print("\n\n⚠️  操作被中斷")
                return
        else:
            print(f"❌ 啟動失敗: {response.get('message', '')}")
        
        try:
            input("\n按 Enter 繼續...")
        except KeyboardInterrupt:
            print("\n")
    
    def player_ready(self):
        """玩家加入遊戲（非房主）"""
        print("\n🎮 加入遊戲")
        
        # 先查詢房間狀態取得 Game Server 資訊
        response = self.send_request("get_room_status", {"room_id": self.current_room})
        
        if response["status"] != "success":
            print(f"❌ 無法取得房間資訊: {response.get('message', '')}")
            try:
                input("\n按 Enter 繼續...")
            except KeyboardInterrupt:
                print("\n")
            return
        
        room_data = response["data"]
        
        if room_data.get("status") != "playing":
            print("⚠️  遊戲尚未啟動，請等待房主啟動遊戲")
            try:
                input("\n按 Enter 繼續...")
            except KeyboardInterrupt:
                print("\n")
            return
        
        if not room_data.get("server_port"):
            print("⚠️  找不到 Game Server 資訊")
            try:
                input("\n按 Enter 繼續...")
            except KeyboardInterrupt:
                print("\n")
            return
        
        print(f"✅ 找到 Game Server: {self.host}:{room_data['server_port']}")
        print(f"   正在連線...")
        
        # 連線到遊戲
        try:
            self._launch_game_client(room_data, auto_start=True)
        except KeyboardInterrupt:
            print("\n\n⚠️  操作被中斷")
    
    def cancel_ready_check(self):
        """取消準備確認（房主專用）"""
        print("\n🚫 取消準備確認")
        
        confirm = self.get_input("確定要取消嗎? (y/n)", required=False) or "n"
        if confirm.lower() not in ["yes", "y"]:
            print("已取消")
            input("\n按 Enter 繼續...")
            return
        
        response = self.send_request("cancel_ready_check", {"room_id": self.current_room})
        
        if response["status"] == "success":
            print("✅ 準備確認已取消")
        else:
            print(f"❌ 取消失敗: {response.get('message', '')}")
        
        input("\n按 Enter 繼續...")
    
    def _old_start_game(self):
        """舊的啟動遊戲（保留參考）"""
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