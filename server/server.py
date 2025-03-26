from flask import Flask, jsonify, request
import sqlite3
import datetime
from typing import List, Dict, Any
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    
    # 创建命令表
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command TEXT NOT NULL,
                  requested BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # 创建结果表
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command_id INTEGER,
                  command TEXT,
                  execution_time FLOAT,
                  output TEXT,
                  memory_usage FLOAT,
                  success BOOLEAN,
                  client_description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (command_id) REFERENCES commands (id))''')
    
    # 创建索引以提高查询性能
    c.execute('CREATE INDEX IF NOT EXISTS idx_commands_requested ON commands(requested)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_results_command_id ON results(command_id)')
    
    # 检查是否已经存在示例命令
    c.execute("SELECT COUNT(*) FROM commands WHERE command IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              ("echo 'Hello World'", "ls -la", "date", "whoami", "pwd", 
               "df -h", "free -m", "top -n 1", "ps aux", "netstat -tuln"))
    
    if c.fetchone()[0] == 0:
        commands = [
            "echo 'Hello World'",
            "ls -la",
            "date",
            "whoami",
            "pwd",
            "df -h",
            "free -m",
            "top -n 1",
            "ps aux",
            "netstat -tuln"
        ]
        for cmd in commands:
            c.execute("INSERT INTO commands (command, requested) VALUES (?, 0)", (cmd,))
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('commands.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/get_commands', methods=['GET'])
def get_commands():
    try:
        batch_size = min(int(request.args.get('batch_size', 1)), 50)  # 限制最大批次数
        conn = get_db()
        c = conn.cursor()
        
        # 获取未请求的命令
        c.execute("""
            SELECT id, command 
            FROM commands 
            WHERE requested = 0 
            ORDER BY RANDOM() 
            LIMIT ?
        """, (batch_size,))
        
        commands = [{'id': row['id'], 'command': row['command']} for row in c.fetchall()]
        
        if commands:
            # 标记命令为已请求
            command_ids = [cmd['id'] for cmd in commands]
            c.execute("""
                UPDATE commands 
                SET requested = 1 
                WHERE id IN ({})
            """.format(','.join('?' * len(command_ids))), command_ids)
            conn.commit()
        
        conn.close()
        return jsonify(commands)
        
    except Exception as e:
        logging.error(f"获取命令时出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/submit_results', methods=['POST'])
def submit_results():
    try:
        data = request.json
        if not isinstance(data, list):
            return jsonify({'error': '数据格式错误，需要列表格式'}), 400
            
        conn = get_db()
        c = conn.cursor()
        
        for result in data:
            if not all(k in result for k in ['command_id', 'command', 'execution_time', 'output', 'memory_usage', 'client_description']):
                continue
                
            c.execute("""
                INSERT INTO results 
                (command_id, command, execution_time, output, memory_usage, success, client_description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result['command_id'],
                result['command'],
                result['execution_time'],
                result['output'],
                result.get('memory_usage', 0),
                result.get('success', False),
                result['client_description']
            ))
        
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'count': len(data)})
        
    except Exception as e:
        logging.error(f"提交结果时出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 检查数据库连接
        c.execute("SELECT 1")
        c.fetchone()
        
        # 获取统计信息
        c.execute("SELECT COUNT(*) FROM commands WHERE requested = 0")
        available_commands = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM results")
        total_results = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'available_commands': available_commands,
            'total_results': total_results
        })
        
    except Exception as e:
        logging.error(f"健康检查时出错: {str(e)}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)