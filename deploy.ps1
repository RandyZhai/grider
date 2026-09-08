# Grider Docker 部署脚本 (AKShare版)
# 使用方法: .\deploy.ps1

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Grider Docker Deployment"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Grider Docker 部署脚本 (AKShare版)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Step 1: 检查Docker
Write-Host "[1/4] 检查Docker环境..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "✅ $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker未安装或未启动！" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# Step 2: 构建镜像
Write-Host ""
Write-Host "[2/4] 构建Docker镜像（包含AKShare依赖）..." -ForegroundColor Yellow
Write-Host "⏳ 这可能需要3-5分钟，请耐心等待..." -ForegroundColor DarkGray
Write-Host ""

try {
    docker-compose build 2>&1 | Tee-Object -Variable buildOutput
    if ($LASTEXITCODE -ne 0) { throw "构建失败" }
    Write-Host "`n✅ 构建成功！" -ForegroundColor Green
} catch {
    Write-Host "`n❌ 构建失败！请检查上面的错误信息。" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# Step 3: 启动容器
Write-Host ""
Write-Host "[3/4] 启动Docker容器..." -ForegroundColor Yellow

try {
    docker-compose up -d 2>&1 | Tee-Object -Variable upOutput
    if ($LASTEXITCODE -ne 0) { throw "启动失败" }
    Write-Host "✅ 容器启动成功！" -ForegroundColor Green
} catch {
    Write-Host "❌ 启动失败！" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# Step 4: 等待并验证
Write-Host ""
Write-Host "[4/4] 等待服务就绪..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ 部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 服务信息：" -ForegroundColor White
Write-Host "  - 地址: http://localhost:5000" -ForegroundColor White
Write-Host "  - 容器名: grider" -ForegroundColor White
Write-Host "  - 数据源: AKShare (新浪/腾讯)" -ForegroundColor White
Write-Host ""
Write-Host "📋 常用命令：" -ForegroundColor White
Write-Host "  - 查看日志: docker-compose logs -f grider" -ForegroundColor Gray
Write-Host "  - 进入容器: docker exec -it grider /bin/bash" -ForegroundColor Gray
Write-Host "  - 停止服务: docker-compose down" -ForegroundColor Gray
Write-Host "  - 重启服务: docker-compose restart" -ForegroundColor Gray
Write-Host ""

# 验证AKShare
Write-Host "🧪 验证AKShare安装:" -ForegroundColor Yellow
try {
    $akshareCheck = docker exec grider python -c "import akshare; print(f'AKShare版本: {akshare.__version__}')" 2>&1
    Write-Host "✅ $akshareCheck" -ForegroundColor Green
} catch {
    Write-Host "⚠️ AKShare验证失败（可能需要等待容器完全启动）" -ForegroundColor Yellow
}

Write-Host ""
Read-Host "按回车键退出"
