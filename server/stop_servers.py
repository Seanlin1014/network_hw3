#!/usr/bin/env python3
"""
Game Store Server 停止腳本
停止所有運行中的 Server
"""

import os
import signal
import sys

def stop_server(name, pid_file):
    """停止指定的 Server"""
    if not os.path.exists(pid_file):
        print(f"⚠️  {name}: No PID file found ({pid_file})")
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # 停止 process group
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        print(f"✅ {name} stopped (PID: {pid})")
        
        # 刪除 PID 檔案
        os.remove(pid_file)
        return True
        
    except ProcessLookupError:
        print(f"⚠️  {name}: Process not found (PID: {pid})")
        os.remove(pid_file)
        return False
    except Exception as e:
        print(f"❌ {name}: Failed to stop - {e}")
        return False

def main():
    print("=" * 60)
    print("🛑 Game Store Server - Stopping All Services")
    print("=" * 60)
    
    # 停止所有 Servers
    stop_server("DB Server", ".db_server.pid")
    stop_server("Game Store Server", ".game_store.pid")
    
    # 清理 port 檔案
    for port_file in [".db_port", ".dev_port", ".lobby_port"]:
        if os.path.exists(port_file):
            os.remove(port_file)
    
    print("=" * 60)
    print("✅ All servers stopped and cleaned up")
    print("=" * 60)

if __name__ == "__main__":
    main()
