@echo off
cd /d F:\GitHub\TVBOX

:: 1. 复制文件到仓库（使用短路径或PowerShell避免中文问题）
powershell -Command "Copy-Item 'F:\1.中铁物贸...\发货计划（宜宾项目）汇总.xlsx' ."

:: 2. 提交并推送
git add .
git commit -m "自动更新: 发货计划 %date% %time%"
git push origin main

:: 3. 可选：触发 GitHub Actions（如果有）
gh workflow run -R monizhou/TVBOX