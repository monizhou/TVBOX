@echo off
cd /d F:\GitHub\TVBOX

:: 使用短路径复制（示例，替换实际短名称）
copy "F:\ZG中铁~1\钢材-~1\钢筋发~1\发货计~1.XLS" .

:: Git操作
git add .
git commit -m "自动更新: %date% %time%"
git push origin main