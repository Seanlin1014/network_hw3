# Developer 端 - 遊戲開發環境

## 說明

此目錄為遊戲開發者的工作環境，用於開發、測試和上架遊戲。

## 目錄結構

```
developer/
├── developer_client.py    # Developer Client（上架/更新/下架）
├── lpfp.py                # 通訊協定
├── games/                 # 開發中的遊戲（本地測試用）
│   ├── tetris_game/       # Tetris Battle（GUI）
│   └── tictactoe_game/    # Tic-Tac-Toe（CLI）
└── template/              # 遊戲範本與開發指南
    └── README.md
```

## 快速開始

### 1. 啟動 Developer Client

```bash
python3 developer_client.py
```

如果 Server 端的 port 檔案（`.dev_port`）不在當前目錄，需要手動指定：

```bash
python3 developer_client.py <server_host> <dev_port>
```

### 2. 註冊/登入開發者帳號

首次使用需要註冊開發者帳號：
1. 啟動 Developer Client
2. 選擇「2. 註冊 (Register)」
3. 輸入帳號名稱和密碼
4. 註冊成功後，選擇「1. 登入 (Login)」

### 3. 開發遊戲

#### 使用範本建立新遊戲
```bash
# 複製範本
cp -r template/ games/my_new_game/

# 開發你的遊戲
cd games/my_new_game/
# 編輯 game_client.py, game_server.py, README.md
```

#### 參考範例遊戲
- `games/tetris_game/` - GUI 雙人對戰遊戲（Python + pygame）
- `games/tictactoe_game/` - CLI 雙人對戰遊戲（C++）

### 4. 本地測試

在上架前，先在本地測試遊戲：

```bash
cd games/my_new_game/

# 測試遊戲 Client
python3 game_client.py

# 如果有 Server，先啟動 Server
python3 game_server.py
```

### 5. 上架遊戲

遊戲開發完成後，透過 Developer Client 上架：

1. 啟動 Developer Client 並登入
2. 選擇「2. 上架新遊戲」
3. 依照提示輸入資訊：
   - 遊戲名稱
   - 遊戲類型（CLI / GUI / Multiplayer）
   - 遊戲簡介
   - 最大玩家數
   - 版本號（預設 1.0.0）
   - 遊戲檔案目錄路徑（例如：`./games/my_new_game`）
   - 啟動命令（例如：`python3 game_client.py`）
   - Server 命令（如果有）
4. 確認上架

## Developer Client 功能

### 主選單
```
📋 選單:
1. 查看我的遊戲
2. 上架新遊戲
3. 更新遊戲
4. 下架遊戲
5. 登出
```

### 1. 查看我的遊戲
列出你已上架的所有遊戲：
- 遊戲名稱
- 版本號
- 狀態（active / inactive）
- 下載次數
- 平均評分

### 2. 上架新遊戲
將本地開發完成的遊戲上架到平台：
- 自動打包遊戲目錄成 ZIP
- Base64 編碼傳輸
- Server 端自動解壓

### 3. 更新遊戲
更新已上架遊戲的新版本：
- 保留舊版本檔案
- 新版本成為預設下載版本
- 玩家可選擇更新

### 4. 下架遊戲
將遊戲從商城移除：
- 軟刪除（檔案保留，狀態改為 inactive）
- 玩家無法再下載或建立新房間
- 已下載的玩家仍可遊玩

## 遊戲開發規範

### 必要檔案
每個遊戲專案至少需要：
1. `README.md` - 遊戲說明
2. `game_client.py` 或同等的遊戲啟動檔案
3. （選用）`config.json` - 配置檔

### README.md 必要內容
```markdown
# 遊戲名稱

## 遊戲類型
CLI / GUI / Multiplayer

## 玩家數
最小-最大玩家數

## 遊戲說明
簡短描述

## 操作方式
控制說明

## 系統需求
必要套件
```

### config.json 格式
```json
{
  "start_command": "python3 game_client.py",
  "server_command": "python3 game_server.py",
  "compile": "make",
  "max_players": 2
}
```

## 開發技巧

### 1. 使用版本控制
```bash
git init
git add .
git commit -m "Initial game version"
```

### 2. 測試多人連線
```bash
# 終端機 1: 啟動 Server
python3 game_server.py

# 終端機 2: 玩家 A
python3 game_client.py

# 終端機 3: 玩家 B
python3 game_client.py
```

### 3. 除錯技巧
```python
# 加入日誌
import logging
logging.basicConfig(level=logging.DEBUG)
logging.debug("Game state: %s", game_state)

# 錯誤處理
try:
    # 遊戲邏輯
except Exception as e:
    logging.error("Error: %s", e)
```

## 疑難排解

### Q: 上架時提示「無法讀取遊戲目錄」
- 確認路徑正確，使用相對路徑（例如 `./games/my_game`）
- 確認目錄內有必要檔案

### Q: 玩家反應遊戲無法啟動
- 檢查 start_command 是否正確
- 確認遊戲在 Linux 環境可以執行
- 檢查是否有缺少的相依套件

### Q: 更新遊戲後玩家看不到新版本
- 玩家需要重新下載遊戲
- 或在遊戲列表中選擇「更新」

### Q: Developer Client 無法連線
- 確認 Server 端已啟動
- 檢查 `.dev_port` 檔案是否存在
- 確認防火牆設定

## 最佳實踐

1. **充分測試**
   - 完整測試遊戲流程
   - 測試多種輸入情況
   - 測試錯誤處理

2. **清楚的文件**
   - README.md 寫清楚
   - 註解重要邏輯
   - 說明已知問題

3. **版本管理**
   - 使用語意化版本號（1.0.0, 1.1.0, 2.0.0）
   - 在更新說明中寫明變更內容
   - 保留重要版本的備份

4. **使用者體驗**
   - 提供清楚的操作提示
   - 錯誤訊息要明確
   - 遊戲結束要有明確提示

5. **效能最佳化**
   - 避免無限迴圈
   - 適當的延遲（避免 CPU 100%）
   - 及時釋放資源

## 進階主題

### 遊戲存檔
```python
import json

def save_game(state, player_name):
    with open(f"saves/{player_name}.json", "w") as f:
        json.dump(state, f)

def load_game(player_name):
    with open(f"saves/{player_name}.json", "r") as f:
        return json.load(f)
```

### 網路同步
```python
import threading

def sync_game_state(sock, state):
    threading.Thread(
        target=send_state,
        args=(sock, state),
        daemon=True
    ).start()
```

### 排行榜
```python
def update_leaderboard(player, score):
    leaderboard = load_leaderboard()
    leaderboard[player] = max(
        leaderboard.get(player, 0),
        score
    )
    save_leaderboard(leaderboard)
```

## 更多資源

- 範例遊戲原始碼：`games/` 目錄
- 遊戲範本：`template/` 目錄
- Server API 文件：`../server/README.md`
- 玩家端功能：`../player/README.md`
