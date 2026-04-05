@echo off
chcp 65001 >nul
echo ========================================
echo   校园水浸监测系统 - Docker 启动脚本
echo ========================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0start-docker.ps1"
