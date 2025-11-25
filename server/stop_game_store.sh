#!/bin/bash
# stop_game_store.sh - 停止遊戲商店系統

echo "================================"
echo "Stopping Game Store System"
echo "================================"
echo ""

if [ -f ".db_pid" ]; then
    DB_PID=$(cat .db_pid)
    if ps -p $DB_PID > /dev/null 2>&1; then
        echo "🛑 Stopping DB Server (PID: $DB_PID)..."
        kill $DB_PID
        echo "✅ DB Server stopped"
    else
        echo "⚠️  DB Server not running"
    fi
    rm -f .db_pid
else
    echo "⚠️  No DB Server PID file found"
fi

if [ -f ".store_pid" ]; then
    STORE_PID=$(cat .store_pid)
    if ps -p $STORE_PID > /dev/null 2>&1; then
        echo "🛑 Stopping Game Store Server (PID: $STORE_PID)..."
        kill $STORE_PID
        echo "✅ Game Store Server stopped"
    else
        echo "⚠️  Game Store Server not running"
    fi
    rm -f .store_pid
else
    echo "⚠️  No Game Store Server PID file found"
fi

# 清理 port 檔案
rm -f .dev_port .lobby_port .db_port

echo ""
echo "================================"
echo "✅ All Servers Stopped"
echo "================================"
