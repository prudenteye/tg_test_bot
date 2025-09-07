#!/usr/bin/env python3
"""
本地测试服务器
用于测试Telegram Bot webhook功能
"""

import os
import json
from flask import Flask, request, jsonify
from api.webhook import handler

# 设置环境变量（用于测试）
if not os.environ.get('TELEGRAM_BOT_TOKEN'):
    # 这里放置您的测试Bot Token
    os.environ['TELEGRAM_BOT_TOKEN'] = 'YOUR_BOT_TOKEN_HERE'

app = Flask(__name__)

class FlaskRequestWrapper:
    """包装Flask request对象以兼容webhook handler"""
    def __init__(self, flask_request):
        self.method = flask_request.method
        self.json = flask_request.get_json()
        self._flask_request = flask_request
    
    def get_json(self):
        return self._flask_request.get_json()

@app.route('/', methods=['GET'])
def health_check():
    """健康检查端点"""
    bot_token_configured = bool(os.environ.get('TELEGRAM_BOT_TOKEN')) and \
                          os.environ.get('TELEGRAM_BOT_TOKEN') != 'YOUR_BOT_TOKEN_HERE'
    
    return jsonify({
        'status': 'ok',
        'message': 'Telegram Bot Webhook Server is running',
        'bot_configured': bot_token_configured,
        'endpoints': {
            'webhook': '/api/webhook',
            'test': '/test'
        }
    })

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """处理Telegram webhook"""
    try:
        # 包装Flask request对象
        wrapped_request = FlaskRequestWrapper(request)
        
        # 调用webhook handler
        result = handler(wrapped_request)
        
        # 返回结果
        return jsonify(json.loads(result['body'])), result['statusCode']
    
    except Exception as e:
        print(f"Error in webhook endpoint: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """测试端点 - 模拟Telegram消息"""
    if request.method == 'GET':
        return jsonify({
            'message': 'Send POST request with test data',
            'example': {
                'text': 'hello',
                'chat_id': 123456789
            }
        })
    
    try:
        data = request.get_json()
        test_text = data.get('text', 'hello')
        test_chat_id = data.get('chat_id', 123456789)
        
        # 构造测试消息
        test_message = {
            'update_id': 123456789,
            'message': {
                'message_id': 1,
                'from': {
                    'id': test_chat_id,
                    'is_bot': False,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': test_chat_id,
                    'first_name': 'Test',
                    'username': 'testuser',
                    'type': 'private'
                },
                'date': 1234567890,
                'text': test_text
            }
        }
        
        # 创建模拟请求
        class MockRequest:
            def __init__(self, data):
                self.method = 'POST'
                self.json = data
            
            def get_json(self):
                return self.json
        
        mock_request = MockRequest(test_message)
        result = handler(mock_request)
        
        return jsonify({
            'input': test_text,
            'expected_output': test_text[::-1],
            'handler_result': json.loads(result['body']),
            'status_code': result['statusCode']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("Telegram Bot 测试服务器")
    print("=" * 50)
    print(f"服务器地址: http://localhost:5000")
    print(f"Webhook端点: http://localhost:5000/api/webhook")
    print(f"测试端点: http://localhost:5000/test")
    print(f"健康检查: http://localhost:5000/")
    print("=" * 50)
    
    # 检查Bot Token配置
    if not os.environ.get('TELEGRAM_BOT_TOKEN') or \
       os.environ.get('TELEGRAM_BOT_TOKEN') == 'YOUR_BOT_TOKEN_HERE':
        print("⚠️  警告: TELEGRAM_BOT_TOKEN 未配置")
        print("请设置环境变量或修改 test_server.py 中的 Bot Token")
        print("export TELEGRAM_BOT_TOKEN='your_bot_token_here'")
        print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)