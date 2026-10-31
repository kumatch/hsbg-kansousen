<#
.SYNOPSIS
  ローカルダッシュボード (hsbg serve) を起動する。デスクトップショートカット用。

.DESCRIPTION
  リポジトリのフォルダで `uv run hsbg serve` を実行する（`hsbg` をインストール済みなら、ワークスペースで `hsbg serve` でもよい）。ブラウザが http://127.0.0.1:8501 を開く。
  ショートカットの作り方: デスクトップを右クリック → 新規作成 → ショートカット → 項目の場所に
    pwsh.exe -NoExit -ExecutionPolicy Bypass -File "<このリポジトリ>\scripts\start-dashboard.ps1"
  （PowerShell 5.1 なら pwsh.exe を powershell.exe に）。終了はそのウィンドウで Ctrl+C。
  ワークスペース（hsbg.toml のあるフォルダ）の設定を使うときは -Workspace <フォルダ> を付ける（環境変数 HSBG_WORKSPACE でも可）。

.EXAMPLE
  .\scripts\start-dashboard.ps1
  .\scripts\start-dashboard.ps1 -Port 8600
  .\scripts\start-dashboard.ps1 -Workspace "$env:USERPROFILE\src\hsbg-kansousen-workspace"
#>
[CmdletBinding()]
param(
    [int]$Port = 8501,
    [string]$LogDir,
    [string]$Workspace
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$analysis = $repoRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv が見つかりません。README の手順で `winget install astral-sh.uv` を実行してください。' -ForegroundColor Yellow
    exit 1
}

if ($Workspace) {
    if (-not (Test-Path (Join-Path $Workspace 'hsbg.toml'))) {
        Write-Host "hsbg.toml がありません: $Workspace（uv run hsbg init <フォルダ> で作れます）" -ForegroundColor Yellow
        exit 1
    }
    $env:HSBG_WORKSPACE = (Resolve-Path $Workspace).Path
}

Push-Location $analysis
try {
    $args = @('run', 'hsbg', 'serve', '--port', $Port)
    if ($LogDir) { $args += @('--dir', $LogDir) }
    & uv @args
}
finally {
    Pop-Location
}
