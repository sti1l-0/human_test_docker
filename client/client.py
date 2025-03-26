#!/Usr/Bin/Python3

Import Subprocess
Import Time
Import Psutil
Import Os
From Concurrent.Futures Import ThreadPoolExecutor, As_Completed
Import Logging
From Typing Import Dict, Any, List, Set, Optional
Import Sys
Import Threading
Import Signal
From Pathlib Import Path
Import Requests
Import Json
From Queue Import Queue
From Dataclasses Import Dataclass
From Datetime Import Datetime

# 配置日志
Logging.BasicConfig(
    Level=Logging.INFO,
    Format='%(Asctime)S - %(Levelname)S - %(Message)S',
    Handlers=[
        Logging.FileHandler('Execution.Log'),
        Logging.StreamHandler(Sys.Stdout)
    ]
)

# 配置常量
SERVER_URL = Os.Getenv('SERVER_URL', 'Http://172.23.216.211:5000')
CLIENT_DESCRIPTION = Os.Getenv('CLIENT_DESCRIPTION', 'Default Client - No Description Provided')
MAX_CPU_PERCENT = 90
MAX_MEMORY_PERCENT = 90
RESOURCE_CHECK_INTERVAL = 5
BATCH_SIZE = 20
COMMAND_TIMEOUT = 30
CHECKPOINT_INTERVAL = 50
MAX_RETRIES = 3
RETRY_DELAY = 10
MAX_CONCURRENT_BATCHES = 2  # 最大并发批次数
BATCH_SUBMIT_INTERVAL = 5  # 批次提交间隔（秒）

@Dataclass
Class CommandResult:
    Command_Id: Str
    Command: Str
    Execution_Time: Float
    Output: Str
    Memory_Usage: Float
    Success: Bool
    Timestamp: Datetime = Datetime.Now()

Class ResultQueue:
    Def __Init__(Self, Max_Size: Int = 100):
        Self.Queue = Queue(Maxsize=Max_Size)
        Self.Lock = Threading.Lock()
        
    Def Put(Self, Result: CommandResult):
        Try:
            Self.Queue.Put(Result, Timeout=1)
        Except Exception As E:
            Logging.Error(F"添加结果到队列失败: {Str(E)}")
            
    Def Get_Batch(Self, Size: Int) -> List[CommandResult]:
        Results = []
        While Len(Results) < Size And Not Self.Queue.Empty():
            Try:
                Result = Self.Queue.Get(Timeout=1)
                Results.Append(Result)
            Except Exception:
                Break
        Return Results

# 全局控制标志
Should_Stop = Threading.Event()
Result_Queue = ResultQueue()

Def Get_Commands(Batch_Size: Int = BATCH_SIZE) -> Optional[List[Dict[Str, Any]]]:
    """从服务器获取一批命令，包含重试机制"""
    For Attempt In Range(MAX_RETRIES):
        Try:
            Response = Requests.Get(
                F'{SERVER_URL}/Get_Commands',
                Params={'Batch_Size': Batch_Size},
                Timeout=10
            )
            If Response.Status_Code == 200:
                Return Response.Json()
            Logging.Warning(F"获取命令失败，状态码: {Response.Status_Code}")
        Except Requests.Exceptions.RequestException As E:
            Logging.Error(F"连接服务器错误: {Str(E)}")
        If Attempt < MAX_RETRIES - 1:
            Time.Sleep(RETRY_DELAY)
    Return None

Class ResourceMonitor:
    """系统资源监控类"""
    @Staticmethod
    Def Monitor():
        While Not Should_Stop.Is_Set():
            Try:
                Cpu_Percent = Psutil.Cpu_Percent(Interval=1)
                Memory_Percent = Psutil.Virtual_Memory().Percent
                
                If Cpu_Percent > MAX_CPU_PERCENT Or Memory_Percent > MAX_MEMORY_PERCENT:
                    Logging.Warning(F"系统资源使用过高: CPU {Cpu_Percent}%, 内存 {Memory_Percent}%")
                    Should_Stop.Set()
                    Break
                    
                Time.Sleep(RESOURCE_CHECK_INTERVAL)
            Except Exception As E:
                Logging.Error(F"资源监控错误: {Str(E)}")
                Break

Class CommandExecutor:
    """命令执行类"""
    @Staticmethod
    Def Execute(Command_Data: Dict[Str, Any]) -> Optional[CommandResult]:
        If Should_Stop.Is_Set():
            Return None
            
        Try:
            Command_Id = Command_Data.Get('Id')
            Command = Command_Data.Get('Command')
            
            If Not Command_Id Or Not Command:
                Logging.Error("命令数据不完整")
                Return None
            
            Start_Time = Time.Time()
            Process = Psutil.Process(Os.Getpid())
            Start_Mem = Process.Memory_Info().Rss / 1024 / 1024
            
            With Subprocess.Popen(
                Command,
                Shell=True,
                Stdout=Subprocess.PIPE,
                Stderr=Subprocess.PIPE,
                Text=True,
                Preexec_Fn=Os.Setsid
            ) As Proc:
                Try:
                    Stdout, Stderr = Proc.Communicate(Timeout=COMMAND_TIMEOUT)
                    Success = Proc.Returncode == 0
                    Output = Stdout If Success Else Stderr
                    Output = Output.Replace('\N', '\\N').Replace('\R', '\\R')
                Except Subprocess.TimeoutExpired:
                    Os.Killpg(Os.Getpgid(Proc.Pid), Signal.SIGTERM)
                    Output = F"命令执行超时 ({COMMAND_TIMEOUT}秒)"
                    Success = False
            
            Execution_Time = Time.Time() - Start_Time
            Memory_Usage = Process.Memory_Info().Rss / 1024 / 1024 - Start_Mem
            
            Return CommandResult(
                Command_Id=Command_Id,
                Command=Command,
                Execution_Time=Execution_Time,
                Output=Output,
                Memory_Usage=Memory_Usage,
                Success=Success
            )
        Except Exception As E:
            Logging.Error(F"执行命令 {Command_Data.Get('Id', 'Unknown')} 时出错: {Str(E)}")
            Return None

Def Submit_Results(Results: List[CommandResult]) -> Bool:
    """批量提交执行结果到服务器"""
    If Not Results:
        Return True
        
    Try:
        Data = [{
            'Command_Id': Result.Command_Id,
            'Command': Result.Command,
            'Execution_Time': Result.Execution_Time,
            'Output': Result.Output,
            'Memory_Usage': Result.Memory_Usage,
            'Client_Description': CLIENT_DESCRIPTION
        } For Result In Results]
        
        Response = Requests.Post(
            F'{SERVER_URL}/Submit_Results',
            Json=Data,
            Timeout=10
        )
        
        If Response.Status_Code != 200:
            Logging.Error(F"提交结果失败，状态码: {Response.Status_Code}")
        Return Response.Status_Code == 200
    Except Requests.Exceptions.RequestException As E:
        Logging.Error(F"提交结果时发生错误: {Str(E)}")
        Return False

Class BatchProcessor:
    """批处理类"""
    Def __Init__(Self):
        Self.Active_Batches = 0
        Self.Lock = Threading.Lock()
        
    Def Process_Batch(Self, Commands: List[Dict[Str, Any]]):
        If Not Commands:
            Return
            
        With Self.Lock:
            If Self.Active_Batches >= MAX_CONCURRENT_BATCHES:
                Logging.Warning("已达到最大并发批次数，跳过当前批次")
                Return
            Self.Active_Batches += 1
            
        Try:
            Max_Workers = Min(8, Len(Commands))
            
            With ThreadPoolExecutor(Max_Workers=Max_Workers) As Executor:
                Future_To_Cmd = {
                    Executor.Submit(CommandExecutor.Execute, Cmd): Cmd.Get('Id', 'Unknown')
                    For Cmd In Commands
                }
                
                For Future In As_Completed(Future_To_Cmd):
                    If Should_Stop.Is_Set():
                        Break
                        
                    Cmd_Id = Future_To_Cmd[Future]
                    Try:
                        Result = Future.Result()
                        If Result:
                            Result_Queue.Put(Result)
                            Logging.Info(F"命令 {Cmd_Id} 执行完成")
                    Except Exception As E:
                        Logging.Error(F"命令 {Cmd_Id} 执行失败: {Str(E)}")
                        
        Finally:
            With Self.Lock:
                Self.Active_Batches -= 1

Def Result_Submitter():
    """结果提交线程"""
    While Not Should_Stop.Is_Set():
        Try:
            Results = Result_Queue.Get_Batch(BATCH_SIZE)
            If Results:
                Submit_Results(Results)
            Time.Sleep(BATCH_SUBMIT_INTERVAL)
        Except Exception As E:
            Logging.Error(F"结果提交线程错误: {Str(E)}")
            Time.Sleep(RETRY_DELAY)

Def Main():
    Try:
        Batch_Processor = BatchProcessor()
        
        # 启动资源监控
        Monitor_Thread = Threading.Thread(Target=ResourceMonitor.Monitor)
        Monitor_Thread.Daemon = True
        Monitor_Thread.Start()
        
        # 启动结果提交线程
        Submitter_Thread = Threading.Thread(Target=Result_Submitter)
        Submitter_Thread.Daemon = True
        Submitter_Thread.Start()
        
        While Not Should_Stop.Is_Set():
            Commands = Get_Commands()
            If Not Commands:
                Logging.Info("没有获取到命令，等待10秒后重试...")
                Time.Sleep(10)
                Continue
            
            Batch_Processor.Process_Batch(Commands)
            Time.Sleep(1)  # 避免过于频繁的请求
                
    Except Exception As E:
        Logging.Error(F"程序执行出错: {Str(E)}")
        Raise
    Finally:
        Should_Stop.Set()
        Logging.Info("程序正在退出...")

If __Name__ == "__Main__":
    Main()