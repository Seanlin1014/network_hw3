#!/usr/bin/env python3
"""
Protocol - 訊息編解碼
"""

import json


def encode_message(data):
    """將資料編碼為 bytes"""
    return json.dumps(data).encode("utf-8")


def decode_message(data):
    """將 bytes 解碼為資料"""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)