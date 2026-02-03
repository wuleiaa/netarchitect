# utils/db_helper.py (新建文件)
import os
import sqlite3
from pathlib import Path

def get_db_path():
    """智能判断运行环境"""
    if os.getenv("STREAMLIT_CLOUD"):  # 云端环境
        # 使用Streamlit Cloud的持久化目录
        return "/mount/src/netarchitect/netarchitect.db"
    return "netarchitect.db"  # 本地环境

def init_db():
    db_path = get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # ...（原有建表逻辑）
    return conn