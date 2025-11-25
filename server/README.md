# Server 端 - Game Store Server

## 說明

此目錄包含部署在系計 Linux 機器上的所有 Server 端程式。

## 檔案說明

- `db_server_extended.py` - 資料庫 Server（管理 Developer 和 Player 帳號）
- `game_store_server.py` - 遊戲商店 Server
  - Developer Server: 處理遊戲上架/更新/下架
  - Lobby Server: 處理玩家大廳、房間、下載
- `lpfp.py` - 通訊協定（Length-Prefixed Framing Protocol）
- `start_game_store.sh` - 啟動腳本
- `stop_game_store.sh` - 停止腳本

## 部署步驟

### 1. 環境需求
- Python 3.7+
- Linux 環境

### 2. 啟動 Server
```bash
chmod +x start_game_store.sh stop_game_store.sh
./start_game_store.sh
```

Server 會自動啟動三個服務：
- DB Server（動態 Port，儲存在 `.db_port`）
- Developer Server（動態 Port，儲存在 `.dev_port`）
- Lobby Server（動態 Port，儲存在 `.lobby_port`）

### 3. 停止 Server
```bash
./stop_game_store.sh
```

### 4. 查看日誌
```bash
tail -f logs/db_server.log
tail -f logs/game_store.log
```

## 資料儲存

### 資料目錄
- `db_data/` - 帳號資料
  - `developers.json` - Developer 帳號
  - `players.json` - Player 帳號
- `game_store_data/` - 遊戲商店資料
  - `games_metadata.json` - 遊戲 metadata
  - `reviews.json` - 玩家評論
- `uploaded_games/` - 上架的遊戲檔案
  - `<game_name>/<version>/` - 各版本遊戲檔案

### 資料持久化
- 所有資料以 JSON 格式儲存
- 使用原子性寫入（temp file + rename）
- Server 重啟後資料不會遺失

## API 端點

### DB Server
- `create` - 建立帳號
- `query` - 查詢帳號（登入驗證）

### Developer Server
- `login` - 開發者登入
- `upload_game` - 上架遊戲
- `update_game` - 更新遊戲
- `remove_game` - 下架遊戲
- `list_my_games` - 查看我的遊戲

### Lobby Server
- `list_games` - 列出所有遊戲
- `get_game_info` - 取得遊戲詳情
- `download_game` - 下載遊戲
- `submit_review` - 提交評論
- `create_room` - 建立房間
- `join_room` - 加入房間
- `leave_room` - 離開房間
- `start_game` - 啟動遊戲
- `list_rooms` - 列出所有房間

## 設定說明

### Port 設定
Server 使用動態 Port（避免衝突），啟動後會將 Port 儲存在隱藏檔案：
- `.db_port` - DB Server Port
- `.dev_port` - Developer Server Port
- `.lobby_port` - Lobby Server Port

Client 端會自動讀取這些檔案來連線。

### 清空測試資料
```bash
# 清空所有資料
rm -rf db_data game_store_data uploaded_games logs .*.pid .*.port

# 重新啟動
./start_game_store.sh
```

## 疑難排解

### Q: Server 啟動失敗
```bash
# 檢查是否有舊 Server 還在執行
ps aux | grep python3 | grep server

# 停止所有 Server
./stop_game_store.sh

# 重新啟動
./start_game_store.sh
```

### Q: Port 衝突
Server 使用動態 Port（port 0），由 OS 自動分配，不應該有衝突。

### Q: 資料損毀
系統會自動備份損毀的檔案（加上時間戳），可以從備份恢復。

## 注意事項

1. **部署環境**: 必須部署在 Linux 環境（系計機器）
2. **資料備份**: 建議定期備份 `db_data/` 和 `game_store_data/`
3. **日誌監控**: 定期檢查 `logs/` 目錄下的日誌檔案
4. **安全性**: 
   - 密碼使用 SHA-256 雜湊
   - 權限檢查（開發者只能操作自己的遊戲）
   - 輸入驗證
