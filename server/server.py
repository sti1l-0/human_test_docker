from flask import Flask, jsonify, request
import sqlite3
import datetime

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command TEXT NOT NULL,
                  requested BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command_id INTEGER,
                  execution_time FLOAT,
                  output TEXT,
                  client_description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (command_id) REFERENCES commands (id))''')
    
    # 插入一些示例命令
    c.execute("SELECT COUNT(*) FROM commands")
    if c.fetchone()[0] == 0:
        commands = [
            "echo 'Hello World'",
            "ls -la",
            "date",
            "whoami",
            "pwd"
        ]
        for cmd in commands:
            c.execute("INSERT INTO commands (command, requested) VALUES (?, 0)", (cmd,))
    
    conn.commit()
    conn.close()

@app.route('/get_command', methods=['GET'])
def get_command():
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    # 只选择未被请求过的命令
    c.execute("SELECT id, command FROM commands WHERE requested = 0 ORDER BY RANDOM() LIMIT 1")
    result = c.fetchone()
    
    if result:
        # 标记该命令为已请求
        c.execute("UPDATE commands SET requested = 1 WHERE id = ?", (result[0],))
        conn.commit()
        conn.close()
        return jsonify({
            'id': result[0],
            'command': result[1]
        })
    
    conn.close()
    return jsonify({'error': 'No available commands'}), 404

@app.route('/submit_result', methods=['POST'])
def submit_result():
    data = request.json
    if not data or 'command_id' not in data or 'execution_time' not in data or 'output' not in data or 'client_description' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    c.execute("""INSERT INTO results (command_id, execution_time, output, client_description)
                 VALUES (?, ?, ?, ?)""",
              (data['command_id'], data['execution_time'], data['output'], data['client_description']))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000) 