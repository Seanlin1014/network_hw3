#!/usr/bin/env python3
"""
Game Store Server 啟動腳本
啟動所有必要的 Server: DB Server, Developer Server, Lobby Server
"""

import subprocess
import time
import os
import signal
import sys

def start_server(script_name, log_file, port_file):
    """啟動一個 Server 並返回 process"""
    print(f"🚀 Starting {script_name}...")
    
    # 建立 logs 目錄
    os.makedirs("logs", exist_ok=True)
    
    # 啟動 Server
    log = open(f"logs/{log_file}", "w")
    process = subprocess.Popen(
        [sys.executable, script_name],
        stdout=log,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None
    )
    
    # 等待 port 檔案產生
    max_wait = 10  # 最多等 10 秒
    for _ in range(max_wait * 10):
        if os.path.exists(port_file):
            with open(port_file, 'r') as f:
                port = f.read().strip()
            print(f"  ✅ {script_name} started on port {port} (PID: {process.pid})")
            return process, port
        time.sleep(0.1)
    
    print(f"  ❌ {script_name} failed to start (timeout)")
    return None, None

def save_pid(pid, pid_file):
    """儲存 PID 到檔案"""
    with open(pid_file, 'w') as f:
        f.write(str(pid))

def main():
    print("=" * 60)
    print("🎮 Game Store Server - Starting All Services")
    print("=" * 60)
    
    processes = []
    
    # 1. 啟動 DB Server
    db_proc, db_port = start_server(
        "db_server_extended.py",
        "db_server.log",
        ".db_port"
    )
    if db_proc:
        processes.append(("DB Server", db_proc))
        save_pid(db_proc.pid, ".db_server.pid")
    else:
        print("❌ Failed to start DB Server. Exiting.")
        sys.exit(1)
    
    # 2. 啟動 Game Store Server (Developer + Lobby)
    time.sleep(1)  # 等待 DB Server 完全啟動
    
    game_proc, dev_port = start_server(
        "game_store_server.py",
        "game_store.log",
        ".dev_port"
    )
    if game_proc:
        processes.append(("Game Store Server", game_proc))
        save_pid(game_proc.pid, ".game_store.pid")
        
        # 讀取 Lobby Port
        if os.path.exists(".lobby_port"):
            with open(".lobby_port", 'r') as f:
                lobby_port = f.read().strip()
        else:
            lobby_port = "N/A"
    else:
        print("❌ Failed to start Game Store Server. Exiting.")
        # 停止 DB Server
        os.killpg(os.getpgid(db_proc.pid), signal.SIGTERM)
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ All Servers Started Successfully!")
    print("=" * 60)
    print(f"📊 Server Information:")
    print(f"  💾 DB Server:         Port {db_port:<6} (PID: {db_proc.pid})")
    print(f"  🎮 Developer Server:  Port {dev_port:<6} (PID: {game_proc.pid})")
    print(f"  🎯 Lobby Server:      Port {lobby_port:<6} (same process)")
    print("=" * 60)
    print(f"\n📝 Port files saved:")
    print(f"  .db_port      -> {db_port}")
    print(f"  .dev_port     -> {dev_port}")
    print(f"  .lobby_port   -> {lobby_port}")
    print(f"\n📋 PID files saved:")
    print(f"  .db_server.pid")
    print(f"  .game_store.pid")
    print(f"\n📖 Logs:")
    print(f"  logs/db_server.log")
    print(f"  logs/game_store.log")
    print("\n💡 To stop servers, run: python3 stop_servers.py")
    print("=" * 60)
    
    # 保持運行
    try:
        print("\n⌨️  Press Ctrl+C to stop all servers...\n")
        while True:
            # 檢查 processes 是否還在運行
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"⚠️  {name} has stopped unexpectedly!")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping all servers...")
        for name, proc in processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                print(f"  ✅ {name} stopped")
            except Exception as e:
                print(f"  ⚠️  Failed to stop {name}: {e}")
        
        # 清理 PID 檔案
        for pid_file in [".db_server.pid", ".game_store.pid"]:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        
        print("✅ All servers stopped")

if __name__ == "__main__":
    main()
