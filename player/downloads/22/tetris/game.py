# game.py - 客戶端遊戲渲染（支持玩家模式和觀戰模式）
# 修復: 1. 遊戲結束畫面卡住 2. 中文顯示問題 3. 非法斷線問題
import pygame
import sys
import time
import socket
import json
import threading
from lpfp import send_frame, recv_frame
from protocol import encode_message, decode_message

# 顏色定義
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (100, 100, 100)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
BLUE = (50, 50, 255)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (148, 0, 211)

# 遊戲常數
CELL = 24
ROWS, COLS = 20, 10
FPS = 30


class TetrisGame:
    """客戶端遊戲（玩家模式）"""
    
    def __init__(self, seed=None, conn=None, username=None):
        self.conn = conn
        self.running = True
        self.waiting_for_end = False
        self.game_end_data = None
        self.username = username
        self.mode = "player"
        
        # 等待狀態
        self.game_started = False  # 遊戲是否已開始
        self.current_players = 1
        self.expected_players = 2
        self.connected_players = []
        
        # 遊戲狀態
        self.my_state = None
        self.opponent_state = None
        self.my_name = username
        self.opponent_name = None
        
        # pygame 初始化
        try:
            pygame.init()
            self.screen = pygame.display.set_mode((COLS * CELL * 2 + 200, ROWS * CELL + 150))
            pygame.display.set_caption("Tetris Battle - Player Mode")
            self.clock = pygame.time.Clock()
            self.font = pygame.font.Font(None, 24)
            self.big_font = pygame.font.Font(None, 48)
        except pygame.error:
            print("[!] Cannot start pygame window, need graphical environment")
            sys.exit(1)
        
        # 啟動背景執行緒接收伺服器狀態
        if self.conn:
            threading.Thread(target=self.listen_server, daemon=True).start()
    
    def listen_server(self):
        """接收伺服器的遊戲狀態更新"""
        if self.conn:
            self.conn.settimeout(None)
        
        while True:
            try:
                raw = recv_frame(self.conn)
                if not raw:
                    if self.running or self.waiting_for_end:
                        print("[Server] Connection closed unexpectedly")
                    break
                
                data = decode_message(raw)
                
                if not data:
                    continue
                
                msg_type = data.get("type")
                
                # 處理等待訊息
                if msg_type == "WAITING":
                    self.current_players = data.get("current_players", 1)
                    self.expected_players = data.get("expected_players", 2)
                    self.connected_players = data.get("players", [])
                    # 不輸出太多日誌，避免干擾
                
                # 處理遊戲開始訊息
                elif msg_type == "GAME_START":
                    print(f"[Game] Game starting! Players: {data.get('players', [])}")
                    self.game_started = True
                    self.connected_players = data.get("players", [])
                
                # 處理遊戲狀態
                elif msg_type == "GAME_STATE":
                    if self.running:
                        self.game_started = True  # 收到狀態表示遊戲已開始
                        states = data.get("states", {})
                        
                        if self.my_name and self.my_name in states:
                            self.my_state = states[self.my_name]
                            
                            for name in states.keys():
                                if name != self.my_name:
                                    self.opponent_name = name
                                    self.opponent_state = states[name]
                                    break
                        elif len(states) >= 2:
                            names = list(states.keys())
                            if not self.my_name:
                                self.my_name = names[0]
                                self.opponent_name = names[1]
                            self.my_state = states.get(self.my_name)
                            self.opponent_state = states.get(self.opponent_name)
                
                elif msg_type == "GAME_END":
                    print("[Game] Received GAME_END message")
                    self.game_end_data = data
                    self.running = False
                    self.waiting_for_end = False
                    try:
                        pygame.event.post(pygame.event.Event(pygame.USEREVENT))
                    except:
                        pass
                    break
            
            except Exception as e:
                if self.running or self.waiting_for_end:
                    print(f"[Error] Receive error: {e}")
                break
        
        print("[Game] Listen server thread exiting")
    
    def handle_game_end(self, data):
        """處理遊戲結束"""
        winner = data.get("winner", "Unknown")
        results = data.get("results", [])
        
        print("\n" + "="*50)
        print(f"GAME OVER! Winner: {winner}")
        for result in results:
            player = result.get('player', 'Unknown')
            score = result.get('score', 0)
            lines = result.get('lines', 0)
            is_winner = result.get('is_winner', False)
            symbol = "[WIN]" if is_winner else "     "
            print(f"{symbol} {player}: {lines} lines {score} pts")
        print("="*50 + "\n")
        
        # 顯示結果畫面 10 秒
        countdown = 10
        start_time = time.time()
        
        while countdown > 0:
            # 先處理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("[Game] Window closed during results")
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        print("[Game] ESC pressed, returning to lobby")
                        return
            
            self.screen.fill(BLACK)
            
            # 標題
            title = self.big_font.render("GAME OVER!", True, YELLOW)
            title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
            self.screen.blit(title, title_rect)
            
            # 結果
            y = 150
            for result in results:
                player = result.get('player', 'Unknown')
                score = result.get('score', 0)
                lines = result.get('lines', 0)
                is_winner = result.get('is_winner', False)
                
                color = GREEN if is_winner else WHITE
                prefix = "[WINNER] " if is_winner else ""
                text = f"{prefix}{player}: {lines} lines {score} pts"
                rendered = self.font.render(text, True, color)
                text_rect = rendered.get_rect(center=(self.screen.get_width() // 2, y))
                self.screen.blit(rendered, text_rect)
                y += 40
            
            # 倒數提示
            instruction1 = self.font.render(f"Returning to lobby in {countdown} sec", True, YELLOW)
            instruction2 = self.font.render("Press ESC to return now", True, WHITE)
            inst1_rect = instruction1.get_rect(center=(self.screen.get_width() // 2, y + 50))
            inst2_rect = instruction2.get_rect(center=(self.screen.get_width() // 2, y + 80))
            self.screen.blit(instruction1, inst1_rect)
            self.screen.blit(instruction2, inst2_rect)
            
            pygame.display.flip()
            
            # 更新倒數
            elapsed = time.time() - start_time
            countdown = 10 - int(elapsed)
            time.sleep(0.1)
        
        print("[Game] Auto-returning to lobby")
    
    def draw_board(self, board, offset_x, offset_y):
        """繪製單個遊戲畫面"""
        if not board:
            return
        
        for r in range(ROWS):
            for c in range(COLS):
                if board[r][c]:
                    pygame.draw.rect(
                        self.screen, BLUE,
                        (offset_x + c * CELL, offset_y + r * CELL, CELL - 1, CELL - 1)
                    )
        
        # 邊框
        pygame.draw.rect(self.screen, GRAY, (offset_x, offset_y, COLS * CELL, ROWS * CELL), 2)
    
    def draw_falling(self, falling, offset_x, offset_y, color):
        """繪製下落中的方塊"""
        if not falling:
            return
        
        shape = falling.get('shape', [])
        x = falling.get('x', 0)
        y = falling.get('y', 0)
        
        for r, row in enumerate(shape):
            for c, val in enumerate(row):
                if val:
                    pygame.draw.rect(
                        self.screen, color,
                        (offset_x + (x + c) * CELL, offset_y + (y + r) * CELL, CELL - 1, CELL - 1)
                    )
    
    def draw(self):
        """繪製完整畫面"""
        self.screen.fill(BLACK)
        
        # 如果遊戲尚未開始，顯示等待畫面
        if not self.game_started:
            self.draw_waiting_for_players()
            pygame.display.flip()
            return
        
        # 繪製遊戲目標
        goal_text = self.font.render("Goal: First to clear 1 line!", True, YELLOW)
        self.screen.blit(goal_text, (150, 10))
        
        # 左邊：自己
        if self.my_state:
            name_text = self.font.render(f"{self.my_name} (YOU)", True, GREEN)
            self.screen.blit(name_text, (10, 60))
            
            self.draw_board(self.my_state.get('board', []), 10, 90)
            self.draw_falling(self.my_state.get('falling'), 10, 90, GREEN)
            
            score_text = self.font.render(f"Score: {self.my_state.get('score', 0)}", True, WHITE)
            lines_text = self.font.render(f"Lines: {self.my_state.get('lines', 0)}", True, WHITE)
            self.screen.blit(score_text, (10, ROWS * CELL + 100))
            self.screen.blit(lines_text, (10, ROWS * CELL + 125))
        else:
            status_text = self.font.render("Waiting for game state...", True, YELLOW)
            self.screen.blit(status_text, (10, ROWS * CELL // 2))
        
        # 右邊：對手
        if self.opponent_state:
            offset_x = COLS * CELL + 50
            
            name_text = self.font.render(f"{self.opponent_name} (OPP)", True, CYAN)
            self.screen.blit(name_text, (offset_x, 60))
            
            self.draw_board(self.opponent_state.get('board', []), offset_x, 90)
            self.draw_falling(self.opponent_state.get('falling'), offset_x, 90, CYAN)
            
            score_text = self.font.render(f"Score: {self.opponent_state.get('score', 0)}", True, WHITE)
            lines_text = self.font.render(f"Lines: {self.opponent_state.get('lines', 0)}", True, WHITE)
            self.screen.blit(score_text, (offset_x, ROWS * CELL + 100))
            self.screen.blit(lines_text, (offset_x, ROWS * CELL + 125))
            
            if self.opponent_state.get('game_over'):
                over_text = self.font.render("GAME OVER!", True, RED)
                self.screen.blit(over_text, (offset_x + 20, 35))
        else:
            offset_x = COLS * CELL + 50
            status_text = self.font.render("Waiting for opponent...", True, YELLOW)
            self.screen.blit(status_text, (offset_x, ROWS * CELL // 2))
        
        pygame.display.flip()
    
    def draw_waiting_for_players(self):
        """繪製等待其他玩家的畫面"""
        # 標題
        title = self.big_font.render("Waiting for Players...", True, YELLOW)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 100))
        self.screen.blit(title, title_rect)
        
        # 玩家數量
        count_text = self.font.render(
            f"Players: {self.current_players} / {self.expected_players}",
            True, WHITE
        )
        count_rect = count_text.get_rect(center=(self.screen.get_width() // 2, 180))
        self.screen.blit(count_text, count_rect)
        
        # 已連線的玩家列表
        y = 230
        for i, player in enumerate(self.connected_players, 1):
            color = GREEN if player == self.my_name else CYAN
            player_text = self.font.render(f"{i}. {player}", True, color)
            player_rect = player_text.get_rect(center=(self.screen.get_width() // 2, y))
            self.screen.blit(player_text, player_rect)
            y += 30
        
        # 提示
        hint_text = self.font.render("Game will start when all players connect", True, GRAY)
        hint_rect = hint_text.get_rect(center=(self.screen.get_width() // 2, 350))
        self.screen.blit(hint_text, hint_rect)
        
        # 動畫點點點
        dots = "." * (int(time.time() * 2) % 4)
        loading_text = self.font.render(f"Loading{dots}", True, WHITE)
        loading_rect = loading_text.get_rect(center=(self.screen.get_width() // 2, 400))
        self.screen.blit(loading_text, loading_rect)
    
    def show_waiting_screen(self):
        """顯示等待結果的畫面"""
        wait_start = time.time()
        print("[Game] Entering waiting screen...")
        
        while time.time() - wait_start < 10:
            # 檢查是否收到遊戲結束訊息
            if self.game_end_data:
                print("[Game] Game end data received in waiting screen!")
                break
            
            # 處理事件（避免視窗無響應）
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("[Game] Window closed during waiting")
                    return
            
            # 繪製等待畫面
            self.screen.fill(BLACK)
            
            # 標題
            title = self.big_font.render("Game Exited", True, YELLOW)
            title_rect = title.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(title, title_rect)
            
            # 等待提示
            elapsed = int(time.time() - wait_start)
            remaining = 10 - elapsed
            wait_text = self.font.render(f"Waiting for game to end... ({remaining}s)", True, WHITE)
            wait_rect = wait_text.get_rect(center=(self.screen.get_width() // 2, 250))
            self.screen.blit(wait_text, wait_rect)
            
            hint_text = self.font.render("Results will be shown when game ends", True, GRAY)
            hint_rect = hint_text.get_rect(center=(self.screen.get_width() // 2, 300))
            self.screen.blit(hint_text, hint_rect)
            
            pygame.display.flip()
            self.clock.tick(10)  # 降低 CPU 使用率
        
        print(f"[Game] Exiting waiting screen. game_end_data = {self.game_end_data is not None}")
    
    def send_input(self, key):
        """發送輸入到伺服器"""
        if not self.conn:
            return
        try:
            # 使用 Server 期望的格式
            request = {
                "action": "input",
                "key": key
            }
            send_frame(self.conn, json.dumps(request).encode('utf-8'))
        except Exception:
            pass
    
    def run(self):
        """主遊戲循環"""
        print("[Game] Game started! Controls: <- -> v ^, Space=hard drop, ESC=quit")
        print("[Game] Win condition: First to clear 1 line OR opponent tops out")
        
        while self.running:
            self.clock.tick(FPS)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("[Game] Window closed by user")
                    self.running = False
                    # 通知伺服器玩家退出
                    try:
                        send_frame(self.conn, encode_message("PLAYER_QUIT"))
                    except:
                        pass
                    
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        print("[Game] ESC pressed - quitting game")
                        self.running = False
                        # 通知伺服器玩家退出
                        try:
                            send_frame(self.conn, encode_message("PLAYER_QUIT"))
                        except:
                            pass
                    elif event.key == pygame.K_LEFT:
                        self.send_input("LEFT")
                    elif event.key == pygame.K_RIGHT:
                        self.send_input("RIGHT")
                    elif event.key == pygame.K_DOWN:
                        self.send_input("DOWN")
                    elif event.key == pygame.K_UP:
                        self.send_input("ROTATE")
                    elif event.key == pygame.K_SPACE:
                        self.send_input("HARD_DROP")
            
            self.draw()
        
        # 如果玩家主動退出，等待遊戲結束訊息
        if not self.game_end_data:
            print("[Game] Waiting for game end message (max 10s)...")
            self.show_waiting_screen()
        
        # 遊戲循環結束，如果有遊戲結束數據，顯示結果
        if self.game_end_data:
            print("[Game] Showing game end screen")
            try:
                self.handle_game_end(self.game_end_data)
            except Exception as e:
                print(f"[Game] Cannot show end screen: {e}")
        else:
            print("[Game] No game end data received")
        
        # 最後才關閉 pygame
        pygame.quit()
        print("[Game] Returning to lobby")


class SpectatorMode:
    """觀戰模式"""
    
    def __init__(self, conn=None, player1=None, player2=None):
        self.conn = conn
        self.running = True
        self.waiting_for_end = False  # 等待遊戲結束的狀態
        self.game_end_data = None
        self.player1 = player1
        self.player2 = player2
        
        # 遊戲狀態
        self.player1_state = None
        self.player2_state = None
        
        # pygame 初始化
        try:
            pygame.init()
            self.screen = pygame.display.set_mode((COLS * CELL * 2 + 200, ROWS * CELL + 150))
            pygame.display.set_caption("Tetris Battle - Spectator Mode")
            self.clock = pygame.time.Clock()
            self.font = pygame.font.Font(None, 24)
            self.big_font = pygame.font.Font(None, 48)
        except pygame.error:
            print("[!] Cannot start pygame window, need graphical environment")
            sys.exit(1)
        
        # 啟動背景執行緒接收伺服器狀態
        if self.conn:
            threading.Thread(target=self.listen_server, daemon=True).start()
    
    def listen_server(self):
        """接收伺服器的遊戲狀態更新"""
        # 移除超時限制
        if self.conn:
            self.conn.settimeout(None)
        
        # 即使 running=False，也要繼續接收直到收到 GAME_END 或連線斷開
        while True:
            try:
                raw = recv_frame(self.conn)
                if not raw:
                    # 連線關閉
                    if self.running or self.waiting_for_end:
                        print("[Server] Connection closed unexpectedly")
                    break
                
                data = decode_message(raw)
                
                if not data:
                    continue
                
                if data.get("type") == "GAME_STATE":
                    # 只有在觀戰運行時才更新狀態
                    if self.running:
                        states = data.get("states", {})
                        
                        # 獲取兩位玩家的狀態
                        if self.player1 in states:
                            self.player1_state = states[self.player1]
                        if self.player2 in states:
                            self.player2_state = states[self.player2]
                
                elif data.get("type") == "GAME_END":
                    print("[Spectator] Received GAME_END message")
                    self.game_end_data = data
                    self.running = False  # 停止主循環
                    self.waiting_for_end = False  # 收到結束訊息，停止等待
                    # 發送 USEREVENT 喚醒主循環
                    try:
                        pygame.event.post(pygame.event.Event(pygame.USEREVENT))
                    except:
                        pass
                    break  # 收到 GAME_END 後立即退出
            
            except Exception as e:
                if self.running or self.waiting_for_end:
                    print(f"[Error] Receive error: {e}")
                break
        
        print("[Spectator] Listen server thread exiting")
    
    def handle_game_end(self, data):
        """處理遊戲結束"""
        winner = data.get("winner", "Unknown")
        results = data.get("results", [])
        
        print("\n" + "="*50)
        print(f"GAME OVER! Winner: {winner}")
        for result in results:
            player = result.get('player', 'Unknown')
            score = result.get('score', 0)
            lines = result.get('lines', 0)
            is_winner = result.get('is_winner', False)
            symbol = "[WIN]" if is_winner else "     "
            print(f"{symbol} {player}: {lines} lines {score} pts")
        print("="*50 + "\n")
        
        # 顯示結果畫面 10 秒
        countdown = 10
        start_time = time.time()
        
        while countdown > 0:
            # 先處理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("[Spectator] Window closed during results")
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        print("[Spectator] ESC pressed, returning to lobby")
                        return
            
            self.screen.fill(BLACK)
            
            # 標題
            title = self.big_font.render("GAME OVER!", True, YELLOW)
            title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
            self.screen.blit(title, title_rect)
            
            # 結果
            y = 150
            for result in results:
                player = result.get('player', 'Unknown')
                score = result.get('score', 0)
                lines = result.get('lines', 0)
                is_winner = result.get('is_winner', False)
                
                color = GREEN if is_winner else WHITE
                prefix = "[WINNER] " if is_winner else ""
                text = f"{prefix}{player}: {lines} lines {score} pts"
                rendered = self.font.render(text, True, color)
                text_rect = rendered.get_rect(center=(self.screen.get_width() // 2, y))
                self.screen.blit(rendered, text_rect)
                y += 40
            
            # 倒數提示
            instruction1 = self.font.render(f"Returning to lobby in {countdown} sec", True, YELLOW)
            instruction2 = self.font.render("Press ESC to return now", True, WHITE)
            inst1_rect = instruction1.get_rect(center=(self.screen.get_width() // 2, y + 50))
            inst2_rect = instruction2.get_rect(center=(self.screen.get_width() // 2, y + 80))
            self.screen.blit(instruction1, inst1_rect)
            self.screen.blit(instruction2, inst2_rect)
            
            pygame.display.flip()
            
            # 更新倒數
            elapsed = time.time() - start_time
            countdown = 10 - int(elapsed)
            time.sleep(0.1)
        
        print("[Spectator] Auto-returning to lobby")
    
    def draw_board(self, board, offset_x, offset_y):
        """繪製單個遊戲畫面"""
        if not board:
            return
        
        for r in range(ROWS):
            for c in range(COLS):
                if board[r][c]:
                    pygame.draw.rect(
                        self.screen, BLUE,
                        (offset_x + c * CELL, offset_y + r * CELL, CELL - 1, CELL - 1)
                    )
        
        # 邊框
        pygame.draw.rect(self.screen, GRAY, (offset_x, offset_y, COLS * CELL, ROWS * CELL), 2)
    
    def draw_falling(self, falling, offset_x, offset_y, color):
        """繪製下落中的方塊"""
        if not falling:
            return
        
        shape = falling.get('shape', [])
        x = falling.get('x', 0)
        y = falling.get('y', 0)
        
        for r, row in enumerate(shape):
            for c, val in enumerate(row):
                if val:
                    pygame.draw.rect(
                        self.screen, color,
                        (offset_x + (x + c) * CELL, offset_y + (y + r) * CELL, CELL - 1, CELL - 1)
                    )
    
    def draw(self):
        """繪製觀戰畫面"""
        self.screen.fill(BLACK)
        
        # 觀戰模式標題
        spectator_text = self.font.render("[ SPECTATOR MODE ]", True, ORANGE)
        spec_rect = spectator_text.get_rect(center=(self.screen.get_width() // 2, 10))
        self.screen.blit(spectator_text, spec_rect)
        
        # 顯示遊戲目標
        goal_text = self.font.render("First to clear 1 line wins!", True, YELLOW)
        goal_rect = goal_text.get_rect(center=(self.screen.get_width() // 2, 40))
        self.screen.blit(goal_text, goal_rect)
        
        # 左邊：玩家1
        if self.player1_state:
            name_text = self.font.render(f"{self.player1}", True, PURPLE)
            self.screen.blit(name_text, (10, 85))
            
            self.draw_board(self.player1_state.get('board', []), 10, 115)
            self.draw_falling(self.player1_state.get('falling'), 10, 115, PURPLE)
            
            score_text = self.font.render(f"Score: {self.player1_state.get('score', 0)}", True, WHITE)
            lines_text = self.font.render(f"Lines: {self.player1_state.get('lines', 0)}", True, WHITE)
            self.screen.blit(score_text, (10, ROWS * CELL + 125))
            self.screen.blit(lines_text, (10, ROWS * CELL + 145))
            
            if self.player1_state.get('game_over'):
                over_text = self.font.render("GAME OVER", True, RED)
                self.screen.blit(over_text, (30, 90))
        else:
            status_text = self.font.render("Waiting for player1...", True, YELLOW)
            self.screen.blit(status_text, (10, ROWS * CELL // 2))
        
        # 中間：VS 標示（置中於兩個棋盤之間）
        board_start_y = 115
        board_height = ROWS * CELL
        vs_y = board_start_y + board_height // 2
        vs_text = self.big_font.render("VS", True, WHITE)
        vs_rect = vs_text.get_rect(center=(self.screen.get_width() // 2, vs_y))
        self.screen.blit(vs_text, vs_rect)
        
        # 右邊：玩家2
        if self.player2_state:
            offset_x = COLS * CELL + 50
            
            name_text = self.font.render(f"{self.player2}", True, ORANGE)
            self.screen.blit(name_text, (offset_x, 85))
            
            self.draw_board(self.player2_state.get('board', []), offset_x, 115)
            self.draw_falling(self.player2_state.get('falling'), offset_x, 115, ORANGE)
            
            score_text = self.font.render(f"Score: {self.player2_state.get('score', 0)}", True, WHITE)
            lines_text = self.font.render(f"Lines: {self.player2_state.get('lines', 0)}", True, WHITE)
            self.screen.blit(score_text, (offset_x, ROWS * CELL + 125))
            self.screen.blit(lines_text, (offset_x, ROWS * CELL + 145))
            
            if self.player2_state.get('game_over'):
                over_text = self.font.render("GAME OVER", True, RED)
                self.screen.blit(over_text, (offset_x + 30, 90))
        else:
            offset_x = COLS * CELL + 50
            status_text = self.font.render("Waiting for player2...", True, YELLOW)
            self.screen.blit(status_text, (offset_x, ROWS * CELL // 2))
        
        pygame.display.flip()
    
    def show_waiting_screen(self):
        """顯示等待結果的畫面"""
        wait_start = time.time()
        
        while time.time() - wait_start < 10:
            # 檢查是否收到遊戲結束訊息
            if self.game_end_data:
                break
            
            # 處理事件（避免視窗無響應）
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
            
            # 繪製等待畫面
            self.screen.fill(BLACK)
            
            # 標題
            title = self.big_font.render("Spectator Exited", True, ORANGE)
            title_rect = title.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(title, title_rect)
            
            # 等待提示
            elapsed = int(time.time() - wait_start)
            remaining = 10 - elapsed
            wait_text = self.font.render(f"Waiting for game to end... ({remaining}s)", True, WHITE)
            wait_rect = wait_text.get_rect(center=(self.screen.get_width() // 2, 250))
            self.screen.blit(wait_text, wait_rect)
            
            hint_text = self.font.render("Results will be shown when game ends", True, GRAY)
            hint_rect = hint_text.get_rect(center=(self.screen.get_width() // 2, 300))
            self.screen.blit(hint_text, hint_rect)
            
            pygame.display.flip()
            self.clock.tick(10)  # 降低 CPU 使用率
    
    def run(self):
        """主觀戰循環"""
        print(f"[Spectator] Watching: {self.player1} vs {self.player2}")
        print("[Spectator] Win condition: First to clear 1 line OR opponent tops out")
        print("[Spectator] Press ESC or close window to exit spectator mode")
        
        while self.running:
            self.clock.tick(FPS)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("[Spectator] Window closed by user")
                    self.running = False
                    # 通知伺服器觀戰者退出（不影響遊戲）
                    try:
                        send_frame(self.conn, encode_message("SPECTATOR_QUIT"))
                    except:
                        pass
                    
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        print("[Spectator] ESC pressed - exiting spectator mode")
                        self.running = False
                        # 通知伺服器觀戰者退出（不影響遊戲）
                        try:
                            send_frame(self.conn, encode_message("SPECTATOR_QUIT"))
                        except:
                            pass
            
            self.draw()
        
        # 如果觀戰者主動退出，等待遊戲結束訊息
        if not self.game_end_data:
            print("[Spectator] Waiting for game end message (max 10s)...")
            self.show_waiting_screen()
        
        # 遊戲循環結束，如果有遊戲結束數據，顯示結果
        if self.game_end_data:
            print("[Spectator] Showing game end screen")
            try:
                self.handle_game_end(self.game_end_data)
            except Exception as e:
                print(f"[Spectator] Cannot show end screen: {e}")
        else:
            print("[Spectator] No game end data received")
        
        # 最後才關閉 pygame
        pygame.quit()
        print("[Spectator] Exiting spectator mode, returning to lobby")

# ============================================================
# 主程式入口點
# ============================================================

def main():
    """主程式入口"""
    if len(sys.argv) < 3:
        print("Usage: python3 game.py <host> <port>")
        print("Example: python3 game.py localhost 12345")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2])
    
    # 連接到遊戲伺服器
    try:
        print(f"[Client] Connecting to Game Server at {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"[Client] Connected successfully!")
        
        # 發送加入請求
        username = "Player"
        join_request = {
            "action": "join",
            "player_name": username
        }
        send_frame(sock, json.dumps(join_request).encode('utf-8'))
        
        # 接收回應
        response_raw = recv_frame(sock)
        if not response_raw:
            print("[Client] No response from server")
            sys.exit(1)
        
        response = json.loads(response_raw.decode('utf-8'))
        print(f"[Client] Server response: {response}")
        
        if response.get("status") != "success":
            print(f"[Client] Failed to join: {response.get('message')}")
            sys.exit(1)
        
        # 使用 Server 分配的玩家名稱
        assigned_name = response.get("player_name", username)
        print(f"[Client] Successfully joined game as: {assigned_name}")
        
        # 啟動遊戲
        game = TetrisGame(conn=sock, username=assigned_name)
        game.run()
        
        # 關閉連線
        sock.close()
        print("[Client] Game ended, connection closed")
        
    except ConnectionRefusedError:
        print(f"[Client] ❌ Cannot connect to {host}:{port}")
        print("[Client] Please make sure the Game Server is running")
        sys.exit(1)
    except Exception as e:
        print(f"[Client] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()