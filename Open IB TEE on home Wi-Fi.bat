@echo off
title IB TEE
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_on_home_wifi.ps1"
pause
