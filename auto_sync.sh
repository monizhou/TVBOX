#!/bin/bash

# ==================== 配置区域 ====================
# 仓库根目录 (根据你的截图，这里是 TVBOX 目录)
REPO_PATH="/f/GitHub/TVBOX"

# 源文件路径 (你的 Excel 文件全路径)
SOURCE_FILE="/f/1.中铁物贸成都分公司-四川物供中心/钢材-结算/钢筋发货计划-发丁小刚/发货计划（宜宾项目）汇总.xlsm"

# 日志文件路径
LOG_FILE="$REPO_PATH/sync.log"

# 最大重试次数
MAX_RETRIES=3
# ==================================================

# 定义日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 1. 检查并进入仓库目录
if [ ! -d "$REPO_PATH" ]; then
    echo "错误：仓库路径不存在 -> $REPO_PATH"
    exit 1
fi
cd "$REPO_PATH" || exit 1

# 2. 基础设置与清理
# 防止中文文件名乱码
git config core.quotepath false
# 设置字符集，防止日志乱码
export LANG="zh_CN.UTF-8"

# 清理可能残留的 Git 锁文件 (防止上次强制中断导致 Git 卡死)
if [ -f ".git/index.lock" ]; then
    rm -f ".git/index.lock"
    log "警告：检测到 index.lock 锁文件，已自动清理"
fi

# 3. 复制文件 (带重试)
# 提取文件名
FILENAME=$(basename "$SOURCE_FILE")
retry=0
copy_success=false

while [ $retry -lt $MAX_RETRIES ]; do
    if cp -f "$SOURCE_FILE" "./$FILENAME"; then
        copy_success=true
        log "文件复制成功: $FILENAME"
        break
    else
        log "文件复制失败，正在重试 ($((retry+1))/$MAX_RETRIES)..."
        retry=$((retry+1))
        sleep 5
    fi
done

if [ "$copy_success" = false ]; then
    log "严重错误：文件复制最终失败，请检查源文件是否被打开或占用！"
    exit 1
fi

# 4. Git 同步流程 (核心修复部分)

# 4.1 预先拉取：防止 'non-fast-forward' 错误
# 如果远程有更新，先合并到本地
log "准备同步，正在检查远程更新..."
git pull origin main >> "$LOG_FILE" 2>&1

# 4.2 检查是否有变动
# 如果文件没变，就不提交，避免产生大量无意义 commit
if [ -z "$(git status --porcelain)" ]; then
    log "检测结果：文件未发生变化，跳过提交。"
    exit 0
fi

# 4.3 提交变动
git add . >> "$LOG_FILE" 2>&1
git commit -m "自动更新: $(date '+%Y-%m-%d %H:%M:%S') - $FILENAME" >> "$LOG_FILE" 2>&1

# 4.4 推送 (带重试与冲突修复)
retry=0
while [ $retry -lt $MAX_RETRIES ]; do
    # 尝试推送
    if git push origin main >> "$LOG_FILE" 2>&1; then
        log "同步成功：已推送到 GitHub"
        exit 0
    else
        log "推送失败，可能是远程又有更新，正在尝试 '拉取并合并' 后重试 ($((retry+1))/$MAX_RETRIES)..."
        
        # 关键操作：推送失败通常是因为远程比本地新，所以再次拉取
        git pull origin main >> "$LOG_FILE" 2>&1
        
        retry=$((retry+1))
        sleep 10
    fi
done

log "严重错误：Git 推送最终失败，请手动检查网络或冲突！"
exit 1