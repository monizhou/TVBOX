@echo off
cd /d F:\GitHub\TVBOX
copy "F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx" .
git add .
git commit -m "自动更新: 发货计划 %date% %time%"
git push origin main