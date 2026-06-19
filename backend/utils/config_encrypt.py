"""配置加密模块"""
import os
import json
import base64
import hashlib
from cryptography.fernet import Fernet

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.enc')
KEY_FILE = os.path.join(BASE_DIR, '.config_key')


def get_or_create_key():
    """获取或创建加密密钥"""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'r') as f:
            return f.read().strip()
    
    key = Fernet.generate_key().decode()
    with open(KEY_FILE, 'w') as f:
        f.write(key)
    return key


def encrypt_config(config_data):
    """加密配置"""
    key = get_or_create_key()
    f = Fernet(key)
    json_str = json.dumps(config_data, ensure_ascii=False)
    encrypted = f.encrypt(json_str.encode())
    
    with open(CONFIG_FILE, 'wb') as f:
        f.write(encrypted)
    return True


def decrypt_config():
    """解密配置"""
    if not os.path.exists(CONFIG_FILE):
        return None
    
    try:
        key = get_or_create_key()
        f = Fernet(key)
        
        with open(CONFIG_FILE, 'rb') as file:
            encrypted = file.read()
        
        decrypted = f.decrypt(encrypted)
        return json.loads(decrypted.decode())
    except Exception as e:
        return None


def load_config():
    """加载配置（优先加密，回退明文）"""
    # 尝试解密配置
    config = decrypt_config()
    if config:
        return config
    
    # 回退到明文配置
    from dotenv import dotenv_values
    env_file = os.path.join(BASE_DIR, '.env.database')
    if os.path.exists(env_file):
        return dotenv_values(env_file)
    
    return {}
