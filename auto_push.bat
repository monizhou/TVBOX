@echo off
cd /d F:\GitHub\TVBOX

:: 1. 复制文件（使用PowerShell避免中文路径问题）
powershell -Command "Copy-Item 'F:\1.中铁物贸...\发货计划（宜宾项目）汇总.xlsx' ."

:: 2. Git操作
git add .
git commit -m "自动更新: %date% %time%"
git push origin main

:: 3. 可选：触发GitHub Actions工作流
gh workflow run -R monizhou/TVBOX -f filename="发货计划（宜宾项目）汇总.xlsx"