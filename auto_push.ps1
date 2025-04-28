# 切换到仓库目录
cd F:\GitHub\TVBOX

# 复制 Excel 文件（PowerShell 能正确处理中文路径）
Copy-Item -Path "F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx" -Destination .

# Git 操作
git add .
git commit -m "自动更新: 发货计划 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git push origin main

# 可选：记录日志
Write-Output "文件已推送 $(Get-Date)" >> sync.log