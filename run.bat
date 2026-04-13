@echo off
REM 일햇음청년 제조기 — 더블클릭 또는 cmd에서: 설치 후 백엔드·프론트 창 실행
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-local.ps1" %*
