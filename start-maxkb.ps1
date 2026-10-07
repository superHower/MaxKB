$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root '.venv-backend\Scripts\python.exe'
$Ui = Join-Path $Root 'ui'

if (-not (Test-Path $Python)) {
    Write-Error "找不到后端虚拟环境：$Python"
    Write-Host '请先创建环境：uv venv .venv-backend --python 3.11; uv sync --python .venv-backend\Scripts\python.exe'
    exit 1
}

if (-not (Test-Path (Join-Path $Ui 'node_modules'))) {
    Write-Host '正在安装前端依赖...'
    Push-Location $Ui
    npm install
    Pop-Location
}

Write-Host '正在执行数据库迁移...'
& $Python (Join-Path $Root 'main.py') upgrade_db
if ($LASTEXITCODE -ne 0) {
    Write-Error '数据库迁移失败。请确认 PostgreSQL 和 Redis 已启动。'
    exit $LASTEXITCODE
}

function Start-MaxKBWindow([string]$Title, [string]$WorkingDirectory, [string]$Command) {
    Start-Process powershell.exe -WorkingDirectory $WorkingDirectory -ArgumentList @(
        '-NoExit', '-NoLogo', '-Command',
        "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    ) | Out-Null
}

$Main = Join-Path $Root 'main.py'
$PythonCommand = "& '$Python' '$Main'"

Start-MaxKBWindow 'MaxKB Web' $Root "$PythonCommand dev"
Start-MaxKBWindow 'MaxKB Celery' $Root "$PythonCommand dev celery"
Start-MaxKBWindow 'MaxKB Local Model' $Root "$PythonCommand dev local_model"
Start-MaxKBWindow 'MaxKB Frontend' $Ui 'npm run dev'

Write-Host ''
Write-Host 'MaxKB 已启动。'
Write-Host '管理后台：http://localhost:8080/admin'
Write-Host '前端开发页：http://localhost:5173'
Write-Host '关闭各服务窗口即可停止对应服务。'
