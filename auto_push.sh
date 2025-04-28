#!/bin/bash
# ================ 配置区域 ================
REPO_PATH="/f/GitHub/TVBOX"
SOURCE_FILE="/f/1.中铁物贸成都分公司-四川物供中心/钢材-结算/钢筋发货计划-发丁小刚/发货计划（宜宾项目）汇总.xlsx"
MAX_RETRIES=3  # 最大重试次数
# ==========================================

# 初始化日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$REPO_PATH/sync.log"
}

# 切换到仓库目录
cd "$REPO_PATH" || {
    log "错误：仓库路径不存在！"
    exit 1
}

# 复制文件（带重试逻辑）
retry=0
while [ $retry -lt $MAX_RETRIES ]; do
    if cp -f "$SOURCE_FILE" .; then
        log "文件复制成功: $(ls -l 发货计划*)"
        break
    else
        log "文件复制失败，正在重试 ($((retry+1))/$MAX_RETRIES)"
        retry=$((retry+1))
        sleep 5
    fi
done

# 检查是否复制成功
if [ $retry -eq $MAX_RETRIES ]; then
    log "错误：文件复制失败！"
    exit 1
fi

# Git 操作（带网络重试）
git add . >> "$REPO_PATH/sync.log" 2>&1
git commit -m "自动更新: $(date '+%Y-%m-%d %H:%M:%S')" >> "$REPO_PATH/sync.log" 2>&1

retry=0
while [ $retry -lt $MAX_RETRIES ]; do
    if git push origin main >> "$REPO_PATH/sync.log" 2>&1; then
        log "同步成功"
        exit 0
    else
        log "Git推送失败，正在重试 ($((retry+1))/$MAX_RETRIES)"
        retry=$((retry+1))
        sleep 10
    fi
done

log "错误：Git推送失败！"
exit 1