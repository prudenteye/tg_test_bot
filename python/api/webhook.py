import json
import os
import requests
from typing import Dict, Any, Union

# Telegram Bot API配置
# Support both env names for compatibility
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

def handler(request) -> Dict[str, Any]:
    """Vercel serverless function handler"""
    
    # 只处理POST请求
    if hasattr(request, 'method') and request.method != 'POST':
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    # 检查Bot Token是否配置
    if not BOT_TOKEN:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'TELEGRAM_BOT_TOKEN not configured'})
        }
    
    try:
        # 解析Telegram webhook数据
        data = None
        if hasattr(request, 'get_json') and callable(request.get_json):
            # Flask-like request object
            data = request.get_json()
        elif hasattr(request, 'json') and request.json:
            # Some frameworks use .json property
            data = request.json
        elif hasattr(request, 'body'):
            # Vercel request object
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body) if body else {}
        else:
            # Fallback: try to get data from request directly
            data = getattr(request, 'data', {})
            if isinstance(data, str):
                data = json.loads(data)
        
        if not data:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No data received'})
            }
        
        # 检查是否包含消息
        if 'message' not in data:
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'ok'})
            }
        
        message = data['message']
        chat_id = message['chat']['id']
        
        # 检查是否包含文本消息
        if 'text' not in message:
            send_message(chat_id, "请发送文本消息！")
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'ok'})
            }
        
        text = message['text']
        
        # 检查字符串长度（32字节限制）
        if len(text.encode('utf-8')) > 32:
            send_message(chat_id, "消息太长了！请发送不超过32字节的字符串。")
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'ok'})
            }
        
        # 处理逆序
        reversed_text = text[::-1]
        
        # 发送逆序结果
        send_message(chat_id, f"逆序结果：{reversed_text}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok'})
        }
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def send_message(chat_id: Union[int, str], text: str) -> Dict[str, Any]:
    """发送消息到Telegram"""
    if not TELEGRAM_API_URL:
        print("TELEGRAM_API_URL not configured")
        return {'ok': False, 'error': 'Bot token not configured'}
    
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {str(e)}")
        return {'ok': False, 'error': str(e)}

# Vercel entry point
def handler_vercel(request):
    return handler(request)

# 兼容不同的serverless平台
def lambda_handler(event, context):
    """AWS Lambda handler"""
    class MockRequest:
        def __init__(self, event):
            self.method = event.get('httpMethod', 'POST')
            self.body = event.get('body', '{}')
    
    request = MockRequest(event)
    result = handler(request)
    
    return {
        'statusCode': result['statusCode'],
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': result['body']
    }