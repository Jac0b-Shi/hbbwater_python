@echo off
chcp 65001 >nul
echo ========================================
echo   校园水浸监测系统 - Docker 停止脚本
echo ========================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0stop-docker.ps1"
