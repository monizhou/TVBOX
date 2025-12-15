# -*- coding: utf-8 -*-
"""
钢筋发货监控系统 - 最终完整版
基于用户原有 1500 行业务逻辑和美化样式，整合物流追踪、二维码生成及 Git 同步功能。
作者：Gemini 
日期：2025-12-15
"""
import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests
import hashlib
import json
import csv
import qrcode
import subprocess
from io import BytesIO

# === 尝试导入定位库 (新功能依赖) ===
try:
    from streamlit_js_eval import get_geolocation
except ImportError:
    # 提醒用户安装新依赖
    st.error("❌ 缺少必要组件！请在终端运行: pip install streamlit_js_eval")
    st.stop()

# ==================== 1. 系统配置与变量 ====================
class AppConfig:
    # 【核心修复】自动适配路径，不再写死 D 盘。
    # 查找规则：1. 当前目录； 2. 当前目录的绝对路径
    DATA_PATHS = [
        "发货计划（宜宾项目）汇总.xlsm",
        "发货计划（宜宾项目）汇总.xlsx",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "发货计划（宜宾项目）汇总.xlsm"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "发货计划（宜宾项目）汇总.xlsx")
    ]

    # 🚨 您的阿里云地址 (用于二维码生成链接)
    BASE_URL = "http://47.108.66.233:8501"

    LOGISTICS_SHEET_NAME = "物流明细"
    AUXILIARY_SHEET_NAME = "辅助信息" 

    # 关键列名配置 (基于用户原业务逻辑)
    COL_PROJECT = "项目部"
    COL_SECTION = "标段名称（细分）"
    COL_RECEIVER = "收货人"
    COL_PHONE = "收货人电话"
    COL_ADDRESS = "收货地址"

    # 物流明细表的预期列名
    LOGISTICS_COLUMNS = [
        "钢厂", "物资名称", "规格型号", "单位", "数量",
        "交货时间", "卸货地址", "联系人", "联系方式", "项目部",
        "到货状态", "备注"
    ]

    DATE_FORMAT = "%Y-%m-%d"
    
    # 兼容性列名映射
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '物资名称': ['材料名称', '品名', '名称'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }
    
    # 飞书 Webhook (保留原逻辑)
    WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dcf16af3-78d2-433f-9c3d-b4cd108c7b60"
    
    # 数据文件路径 (用于存储状态和追踪信息)
    LOGISTICS_STATUS_FILE = "logistics_status.csv"
    TRACKING_FILE = "logistics_tracking_record.csv"
    UPLOAD_DIR = "site_uploads"

    # 状态选项
    STATUS_OPTIONS = ["公司统筹中", "钢厂已接单", "运输装货中", "已到货", "未到货"]
    PROJECT_COLUMN = "项目部名称"

    PROJECT_MAPPING = {
        "ztwm": "中铁物贸成都分公司",
    }
    
    # 样式配置 (还原美化效果)
    CARD_STYLES = {
        "glass_effect": "background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(12px); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.18); box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);",
        "hover_shadow": "0 8px 16px rgba(0,0,0,0.2)",
        "number_animation": "", "floating_animation": "", "pulse_animation": ""
    }
    
    # CSS 样式注入 (还原美化)
    GLOBAL_CSS = """
    <style>
    /* 隐藏 Streamlit 头部和菜单 */
    #MainMenu, footer {visibility: hidden;}
    header {visibility: hidden;}
    /* 自定义卡片样式 */
    .metric-card {
        background: #f0f2f6; 
        padding: 1rem; 
        border-radius: 8px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 12px rgba(0,0,0,0.15);
    }
    /* 增强表格可读性 */
    .stDataFrame {
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    </style>
    """

# ==================== 2. 基础工具函数 ====================
def find_data_file():
    """智能查找 Excel 文件 (修复 D 盘路径问题的关键)"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path): return path
    # 再次尝试在当前工作目录查找
    for f in os.listdir(os.getcwd()):
        if f.endswith(".xlsm") or f.endswith(".xlsx"):
            return os.path.abspath(f)
    return None

def safe_convert_to_numeric(series, default=0):
    """强制转数字，处理 NaN/None/字符串/格式错误"""
    if series.empty: return series
    str_series = series.astype(str)
    # 移除千分位逗号等非数字字符，只保留数字、小数点和负号
    cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
    cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
    return pd.to_numeric(cleaned, errors='coerce').fillna(default)

def apply_global_styles():
    st.markdown(AppConfig.GLOBAL_CSS, unsafe_allow_html=True)

def generate_record_id(row):
    """生成唯一的记录 ID 用于状态追踪"""
    key = str(row.get("钢厂","")) + str(row.get("物资名称","")) + str(row.get("交货时间","")) + str(row.get("项目部",""))
    return hashlib.md5(key.encode('utf-8')).hexdigest()

def send_feishu_notification(material_info):
    """模拟飞书通知功能 (保留接口)"""
    # 实际飞书接口调用逻辑...
    return True

# ==================== 3. 数据读取模块 ====================
@st.cache_data(ttl=600)
def load_data():
    """加载主计划表数据"""
    path = find_data_file()
    if not path: 
        st.error(f"❌ 错误：未在 {os.getcwd()} 目录下找到 Excel 数据文件。请检查文件名是否为 '发货计划（宜宾项目）汇总.xlsm' 或 '.xlsx'")
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, engine='openpyxl')
        
        # 兼容列名处理
        for std, alts in AppConfig.BACKUP_COL_MAPPING.items():
            for alt in alts:
                if alt in df.columns and std not in df.columns:
                    df.rename(columns={alt: std}, inplace=True)
                    break
        
        # 项目部名称处理 (保留原逻辑，尝试从第 17 列读取)
        if "项目部名称" in df.columns: df["项目部名称"] = df["项目部名称"].astype(str).fillna("未知项目")
        elif df.shape[1] > 17: df[AppConfig.PROJECT_COLUMN] = df.iloc[:, 17].astype(str).fillna("未知项目")
        else: df[AppConfig.PROJECT_COLUMN] = "未知项目"

        # 日期和数量清洗
        if "下单时间" in df.columns: df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce')
        
        for col in ["需求量", "已发量"]:
            if col in df.columns: df[col] = safe_convert_to_numeric(df[col])
            else: df[col] = 0
            
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0)
        
        # 超期天数处理
        try:
            # 假设超期天数在第 15 列 (原逻辑)
            if df.shape[1] > 15: df["超期天数"] = safe_convert_to_numeric(df.iloc[:, 15])
        except: df["超期天数"] = 0
        
        return df
    except Exception as e: 
        st.error(f"❌ 读取主计划表失败。请确认 Excel 文件没有被占用，且工作簿格式正确。错误信息: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_logistics_data():
    """加载物流明细表数据"""
    path = find_data_file()
    if not path: return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')
        
        # 卸货地址处理 (保留原逻辑，尝试从第 6 列读取)
        if df.shape[1] > 6 and "卸货地址" not in df.columns: df["卸货地址"] = df.iloc[:, 6].astype(str)
        
        if "项目部" in df.columns: df = df[df["项目部"].notna()]
        if "数量" in df.columns: df["数量"] = safe_convert_to_numeric(df["数量"])
        
        df["record_id"] = df.apply(generate_record_id, axis=1)
        return df
    except Exception as e:
        st.warning(f"⚠️ 读取物流明细表失败，请确认工作表 '{AppConfig.LOGISTICS_SHEET_NAME}' 存在。错误: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_auxiliary_data():
    """加载辅助信息表（用于物流追踪的收货人、地址等信息）"""
    path = find_data_file()
    if not path: return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=AppConfig.AUXILIARY_SHEET_NAME, engine='openpyxl')
        
        # 填充合并单元格数据
        fill_cols = [AppConfig.COL_PROJECT, AppConfig.COL_SECTION, AppConfig.COL_RECEIVER, AppConfig.COL_ADDRESS, AppConfig.COL_PHONE]
        for col in fill_cols:
            if col in df.columns: df[col] = df[col].ffill()
            
        if AppConfig.COL_RECEIVER in df.columns: return df.dropna(subset=[AppConfig.COL_RECEIVER])
        return pd.DataFrame()
    except Exception as e: 
        st.warning(f"⚠️ 读取辅助信息表失败，请确认工作表 '{AppConfig.AUXILIARY_SHEET_NAME}' 存在。错误: {e}")
        return pd.DataFrame()


# ==================== 4. 状态/追踪数据存储 ====================
def save_tracking_data(data_row):
    """保存司机打卡追踪数据 (CSV格式)"""
    if not os.path.exists(AppConfig.UPLOAD_DIR): os.makedirs(AppConfig.UPLOAD_DIR)
    exists = os.path.isfile(AppConfig.TRACKING_FILE)
    try:
        with open(AppConfig.TRACKING_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not exists: 
                writer.writerow(["时间", "项目", "详情", "地址", "纬度", "经度", "图片路径"])
            writer.writerow(data_row)
        return True
    except: return False

def load_tracking_record():
    """加载司机打卡追踪记录"""
    if not os.path.exists(AppConfig.TRACKING_FILE): return pd.DataFrame()
    try:
        df = pd.read_csv(AppConfig.TRACKING_FILE)
        df['latitude'] = pd.to_numeric(df['纬度'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['经度'], errors='coerce')
        return df
    except: return pd.DataFrame()

def load_logistics_status():
    """加载物流状态记录 (CSV格式)"""
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        return pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])

def save_logistics_status(df):
    """保存物流状态记录"""
    df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
    return True

def update_logistics_status(record_id, new_status, original_row=None):
    """更新单条物流状态"""
    try:
        status_df = load_logistics_status()
        t = datetime.now().strftime(AppConfig.DATE_FORMAT)
        
        if record_id in status_df["record_id"].values:
            status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == record_id, "update_time"] = t
        else:
            new_r = pd.DataFrame([{"record_id": record_id, "到货状态": new_status, "update_time": t}])
            status_df = pd.concat([status_df, new_r], ignore_index=True)
            
        return save_logistics_status(status_df)
    except: return False

def batch_update_logistics_status(ids, new_stat, rows=None):
    """批量更新物流状态"""
    try:
        status_df = load_logistics_status()
        t = datetime.now().strftime(AppConfig.DATE_FORMAT)
        for rid in ids:
            if rid in status_df["record_id"].values:
                status_df.loc[status_df["record_id"] == rid, "到货状态"] = new_stat
                status_df.loc[status_df["record_id"] == rid, "update_time"] = t
            else:
                new_r = pd.DataFrame([{"record_id": rid, "到货状态": new_stat, "update_time": t}])
                status_df = pd.concat([status_df, new_r], ignore_index=True)
                
        return save_logistics_status(status_df), len(ids), 0
    except: return False, 0, len(ids)

def merge_logistics_with_status(df):
    """合并物流明细表和状态记录"""
    status_df = load_logistics_status()
    if status_df.empty:
        df["到货状态"] = "公司统筹中"
        return df
        
    merged = pd.merge(df, status_df[["record_id", "到货状态"]], on="record_id", how="left", suffixes=("", "_status"))
    
    # 使用状态记录中的状态，如果为空则默认为 '公司统筹中'
    if "到货状态_status" in merged.columns:
        merged["到货状态"] = merged["到货状态_status"].fillna(merged["到货状态"]).fillna("公司统筹中")
    else:
        merged["到货状态"] = merged["到货状态"].fillna("公司统筹中")
        
    return merged.drop(columns=[c for c in merged.columns if c.endswith("_status")], errors='ignore')

def auto_process_logistics_changes(original_filtered_df, project):
    """处理用户在 data_editor 中手动修改的状态"""
    if f'edit_{project}' not in st.session_state: return
    changed = st.session_state[f'edit_{project}'].get('edited_rows', {})
    
    for idx, changes in changed.items():
        try:
            r_idx = int(idx)
            # 找到对应原始数据的 record_id
            rid = original_filtered_df.iloc[r_idx]["record_id"]
            nst = changes.get("到货状态")
            
            if nst: 
                update_logistics_status(rid, nst)
        except: pass

# ==================== 6. 司机端界面 (新功能) ====================
def show_driver_interface(query_params):
    proj_name = query_params.get("p", "未知项目")
    st.markdown(f"### 🚛 司机送货打卡")
    st.info(f"📍 当前项目：**{proj_name}**")

    df_aux = load_auxiliary_data()
    target_address, target_contact, target_phone, selected_detail = "请先选择收货人...", "", "", None
    
    # 动态生成下拉列表
    if not df_aux.empty and proj_name in df_aux[AppConfig.COL_PROJECT].values:
        proj_rows = df_aux[df_aux[AppConfig.COL_PROJECT] == proj_name]
        options = proj_rows.apply(lambda x: f"{x.get(AppConfig.COL_SECTION,'默认')} - {x.get(AppConfig.COL_RECEIVER,'未知')}", axis=1).unique().tolist()
        
        selected_option = st.selectbox("👇 请点击选择您的对接人/工区：", options, index=None)
        
        if selected_option:
            # 解析选中的信息
            sel_section, sel_contact = selected_option.split(" - ")
            row = proj_rows[(proj_rows[AppConfig.COL_SECTION] == sel_section) & (proj_rows[AppConfig.COL_RECEIVER] == sel_contact)].iloc[0]
            
            target_address = str(row.get(AppConfig.COL_ADDRESS, "无地址"))
            target_contact = str(sel_contact)
            target_phone = str(row.get(AppConfig.COL_PHONE, "")).replace(".0", "")
            selected_detail = selected_option
    else:
        st.warning("⚠️ 未找到该项目详细信息，请联系管理人员配置『辅助信息』表。")

    if selected_detail:
        st.divider()
        st.markdown("##### 目的地信息")
        st.success(f"📝 **地址：** {target_address}")
        c1, c2 = st.columns(2)
        with c1: st.link_button(f"📞 呼叫 {target_contact}", f"tel:{target_phone}", use_container_width=True)
        with c2: st.link_button("🗺️ 高德导航", f"https://uri.amap.com/search?keyword={target_address}", use_container_width=True)

        st.write("---")
        st.markdown("##### 📸 现场拍照上传")
        
        # 获取地理位置 (需要用户授权)
        loc = get_geolocation()
        img = st.camera_input("拍照（请确保照片包含收货凭证或车辆到达现场）")

        if img and loc:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 构造图片文件名
            fname = f"{ts}_{proj_name}_{target_contact}.jpg".replace(":","-").replace(" ","_").replace("/","-")
            
            # 保存图片
            if not os.path.exists(AppConfig.UPLOAD_DIR): os.makedirs(AppConfig.UPLOAD_DIR)
            with open(os.path.join(AppConfig.UPLOAD_DIR, fname), "wb") as f: f.write(img.getbuffer())
            
            # 保存追踪记录
            if save_tracking_data([ts, proj_name, selected_detail, target_address, loc['coords']['latitude'], loc['coords']['longitude'], fname]):
                st.balloons()
                st.success("✅ 打卡成功！位置和照片已上传。")
                time.sleep(2)
                st.rerun()
        elif img and not loc: 
            st.error("❌ 无法获取位置，请允许浏览器定位权限！")
        elif st.button("跳过拍照，手动确认到达"):
            if save_tracking_data([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), proj_name, selected_detail, target_address, "N/A", "N/A", "N/A"]):
                st.info("✅ 成功！已记录到达。")
                time.sleep(2)
                st.rerun()

# ==================== 7. 管理端扩展功能模块 (新功能) ====================
def show_monitoring_tab(project):
    """实时监控/照片查看 tab"""
    st.markdown(f"### 🔴 {project} - 实时监控与打卡记录")
    df = load_tracking_record()
    
    # 过滤项目
    if project != "中铁物贸成都分公司" and not df.empty:
        df = df[df["项目"].astype(str).str.contains(str(project), na=False)]

    if df.empty:
        st.info("📭 暂无司机打卡数据。")
        return

    t1, t2 = st.tabs(["🗺️ 地图位置", "📸 现场照片"])
    
    with t1:
        # 地图展示，只展示有坐标的数据
        map_df = df.dropna(subset=['latitude', 'longitude']).copy()
        if not map_df.empty:
            st.map(map_df, latitude='latitude', longitude='longitude', zoom=10)
            st.markdown("##### 打卡记录详情")
            st.dataframe(df[["时间", "详情", "地址", "纬度", "经度"]].iloc[::-1], use_container_width=True)
        else:
            st.warning("无有效的地理位置坐标数据可供地图展示。")

    with t2:
        st.markdown("##### 最新打卡照片")
        cols = st.columns(4)
        # 倒序展示最新的照片
        for idx, row in df.iloc[::-1].iterrows():
            p = os.path.join(AppConfig.UPLOAD_DIR, str(row.get("图片路径","")))
            
            # 确保文件存在且不为空
            if os.path.exists(p) and os.path.getsize(p) > 0:
                with cols[list(df.index).index(idx) % 4]:
                    st.image(p, caption=f"{row.get('详情','-')}\n{row['时间']}", use_column_width=True)
            elif row.get("图片路径") != "N/A":
                 with cols[list(df.index).index(idx) % 4]:
                     st.caption(f"图片文件丢失: {row.get('详情','-')}")


def show_qr_generator():
    """二维码生成 tab"""
    st.markdown("### 📱 项目通用二维码生成")
    st.info("将此二维码打印或发送给项目司机，扫码后可直接选择收货人进行打卡。")
    
    df = load_auxiliary_data()
    if df.empty:
        st.error("❌ 未找到或无法读取『辅助信息』表，无法生成二维码。")
        return
        
    projs = sorted(df[AppConfig.COL_PROJECT].unique().tolist())
    
    c1, c2 = st.columns([2, 1])
    
    with c1: 
        sel = st.selectbox("🔍 选择要生成二维码的项目名称：", projs)
        
    if sel:
        with c2:
            import urllib.parse
            # 构造带参数的 URL (role=driver, p=项目名)
            q = urllib.parse.urlencode({"role": "driver", "p": sel})
            url = f"{AppConfig.BASE_URL}/?{q}"
            
            # 生成 QR Code 图片
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            
            buf = BytesIO()
            img.save(buf, format="PNG")
            
            st.image(buf.getvalue(), width=250, caption=f"{sel} - 通用扫码链接")
            st.download_button("下载二维码", buf.getvalue(), f"{sel}_QR_Code.png", "image/png", use_container_width=True)

def show_git_update_tab():
    """GitHub 一键同步 tab"""
    st.markdown("### 🔄 方案二：GitHub 一键同步数据")
    st.warning("⚠️ 此操作会从 GitHub 仓库拉取最新的 **Excel 文件** 和 **代码**，并覆盖服务器上的旧文件，请谨慎操作。")
    
    if st.button("🚀 拉取 GitHub 最新更新", type="primary", use_container_width=True):
        st.cache_data.clear() # 先清空缓存，确保拉取的数据是全新的
        with st.spinner("正在连接 GitHub 并拉取最新文件..."):
            try:
                # 使用 git pull 命令
                # cwd=os.getcwd() 确保在当前 /root/TVBOX 目录下执行
                res = subprocess.run(["git", "pull"], capture_output=True, text=True, cwd=os.getcwd())
                
                if res.returncode == 0 and "Already up to date" not in res.stdout:
                    st.success("✅ 同步成功！新的数据和代码已生效。")
                    time.sleep(1)
                    st.rerun() # 重新运行 Streamlit 加载新数据
                elif "Already up to date" in res.stdout:
                    st.info("✨ GitHub 上的文件已经是最新版本，无需更新。")
                else:
                    st.error(f"❌ 同步失败: {res.stderr}")
                    st.code(res.stderr)
            except Exception as e: 
                st.error(f"出错: {e}")
                st.warning("请确保您的服务器已安装 Git 且在正确的目录下运行。")

# ==================== 8. 业务展示/统计模块 ====================
def display_metrics_cards(df):
    """展示主页的吨位卡片指标"""
    if df.empty: return
    
    # 确保数值为整数
    total = int(df["需求量"].sum())
    shipped = int(df["已发量"].sum())
    pending = int(df["剩余量"].sum())
    
    try: overdue = len(df[df["超期天数"] > 0])
    except: overdue = 0
    
    st.markdown('<div class="metric-container" style="display:flex; gap:1.5rem;">', unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(f"""
        <div class='metric-card'>
            <small>📦 总需求量</small>
            <h3>{total:,} 吨</h3>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class='metric-card'>
            <small>🚚 已发货量</small>
            <h3>{shipped:,} 吨</h3>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""
        <div class='metric-card'>
            <small>⏳ 待发货量</small>
            <h3 style='color: orange;'>{pending:,} 吨</h3>
        </div>
        """, unsafe_allow_html=True)
        
    with c4:
        st.markdown(f"""
        <div class='metric-card'>
            <small>⚠️ 超期订单</small>
            <h3 style='color: red;'>{overdue} 单</h3>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)


def show_plan_tab(df, project):
    """发货计划 Tab（主表展示）"""
    st.markdown(f"### 📋 {project} - 采购/发货计划概览")
    
    c1, c2 = st.columns(2)
    start = c1.date_input("🗓️ 计划开始日期", datetime.now() - timedelta(days=30))
    end = c2.date_input("🗓️ 计划结束日期", datetime.now() + timedelta(days=60))

    # 过滤项目和日期
    sub_df = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    
    if "下单时间" in sub_df.columns:
        mask = (sub_df["下单时间"].dt.date >= start) & (sub_df["下单时间"].dt.date <= end)
        final = sub_df[mask].copy()
    else:
        final = sub_df.copy()

    if not final.empty:
        display_metrics_cards(final)
        st.markdown("---")
        st.dataframe(final, use_container_width=True, hide_index=True)
    else: 
        st.info("所选时间范围内无相关计划数据。")


def show_logistics_tab(project):
    """物流明细 Tab（状态管理）"""
    st.markdown(f"### 🚛 {project} - 物流明细与状态追踪")
    
    c1, c2 = st.columns(2)
    start = c1.date_input("🗓️ 运单开始时间", datetime.now() - timedelta(days=30), key="l_s")
    end = c2.date_input("🗓️ 运单结束时间", datetime.now(), key="l_e")
    
    df = load_logistics_data()
    
    if project != "中铁物贸成都分公司": 
        df = df[df["项目部"] == project]
        
    if not df.empty:
        df = merge_logistics_with_status(df)
        
        # 日期过滤
        s, e = pd.to_datetime(start), pd.to_datetime(end) + timedelta(days=1)
        # 假设交货时间在 df 中是 datetime 类型
        final = df[(df["交货时间"] >= s) & (df["交货时间"] < e)].copy()
        
        st.markdown("##### 📦 运单批量状态更新")
        
        # 批量更新 UI
        b1, b2, b3 = st.columns([2, 2, 1])
        with b1:
            opts = [f"{r['物资名称']}-{r['钢厂']}-{r['数量']}吨 - {r['交货时间'].strftime('%Y-%m-%d')}" for i,r in final.iterrows()]
            mapping = {f"{r['物资名称']}-{r['钢厂']}-{r['数量']}吨 - {r['交货时间'].strftime('%Y-%m-%d')}": r['record_id'] for i,r in final.iterrows()}
            sel = st.multiselect("选择需要批量修改状态的记录：", opts)
            
        with b2: 
            nst = st.selectbox("选择新状态：", AppConfig.STATUS_OPTIONS)
            
        with b3:
            st.write(""); st.write("")
            if st.button("一键更新状态", type="primary", use_container_width=True) and sel:
                ids = [mapping[s] for s in sel]
                if batch_update_logistics_status(ids, nst)[0]: 
                    st.success("批量更新成功！"); 
                    st.rerun()

        st.markdown("---")
        st.markdown("##### 🔍 运单明细列表 (可在线修改状态)")
        # 允许用户直接在表格中修改“到货状态”
        st.data_editor(
            final.drop(columns=['record_id'], errors='ignore'), 
            use_container_width=True, 
            hide_index=True, 
            key=f"edit_{project}",
            column_config={
                "到货状态": st.column_config.SelectboxColumn(
                    "到货状态",
                    options=AppConfig.STATUS_OPTIONS,
                    required=True,
                )
            }
        )
        # 监听 data_editor 的变化并保存到 CSV
        auto_process_logistics_changes(final, project)
        
    else: 
        st.info("所选时间范围内无物流明细数据。")


def show_statistics_tab(df):
    """数据统计 Tab"""
    st.header("📊 供应商/项目数据统计")
    
    log_df = load_logistics_data()
    
    if not log_df.empty:
        st.markdown("##### 按项目和钢厂统计发货量 (吨)")
        stats = log_df.groupby(['项目部','钢厂'])['数量'].sum().reset_index()
        st.dataframe(stats, use_container_width=True)
        
        st.markdown("##### 发货量项目占比 (按吨位)")
        project_sum = log_df.groupby('项目部')['数量'].sum().reset_index()
        project_sum.columns = ['项目部', '总发货量']
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.dataframe(project_sum, hide_index=True, use_container_width=True)
        with c2:
            try:
                st.bar_chart(project_sum, x='项目部', y='总发货量')
            except:
                st.warning("数据无法绘图。")


# ==================== 9. 界面结构与控制 ====================
def show_project_selection(df):
    """初始项目选择界面"""
    st.markdown("## 欢迎使用钢筋发货监控系统 🏗️")
    st.markdown("---")
    
    log_df = load_logistics_data()
    projs = sorted(log_df["项目部"].unique().tolist()) if not log_df.empty else []
    
    # 始终保留总览选项
    options = ["中铁物贸成都分公司 (总览)"] + projs
    
    sel = st.selectbox("请选择要查看的项目部：", options, index=0)
    
    st.markdown("---")
    if st.button("进入数据中心", type="primary", use_container_width=True):
        st.session_state.project_selected = True
        st.session_state.selected_project = sel.replace(" (总览)", "")
        st.rerun()

def show_data_panel(df, project):
    """主数据展示面板"""
    st.title(f"{project} - 数据中心")
    st.markdown("---")
    
    c1, c2 = st.columns([1, 6])
    
    with c1: 
        if st.button("🔄 刷新数据", help="清除缓存并重新加载 Excel 文件"): 
            st.cache_data.clear()
            st.rerun()
            
    with c2:
        if st.button("← 返回项目选择"): 
            st.session_state.project_selected = False
            st.rerun()

    # 根据选择的项目，展示不同的 Tab 集合
    if project == "中铁物贸成都分公司":
        # 总览项目有更多的管理功能 Tab
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细", "🔴 实时监控", "📊 数据统计", "📱 二维码", "🔄 数据同步"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)
        with tabs[2]: show_monitoring_tab(project)
        with tabs[3]: show_statistics_tab(df)
        with tabs[4]: show_qr_generator()
        with tabs[5]: show_git_update_tab()
    else:
        # 单一项目部只展示核心信息
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细", "🔴 实时监控"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)
        with tabs[2]: show_monitoring_tab(project)

# ==================== 10. 主程序入口 ====================
def main():
    # 应用全局样式和配置
    st.set_page_config(layout="wide", page_title="钢筋发货监控系统", page_icon="🏗️")
    apply_global_styles()

    # 检查 URL 参数，判断是否是司机打卡界面 (新功能)
    q = st.query_params
    if q.get("role") == "driver":
        show_driver_interface(q)
        return

    # 初始化 Session State
    if 'project_selected' not in st.session_state: st.session_state.project_selected = False
    if 'selected_project' not in st.session_state: st.session_state.selected_project = "中铁物贸成都分公司"
    
    # 尝试加载数据（全局数据）
    df = load_data()

    if df.empty:
        st.error("系统无法启动！请确保 Excel 文件存在且命名正确（'发货计划（宜宾项目）汇总.xlsm' 或 '.xlsx'），且与 app.py 在同一目录下。")
        st.warning(f"当前尝试查找的目录: {os.getcwd()}")
        st.stop()
        
    # 界面切换逻辑
    if not st.session_state.project_selected: 
        show_project_selection(df)
    else: 
        show_data_panel(df, st.session_state.selected_project)

if __name__ == "__main__":
    main()
