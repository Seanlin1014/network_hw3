# Player 端 - 玩家遊玩環境

## 說明

此目錄為玩家的遊玩環境，透過 Lobby Client 瀏覽遊戲、下載遊戲、建立房間並遊玩。

## 目錄結構

```
player/
├── lobby_client.py        # Lobby Client（大廳/商城）
├── lpfp.py               # 通訊協定
└── downloads/            # 玩家下載的遊戲
    ├── Player1/          # 玩家 1 的遊戲
    ├── Player2/          # 玩家 2 的遊戲
    └── Player3/          # 玩家 3 的遊戲
```

## 快速開始

### 1. 啟動 Lobby Client

```bash
python3 lobby_client.py
```

如果 Server 端的 port 檔案不在當前目錄，需要手動指定：

```bash
python3 lobby_client.py <server_host> <lobby_port> <db_port>
```

### 2. 註冊/登入玩家帳號

首次使用需要註冊玩家帳號：
1. 啟動 Lobby Client
2. 選擇「2. 註冊 (Register)」
3. 輸入帳號名稱和密碼
4. 註冊成功後，選擇「1. 登入 (Login)」

### 3. 遊玩流程

完整流程：**瀏覽 → 下載 → 建立房間 → 啟動遊戲**

#### Step 1: 瀏覽遊戲商城
```
選擇: 1. 瀏覽遊戲商城
→ 查看所有可用遊戲
→ 選擇: 2. 查看遊戲詳情
→ 輸入遊戲名稱查看詳細資訊
```

#### Step 2: 下載遊戲
```
選擇: 3. 下載/更新遊戲
→ 輸入遊戲名稱
→ 系統自動下載並解壓到 downloads/<你的帳號>/
```

#### Step 3: 建立房間
```
選擇: 7. 建立房間
→ 輸入遊戲名稱
→ 記下房間 ID（例如 ROOM_0001）
→ 等待其他玩家加入
```

#### Step 4: 其他玩家加入房間
```
（在另一個終端機，啟動另一個 Lobby Client）
選擇: 8. 加入房間
→ 輸入房間 ID
→ 等待房主啟動遊戲
```

#### Step 5: 啟動遊戲
```
（房主）
選擇: 9. 離開房間
→ 選擇: 1. 啟動遊戲
→ 選擇: yes (自動啟動)
→ 遊戲視窗自動開啟！
```

## Lobby Client 功能

### 主選單（已登入）
```
📋 選單:
1. 瀏覽遊戲商城
2. 查看遊戲詳情
3. 下載/更新遊戲
4. 我的遊戲
5. ---房間功能---
6. 查看所有房間
7. 建立房間
8. 加入房間
9. 離開房間
10. 登出
```

### 1. 瀏覽遊戲商城
查看所有可用遊戲：
- 遊戲名稱和版本
- 開發者
- 遊戲類型（CLI / GUI / Multiplayer）
- 最多玩家數
- 平均評分
- 下載次數
- 簡介

### 2. 查看遊戲詳情
查看特定遊戲的詳細資訊：
- 完整遊戲資訊
- 最新 5 則玩家評論
- 評分分布

### 3. 下載/更新遊戲
下載遊戲到本地：
- 自動下載最新版本
- 自動解壓縮
- 儲存版本資訊（`.version`）
- 儲存配置檔（`.config.json`）

下載位置：`downloads/<你的帳號>/<遊戲名稱>/`

### 4. 我的遊戲
查看已下載的遊戲：
- 遊戲名稱
- 本地版本號
- 儲存位置

### 6. 查看所有房間
查看當前所有房間：
- 房間 ID
- 遊戲名稱
- 房主
- 當前玩家數 / 最大玩家數
- 房間狀態（waiting / playing）

### 7. 建立房間
建立新的遊戲房間：
- 選擇遊戲
- 系統檢查是否已下載
- 建立成功後顯示房間 ID
- 等待其他玩家加入

### 8. 加入房間
加入現有房間：
- 輸入房間 ID
- 系統檢查房間狀態
- 加入成功後等待房主啟動

### 9. 離開房間 / 啟動遊戲
房間操作：
- **一般玩家**: 離開房間
- **房主**: 啟動遊戲或解散房間

## 遊戲下載機制

### 下載流程
1. 選擇要下載的遊戲
2. 系統檢查本地是否已有該遊戲
   - 沒有 → 執行首次下載
   - 有 → 比對版本，提示是否更新
3. Server 回傳 Base64 編碼的 ZIP 檔案
4. Client 自動解碼並解壓縮
5. 儲存版本資訊和配置檔

### 下載位置
```
downloads/
└── <玩家帳號>/
    ├── <遊戲 1>/
    │   ├── .version          # 版本資訊
    │   ├── .config.json      # 配置檔
    │   ├── game_client.py    # 遊戲檔案
    │   └── ...
    └── <遊戲 2>/
        └── ...
```

### 版本管理
- `.version` 檔案記錄當前版本號
- 下載前檢查是否有新版本
- 可以手動觸發更新

## 房間系統

### 房間狀態
- **waiting**: 等待玩家加入
- **playing**: 遊戲進行中
- **finished**: 遊戲結束

### 房主權限
- 啟動遊戲
- 解散房間（離開房間時自動解散）

### 一般玩家
- 加入房間
- 離開房間
- 等待房主啟動

### 遊戲啟動
當房主啟動遊戲時：
1. Server 回傳遊戲配置（啟動命令、玩家列表等）
2. Client 讀取配置檔（`.config.json`）
3. 在遊戲目錄下執行啟動命令
4. 遊戲自動開啟

## 多人 Demo 設定

在同一台電腦上模擬多位玩家：

### 方法 1: 多個終端機
```bash
# 終端機 1 - 玩家 A
python3 lobby_client.py
# 註冊帳號: PlayerA
# 建立房間

# 終端機 2 - 玩家 B
python3 lobby_client.py
# 註冊帳號: PlayerB
# 加入房間

# 終端機 3 - 玩家 C（如果支援多人）
python3 lobby_client.py
# 註冊帳號: PlayerC
# 加入房間
```

### 方法 2: 不同目錄
```bash
# 目錄 1
cd ~/player1
python3 lobby_client.py

# 目錄 2
cd ~/player2
python3 lobby_client.py
```

## 支援的遊戲

### Tetris Battle（GUI）
- **類型**: GUI
- **玩家數**: 2 人
- **系統需求**: `pip install pygame`
- **啟動**: 自動啟動視窗

### Tic-Tac-Toe Online（CLI）
- **類型**: CLI
- **玩家數**: 2 人
- **系統需求**: g++ 編譯器
- **編譯**: 下載後執行 `make`
- **啟動**: 
  ```bash
  # 先啟動 Lobby Server
  ./lobby_server 15555 &
  
  # 玩家 A
  ./playerA 127.0.0.1 15555
  
  # 玩家 B
  ./playerB 127.0.0.1 15555
  ```

## 疑難排解

### Q: Lobby Client 無法連線
```bash
# 確認 Server 已啟動
cd ../server
./start_game_store.sh

# 檢查 port 檔案
ls -la .lobby_port .db_port

# 如果檔案不存在，需要手動指定 port
python3 lobby_client.py <host> <lobby_port> <db_port>
```

### Q: 遊戲下載失敗
- 確認網路連線正常
- 檢查磁碟空間
- 查看錯誤訊息
- 重新嘗試下載

### Q: 遊戲無法啟動
```bash
# 確認遊戲已下載
ls downloads/<你的帳號>/

# 確認遊戲檔案完整
cd downloads/<你的帳號>/<遊戲名稱>/
ls -la

# 手動測試啟動
python3 game_client.py  # 或其他啟動命令
```

### Q: pygame 遊戲無法顯示
```bash
# 安裝 pygame
pip install pygame

# 確認有圖形環境
echo $DISPLAY

# 如果在 SSH，需要 X forwarding
ssh -X user@host
```

### Q: C++ 遊戲無法編譯
```bash
# 安裝編譯工具
sudo apt-get install g++ make

# 手動編譯
cd downloads/<你的帳號>/<遊戲名稱>/
make
```

### Q: 房間無法加入
- 確認房間 ID 正確
- 檢查房間是否已滿
- 確認遊戲已下載
- 查看房間狀態（可能已開始遊戲）

### Q: 無法看到其他玩家
- 確認在同一個房間
- 檢查網路連線
- 重新整理房間列表

## 訪客模式

如果只想瀏覽遊戲，無需註冊：
1. 啟動 Lobby Client
2. 選擇「3. 訪客模式 (Guest - 瀏覽遊戲)」
3. 可以瀏覽遊戲列表和詳情
4. 但無法下載、建立房間或評分

## 最佳實踐

1. **定期更新遊戲**
   - 檢查是否有新版本
   - 在遊玩前更新到最新版

2. **管理下載空間**
   - 定期清理不玩的遊戲
   - 備份遊戲存檔（如果有）

3. **網路環境**
   - 使用穩定的網路連線
   - 避免高延遲環境

4. **多人遊戲**
   - 提前和朋友約定時間
   - 確保所有玩家都有下載遊戲
   - 測試連線是否正常

5. **評分與回饋**
   - 遊玩後給予真實評分
   - 提供建設性的評論
   - 幫助開發者改進遊戲

## 進階功能

### 自訂啟動腳本
如果遊戲啟動流程複雜，可以建立啟動腳本：

```bash
#!/bin/bash
# start_game.sh

cd downloads/$USER/MyGame/
export GAME_CONFIG=config.json
python3 game_client.py --fullscreen
```

### 遊戲快捷方式
```bash
# 建立 alias
echo "alias play-tetris='cd ~/player/downloads/$USER/Tetris\ Battle && python3 game.py'" >> ~/.bashrc
source ~/.bashrc

# 使用
play-tetris
```

## 更多資源

- Server 端文件：`../server/README.md`
- Developer 端文件：`../developer/README.md`
- 遊戲開發範本：`../developer/template/`
