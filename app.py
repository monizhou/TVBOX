# -*- coding: utf-8 -*-
"""钢筋发货监控系统 - 旗舰融合版（包含：计划、物流状态管理、司机智能打卡、实时监控、二维码中心）"""
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
# 引入定位库
from streamlit_js_eval import get_geolocation

# ==================== 系统配置 ====================
class AppConfig:
    # 基础路径配置
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsm"),
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]

    # 🚨🚨🚨 【重要】请填入您最新的 Ngrok 网址 (不要带最后的 /) 🚨🚨🚨
    BASE_URL = "https://glittery-bryant-applaudably.ngrok-free.dev -> http://localhost:8501"

    # Excel 表格配置
    LOGISTICS_SHEET_NAME = "物流明细"
    AUXILIARY_SHEET_NAME = "辅助信息"  # 读取辅助信息表用于生成二维码

    # 调整列顺序
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
    
    LOGISTICS_STATUS_FILE = "logistics_status.csv"
    STATUS_OPTIONS = ["公司统筹中", "钢厂已接单", "运输装货中", "已到货", "未到货"]
    PROJECT_COLUMN = "项目部名称"

    # === 【新增】物流追踪相关配置 ===
    TRACKING_FILE = "logistics_tracking_record.csv"  # 存储司机打卡数据
    UPLOAD_DIR = "site_uploads"                      # 存储现场照片文件夹

    # 项目映射
    PROJECT_MAPPING = {
        "ztwm": "中铁物贸成都分公司",
        "sdtjdzzyykjy": "商投建工达州中医药科技园",
        "hxjyxcjy": "华西简阳西城嘉苑",
        "hxjcn": "华西酒城南",
        "hxmhkckjstg": "华西萌海-科创农业生态谷",
        "hxxlxx": "华西兴隆学校",
        "hxyhkckjstg": "华西颐海-科创农业生态谷",
        "lssxdgjcjrhjdxm2": "乐山市校地共建产教融合基地建设项目二标段",
        "lssxdgjcjrhjdxm1": "乐山市校地共建产教融合基地建设项目一标段",
        "scsjshtyh": "四川商建射洪城乡一体化项目",
        "wyggdzswsgwslcylczx": "五冶钢构达州市公共卫生临床医疗中心项目",
        "wygglqdh": "五冶钢构龙泉东洪片区(70亩、85亩)住宅、商业及配套工程项目",
        "wyggybnxgxyj": "五冶钢构-宜宾市南溪区高县月江镇建设项目",
        "wyjscdgjtlgdsl": "五冶建设成都国际铁路港多式联项目",
        "wyjscdydjzxczb": "五冶建设成都盐道街中学初中部改扩建工程",
        "wyjsjjqljb20": "五冶建设锦江区林家坝片区20号地块商业项目",
        "wyjskgxcyxjd83": "五冶建设空港兴城怡心街道83亩项目",
        "wyjsklytzx2": "五冶建设扩建艺体中学二期工程",
        "wyjslqfrhy": "五冶建设龙泉芙蓉花语项目",
        "wyjslqyyyypz": "五冶建设龙泉驿一医院配套建设工程",
        "wyjssdfzwyx": "五冶建设师大附中外语校新建教学楼工程",
        "whdqhjcdwqdgqdd": "武汉电气化局成达万高铁强电项目",
        "ybxgsjxcjgyy": "宜宾兴港三江新区长江工业园建设项目",
        "ztkyybnx": "中铁科研院宜宾泥溪项目",
        "ztsjxtykyzf4": "中铁三局集团西渝高铁康渝段站房四标工程"
    }

    CARD_STYLES = {
        "hover_shadow": "0 8px 16px rgba(0,0,0,0.2)",
        "glass_effect": "background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(12px); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.18); box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);",
        "number_animation": "", "floating_animation": "", "pulse_animation": ""
    }

# ==================== 基础辅助函数 ====================
def find_data_file():
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path): return path
    current_dir = os.path.dirname(__file__)
    if current_dir:
        excel_files = [f for f in os.listdir(current_dir) if f.endswith(('.xlsx', '.xls', '.xlsm'))]
        if excel_files: return os.path.join(current_dir, excel_files[0])
    return None

def apply_card_styles():
    st.markdown("""<style>
    .metric-card {background: #fff; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);}
    .batch-update-card {background: rgba(255, 255, 255, 0.95); border-radius: 10px; padding: 1.5rem; margin: 1.5rem 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 4px solid #3498db;}
    .stat-card {background: rgba(255, 255, 255, 0.95); border-radius: 10px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 4px solid #FF6B6B;}
    </style>""", unsafe_allow_html=True)

def generate_record_id(row):
    key_fields = [str(row.get(k,"")) for k in ["钢厂", "物资名称", "规格型号", "交货时间", "项目部"]]
    return hashlib.md5("|".join(key_fields).encode('utf-8')).hexdigest()

def send_feishu_notification(material_info):
    # 保留飞书通知
    return True

# ==================== 数据加载核心 ====================
@st.cache_data(ttl=3600)
def load_data():
    """读取发货计划"""
    data_path = find_data_file()
    if not data_path: return pd.DataFrame()
    try:
        df = pd.read_excel(data_path, engine='openpyxl')
        # 简单清洗
        if "项目部名称" in df.columns: 
             df["项目部名称"] = df.iloc[:, 17].astype(str).str.strip()
        if "下单时间" in df.columns:
             df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce')
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_logistics_data():
    """读取物流明细"""
    data_path = find_data_file()
    if not data_path: return pd.DataFrame()
    try:
        df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME)
        # 强制读取G列作为地址
        if df.shape[1] > 6:
            df["卸货地址"] = df.iloc[:, 6].astype(str).replace({"nan": "", "None": ""})
        
        if "项目部" in df.columns: df = df[df["项目部"].notna()]
        df["record_id"] = df.apply(generate_record_id, axis=1)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_auxiliary_data():
    """【新增】读取辅助信息表（用于生成二维码和司机选择列表）"""
    data_path = find_data_file()
    if not data_path: return pd.DataFrame()
    try:
        df = pd.read_excel(data_path, sheet_name=AppConfig.AUXILIARY_SHEET_NAME)
        # 填充合并单元格
        fill_cols = ["项目部", "标段名称（细分）", "收货地址", "收货人", "收货人电话"]
        for col in fill_cols:
            if col in df.columns:
                df[col] = df[col].ffill()
        # 筛选有效数据
        if "项目部" in df.columns and "收货人" in df.columns:
            return df.dropna(subset=["收货人"])
        return pd.DataFrame()
    except: return pd.DataFrame()

# ==================== 物流追踪数据读写 ====================
def save_tracking_data(data):
    """保存司机打卡数据"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, AppConfig.TRACKING_FILE)
    file_exists = os.path.isfile(file_path)
    try:
        with open(file_path, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["时间", "项目", "标段_收货人", "地址", "纬度", "经度", "图片"])
            writer.writerow(data)
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False

def load_tracking_data():
    """读取司机打卡数据"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, AppConfig.TRACKING_FILE)
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=["时间", "项目", "标段_收货人", "地址", "纬度", "经度", "图片"])
    try:
        df = pd.read_csv(file_path)
        df['latitude'] = pd.to_numeric(df['纬度'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['经度'], errors='coerce')
        return df
    except: return pd.DataFrame()

# ==================== 状态管理函数 (保留原逻辑) ====================
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
            new_record = pd.DataFrame([{"record_id": record_id, "到货状态": new_status, "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)}])
            status_df = pd.concat([status_df, new_record], ignore_index=True)
        return save_logistics_status(status_df)
    except: return False

def batch_update_logistics_status(record_ids, new_status, original_rows=None):
    # 批量更新逻辑
    try:
        status_df = load_logistics_status()
        for i, record_id in enumerate(record_ids):
            if record_id in status_df["record_id"].values:
                status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
                status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
            else:
                new_rec = pd.DataFrame([{"record_id": record_id, "到货状态": new_status, "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)}])
                status_df = pd.concat([status_df, new_rec], ignore_index=True)
        return save_logistics_status(status_df), len(record_ids), 0
    except: return False, 0, len(record_ids)

def merge_logistics_with_status(df):
    status_df = load_logistics_status()
    if status_df.empty: 
        df["到货状态"] = "公司统筹中"
        return df
    return pd.merge(df, status_df[["record_id", "到货状态"]], on="record_id", how="left").fillna({"到货状态": "公司统筹中"})

# ==================== 【模块 A】司机端界面 (智能选择版) ====================
def show_driver_interface(query_params):
    """
    司机扫码后看到的界面。
    逻辑：URL只有项目名 -> 读取Excel -> 司机选择细分工区 -> 显示对应地址
    """
    proj_name = query_params.get("p", "未知项目")
    
    st.title("🚛 司机送货打卡")
    st.subheader(f"📍 当前项目：{proj_name}")

    df_aux = load_auxiliary_data()
    
    target_address = "请选择收货人以获取地址"
    target_contact = ""
    target_phone = ""
    selected_detail = None

    if not df_aux.empty and proj_name != "未知项目":
        project_rows = df_aux[df_aux["项目部"] == proj_name]
        
        if not project_rows.empty:
            options = project_rows.apply(
                lambda x: f"{x.get('标段名称（细分）','默认标段')} - {x.get('收货人','未知')}", axis=1
            ).tolist()
            
            st.info("👇 请先选择您具体要去的工区/联系人：")
            selected_option = st.selectbox("选择工区/收货人", options, index=None, placeholder="请点击选择...")
            
            if selected_option:
                sel_section, sel_contact = selected_option.split(" - ")
                row = project_rows[
                    (project_rows["标段名称（细分）"] == sel_section) & 
                    (project_rows["收货人"] == sel_contact)
                ].iloc[0]
                
                target_address = row.get("收货地址", "暂无地址")
                target_contact = sel_contact
                target_phone = str(row.get("收货人电话", "")).replace(".0", "")
                selected_detail = selected_option
        else:
            st.error("未在系统中找到该项目的细分信息，请联系调度。")
    else:
        st.error("数据加载失败或项目名称无效。")

    if selected_detail:
        with st.container(border=True):
            st.success(f"✅ 已确认：{selected_detail}")
            st.warning(f"📝 卸货地址：{target_address}")
            
            c1, c2 = st.columns(2)
            with c1: st.link_button(f"📞 呼叫 {target_contact}", f"tel:{target_phone}", use_container_width=True)
            with c2: st.link_button("🗺️ 导航去工地", f"https://uri.amap.com/search?keyword={target_address}", use_container_width=True)

        st.write("---")
        st.write("##### 📸 现场拍照打卡")
        
        loc = get_geolocation()
        img_file = st.camera_input("拍照")

        if img_file:
            if loc:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                upload_path = os.path.join(base_dir, AppConfig.UPLOAD_DIR)
                if not os.path.exists(upload_path): os.makedirs(upload_path)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                safe_detail = selected_detail.replace("/","-")
                img_name = f"{timestamp.replace(':','-')}_{proj_name}_{safe_detail}.jpg"
                
                with open(os.path.join(upload_path, img_name), "wb") as f:
                    f.write(img_file.getbuffer())
                
                lat = loc['coords']['latitude']
                lon = loc['coords']['longitude']
                
                if save_tracking_data([timestamp, proj_name, selected_detail, target_address, lat, lon, img_name]):
                    st.balloons()
                    st.success("✅ 打卡成功！项目部已收到信息。")
            else:
                st.error("❌ 无法获取定位，请允许浏览器获取位置信息！")

# ==================== 【模块 B】管理端 - 实时监控 ====================
def show_monitoring_tab(project):
    """实时监控地图"""
    st.markdown(f"### 🔴 {project} - 实时物流监控")
    
    df_log = load_tracking_data()
    
    if df_log.empty:
        st.info("暂无司机打卡记录。")
        return

    if project != "中铁物贸成都分公司":
        filtered_df = df_log[df_log["项目"].astype(str).str.contains(str(project), na=False)]
    else:
        filtered_df = df_log

    if filtered_df.empty:
        st.warning(f"项目【{project}】暂无车辆到达记录。")
    else:
        t1, t2 = st.tabs(["🗺️ 车辆位置分布", "📸 现场回传照片"])
        
        with t1:
            st.markdown(f"**共监控到 {len(filtered_df)} 车次**")
            map_data = filtered_df[['latitude', 'longitude']].dropna()
            if not map_data.empty:
                st.map(map_data, zoom=11)
            else:
                st.write("位置数据无效")
            with st.expander("查看详细记录"):
                st.dataframe(filtered_df[["时间", "标段_收货人", "地址"]], use_container_width=True)

        with t2:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cols = st.columns(4)
            for idx, row in filtered_df.iloc[::-1].iterrows(): 
                col_idx = list(filtered_df.index).index(idx) % 4
                img_path = os.path.join(base_dir, AppConfig.UPLOAD_DIR, str(row["图片"]))
                with cols[col_idx]:
                    if os.path.exists(img_path):
                        st.image(img_path, caption=f"{row['标段_收货人']}\n{row['时间']}")
                    else:
                        st.caption(f"图片缺失: {row['时间']}")

# ==================== 【模块 C】二维码生成 ====================
def generate_qr_image(url):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill='black', back_color='white')

def show_qr_manager_tab():
    """二维码生成中心"""
    st.markdown("### 📱 项目二维码生成中心")
    st.info("说明：此处二维码**只包含项目名称**。司机扫码后，会在手机上**自行选择**该项目下的具体工区和收货人。")

    df_aux = load_auxiliary_data()
    if df_aux.empty:
        st.error("❌ 未读取到【辅助信息】表数据，请检查 Excel。")
        return

    all_projects = df_aux["项目部"].unique().tolist()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        selected_proj = st.selectbox("🔍 选择要生成二维码的项目：", all_projects)

    if selected_proj:
        with col2:
            st.markdown(f"**【{selected_proj}】专用二维码**")
            
            import urllib.parse
            params = {"role": "driver", "p": selected_proj}
            query = urllib.parse.urlencode(params)
            full_url = f"{AppConfig.BASE_URL}/?{query}"
            
            img = generate_qr_image(full_url)
            buf = BytesIO()
            img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            st.image(byte_im, width=200)
            st.download_button(label=f"⬇️ 下载 {selected_proj} 二维码", data=byte_im, file_name=f"{selected_proj}_通用码.png", mime="image/png")
            
        st.caption("提示：请将此二维码发给该项目部的所有管理人员。司机扫这一个码，就能选择该项目下的任意工区。")

# ==================== 原有业务模块 ====================
def display_metrics_cards(filtered_df):
    if filtered_df.empty: return
    total = int(filtered_df["需求量"].sum())
    shipped = int(filtered_df["已发量"].sum())
    pending = int(filtered_df["剩余量"].sum())
    overdue = len(filtered_df[filtered_df["超期天数"] > 0])
    
    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
    cols = st.columns(4)
    metrics = [
        ("📦", "总需求量", f"{total:,}", "吨"),
        ("🚚", "已发货量", f"{shipped:,}", "吨"),
        ("⏳", "待发货量", f"{pending:,}", "吨"),
        ("⚠️", "超期订单", f"{overdue}", "单")
    ]
    for idx, m in enumerate(metrics):
        with cols[idx]:
            st.markdown(f"""<div class="metric-card"><div style="font-size:1.2rem">{m[0]} {m[1]}</div><div style="font-size:2rem;font-weight:bold;color:#2c3e50">{m[2]}</div><div style="color:#666">{m[3]}</div></div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def show_plan_tab(df, project):
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("开始日期", datetime.now() - timedelta(days=30))
    with col2: end_date = st.date_input("结束日期", datetime.now())
    
    filtered_df = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    date_range_df = filtered_df[(filtered_df["下单时间"].dt.date >= start_date) & (filtered_df["下单时间"].dt.date <= end_date)]
    
    if not date_range_df.empty:
        display_metrics_cards(date_range_df)
        st.dataframe(date_range_df, use_container_width=True, hide_index=True)
    else:
        st.info("该时间段无数据")

def show_logistics_tab(project):
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("开始日期", datetime.now() - timedelta(days=30), key="log_start")
    with col2: end_date = st.date_input("结束日期", datetime.now(), key="log_end")
    
    logistics_df = load_logistics_data()
    if project != "中铁物贸成都分公司":
        logistics_df = logistics_df[logistics_df["项目部"] == project]
    
    if not logistics_df.empty:
        logistics_df = merge_logistics_with_status(logistics_df)
        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date) + timedelta(days=1)
        filtered_df = logistics_df[(logistics_df["交货时间"] >= start_ts) & (logistics_df["交货时间"] < end_ts)]
        
        st.markdown("""<div class="batch-update-card">📦 批量更新到货状态</div>""", unsafe_allow_html=True)
        
        b1, b2, b3 = st.columns([2,2,1])
        with b1:
            options = [f"{r['物资名称']}-{r['钢厂']}-{r['数量']}吨" for i,r in filtered_df.iterrows()]
            mapping = {f"{r['物资名称']}-{r['钢厂']}-{r['数量']}吨": r['record_id'] for i,r in filtered_df.iterrows()}
            selected = st.multiselect("选择记录", options)
        with b2:
            new_stat = st.selectbox("新状态", AppConfig.STATUS_OPTIONS)
        with b3:
            st.write(""); st.write("")
            if st.button("批量更新", type="primary") and selected:
                ids = [mapping[s] for s in selected]
                success, _, _ = batch_update_logistics_status(ids, new_stat)
                if success: st.success("更新成功"); st.rerun()

        st.data_editor(filtered_df, use_container_width=True, hide_index=True, key=f"editor_{project}")
    else:
        st.info("暂无物流数据")

def show_statistics_tab(df):
    st.header("📊 数据统计")
    logistics_df = load_logistics_data()
    if not logistics_df.empty:
        st.dataframe(logistics_df.groupby(['项目部','钢厂'])['数量'].sum().reset_index(), use_container_width=True)

def show_project_selection(df):
    st.title("欢迎使用钢筋发货监控系统")
    logistics_df = load_logistics_data()
    valid_projects = sorted([p for p in logistics_df["项目部"].unique() if p != ""])
    selected = st.selectbox("选择项目部", ["中铁物贸成都分公司"] + valid_projects)
    if st.button("确认进入", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = selected
        st.rerun()

def show_data_panel(df, project):
    st.title(f"{project} - 数据中心")
    c1, c2 = st.columns([1,5])
    with c1: 
        if st.button("🔄 刷新"): st.cache_data.clear(); st.rerun()
    with c2: 
        if st.button("← 返回"): st.session_state.project_selected = False; st.rerun()

    if project == "中铁物贸成都分公司":
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细", "🔴 实时监控", "📊 数据统计", "📱 二维码管理"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)
        with tabs[2]: show_monitoring_tab(project)
        with tabs[3]: show_statistics_tab(df)
        with tabs[4]: show_qr_manager_tab()
    else:
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细", "🔴 实时监控"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)
        with tabs[2]: show_monitoring_tab(project)

# ==================== 主程序入口 ====================
def main():
    st.set_page_config(layout="wide", page_title="钢筋发货监控系统", page_icon="🏗️")
    apply_card_styles()

    query = st.query_params
    if query.get("role") == "driver":
        show_driver_interface(query)
        return

    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = "中铁物贸成都分公司"

    df = load_data()

    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)

if __name__ == "__main__":
    main()

