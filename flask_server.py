from flask import Flask, send_from_directory, jsonify, request
import os
import json
import uuid
from datetime import datetime
import glob
import time
import sys
from flask import g
import threading
import subprocess

app = Flask(__name__)

# ==================== 路径配置 ====================
# 容器内的固定路径
BASE_DIR = '/app'

# 固定路径定义
HTML_DIR = os.path.join(BASE_DIR, 'html')
CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'astrbot_plugin_yoimg_config.json')
PLUGIN_DATA_DIR = os.path.join(BASE_DIR, 'data')

# 具体文件路径
PERSONAS_FILE = os.path.join(PLUGIN_DATA_DIR, 'personas.json')
IMG_DIR = os.path.join(PLUGIN_DATA_DIR, 'img')
GITEE_IMG_DIR = os.path.join(IMG_DIR, 'giteeimg')
LOGS_DIR = os.path.join(PLUGIN_DATA_DIR, 'logs')
FLASK_LOG = os.path.join(LOGS_DIR, 'flask.log')
GITEE_LOG = os.path.join(LOGS_DIR, 'gitee.log')

# ==================== 目录初始化 ====================
# 创建所有必要的目录
for dir_path in [HTML_DIR, os.path.dirname(CONFIG_FILE), PLUGIN_DATA_DIR, 
                 IMG_DIR, GITEE_IMG_DIR, LOGS_DIR]:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception as e:
        print(f"创建目录失败 {dir_path}: {e}")

# ==================== 日志记录函数 ====================
def log_access(request, response=None, status_code=200):
    try:
        timestamp = datetime.now().strftime('%d/%b/%Y %H:%M:%S')
        ip = request.remote_addr
        method = request.method
        path = request.path
        
        if response:
            log_line = f'{ip} - - [{timestamp}] "{method} {path} HTTP/1.1" {status_code} -\n'
        else:
            log_line = f'{ip} - - [{timestamp}] "{method} {path} HTTP/1.1" -\n'
        
        with open(FLASK_LOG, 'a', encoding='utf-8') as f:
            f.write(log_line)
    except Exception as e:
        pass

# ==================== 请求钩子 ====================
@app.before_request
def before_request():
    g.request_start_time = time.time()

@app.after_request
def after_request(response):
    try:
        log_access(request, response, response.status_code)
    except:
        pass
    return response

@app.teardown_request
def teardown_request(exception=None):
    if exception:
        try:
            log_access(request, status_code=500)
        except:
            pass

# ==================== 配置管理函数 ====================
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            # 处理UTF-8 BOM头问题
            for encoding in ['utf-8-sig', 'utf-8']:
                try:
                    with open(CONFIG_FILE, 'r', encoding=encoding) as f:
                        content = f.read()
                        # 如果文件为空，返回空字典
                        if not content.strip():
                            return {}
                        return json.loads(content)
                except UnicodeDecodeError:
                    continue
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}")
                    return {}
    except Exception as e:
        print(f"读取配置失败: {e}")
    return {}

def save_config(config_data):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

# ==================== 人格管理函数 ====================
def load_personas():
    try:
        os.makedirs(PLUGIN_DATA_DIR, exist_ok=True)
        
        if os.path.exists(PERSONAS_FILE):
            with open(PERSONAS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return []

def save_personas(personas_data):
    try:
        os.makedirs(PLUGIN_DATA_DIR, exist_ok=True)
        
        with open(PERSONAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(personas_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存人格失败: {e}")
        return False

# ==================== Gitee日志接口 ====================
@app.route('/api/get_gitee_log', methods=['GET'])
def get_gitee_log():
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(GITEE_LOG), exist_ok=True)
        
        if not os.path.exists(GITEE_LOG):
            # 创建空文件
            with open(GITEE_LOG, 'w', encoding='utf-8') as f:
                f.write("")
            return jsonify({"success": True, "content": "gitee.log 日志文件已创建，暂无内容"})
        
        with open(GITEE_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines or all(line.strip() == '' for line in lines):
            return jsonify({"success": True, "content": "gitee.log 日志文件暂无内容"})
        
        if len(lines) > 500:
            lines = lines[-500:]
        content = ''.join(lines)
        
        return jsonify({"success": True, "content": content})
    except Exception as e:
        return jsonify({"success": False, "content": f"读取gitee.log失败: {str(e)}"})

# ==================== Gitee图片管理接口 ====================
@app.route('/api/giteeimg/list', methods=['GET'])
def get_giteeimg_list():
    try:
        img_list = []
        img_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
        for filename in os.listdir(GITEE_IMG_DIR):
            if filename.lower().endswith(img_extensions):
                file_path = os.path.join(GITEE_IMG_DIR, filename)
                file_size = os.path.getsize(file_path) / 1024
                create_time = datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                img_list.append({
                    'filename': filename,
                    'size': f"{file_size:.2f} KB",
                    'create_time': create_time,
                    'url': f'/api/giteeimg/show/{filename}'
                })
        img_list.sort(key=lambda x: x['create_time'], reverse=True)
        return jsonify({"success": True, "data": img_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/giteeimg/delete/<filename>', methods=['DELETE'])
def delete_giteeimg(filename):
    try:
        file_path = os.path.join(GITEE_IMG_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({"success": False, "message": "图片不存在"}), 404
        os.remove(file_path)
        return jsonify({"success": True, "message": "删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/giteeimg/show/<filename>', methods=['GET'])
def show_giteeimg(filename):
    return send_from_directory(GITEE_IMG_DIR, filename)

# ==================== 原有日志接口 ====================
@app.route('/api/flask_logs', methods=['GET'])
def get_flask_logs():
    try:
        if os.path.exists(FLASK_LOG):
            with open(FLASK_LOG, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.strip().split('\n')
            if len(lines) > 100:
                content = '\n'.join(lines[-100:])
            return jsonify({"success": True, "logs": content})
        else:
            return jsonify({"success": True, "logs": "暂无日志"})
    except Exception as e:
        return jsonify({"success": False, "logs": f"读取日志失败: {str(e)}"})

@app.route('/api/file_logs', methods=['GET'])
def get_file_logs():
    logs = []
    try:
        request_files = glob.glob(os.path.join(LOGS_DIR, 'req_*_request.log'))
        for req_file in request_files:
            filename = os.path.basename(req_file)
            req_id = filename.replace('_request.log', '')
            with open(req_file, 'r', encoding='utf-8') as f:
                req_content = f.read()
            time_str = ''
            for line in req_content.split('\n'):
                if line.startswith('时间:'):
                    time_str = line.replace('时间:', '').strip()
                    break
            logs.append({
                'id': req_id,
                'time': time_str,
                'request_file': filename,
                'response_file': req_id + '_response.log'
            })
        logs.sort(key=lambda x: x['time'], reverse=True)
    except Exception as e:
        pass
    return jsonify({"success": True, "logs": logs})

@app.route('/api/logs/<log_id>', methods=['GET'])
def get_log_detail(log_id):
    log_type = request.args.get('type', 'request')
    try:
        if log_type == 'request':
            file_path = os.path.join(LOGS_DIR, f"{log_id}_request.log")
        else:
            file_path = os.path.join(LOGS_DIR, f"{log_id}_response.log")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"success": True, "content": content})
        else:
            return jsonify({"success": False, "message": "日志不存在"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== 页面路由 ====================
@app.route('/')
def index():
    return send_from_directory(HTML_DIR, 'index.html')

@app.route('/config')
def config():
    return send_from_directory(HTML_DIR, 'config.html')

@app.route('/personas')
def personas():
    return send_from_directory(HTML_DIR, 'personas.html')

@app.route('/logs')
def logs():
    return send_from_directory(HTML_DIR, 'logs.html')

@app.route('/giteeimg')
def giteeimg_page():
    return send_from_directory(HTML_DIR, 'giteeimg.html')

# ==================== 原有API路由 ====================
@app.route('/api/config', methods=['GET'])
def get_config():
    config_data = load_config()
    schema = {}
    for key, value in config_data.items():
        schema[key] = {"default": value}
    return jsonify({
        "success": True,
        "schema": schema,
        "config": config_data
    })

@app.route('/api/config', methods=['POST'])
def post_config():
    try:
        data = request.json
        if save_config(data):
            return jsonify({"success": True, "message": "保存成功"})
        return jsonify({"success": False, "message": "保存失败"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/personas', methods=['GET'])
def get_personas():
    personas = load_personas()
    return jsonify({
        "success": True,
        "personas": personas
    })

@app.route('/api/personas', methods=['POST'])
def post_personas():
    try:
        data = request.json
        if save_personas(data):
            return jsonify({"success": True, "message": "保存成功"})
        return jsonify({"success": False, "message": "保存失败"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "没有文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "没有选择文件"}), 400
    
    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(IMG_DIR, filename)
        local_path = os.path.abspath(filepath)
        
        try:
            # 确保目录存在
            os.makedirs(IMG_DIR, exist_ok=True)
            
            # 保存文件
            file.save(filepath)
            
            # 验证文件保存成功
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return jsonify({
                    "success": True,
                    "url": f"/img/{filename}",
                    "filename": filename,
                    "local_path": local_path
                })
            else:
                return jsonify({"success": False, "message": "文件保存失败或文件为空"}), 500
                
        except Exception as e:
            return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500
    
    return jsonify({"success": False, "message": "不支持的文件类型"}), 400

# ==================== 静态资源路由 ====================
@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory(IMG_DIR, filename)

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(HTML_DIR, filename)

# ==================== 启动函数 ====================
if __name__ == '__main__':
    # 确保所有目录都存在
    directories = [
        LOGS_DIR,
        IMG_DIR, 
        GITEE_IMG_DIR,
        os.path.dirname(CONFIG_FILE),
        PLUGIN_DATA_DIR
    ]
    
    for dir_path in directories:
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            print(f"创建目录失败 {dir_path}: {e}")
    
    # 初始化日志文件
    for log_file, log_name in [(FLASK_LOG, "Flask"), (GITEE_LOG, "Gitee")]:
        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] {log_name}日志文件初始化\n")
                print(f"{log_name}日志文件初始化完成: {log_file}")
            except Exception as e:
                print(f"初始化{log_name}日志失败: {e}")
    
    app.run(host='0.0.0.0', port=1200, debug=False)