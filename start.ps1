# 激活虚拟环境（如果使用的是虚拟环境）
if (Test-Path "video_env") {
    .\video_env\Scripts\Activate.ps1
}

# 启动Flask应用
$env:PYTHONPATH = "."
Start-Process -FilePath "python" -ArgumentList "app.py" -WindowStyle Normal
Write-Host "Flask应用已启动，访问 http://localhost:5000" 