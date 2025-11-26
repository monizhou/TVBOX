# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 全中文深蓝地图修复版"""
import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests
import hashlib
import json
import pydeck as pdk
import random

# ==================== 系统配置 ====================
class AppConfig:
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsm"),
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]

    LOGISTICS_SHEET_NAME = "物流明细"
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

    PROJECT_MAPPING = {
        "ztwm": "中铁物贸成都分公司",
        "sdtjdzzyykjy": "商投建工达州中医药科技园",
        "hxjyxcjy": "华西简阳西城嘉苑",
        "hxjcn": "华西酒城南",
        "hxmhkckjstg": "华西萌海-科创农业生态谷",
        "hxxlxx": "华西兴隆学校",
        "hxyhkckjstg": "华西颐海-科创农业生态谷",
    }

    # 【地址库 1】项目坐标 (城市级别模糊匹配)
    CITY_COORDINATES = {
        "宜宾": [104.6432, 28.7518],
        "南溪": [104.9811, 28.8398],
        "成都": [104.0665, 30.5723],
        "龙泉": [104.2746, 30.5566],
        "简阳": [104.5486, 30.3904],
        "天府": [104.0757, 30.4045],
        "双流": [103.9237, 30.5744],
        "锦江": [104.0809, 30.5951],
        "达州": [107.5022, 31.2094],
        "乐山": [103.7656, 29.5520],
        "射洪": [105.3892, 30.8712],
        "泸州": [105.4422, 28.8715],
        "酒城": [105.4422, 28.8715],
        "西渝": [108.3000, 31.2000],
        "成达万": [106.5000, 31.5000],
        "雅安": [103.0000, 29.9800],
        "眉山": [103.8000, 30.0700],
        "绵阳": [104.7000, 31.4600],
        "自贡": [104.7700, 29.3500],
    }
    
    # 【地址库 2】钢厂坐标 (用于绘制飞线起点)
    FACTORY_COORDINATES = {
        "达钢": [107.50, 31.21],   # 达州
        "威钢": [104.70, 29.50],   # 内江威远
        "川福": [104.30, 30.80],   # 什邡/德阳附近
        "龙钢": [110.44, 35.47],   # 陕西韩城
        "陕钢": [108.93, 34.34],   # 西安
        "重钢": [106.55, 29.57],   # 重庆
        "长峰": [104.06, 30.57],   # 成都(假设)
        "攀钢": [101.71, 26.58],   # 攀枝花
        "昆钢": [102.71, 25.04],   # 昆明
        "德胜": [103.76, 29.55],   # 乐山
        "成实": [104.06, 30.60],   # 成都
        "陕西": [108.93, 34.34],
        "重庆": [106.55, 29.57],
    }
    
    DEFAULT_CENTER = [104.0665, 30.5723]

    CARD_STYLES = {
        "hover_shadow": "0 8px 16px rgba(0,0,0,0.2)",
        "glass_effect": """
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        """
    }


# ==================== 辅助函数 ====================
def find_data_file():
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    current_dir = os.path.dirname(__file__)
    if current_dir:
        excel_files = [f for f in os.listdir(current_dir) if f.endswith(('.xlsx', '.xls', '.xlsm'))]
        if excel_files:
            return os.path.join(current_dir, excel_files[0])
    st.error("❌ 未找到任何Excel数据文件")
    return None

def get_coordinates(name, db, default_jitter=True):
    """通用坐标获取函数"""
    if not isinstance(name, str):
        return [104.0 + random.uniform(-0.1, 0.1), 30.5 + random.uniform(-0.1, 0.1)]
    
    base_coord = None
    # 1. 精确/模糊匹配
    for key, coord in db.items():
        if key in name:
            base_coord = coord
            break
            
    # 2. 默认值
    if base_coord is None:
        return None 
            
    # 3. 随机抖动 (防止点重合)
    if default_jitter:
        return [
            base_coord[0] + random.uniform(-0.03, 0.03),
            base_coord[1] + random.uniform(-0.03, 0.03)
        ]
    return base_coord

def apply_card_styles():
    st.markdown(f"""
    <style>
        .remark-card {{
            background: rgba(245, 245, 247, 0.9);
            border-radius: 10px;
            padding: 1rem;
            margin: 1.5rem 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 4px solid;
        }}
        .plan-remark {{ border-color: #2196F3; }}
        .logistics-remark {{ border-color: #4CAF50; }}
        .remark-content {{
            font-size: 1rem;
            color: #666;
            text-align: center;
            padding: 1rem;
        }}
        .metric-container {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 1rem; 
            margin: 1rem 0; 
        }}
        .metric-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            transition: all 0.3s ease;
            padding: 1.5rem;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }}
        .card-value {{
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0.5rem 0;
        }}
        .batch-update-card {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1.5rem 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 4px solid #3498db;
        }}
        .batch-update-title {{
            font-size: 1.2rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #2c3e50;
        }}
        .map-container-title {{
            color: #00f2ea;
            font-family: 'Courier New', monospace;
            text-shadow: 0 0 10px #00f2ea;
            margin-bottom: 10px;
        }}
    </style>
    """, unsafe_allow_html=True)


def generate_record_id(row):
    key_fields = [
        str(row["钢厂"]),
        str(row["物资名称"]),
        str(row["规格型号"]),
        str(row["交货时间"]),
        str(row["项目部"])
    ]
    return hashlib.md5("|".join(key_fields).encode('utf-8')).hexdigest()


def send_feishu_notification(material_info):
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "elements": [{
                "tag": "div",
                "text": {
                    "content": f"**物资名称**: {material_info['物资名称']}\n"
                               f"**规格型号**: {material_info['规格型号']}\n"
                               f"**数量**: {material_info['数量']}\n"
                               f"**交货时间**: {material_info['交货时间']}\n"
                               f"**项目部**: {material_info['项目部']}",
                    "tag": "lark_md"
                }
            }, {
                "tag": "hr"
            }, {
                "tag": "note",
                "elements": [{
                    "content": "⚠️ 该物资状态已更新为【未到货】，请及时跟进",
                    "tag": "plain_text"
                }]
            }],
            "header": {
                "template": "red",
                "title": {
                    "content": "【物流状态更新通知】",
                    "tag": "plain_text"
                }
            }
        }
    }
    try:
        requests.post(AppConfig.WEBHOOK_URL, data=json.dumps(message), headers={'Content-Type': 'application/json'})
        return True
    except Exception:
        return False


# ==================== 数据加载 ====================
@st.cache_data(ttl=3600)
def load_data():
    def safe_convert_to_numeric(series, default=0):
        str_series = series.astype(str)
        cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
        cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
        return pd.to_numeric(cleaned, errors='coerce').fillna(default)

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到发货计划数据文件")
        return pd.DataFrame()

    try:
        df = pd.read_excel(data_path, engine='openpyxl')
        for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
            for alt_col in alt_cols:
                if alt_col in df.columns and std_col not in df.columns:
                    df.rename(columns={alt_col: std_col}, inplace=True)
                    break
        
        df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({"": "未指定", "nan": "未指定"})
        df[AppConfig.PROJECT_COLUMN] = df.iloc[:, 17].astype(str).str.strip().replace({"": "未指定", "nan": "未指定"})
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce')
        df["需求量"] = safe_convert_to_numeric(df["需求量"]).astype(int)
        df["已发量"] = safe_convert_to_numeric(df.get("已发量", 0)).astype(int)
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)
        
        try:
            df["超期天数"] = safe_convert_to_numeric(df.iloc[:, 15]).astype(int)
        except:
            df["超期天数"] = 0
            
        return df
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_logistics_data():
    data_path = find_data_file()
    if not data_path:
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

    try:
        df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')
        if df.shape[1] > 6:
            df["卸货地址"] = df.iloc[:, 6].astype(str).replace({"nan": "", "None": ""})
        else:
            df["卸货地址"] = ""

        for col in AppConfig.LOGISTICS_COLUMNS:
            if col not in df.columns:
                df[col] = "" if col != "数量" else 0

        for col in ["物资名称", "钢厂", "项目部"]:
            df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})
        
        df = df[df["项目部"] != ""]
        df["数量"] = pd.to_numeric(df["数量"], errors='coerce').fillna(0)
        df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")
        df["record_id"] = df.apply(generate_record_id, axis=1)

        return df[AppConfig.LOGISTICS_COLUMNS + ["record_id"]]

    except Exception:
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])


# ==================== 状态管理 ====================
def load_logistics_status():
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        try:
            return pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
        except:
            pass
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])

def save_logistics_status(status_df):
    try:
        status_df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
        return True
    except:
        return False

def merge_logistics_with_status(logistics_df):
    if logistics_df.empty: return logistics_df
    status_df = load_logistics_status()
    
    if "到货状态" not in logistics_df.columns:
        logistics_df["到货状态"] = "钢厂已接单"
        
    current_date = datetime.now().date()
    three_days_ago = current_date - timedelta(days=3)
    
    if not status_df.empty:
        status_df = status_df[["record_id", "到货状态"]]
        logistics_df = pd.merge(logistics_df, status_df, on="record_id", how="left", suffixes=("", "_db"))
        logistics_df["到货状态"] = logistics_df["到货状态_db"].combine_first(logistics_df["到货状态"])
        logistics_df = logistics_df.drop(columns=["到货状态_db"], errors='ignore')

    mask_auto = (logistics_df["到货状态"].isna()) | (logistics_df["到货状态"] == "钢厂已接单")
    mask_time = logistics_df["交货时间"].apply(lambda x: pd.notna(x) and x.date() < three_days_ago)
    logistics_df.loc[mask_auto & mask_time, "到货状态"] = "已到货"
    logistics_df["到货状态"] = logistics_df["到货状态"].fillna("钢厂已接单")
    
    return logistics_df

def update_logistics_status(record_id, new_status, original_row=None):
    status_df = load_logistics_status()
    if record_id in status_df["record_id"].values:
        status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
        status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
    else:
        new_rec = pd.DataFrame([{"record_id": record_id, "到货状态": new_status, "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)}])
        status_df = pd.concat([status_df, new_rec], ignore_index=True)
    
    if save_logistics_status(status_df):
        if new_status == "未到货" and original_row is not None:
            material_info = {
                "物资名称": original_row["物资名称"],
                "规格型号": original_row["规格型号"],
                "数量": original_row["数量"],
                "交货时间": original_row["交货时间"].strftime("%Y-%m-%d %H:%M") if pd.notna(original_row["交货时间"]) else "未知",
                "项目部": original_row["项目部"]
            }
            send_feishu_notification(material_info)
        return True
    return False

def batch_update_logistics_status(record_ids, new_status, original_rows=None):
    status_df = load_logistics_status()
    now = datetime.now().strftime(AppConfig.DATE_FORMAT)
    cnt = 0
    
    new_records = []
    existing_ids = set(status_df["record_id"].values)
    
    for rid in record_ids:
        if rid in existing_ids:
            status_df.loc[status_df["record_id"] == rid, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == rid, "update_time"] = now
        else:
            new_records.append({"record_id": rid, "到货状态": new_status, "update_time": now})
        cnt += 1
        
    if new_records:
        status_df = pd.concat([status_df, pd.DataFrame(new_records)], ignore_index=True)
        
    save_logistics_status(status_df)
    return cnt, 0


# ==================== 【全中文】3D 飞线驾驶舱 ====================
def show_cockpit_tab():
    st.markdown('<h3 class="map-container-title">🛸 G.L.M.S - 3D 飞线战术地图</h3>', unsafe_allow_html=True)
    
    logistics_df = load_logistics_data()
    if logistics_df.empty:
        st.info("暂无数据")
        return

    # 数据处理：匹配坐标
    grouped = logistics_df.groupby(["项目部", "钢厂"])["数量"].sum().reset_index()
    grouped["target_coord"] = grouped["项目部"].apply(lambda x: get_coordinates(x, AppConfig.CITY_COORDINATES, True))
    grouped["source_coord"] = grouped["钢厂"].apply(lambda x: get_coordinates(x, AppConfig.FACTORY_COORDINATES, True))
    
    valid_data = grouped.dropna(subset=["target_coord", "source_coord"]).copy()
    if valid_data.empty:
        st.warning("⚠️ 无法匹配坐标，请检查项目/钢厂名称是否包含关键词 (如: 宜宾, 成都)")
        return
        
    valid_data["t_lon"] = valid_data["target_coord"].apply(lambda x: x[0])
    valid_data["t_lat"] = valid_data["target_coord"].apply(lambda x: x[1])
    valid_data["s_lon"] = valid_data["source_coord"].apply(lambda x: x[0])
    valid_data["s_lat"] = valid_data["source_coord"].apply(lambda x: x[1])
    
    # 颜色策略
    def get_color(val):
        if val > 100: return [255, 69, 0, 180] # Red-Orange
        if val > 50: return [255, 215, 0, 160] # Gold
        return [0, 255, 255, 140] # Cyan

    valid_data["color"] = valid_data["数量"].apply(get_color)

    # 交互控制
    col_sel, col_info = st.columns([1, 2])
    with col_sel:
        selected_proj = st.selectbox("🔭 聚焦阵地", ["全部显示"] + sorted(list(valid_data["项目部"].unique())))

    view_state = pdk.ViewState(latitude=30.8, longitude=105.0, zoom=6.5, pitch=60)
    if selected_proj != "全部显示":
        target = valid_data[valid_data["项目部"] == selected_proj].iloc[0]
        view_state = pdk.ViewState(latitude=target["t_lat"], longitude=target["t_lon"], zoom=9, pitch=60, bearing=30)

    # ================= 3D 图层构建 =================
    layers = []
    
    # 0. 底图层：强制使用【智图-深蓝夜色】中文瓦片
    base_map_layer = pdk.Layer(
        "TileLayer",
        data=None,
        # GeoQ 智图 - 深蓝夜色 (全中文)
        get_tile_data="https://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineStreetPurplishBlue/MapServer/tile/{z}/{y}/{x}",
        min_zoom=0,
        max_zoom=16,
        tileSize=256,
        pickable=False,
    )
    layers.append(base_map_layer)

    # 1. 飞线层
    arc_layer = pdk.Layer(
        "ArcLayer",
        data=valid_data,
        get_source_position=["s_lon", "s_lat"],
        get_target_position=["t_lon", "t_lat"],
        get_source_color=[0, 255, 255, 80],
        get_target_color="color",
        get_width=3,
        get_tilt=15,
        pickable=True,
    )
    layers.append(arc_layer)

    # 2. 柱状图层
    proj_agg = valid_data.groupby(["项目部", "t_lon", "t_lat"])["数量"].sum().reset_index()
    proj_agg["color"] = proj_agg["数量"].apply(get_color)
    
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=proj_agg,
        get_position=["t_lon", "t_lat"],
        get_elevation="数量",
        elevation_scale=100,
        radius=1000,
        get_fill_color="color",
        pickable=True,
        extruded=True,
        auto_highlight=True,
    )
    layers.append(column_layer)

    # 3. 文本层 (中文标注，弥补底图字体过小的问题)
    text_layer = pdk.Layer(
        "TextLayer",
        data=proj_agg,
        get_position=["t_lon", "t_lat"],
        get_text="项目部",
        get_color=[255, 255, 255],
        get_size=13,
        get_alignment_baseline="'bottom'",
        get_text_anchor="'middle'",
        get_pixel_offset=[0, -15],
    )
    layers.append(text_layer)

    tooltip = {
        "html": "<b>{项目部}</b><br/>从 {钢厂} 发货<br/>📦 数量: {数量} 吨",
        "style": {"backgroundColor": "#111", "color": "#fff", "border": "1px solid #00f2ea"}
    }
    
    st.pydeck_chart(pdk.Deck(
        map_provider=None, 
        initial_view_state=view_state,
        layers=layers,
        tooltip=tooltip,
        parameters={"blendFunc": [770, 771]} 
    ))

    if selected_proj != "全部显示":
        st.info(f"✅ 当前聚焦：{selected_proj}")
        dt = logistics_df[logistics_df["项目部"] == selected_proj]
        st.dataframe(dt[["交货时间", "物资名称", "钢厂", "数量", "到货状态"]].head(10), use_container_width=True)


# ==================== 物流明细 Tab (修复版) ====================
def auto_process_logistics_changes(edited_df, original_filtered_df, project):
    if f'logistics_editor_{project}' not in st.session_state: return
    changed = st.session_state[f'logistics_editor_{project}'].get('edited_rows', {})
    if not changed: return

    pkey = f"processed_changes_{project}"
    if pkey not in st.session_state: st.session_state[pkey] = set()

    count = 0
    for idx_str, changes in changed.items():
        chash = f"{idx_str}_{changes.get('到货状态', '')}"
        if chash not in st.session_state[pkey]:
            st.session_state[pkey].add(chash)
            try:
                idx = int(idx_str)
                if idx < len(original_filtered_df):
                    rec_id = original_filtered_df.iloc[idx]["record_id"]
                    orig = original_filtered_df.iloc[idx]
                    nst = changes.get("到货状态", orig["到货状态"])
                    if nst != orig["到货状态"]:
                        if update_logistics_status(rec_id, nst, orig):
                            count += 1
                            st.toast(f"✅ {orig['物资名称']} 状态更新", icon="ok")
            except: pass
    
    if count > 0:
        time.sleep(1)
        st.rerun()

def show_logistics_tab(project):
    yesterday = datetime.now().date() - timedelta(days=1)
    col1, col2 = st.columns(2)
    with col1: start = st.date_input("开始日期", yesterday, key="log_s")
    with col2: end = st.date_input("结束日期", yesterday, key="log_e")

    with st.spinner("加载物流信息..."):
        df = load_logistics_data()
        if project != "中铁物贸成都分公司":
            df = df[df["项目部"] == project]

        if not df.empty:
            df = merge_logistics_with_status(df)
            mask = (df["交货时间"] >= pd.to_datetime(start)) & (df["交货时间"] < pd.to_datetime(end) + timedelta(days=1))
            filtered = df[mask].copy()

            # Metrics
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            total = len(filtered)
            arrived = filtered['到货状态'].eq('已到货').sum()
            overdue = filtered['到货状态'].eq('未到货').sum()
            progress = total - arrived - overdue
            cols = st.columns(4)
            metrics = [("📦 总单数", total), ("✅ 已到货", arrived), ("🔄 进行中", progress), ("⚠️ 未到货", overdue)]
            for i, (l, v) in enumerate(metrics):
                with cols[i]:
                    st.markdown(f'<div class="metric-card"><div style="font-size:1.2rem">{l}</div><div class="card-value">{v}</div></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Batch Update
            st.markdown("""<div class="batch-update-card"><div class="batch-update-title">📦 批量更新到货状态</div></div>""", unsafe_allow_html=True)
            b1, b2, b3 = st.columns([2, 1, 1])
            with b1:
                rmap = {f"{r['物资名称']}-{r['钢厂']}-{r['数量']}t": r['record_id'] for _, r in filtered.iterrows()}
                sels = st.multiselect("选择记录", list(rmap.keys()))
            with b2:
                nst = st.selectbox("状态", AppConfig.STATUS_OPTIONS)
            with b3:
                st.write(""); st.write("")
                if st.button("🚀 更新", type="primary") and sels:
                    ids = [rmap[k] for k in sels]
                    rows = [filtered[filtered['record_id'] == i].iloc[0] for i in ids]
                    s, e = batch_update_logistics_status(ids, nst, rows)
                    if s > 0: st.success(f"已更新 {s} 条"); st.rerun()

            # Data Editor
            disp_cols = [c for c in filtered.columns if c not in ["record_id", "收货地址"]]
            disp_df = filtered[disp_cols].reset_index(drop=True)
            st.markdown("**物流明细表** (修改自动保存)")
            edited = st.data_editor(
                disp_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "到货状态": st.column_config.SelectboxColumn("到货状态", options=AppConfig.STATUS_OPTIONS, required=True),
                    "交货时间": st.column_config.DatetimeColumn("交货时间", format="YYYY-MM-DD HH:mm"),
                },
                key=f"logistics_editor_{project}"
            )
            auto_process_logistics_changes(edited, filtered, project)
        else:
            st.info("📭 当前无数据")


# ==================== 其他 Tab 组件 ====================
def show_plan_tab(df, project):
    col1, col2 = st.columns(2)
    with col1: start = st.date_input("开始", datetime.now(), key="ps")
    with col2: end = st.date_input("结束", datetime.now(), key="pe")
    
    filtered = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    mask = (filtered["下单时间"].dt.date >= start) & (filtered["下单时间"].dt.date <= end)
    res = filtered[mask]
    
    if not res.empty:
        total = int(res["需求量"].sum())
        shipped = int(res["已发量"].sum())
        cols = st.columns(3)
        cols[0].metric("总需求", f"{total} 吨")
        cols[1].metric("已发货", f"{shipped} 吨")
        cols[2].metric("进度", f"{shipped/total*100:.1f}%" if total>0 else "0%")
        
        target_cols = {
            "标段名称": "工程标段", "物资名称": "材料名称", "规格型号": "规格型号",
            "需求量": "需求(吨)", "已发量": "已发(吨)", "剩余量": "待发(吨)",
            "超期天数": "超期天数", "下单时间": "下单", "计划进场时间": "计划进场"
        }
        available = {k: v for k, v in target_cols.items() if k in res.columns}
        disp = res[list(available.keys())].rename(columns=available)
        st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.info("无数据")

def show_statistics_tab(df):
    st.subheader("📊 数据统计")
    log_df = load_logistics_data()
    if log_df.empty: return
    grp = log_df.groupby(['项目部', '钢厂'])['数量'].sum().reset_index()
    st.dataframe(grp, use_container_width=True)

# ==================== 主控逻辑 ====================
def show_data_panel(df, project):
    st.title(f"{project} - 发货数据")
    
    c1, c2 = st.columns([1, 6])
    with c1: 
        if st.button("🔄 刷新"): st.cache_data.clear(); st.rerun()
    with c2:
        if st.button("🏠 首页"): st.session_state.project_selected = False; st.rerun()

    if project == "中铁物贸成都分公司":
        tabs = st.tabs(["🚀 3D飞线驾驶舱", "📋 发货计划", "🚛 物流明细", "📊 数据统计"])
        with tabs[0]: show_cockpit_tab()
        with tabs[1]: show_plan_tab(df, project)
        with tabs[2]: show_logistics_tab(project)
        with tabs[3]: show_statistics_tab(df)
    else:
        tabs = st.tabs(["📋 发货计划", "🚛 物流明细"])
        with tabs[0]: show_plan_tab(df, project)
        with tabs[1]: show_logistics_tab(project)

def show_project_selection(df):
    st.markdown("<h1 style='text-align: center;'>钢筋发货监控系统</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>中铁物贸成都分公司</p>", unsafe_allow_html=True)
    
    log_df = load_logistics_data()
    projs = sorted([p for p in log_df["项目部"].unique() if p]) if not log_df.empty else []
    
    sel = st.selectbox("选择项目部", ["中铁物贸成都分公司"] + projs)
    if st.button("进入系统", type="primary", use_container_width=True):
        if sel == "中铁物贸成都分公司":
            st.session_state.temp = sel; st.session_state.pwd = True
        else:
            st.session_state.project_selected = True; st.session_state.selected_project = sel; st.rerun()
            
    if st.session_state.get('pwd', False):
        if st.text_input("密码", type="password") == "123456":
            st.session_state.project_selected = True; st.session_state.selected_project = st.session_state.temp; st.rerun()

def main():
    st.set_page_config(layout="wide", page_title="发货监控", page_icon="🏗️")
    apply_card_styles()
    
    if 'project_selected' not in st.session_state: st.session_state.project_selected = False
    
    qp = st.query_params
    if 'project' in qp:
        pkey = qp['project'] if not isinstance(qp['project'], list) else qp['project'][0]
        pname = AppConfig.PROJECT_MAPPING.get(pkey.lower(), "中铁物贸成都分公司")
        st.session_state.project_selected = True
        st.session_state.selected_project = pname

    df = load_data()
    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)

if __name__ == "__main__":
    main()
