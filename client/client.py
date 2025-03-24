import requests
import subprocess
import time
import json
import os

SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
CLIENT_DESCRIPTION = os.getenv('CLIENT_DESCRIPTION', 'Default Client - No Description Provided')

def get_command():
    response = requests.get(f'{SERVER_URL}/get_command')
    if response.status_code == 200:
        return response.json()
    return None

def execute_command(command):
    start_time = time.time()
    try:
        # 使用subprocess执行命令并捕获输出
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        execution_time = time.time() - start_time
        
        # 组合输出信息
        output = f"Command: {command}\n"
        output += f"Exit Code: {process.returncode}\n"
        output += f"Standard Output:\n{stdout}\n"
        if stderr:
            output += f"Standard Error:\n{stderr}\n"
        
        return execution_time, output
    except Exception as e:
        execution_time = time.time() - start_time
        return execution_time, f"Error executing command: {str(e)}"

def submit_result(command_id, execution_time, output):
    data = {
        'command_id': command_id,
        'execution_time': execution_time,
        'output': output,
        'client_description': CLIENT_DESCRIPTION
    }
    response = requests.post(f'{SERVER_URL}/submit_result', json=data)
    return response.status_code == 200

def main():
    print(f"Client started with description: {CLIENT_DESCRIPTION}")
    while True:
        try:
            # 获取命令
            command_data = get_command()
            if not command_data:
                print("Failed to get command from server")
                time.sleep(5)
                continue
            
            # 执行命令
            execution_time, output = execute_command(command_data['command'])
            
            # 提交结果
            if submit_result(command_data['id'], execution_time, output):
                print(f"Successfully executed and submitted results for command: {command_data['command']}")
            else:
                print("Failed to submit results to server")
            
            # 等待一段时间后继续
            time.sleep(5)
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(5)

if __name__ == '__main__':
    main() 