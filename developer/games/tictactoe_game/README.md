# Tic-Tac-Toe Online - 圈圈叉叉線上對戰

## 遊戲介紹
經典的圈圈叉叉雙人對戰遊戲，透過網路連線進行即時對戰。

## 遊戲類型
- **類型**: CLI (命令列介面遊戲)
- **玩家數**: 2 人對戰
- **開發者**: 113550022

## 遊戲規則
1. 3x3 棋盤
2. 玩家輪流下棋
3. 先連成一直線（橫/直/斜）者獲勝
4. 棋盤滿但無人獲勝則平手

## 操作方式
- 輸入位置編號 (1-9) 來下棋
- 棋盤編號如下：
```
 1 | 2 | 3
-----------
 4 | 5 | 6
-----------
 7 | 8 | 9
```

## 系統需求
- C++ 編譯器 (g++)
- Linux/Unix 環境

## 編譯方式
```bash
# 編譯 Lobby Server
g++ -o lobby_server lobby_server.cpp -std=c++11

# 編譯 Player A Client
g++ -o playerA game_client.cpp -pthread -std=c++11

# 編譯 Player B Client  
g++ -o playerB playerB_client.cpp -pthread -std=c++11
```

## 啟動方式

### 1. 啟動 Lobby Server
```bash
./lobby_server 15555
```

### 2. 玩家 A 啟動
```bash
./playerA 127.0.0.1 15555
```

### 3. 玩家 B 啟動
```bash
./playerB 127.0.0.1 15555
```

## 遊戲流程
1. 註冊/登入帳號
2. 進入大廳
3. 玩家 A 建立房間（監聽模式）
4. 玩家 B 連線到玩家 A
5. 開始遊戲對戰
6. 遊戲結束後顯示結果

## 特色功能
- ✅ 帳號系統（註冊/登入）
- ✅ 戰績記錄（勝/負/平）
- ✅ UDP 即時通訊
- ✅ 完整遊戲邏輯
- ✅ CLI 介面

## 計分方式
- 勝利：Win +1
- 失敗：Lose +1
- 平手：Draw +1

## 注意事項
- 必須先啟動 Lobby Server
- 兩位玩家需要在同一網路環境或可互相連線
- 預設 Port: 15555
