#!/bin/bash
# 配置区域（根据实际情况修改）
REPO_PATH="/f/GitHub/TVBOX"  # 本地仓库路径（Git Bash路径格式）
SOURCE_FILE="/f/1.中铁物贸成都分公司-四川物供中心/钢材-结算/钢筋发货计划-发丁小刚/发货计划（宜宾项目）汇总.xlsx"  # 源文件路径

# 切换到仓库目录（失败则退出）
cd "$REPO_PATH" || {
    echo "[$(date)] 错误：仓库路径不存在！" >> error.log
    exit 1
}

# 复制文件（处理中文路径）
if cp -f "$SOURCE_FILE" .; then
    echo "[$(date)] 文件复制成功: $(ls -l 发货计划*)" >> sync.log
else
    echo "[$(date)] 错误：文件复制失败！" >> error.log
    exit 1
fi

# Git 操作
git add . >> sync.log 2>&1
git commit -m "自动更新: $(date '+%Y-%m-%d %H:%M:%S')" >> sync.log 2>&1
if git push origin main >> sync.log 2>&1; then
    echo "[$(date)] 同步成功" >> sync.log
else
    echo "[$(date)] 错误：Git推送失败！" >> error.log
    exit 1
fi