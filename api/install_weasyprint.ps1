# WeasyPrint安装脚本（Windows PowerShell）

Write-Host "================================" -ForegroundColor Cyan
Write-Host "WeasyPrint 安装脚本 (Windows)" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否以管理员权限运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠ 警告: 建议以管理员权限运行此脚本" -ForegroundColor Yellow
    Write-Host ""
}

# 检查Chocolatey
Write-Host "检查Chocolatey..." -ForegroundColor Yellow
$chocoInstalled = Get-Command choco -ErrorAction SilentlyContinue

if ($chocoInstalled) {
    Write-Host "✓ Chocolatey已安装" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "正在安装GTK3运行时..." -ForegroundColor Yellow
    choco install gtk-runtime -y
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ GTK3运行时安装完成" -ForegroundColor Green
    } else {
        Write-Host "❌ GTK3运行时安装失败" -ForegroundColor Red
        Write-Host "请手动下载安装: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ 未检测到Chocolatey" -ForegroundColor Red
    Write-Host ""
    Write-Host "请选择以下方式之一安装GTK3:" -ForegroundColor Yellow
    Write-Host "1. 安装Chocolatey后运行: choco install gtk-runtime" -ForegroundColor White
    Write-Host "   Chocolatey安装: https://chocolatey.org/install" -ForegroundColor White
    Write-Host ""
    Write-Host "2. 手动下载GTK3安装程序:" -ForegroundColor White
    Write-Host "   https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases" -ForegroundColor White
    Write-Host ""
    
    $continue = Read-Host "是否继续安装Python依赖? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
}

Write-Host ""
Write-Host "正在安装Python依赖..." -ForegroundColor Yellow

# 安装Python包
pip install weasyprint>=68.1 markdown>=3.5.0 pygments>=2.17.0

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Python依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "❌ Python依赖安装失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "正在验证安装..." -ForegroundColor Yellow

# 验证安装
try {
    $weasyVersion = python -c "import weasyprint; print(weasyprint.__version__)" 2>&1
    $markdownVersion = python -c "import markdown; print(markdown.__version__)" 2>&1
    $pygmentsVersion = python -c "import pygments; print(pygments.__version__)" 2>&1
    
    Write-Host "WeasyPrint版本: $weasyVersion" -ForegroundColor White
    Write-Host "Markdown版本: $markdownVersion" -ForegroundColor White
    Write-Host "Pygments版本: $pygmentsVersion" -ForegroundColor White
    
    Write-Host ""
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "✓ 安装成功！" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Yellow
    Write-Host "1. 重启终端（使GTK3环境变量生效）" -ForegroundColor White
    Write-Host "2. 运行测试: python test_markdown_pdf.py" -ForegroundColor White
    Write-Host "3. 查看文档: docs\WeasyPrint使用说明.md" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "❌ 验证失败" -ForegroundColor Red
    Write-Host "错误信息: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "可能的原因:" -ForegroundColor Yellow
    Write-Host "1. GTK3运行时未正确安装" -ForegroundColor White
    Write-Host "2. 需要重启终端使环境变量生效" -ForegroundColor White
    Write-Host "3. Python版本不兼容（需要Python 3.8+）" -ForegroundColor White
    exit 1
}
