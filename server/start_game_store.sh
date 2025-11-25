#!/bin/bash
# start_game_store.sh - 啟動遊戲商店系統

echo "================================"
echo "Game Store System Startup"
echo "================================"
echo ""

# 檢查必要檔案
if [ ! -f "db_server_extended.py" ]; then
    echo "❌ Error: db_server_extended.py not found"
    exit 1
fi

if [ ! -f "game_store_server.py" ]; then
    echo "❌ Error: game_store_server.py not found"
    exit 1
fi

if [ ! -f "lpfp.py" ]; then
    echo "❌ Error: lpfp.py not found"
    exit 1
fi

# 建立 logs 目錄
mkdir -p logs

# 清理舊的 log 檔案
rm -f logs/db_server.log logs/game_store.log

echo "🚀 Starting DB Server..."
python3 db_server_extended.py 0 > logs/db_server.log 2>&1 &
DB_PID=$!

# 等待 DB Server 啟動
sleep 2

# 從 log 檔案讀取 DB Server 的 port
DB_PORT=$(grep "DB Server Port" logs/db_server.log | grep -oP '\d+' | tail -1)

if [ -z "$DB_PORT" ]; then
    echo "❌ Error: Failed to get DB Server port"
    kill $DB_PID 2>/dev/null
    exit 1
fi

echo "✅ DB Server started on port $DB_PORT (PID: $DB_PID)"

echo "🚀 Starting Game Store Server..."
python3 game_store_server.py $DB_PORT > logs/game_store.log 2>&1 &
STORE_PID=$!

# 等待 Game Store Server 啟動
sleep 2

# 從 log 檔案讀取 Game Store Server 的 ports
DEV_PORT=$(grep "Developer Server Port" logs/game_store.log | grep -oP '\d+' | tail -1)
LOBBY_PORT=$(grep "Lobby Server Port" logs/game_store.log | grep -oP '\d+' | tail -1)

if [ -z "$DEV_PORT" ] || [ -z "$LOBBY_PORT" ]; then
    echo "❌ Error: Failed to get Game Store Server ports"
    kill $DB_PID $STORE_PID 2>/dev/null
    exit 1
fi

echo "✅ Game Store Server started (PID: $STORE_PID)"
echo ""
echo "================================"
echo "✅ All Servers Started!"
echo "================================"
echo ""
echo "📊 Server Information:"
echo "  💾 DB Server:         Port $DB_PORT (PID: $DB_PID)"
echo "  🎮 Developer Server:  Port $DEV_PORT (PID: $STORE_PID)"
echo "  🎯 Lobby Server:      Port $LOBBY_PORT (PID: $STORE_PID)"
echo ""
echo "📁 Log Files:"
echo "  DB Server:        logs/db_server.log"
echo "  Game Store:       logs/game_store.log"
echo ""
echo "🛑 To stop all servers, run:"
echo "  ./stop_game_store.sh"
echo ""

# 儲存 PIDs 到檔案
echo "$DB_PID" > .db_pid
echo "$STORE_PID" > .store_pid
echo "$DEV_PORT" > .dev_port
echo "$LOBBY_PORT" > .lobby_port
echo "$DB_PORT" > .db_port

echo "✅ Server info saved to hidden files"
echo ""
echo "Press Ctrl+C to exit (servers will keep running)"
echo "================================"
