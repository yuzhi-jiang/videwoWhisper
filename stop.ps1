# 查找并终止Python进程
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*app.py*' }

if ($pythonProcesses) {
    $pythonProcesses | ForEach-Object { 
        Stop-Process -Id $_.Id -Force
        Write-Host "已终止进程 ID: $($_.Id)"
    }
    Write-Host "Flask应用已停止"
} else {
    Write-Host "未找到运行中的Flask应用"
} 