# �����ļ�·��
$REPO_PATH = "F:\GitHub\TVBOX"
$SOURCE_FILE = "F:\1.������ó�ɶ��ֹ�˾-�Ĵ��﹩����\�ֲ�-����\�ֽ���ƻ�-����С��\�����ƻ����˱���Ŀ������.xlsx"

# �л����ֿ�Ŀ¼
Set-Location -Path $REPO_PATH

# �����ļ���ǿ�Ƹ��ǣ�
try {
    Copy-Item -Path $SOURCE_FILE -Destination . -Force
    Write-Output "[$(Get-Date)] �ļ����Ƴɹ�" | Out-File -Append -FilePath "$REPO_PATH\sync.log"
} catch {
    Write-Output "[$(Get-Date)] ����: $_" | Out-File -Append -FilePath "$REPO_PATH\error.log"
    exit 1
}

# Git����
git add .
git commit -m "�Զ�����: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git push origin main