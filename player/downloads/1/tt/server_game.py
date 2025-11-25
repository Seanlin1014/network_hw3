# server_game.py - 伺服器端遊戲邏輯
import random
import time

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
        self.drop_interval = 0.5  # 自動下落間隔
        
        # 輸入頻率限制
        self.last_input_time = 0
        self.input_cooldown = 0.05  # 50ms 冷卻時間
        
        # 使用固定種子生成方塊序列
        self.rng = random.Random(seed)
        self.falling = self.new_block()
    
    def new_block(self):
        """產生新方塊"""
        shape = self.rng.choice(list(TETROMINOS.values()))
        return {'shape': shape, 'x': 3, 'y': 0}
    
    def collide(self, block):
        """檢查碰撞"""
        shape = block['shape']
        for r, row in enumerate(shape):
            for c, val in enumerate(row):
                if val:
                    x = block['x'] + c
                    y = block['y'] + r
                    if x < 0 or x >= COLS or y >= ROWS or (y >= 0 and self.board[y][x]):
                        return True
        return False
    
    def merge(self, block):
        """合併方塊到場上"""
        for r, row in enumerate(block['shape']):
            for c, val in enumerate(row):
                if val:
                    x = block['x'] + c
                    y = block['y'] + r
                    if 0 <= y < ROWS and 0 <= x < COLS:
                        self.board[y][x] = 1
    
    def clear_lines(self):
        """清除滿行並計分"""
        new_board = []
        lines = 0
        for row in self.board:
            if any(v == 0 for v in row):
                new_board.append(row)
            else:
                lines += 1
        
        while len(new_board) < ROWS:
            new_board.insert(0, [0] * COLS)
        
        self.board = new_board
        self.lines_cleared += lines
        
        # 計分：1行=100, 2行=300, 3行=500, 4行=800
        if lines == 1:
            self.score += 100
        elif lines == 2:
            self.score += 300
        elif lines == 3:
            self.score += 500
        elif lines == 4:
            self.score += 800
        
        return lines
    
    def rotate(self):
        """旋轉方塊"""
        shape = self.falling['shape']
        new_shape = [list(row) for row in zip(*shape[::-1])]
        old = self.falling['shape']
        self.falling['shape'] = new_shape
        if self.collide(self.falling):
            self.falling['shape'] = old
            return False
        return True
    
    def move_left(self):
        """向左移動"""
        self.falling['x'] -= 1
        if self.collide(self.falling):
            self.falling['x'] += 1
            return False
        return True
    
    def move_right(self):
        """向右移動"""
        self.falling['x'] += 1
        if self.collide(self.falling):
            self.falling['x'] -= 1
            return False
        return True
    
    def soft_drop(self):
        """軟降（手動下降一格）"""
        self.falling['y'] += 1
        if self.collide(self.falling):
            self.falling['y'] -= 1
            self.lock_piece()
            return False
        self.score += 1  # 軟降加1分
        return True
    
    def hard_drop(self):
        """硬降（直接降到底）"""
        drop_distance = 0
        while not self.collide(self.falling):
            self.falling['y'] += 1
            drop_distance += 1
        self.falling['y'] -= 1
        self.score += drop_distance * 2  # 硬降加2倍分數
        self.lock_piece()
    
    def lock_piece(self):
        """鎖定方塊並產生新方塊"""
        self.merge(self.falling)
        lines = self.clear_lines()
        self.falling = self.new_block()
        
        if self.collide(self.falling):
            self.game_over = True
        
        return lines
    
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
        """處理玩家輸入，帶頻率限制"""
        if self.game_over:
            return False
        
        # 檢查輸入頻率
        now = time.time()
        if now - self.last_input_time < self.input_cooldown:
            return False  # 忽略過快的輸入
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
        """獲取當前遊戲狀態"""
        return {
            'board': self.board,
            'falling': self.falling,
            'score': self.score,
            'lines': self.lines_cleared,
            'game_over': self.game_over
        }