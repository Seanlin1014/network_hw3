# Game Template - 遊戲範本

## 說明

此範本提供一個標準的遊戲專案結構，讓開發者可以快速建立符合平台規格的遊戲。

## 遊戲規格要求

### 1. 檔案結構
```
game_name/
├── README.md           # 遊戲說明（必要）
├── game_client.py      # 遊戲 Client（必要）
├── game_server.py      # 遊戲 Server（選用，多人遊戲需要）
└── config.json         # 配置檔（選用）
```

### 2. README.md 必要內容
```markdown
# 遊戲名稱

## 遊戲類型
- CLI / GUI / Multiplayer

## 玩家數
- 最小玩家數
- 最大玩家數

## 遊戲說明
簡短描述遊戲玩法

## 操作方式
說明控制方式

## 系統需求
列出必要的套件或編譯工具
```

### 3. config.json 格式（選用）
```json
{
  "start_command": "python3 game_client.py",
  "server_command": "python3 game_server.py",
  "compile": "make",
  "max_players": 2,
  "min_players": 2
}
```

### 4. 遊戲類型

#### CLI 遊戲
- 命令列介面
- 文字輸出
- 鍵盤輸入

#### GUI 遊戲
- 圖形介面（pygame, tkinter 等）
- 視窗顯示
- 滑鼠/鍵盤輸入

#### 多人遊戲
- 支援 2 人以上
- 網路連線
- 同步機制

## 開發流程

### 1. 建立新遊戲專案
```bash
# 複製範本
cp -r template/ games/my_new_game/
cd games/my_new_game/

# 修改遊戲名稱和內容
# 編輯 README.md
# 編輯 game_client.py
# 編輯 game_server.py（如果需要）
```

### 2. 本地測試
```bash
# 測試遊戲 Client
python3 game_client.py

# 測試遊戲 Server（如果有）
python3 game_server.py
```

### 3. 上架到平台
```bash
# 啟動 Developer Client
python3 developer_client.py

# 在選單中選擇「上架新遊戲」
# 選擇 games/my_new_game/
# 填寫必要資訊
# 確認上架
```

## 範例遊戲

### Tetris Battle（GUI 雙人對戰）
位於 `games/tetris_game/`
- 類型: GUI
- 玩家數: 2
- 技術: Python + pygame

### Tic-Tac-Toe Online（CLI 雙人對戰）
位於 `games/tictactoe_game/`
- 類型: CLI
- 玩家數: 2
- 技術: C++

## 注意事項

1. **遊戲檔案完整性**
   - 確保所有必要檔案都在遊戲目錄內
   - 不要依賴絕對路徑

2. **相依套件**
   - 在 README.md 中明確列出
   - 使用常見、容易安裝的套件

3. **啟動方式**
   - 提供清楚的啟動命令
   - 可以寫在 config.json 或 README.md

4. **測試充分**
   - 本地測試遊戲流程完整
   - 確認可以正常開始和結束
   - 測試錯誤處理

## 進階功能（選用）

### 遊戲狀態保存
```python
import json

def save_game_state(state, filename="savegame.json"):
    with open(filename, 'w') as f:
        json.dump(state, f)

def load_game_state(filename="savegame.json"):
    with open(filename, 'r') as f:
        return json.load(f)
```

### 網路連線（多人遊戲）
```python
import socket

# Game Client
def connect_to_server(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock

# Game Server
def start_server(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', port))
    sock.listen(5)
    return sock
```

### 遊戲計分
```python
class ScoreManager:
    def __init__(self):
        self.scores = {}
    
    def add_score(self, player, points):
        if player not in self.scores:
            self.scores[player] = 0
        self.scores[player] += points
    
    def get_winner(self):
        return max(self.scores.items(), key=lambda x: x[1])
```

## 疑難排解

### Q: 上架時提示檔案讀取失敗
確認遊戲目錄結構正確，所有檔案都存在。

### Q: 玩家下載後無法啟動
檢查 config.json 中的 start_command 是否正確。

### Q: 多人遊戲連線失敗
確認遊戲 Server 正確啟動，Port 沒有被佔用。
