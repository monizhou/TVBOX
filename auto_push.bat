@echo off
cd /d F:\GitHub\TVBOX

:: 1. 复制文件（确保路径完整且存在）
powershell -Command "Copy-Item 'F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx' ."

:: 2. Git操作
git add .
git commit -m "自动更新: %date% %time%"
git push origin main

:: 3. 可选：触发GitHub Actions（需替换为实际workflow名称）
gh workflow run -R monizhou/TVBOX "Your Workflow Name" -f filename="发货计划（宜宾项目）汇总.xlsx"