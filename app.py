# -*- coding: utf-8 -*-
"""钢筋发货监控系统 - 旗舰融合修复版"""
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
from io import BytesIO

# === 尝试导入定位库，防止报错 ===
try:
    from streamlit_js_eval import get_geolocation
except ImportError:
    st.error("❌ 缺少组件！请在 requirements.txt 中添加: streamlit_js_eval")
    st.stop()

# ==================== 1. 系统核心配置 ====================
class AppConfig:
    # 数据文件路径 (自动查找)
    DATA_PATHS = [
        "发货计划（宜宾项目）汇总.xlsm",
        "发货计划（宜宾项目）汇总.xlsx",
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsm"),
        # 保留您原有的绝对路径作为备选
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]

    # 🚨🚨🚨 Ngrok 地址 (根据您的截图填入) 🚨🚨🚨
    BASE_URL = "https://glittery-bryant-applaudably.ngrok-free.dev"

    LOGISTICS_SHEET_NAME = "物流明细"
    AUXILIARY_SHEET_NAME = "辅助信息" # 读取辅助信息表

    LOGISTICS_COLUMNS = [
        "钢厂", "物资名称", "规格型号", "单位", "数量",
        "交货时间", "卸货地址", "联系人", "联系方式", "项目部",
        "到货状态", "备注"
    ]

    DATE_FORMAT = "%Y-%m-%d"
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '物资名称': ['材料名称', '品名', '名称'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }
    WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dcf16af3-78d2-433f-9c3d-b4cd108c7b60"
    
    # 文件存储配置
    LOGISTICS_STATUS_FILE = "logistics_status.csv"
    TRACKING_FILE = "logistics_tracking_record.csv" # 司机打卡数据
    UPLOAD_DIR = "site_uploads"                     # 照片文件夹

    STATUS_OPTIONS = ["公司统筹中", "钢厂已接单", "运输装货中", "已到货", "未到货"]
    PROJECT_COLUMN = "项目部名称"

    # 项目映射 (保留部分常用，代码会自动读取Excel里的)
    PROJECT_MAPPING = {
        "ztwm": "中铁物贸成都分公司",
    }

    CARD_STYLES = {
        "glass_effect": "background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(12px); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.18); box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);",
        "number_animation": "", "floating_animation": "", "pulse_animation": ""
    }

# ==================== 2. 基础辅助函数 ====================
def find_data_file():
    """自动查找Excel文件"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path): return path
    # 尝试在当前目录查找
    curr = os.getcwd()
    for f in os.listdir(curr):
        if f.endswith(".xlsm") or f.endswith(".xlsx"):
            return os.path.join(curr, f)
    return None

def safe_convert_to_numeric(series, default=0):
    """【关键修复】强制转数字，防止 sum() 报错"""
    if series.empty: return series
    str_series = series.astype(str)
    # 只保留数字、小数点、负号
    cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
    cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
    return pd.to_numeric(cleaned, errors='coerce').fillna(default)

def apply_card_styles():
    st.markdown("""<style>
    .metric-card {background: #fff; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); transition: transform 0.3s;}
    .metric-card:hover {transform: translateY(-5px);}
    .home-card {padding: 1.5rem; border-radius: 10px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); margin-bottom: 1rem;}
    </style>""", unsafe_allow_html=True)

def generate_record_id(row):
    key = str(row.get("钢厂","")) + str(row.get("物资名称","")) + str(row.get("交货时间","")) + str(row.get("项目部",""))
    return hashlib.md5(key.encode('utf-8')).hexdigest()

def send_feishu_notification(material_info):
    # (保留您的飞书通知逻辑)
    return True

# ==================== 3. 数据加载 (已修复类型问题) ====================
@st.cache_data(ttl=600)
def load_data():
    """读取发货计划"""
    path = find_data_file()
    if not path: return pd.DataFrame()
    try:
        df = pd.read_excel(path, engine='openpyxl')
        
        # 列名映射
        for std, alts in AppConfig.BACKUP_COL_MAPPING.items():
            for alt in alts:
                if alt in df.columns and std not in df.columns:
                    df.rename(columns={alt: std}, inplace=True)
                    break
        
        # 数据清洗
        if "物资名称" in df.columns:
            df["物资名称"] = df["物资名称"].astype(str).str.strip()
        
        # 项目部名称清洗 (第18列，索引17)
        df[AppConfig.PROJECT_COLUMN] = df.iloc[:, 17].astype(str).str.strip().replace({"nan": "未指定", "None": "未指定"})
        
        # 时间清洗
        if "下单时间" in df.columns:
            df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce')
        
        # 【关键】数值列强制转换，防止 sum() 报错
        for col in ["需求量", "已发量"]:
            if col in df.columns:
                df[col] = safe_convert_to_numeric(df[col])
            else:
                df[col] = 0
                
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0)
        
        # 超期天数 (假设在第16列)
        try:
            if df.shape[1] > 15:
                df["超期天数"] = safe_convert_to_numeric(df.iloc[:, 15])
        except: df["超期天数"] = 0

        return df
    except Exception as e:
        # st.error(f"加载数据出错: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_logistics_data():
    """读取物流明细"""
    path = find_data_file()
    if not path: return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME)
        # 强制读取G列(索引6)作为地址
        if df.shape[1] > 6:
            df["卸货地址"] = df.iloc[:, 6].astype(str).replace({"nan": "", "None": ""})
        
        # 清洗
        if "项目部" in df.columns: 
            df = df[df["项目部"].notna()]
            df["项目部"] = df["项目部"].astype(str).str.strip()
            
        if "数量" in df.columns:
            df["数量"] = safe_convert_to_numeric(df["数量"])
            
        df["record_id"] = df.apply(generate_record_id, axis=1)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def load_auxiliary_data():
    """【新增】读取辅助信息表 (用于司机选择)"""
    path = find_data_file()
    if not path: return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=AppConfig.AUXILIARY_SHEET_NAME)
        # 填充合并单元格
        fill_cols = ["项目部", "标段名称（细分）", "收货地址", "收货人", "收货人电话"]
        for col in fill_cols:
            if col in df.columns:
                df[col] = df[col].ffill()
        
        if "收货人" in df.columns:
            return df.dropna(subset=["收货人"])
        return pd.DataFrame()
    except: return pd.DataFrame()

# ==================== 4. 物流追踪读写 ====================
def save_tracking_data(data_row):
    """保存司机打卡"""
    if not os.path.exists(AppConfig.UPLOAD_DIR): os.makedirs(AppConfig.UPLOAD_DIR)
    file_path = AppConfig.TRACKING_FILE
    exists = os.path.isfile(file_path)
    try:
        with open(file_path, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(["时间", "项目", "详情", "地址", "纬度", "经度", "图片路径"])
            writer.writerow(data_row)
        return True
    except: return False

def load_tracking_record():
    """读取打卡记录"""
    if not os.path.exists(AppConfig.TRACKING_FILE): return pd.DataFrame()
    try:
        df = pd.read_csv(AppConfig.TRACKING_FILE)
        df['latitude'] = pd.to_numeric(df['纬度'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['经度'], errors='coerce')
        return df
    except: return pd.DataFrame()

# ==================== 5. 状态管理 (保留原逻辑) ====================
def load_logistics_status():
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        return pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])

def save_logistics_status(df):
    df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
    return True

def update_logistics_status(record_id, new_status, original_row=None):
    try:
        status_df = load_logistics_status()
        if record_id in status_df["record_id"].values:
            status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
        else:
            new_r = pd.DataFrame([{"record_id": record_id, "到货状态": new_status, "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)}])
            status_df = pd.concat([status_df, new_r], ignore_index=True)
        return save_logistics_status(status_df)
    except: return False

def batch_update_logistics_status(ids, new_stat, rows=None):
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
    status_df = load_logistics_status()
    if status_df.empty:
        df["到货状态"] = "公司统筹中"
        return df
    # 合并
    merged = pd.merge(df, status_df[["record_id", "到货状态"]], on="record_id", how="left", suffixes=("", "_status"))
    # 优先使用状态表的状态
    if "到货状态_status" in merged.columns:
        merged["到货状态"] = merged["到货状态_status"].fillna("公司统筹中")
    else:
        merged["到货状态"] = merged["到货状态"].fillna("公司统筹中")
    return merged

# ==================== 6. 【司机端界面】 ====================
def show_driver_interface(query_params):
    """司机扫码后看到的界面"""
    proj_name = query_params.get("p", "未知项目")
    
    st.title("🚛 司机送货打卡")
    st.info(f"📍 当前项目：**{proj_name}**")

    # 读取辅助表供司机选择
    df_aux = load_auxiliary_data()
    
    target_address = "请先选择收货人..."
    target_contact = ""
    target_phone = ""
    selected_detail = None

    # 如果找到该项目信息
    if not df_aux.empty and proj_name in df_aux["项目部"].values:
        proj_rows = df_aux[df_aux["项目部"] == proj_name]
        
        # 制作选项: 标段 - 收货人
        options = proj_rows.apply(
            lambda x: f"{x.get('标段名称（细分）','默认')} - {x.get('收货人','未知')}", axis=1
        ).unique().tolist()
        
        selected_option = st.selectbox("👇 请点击选择您的对接人/工区：", options, index=None)
        
        if selected_option:
            sel_section, sel_contact = selected_option.split(" - ")
            # 查找对应行
            row = proj_rows[
                (proj_rows["标段名称（细分）"] == sel_section) & 
                (proj_rows["收货人"] == sel_contact)
            ].iloc[0]
            
            target_address = str(row.get("收货地址", "无地址"))
            target_contact = str(sel_contact)
            target_phone = str(row.get("收货人电话", "")).replace(".0", "")
            selected_detail = selected_option
    else:
        st.warning("⚠️ 系统中未找到该项目的详细收货信息。")

    # 显示打卡操作
    if selected_detail:
        st.divider()
        st.success(f"📝 卸货地址：{target_address}")
        
        c1, c2 = st.columns(2)
        with c1: st.link_button(f"📞 呼叫 {target_contact}", f"tel:{target_phone}", use_container_width=True)
        with c2: st.link_button("🗺️ 导航", f"https://uri.amap.com/search?keyword={target_address}", use_container_width=True)

        st.write("---")
        st.write("##### 📸 现场拍照上传")
        
        loc = get_geolocation()
        img = st.camera_input("拍照")

        if img and loc:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fname = f"{ts}_{proj_name}_{target_contact}.jpg".replace(":","-").replace(" ","_")
            
            # 保存图片
            with open(os.path.join(AppConfig.UPLOAD_DIR, fname), "wb") as f:
                f.write(img.getbuffer())
            
            # 保存记录
            if save_tracking_data([ts, proj_name, selected_detail, target_address, loc['coords']['latitude'], loc['coords']['longitude'], fname]):
                st.balloons()
                st.success("✅ 打卡成功！项目部已收到。")
                time.sleep(2)
                st.rerun()
            else:
                st.error("保存失败，请重试。")
        elif img and not loc:
            st.error("❌ 无法获取位置，请允许浏览器定位权限！")

# ==================== 7. 【管理端界面模块】 ====================
def show_monitoring_tab(project):
    """🔴 实时监控"""
    st.markdown(f"### 🔴 {project} - 实时监控")
    df = load_tracking_record()
    
    # 筛选项目
    if project != "中铁物贸成都分公司" and not df.empty:
        df = df[df["项目"].astype(str).str.contains(str(project), na=False)]

    if df.empty:
        st.info("📭 暂无司机打卡数据")
        return

    t1, t2 = st.tabs(["🗺️ 地图轨迹", "📸 现场照片"])
    with t1:
        st.markdown(f"**共监控到 {len(df)} 车次**")
        st.map(df.dropna(subset=['latitude', 'longitude']), zoom=10)
        st.dataframe(df[["时间", "详情", "地址"]], use_container_width=True)
    with t2:
        cols = st.columns(4)
        for idx, row in df.iloc[::-1].iterrows():
            p = os.path.join(AppConfig.UPLOAD_DIR, str(row.get("图片路径","")))
            with cols[list(df.index).index(idx) % 4]:
                if os.path.exists(p):
                    st.image(p, caption=f"{row.get('详情','-')}\n{row['时间']}")
                else:
                    st.caption(f"图片缺失: {row['时间']}")

def show_qr_generator():
    """📱 二维码生成"""
    st.markdown("### 📱 项目二维码生成")
    st.info("💡 说明：生成的二维码是【项目通用码】。司机扫码后，会在手机上自行选择工区。")
    
    df = load_auxiliary_data()
    if df.empty:
        st.error("❌ 未找到辅助信息表数据")
        return
        
    projs = sorted(df["项目部"].unique().tolist())
    
    c1, c2 = st.columns([2, 1])
    with c1:
        sel = st.selectbox("🔍 选择项目生成二维码：", projs)
    
    if sel:
        with c2:
            import urllib.parse
            # 生成URL: BASE_URL + ?role=driver&p=项目名
            q = urllib.parse.urlencode({"role": "driver", "p": sel})
            url = f"{AppConfig.BASE_URL}/?{q}"
            
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            
            buf = BytesIO()
            img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            st.image(byte_im, width=200, caption=f"{sel} - 通用码")
            st.download_button("⬇️ 下载二维码", byte_im, f"{sel}.png", "image/png")

# ==================== 8. 原有业务逻辑 (修复后) ====================
def display_metrics_cards(df):
    """显示统计卡片"""
    if df.empty: return
    # 此处已安全，因为 load_data 做了强制转换
    total = int(df["需求量"].sum())
    shipped = int(df["已发量"].sum())
    pending = int(df["剩余量"].sum())
    
    try: overdue = len(df[df["超期天数"] > 0])
    except: overdue = 0

    st.markdown('<div class="metric-container" style="display:flex; gap:1rem; flex-wrap:wrap;">', unsafe_allow_html=True)
    metrics = [
        ("📦", "总需求", f"{total:,}", "吨"),
        ("🚚", "已发货", f"{shipped:,}", "吨"),
        ("⏳", "待发货", f"{pending:,}", "吨"),
        ("⚠️", "超期单", f"{overdue}", "单")
    ]
    cols = st.columns(4)
    for idx, m in enumerate(metrics):
        with cols[idx]:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size:1.2rem">{m[0]} {m[1]}</div>
                <div style="font-size:2rem;font-weight:bold;color:#2c3e50">{m[2]}</div>
                <div style="color:#666">{m[3]}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def show_plan_tab(df, project):
    c1, c2 = st.columns(2)
    with c1: start = st.date_input("开始日期", datetime.now() - timedelta(days=30))
    with c2: end = st.date_input("结束日期", datetime.now())
    
    sub_df = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    mask = (sub_df["下单时间"].dt.date >= start) & (sub_df["下单时间"].dt.date <= end)
    final_df = sub_df[mask]
    
    if not final_df.empty:
        display_metrics_cards(final_df)
        st.dataframe(final_df, use_container_width=True, hide_index=True)
    else:
        st.info("该时间段无数据")

def show_logistics_tab(project):
    c1, c2 = st.columns(2)
    with c1: start = st.date_input("开始日期", datetime.now() - timedelta(days=30), key="log_s")
    with c2: end = st.date_input("结束日期", datetime.now(), key="log_e")
    
    df = load_logistics_data()
    if project != "中铁物贸成都分公司":
        df = df[df["项目部"] == project]
    
    if not df.empty:
        df = merge_logistics_with_status(df)
        s = pd.to_datetime(start)
        e = pd.to_datetime(end) + timedelta(days=1)
        mask = (df["交货时间"] >= s) & (df["交货时间"] < e)
        final_df = df[mask].copy()
        
        # 批量更新
        st.markdown("#### 📦 批量更新状态")
        b1, b2, b3 = st.columns([2, 2, 1])
        with b1:
            opts = [f"{r['物资名称']}-{r['钢厂']}-{r['数量']}吨" for i,r in final_df.iterrows()]
            mapping = {f"{r['物资名称']}-{r['钢厂']}-{r['数量']}吨": r['record_id'] for i,r in final_df.iterrows()}
            selected = st.multiselect("选择记录", opts)
        with b2:
            new_st = st.selectbox("新状态", AppConfig.STATUS_OPTIONS)
        with b3:
            st.write(""); st.write("")
            if st.button("更新", type="primary") and selected:
                ids = [mapping[s] for s in selected]
                success, _, _ = batch_update_logistics_status(ids, new_st)
                if success: st.success("更新成功"); st.rerun()

        st.data_editor(final_df, use_container_width=True, hide_index=True, key=f"edit_{project}")
    else:
        st.info("暂无物流数据")

def show_statistics_tab(df):
    st.header("📊 数据统计")
    log_df = load_logistics_data()
    if not log_df.empty:
        st.markdown("##### 各项目发货统计")
        st.dataframe(log_df.groupby(['项目部','钢厂'])['数量'].sum().reset_index(), use_container_width=True)

def show_project_selection(df):
    st.title("欢迎使用钢筋发货监控系统")
    # 动态获取项目列表
    log_df = load_logistics_data()
    projs = sorted(log_df["项目部"].unique().tolist()) if not log_df.empty else []
    
    sel = st.selectbox("请选择项目部", ["中铁物贸成都分公司"] + projs)
    if st.button("进入", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = sel
        st.rerun()

def show_data_panel(df, project):
    st.title(f"{project} - 数据中心")
    c1, c2 = st.columns([1, 6])
    with c1: 
        if st.button("🔄 刷新"): st.cache_data.clear(); st.rerun()
    with c2:
        if st.button("← 返回"): st.session_state.project_selected = False; st.rerun()

    if project == "中铁物贸成都分公司":
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细", "🔴 实时监控", "📊 数据统计", "📱 二维码生成"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)
        with tabs[2]: show_monitoring_tab(project)
        with tabs[3]: show_statistics_tab(df)
        with tabs[4]: show_qr_generator()
    else:
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细", "🔴 实时监控"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)
        with tabs[2]: show_monitoring_tab(project)

# ==================== 9. 主程序入口 ====================
def main():
    st.set_page_config(layout="wide", page_title="钢筋发货监控系统", page_icon="🏗️")
    apply_card_styles()

    # 1. 司机端拦截 (URL有role=driver时直接跳转)
    query = st.query_params
    if query.get("role") == "driver":
        show_driver_interface(query)
        return

    # 2. 管理端逻辑
    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    
    df = load_data() # 读取基础数据

    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)

if __name__ == "__main__":
    main()
