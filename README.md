git hub連結:
```bash
https://github.com/Seanlin1014/network_hw3
```
### 需要安裝pygame

## 一、Server 端啟動

### 1️. 啟動 DB Server

```bash
cd server
```

```bash
python3 db_server_extended.py
```

或自行指定 port（>10000）：

```bash
python3 db_server_extended.py 12001
```

畫面會顯示：

```
IMPORTANT: DB Server Port = <DB_PORT>
```

記下 `<DB_PORT>`

---

### 2️. 啟動 Game Store Server

```bash
python3 game_store_server.py <DB_PORT>
```

畫面會顯示：

```
Developer Server Port: <DEV_PORT>
Lobby Server Port: <LOBBY_PORT>
```

記下 `<DEV_PORT>`、`<LOBBY_PORT>`

---

## 二、Developer Client 啟動

### 1️. 啟動

```bash
cd developer
```

```bash
python3 developer_client.py <HOST> <DEV_PORT>
```

```bash
host: linux1.cs.nycu.edu.tw
host: linux2.cs.nycu.edu.tw
host: linux3.cs.nycu.edu.tw
host: linux4.cs.nycu.edu.tw
```
---

### 2️. 上架新遊戲

#### Step 1：遊戲名稱
- 任意文字
- 不可空白  
範例：`tetris`

---

#### Step 2：遊戲類型（輸入數字）
- `1` CLI
- `2` GUI
- `3` Multiplayer

---

#### Step 3：遊戲簡介
- 任意文字即可  

---

#### Step 4：最大玩家數
- 直接 Enter → 預設 2  
- 或輸入數字（例如 `4`）

---

#### Step 5：版本號（**格式固定**）

必須是：

```
x.x.x
```

正確：
```
1.0.0
```

錯誤：
```
1
v1.0
1.0
```

---

#### Step 6：遊戲資料夾路徑

輸入「資料夾路徑」，不是檔案：

正確：
```
~/network_hw3/developer/games/tetris_game
```

錯誤：
```
~/network_hw3/developer/games/tetris_game/game.py
```

---

#### Step 7：啟動命令（**一定要包含 {host} {port}**）

正確範例：
```
python3 game.py {host} {port}
```

錯誤：
```
python3 game.py
python3 game.py localhost 12345
```

`{host}` `{port}` 一定要原樣輸入（含大括號）

---

#### Step 8：Server 指令（選填）
- 沒有 server → 直接 Enter
- 有 server → 例如：
```
python3 server_game.py {port}
```

---

#### Step 9：編譯指令（選填）
- C/C++ 才需要  
- 例如：
```
make
```
- 沒有就 Enter

---

### 3️. 更新遊戲版本

1. 選擇「更新遊戲」
2. 輸入遊戲編號
3. 輸入「新的」遊戲資料夾路徑
4. 確認送出

更新後：
- 舊版本會被覆蓋
- 玩家重新下載才會拿到新版本

---

### 4️. 下架遊戲

1. 選擇「下架遊戲」
2. 輸入遊戲編號
3. 輸入 `yes` 確認

---

## 三、Player Client

### 啟動

```bash
cd player
```

```bash
python3 lobby_client.py <HOST> <LOBBY_PORT>
```

```bash
host: linux1.cs.nycu.edu.tw
host: linux2.cs.nycu.edu.tw
host: linux3.cs.nycu.edu.tw
host: linux4.cs.nycu.edu.tw
```
---

### 操作方式
- 全部為數字選單
- 可瀏覽遊戲、下載、建立房間、啟動遊戲

---

### 遊戲畫面
- CLI：在 terminal 內執行
- GUI：跳出視窗，關閉後回到 Lobby

---

## 四、流程

1. 啟動 DB Server  
2. 啟動 Game Store Server  
3. Developer 上架遊戲  
4. Player 下載並遊玩  
