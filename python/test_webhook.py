#!/usr/bin/env python3
"""
Webhook功能测试脚本
"""

import json
import requests
import time
from typing import Dict, Any

def test_webhook_locally(base_url: str = "http://localhost:5000") -> None:
    """测试本地webhook服务"""
    
    print("🚀 开始测试Telegram Bot Webhook功能")
    print("=" * 60)
    
    # 1. 健康检查
    print("1. 健康检查...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务器运行正常")
            print(f"   Bot配置状态: {'✅ 已配置' if data.get('bot_configured') else '❌ 未配置'}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return
    
    print()
    
    # 2. 测试用例
    test_cases = [
        {"text": "hello", "expected": "olleh"},
        {"text": "12345", "expected": "54321"},
        {"text": "你好", "expected": "好你"},
        {"text": "abc", "expected": "cba"},
        {"text": "A", "expected": "A"},
        {"text": "", "expected": ""},
        {"text": "这是一个超过32字节限制的很长很长的测试字符串", "expected": "error"},  # 应该返回错误
    ]
    
    print("2. 功能测试...")
    success_count = 0
    
    for i, test_case in enumerate(test_cases, 1):
        text = test_case["text"]
        expected = test_case["expected"]
        
        print(f"   测试 {i}: '{text}' -> 期望: '{expected}'")
        
        try:
            # 发送测试请求
            response = requests.post(
                f"{base_url}/test",
                json={"text": text, "chat_id": 123456789},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_output = data.get("expected_output", "")
                handler_result = data.get("handler_result", {})
                
                if expected == "error":
                    # 检查是否正确处理了长字符串
                    if len(text.encode('utf-8')) > 32:
                        print(f"      ✅ 正确处理长字符串限制")
                        success_count += 1
                    else:
                        print(f"      ❌ 应该返回错误但没有")
                elif actual_output == expected:
                    print(f"      ✅ 结果正确: '{actual_output}'")
                    success_count += 1
                else:
                    print(f"      ❌ 结果错误: 得到 '{actual_output}', 期望 '{expected}'")
            else:
                print(f"      ❌ 请求失败: {response.status_code}")
                
        except Exception as e:
            print(f"      ❌ 测试异常: {e}")
        
        time.sleep(0.1)  # 避免请求过快
    
    print()
    print(f"测试完成: {success_count}/{len(test_cases)} 通过")
    
    # 3. 直接测试webhook端点
    print()
    print("3. 直接测试Webhook端点...")
    
    webhook_test_data = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1234567890,
            "text": "webhook"
        }
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/webhook",
            json=webhook_test_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ Webhook端点响应正常")
            print(f"   响应: {response.json()}")
        else:
            print(f"   ❌ Webhook端点错误: {response.status_code}")
            print(f"   响应: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Webhook测试异常: {e}")

def test_string_reverse_logic():
    """测试字符串逆序逻辑"""
    print()
    print("4. 字符串逆序逻辑测试...")
    
    test_cases = [
        ("hello", "olleh"),
        ("12345", "54321"),
        ("你好世界", "界世好你"),
        ("a", "a"),
        ("", ""),
        ("abc123", "321cba"),
        ("Hello World!", "!dlroW olleH"),
    ]
    
    success_count = 0
    for text, expected in test_cases:
        actual = text[::-1]
        if actual == expected:
            print(f"   ✅ '{text}' -> '{actual}'")
            success_count += 1
        else:
            print(f"   ❌ '{text}' -> '{actual}' (期望: '{expected}')")
    
    print(f"   逻辑测试: {success_count}/{len(test_cases)} 通过")

if __name__ == "__main__":
    import sys
    
    base_url = "http://localhost:5000"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"测试目标: {base_url}")
    print()
    
    # 测试字符串逆序逻辑
    test_string_reverse_logic()
    
    # 测试webhook服务
    test_webhook_locally(base_url)
    
    print()
    print("🎉 测试完成!")
    print()
    print("如果要测试真实的Telegram Bot:")
    print("1. 配置 TELEGRAM_BOT_TOKEN 环境变量")
    print("2. 部署到公网可访问的服务器")
    print("3. 设置Telegram Webhook")
    print("4. 在Telegram中与机器人对话测试")