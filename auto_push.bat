@echo off
cd /d F:\GitHub\TVBOX

:: 使用已验证的短路径复制文件
copy "F:\1.中铁物贸成都分公司-四川物供中心\钢材-~1\钢筋发~1\发货计~2.XLS" "发货计划（宜宾项目）汇总.xlsx"

:: Git操作
git add .
git commit -m "自动更新: %date% %time%"
git push origin main

:: 日志记录
echo [%date% %time%] 文件已同步 >> auto_push.log