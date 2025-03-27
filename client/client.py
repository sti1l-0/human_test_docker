#!/usr/bin/python3

import subprocess
import time
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from typing import Dict, Any, List, Set, Optional
import sys
import threading
import signal
from pathlib import Path
import requests
import json
from queue import Queue
from dataclasses import dataclass
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('execution.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 配置常量
SERVER_URL = os.getenv('SERVER_URL', 'http://172.23.216.211:5000')
CLIENT_DESCRIPTION = os.getenv('CLIENT_DESCRIPTION', 'Default Client - No Description Provided')
MAX_CPU_PERCENT = 90
MAX_MEMORY_PERCENT = 90
RESOURCE_CHECK_INTERVAL = 5
BATCH_SIZE = 10
COMMAND_TIMEOUT = 30
CHECKPOINT_INTERVAL = 50
MAX_RETRIES = 3
RETRY_DELAY = 10
MAX_CONCURRENT_BATCHES = 2  # 最大并发批次数
BATCH_SUBMIT_INTERVAL = 2  # 批次提交间隔（秒）

@dataclass
class CommandResult:
    command_id: str
    command: str
    execution_time: float
    output: str
    memory_usage: float
    success: bool
    timestamp: datetime = datetime.now()

class ResultQueue:
    def __init__(self, max_size: int = 100):
        self.queue = Queue(maxsize=max_size)
        self.lock = threading.Lock()
        
    def put(self, result: CommandResult):
        try:
            self.queue.put(result, timeout=1)
        except Exception as e:
            logging.error(f"添加结果到队列失败: {str(e)}")
            
    def get_batch(self, size: int) -> List[CommandResult]:
        results = []
        while len(results) < size and not self.queue.empty():
            try:
                result = self.queue.get(timeout=1)
                results.append(result)
            except Exception:
                break
        return results

# 全局控制标志
should_stop = threading.Event()
result_queue = ResultQueue()

def get_commands(batch_size: int = BATCH_SIZE) -> Optional[List[Dict[str, Any]]]:
    """从服务器获取一批命令，包含重试机制"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                f'{SERVER_URL}/get_commands',
                params={'batch_size': batch_size},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            logging.warning(f"获取命令失败，状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error(f"连接服务器错误: {str(e)}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    return None

class ResourceMonitor:
    """系统资源监控类"""
    @staticmethod
    def monitor():
        while not should_stop.is_set():
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                
                if cpu_percent > MAX_CPU_PERCENT or memory_percent > MAX_MEMORY_PERCENT:
                    logging.warning(f"系统资源使用过高: CPU {cpu_percent}%, 内存 {memory_percent}%")
                    should_stop.set()
                    break
                    
                time.sleep(RESOURCE_CHECK_INTERVAL)
            except Exception as e:
                logging.error(f"资源监控错误: {str(e)}")
                break

class CommandExecutor:
    """命令执行类"""
    @staticmethod
    def execute(command_data: Dict[str, Any]) -> Optional[CommandResult]:
        if should_stop.is_set():
            return None
            
        try:
            command_id = command_data.get('id')
            command = command_data.get('command')
            
            if not command_id or not command:
                logging.error("命令数据不完整")
                return None
            
            start_time = time.time()
            process = psutil.Process(os.getpid())
            start_mem = process.memory_info().rss / 1024 / 1024
            
            with subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid
            ) as proc:
                try:
                    stdout, stderr = proc.communicate(timeout=COMMAND_TIMEOUT)
                    success = proc.returncode == 0
                    output = stdout if success else stderr
                    output = output.replace('\n', '\\n').replace('\r', '\\r')
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    output = f"命令执行超时 ({COMMAND_TIMEOUT}秒)"
                    success = False
            
            execution_time = time.time() - start_time
            memory_usage = process.memory_info().rss / 1024 / 1024 - start_mem
            
            return CommandResult(
                command_id=command_id,
                command=command,
                execution_time=execution_time,
                output=output,
                memory_usage=memory_usage,
                success=success
            )
        except Exception as e:
            logging.error(f"执行命令 {command_data.get('id', 'Unknown')} 时出错: {str(e)}")
            return None

def submit_results(results: List[CommandResult]) -> bool:
    """批量提交执行结果到服务器"""
    if not results:
        return True
        
    try:
        data = [{
            'command_id': result.command_id,
            'command': result.command,
            'execution_time': result.execution_time,
            'output': result.output,
            'memory_usage': result.memory_usage,
            'client_description': CLIENT_DESCRIPTION
        } for result in results]
        
        response = requests.post(
            f'{SERVER_URL}/submit_results',
            json=data,
            timeout=10
        )
        
        if response.status_code != 200:
            logging.error(f"提交结果失败，状态码: {response.status_code}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"提交结果时发生错误: {str(e)}")
        return False

class BatchProcessor:
    """批处理类"""
    def __init__(self):
        self.active_batches = 0
        self.lock = threading.Lock()
        
    def process_batch(self, commands: List[Dict[str, Any]]):
        if not commands:
            return
            
        with self.lock:
            if self.active_batches >= MAX_CONCURRENT_BATCHES:
                logging.warning("已达到最大并发批次数，跳过当前批次")
                return
            self.active_batches += 1
            
        try:
            max_workers = min(8, len(commands))
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_cmd = {
                    executor.submit(CommandExecutor.execute, cmd): cmd.get('id', 'Unknown')
                    for cmd in commands
                }
                
                for future in as_completed(future_to_cmd):
                    if should_stop.is_set():
                        break
                        
                    cmd_id = future_to_cmd[future]
                    try:
                        result = future.result()
                        if result:
                            result_queue.put(result)
                            logging.info(f"命令 {cmd_id} 执行完成")
                    except Exception as e:
                        logging.error(f"命令 {cmd_id} 执行失败: {str(e)}")
                        
        finally:
            with self.lock:
                self.active_batches -= 1

def result_submitter():
    """结果提交线程"""
    while not should_stop.is_set():
        try:
            results = result_queue.get_batch(BATCH_SIZE)
            if results:
                submit_results(results)
            time.sleep(BATCH_SUBMIT_INTERVAL)
        except Exception as e:
            logging.error(f"结果提交线程错误: {str(e)}")
            time.sleep(RETRY_DELAY)

def main():
    try:
        batch_processor = BatchProcessor()
        
        # 启动资源监控
        monitor_thread = threading.Thread(target=ResourceMonitor.monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 启动结果提交线程
        submitter_thread = threading.Thread(target=result_submitter)
        submitter_thread.daemon = True
        submitter_thread.start()
        
        while not should_stop.is_set():
            commands = get_commands()
            if not commands:
                logging.info("没有获取到命令，等待10秒后重试...")
                time.sleep(10)
                continue
            
            batch_processor.process_batch(commands)
            time.sleep(1)  # 避免过于频繁的请求
                
    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}")
        raise
    finally:
        should_stop.set()
        logging.info("程序正在退出...")

if __name__ == "__main__":
    main()