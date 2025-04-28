# 配置文件路径
$REPO_PATH = "F:\GitHub\TVBOX"
$SOURCE_FILE = "F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx"

# 切换到仓库目录
Set-Location -Path $REPO_PATH

# 复制文件（强制覆盖）
try {
    Copy-Item -Path $SOURCE_FILE -Destination . -Force
    Write-Output "[$(Get-Date)] 文件复制成功" | Out-File -Append -FilePath "$REPO_PATH\sync.log"
} catch {
    Write-Output "[$(Get-Date)] 错误: $_" | Out-File -Append -FilePath "$REPO_PATH\error.log"
    exit 1
}

# Git操作
git add .
git commit -m "自动更新: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git push origin main