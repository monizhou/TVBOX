# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 3D 智能驾驶舱版"""
import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests
import hashlib
import json
import pydeck as pdk  # 新增：用于3D地图渲染

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

    # 项目名称映射
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

    # 【新增】地理坐标数据库 (City -> [Lon, Lat])
    # 使用模糊匹配，不需要完全匹配项目名
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
        "酒城": [105.4422, 28.8715], # 泸州
        "泸州": [105.4422, 28.8715],
        "西渝": [108.0000, 31.0000], # 估算位置
        "成达万": [106.5000, 31.5000], # 估算位置
    }
    # 默认中心点（成都）
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
        """,
        "number_animation": """
            @keyframes countup {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        """,
        "floating_animation": """
            @keyframes floating {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-8px); }
                100% { transform: translateY(0px); }
            }
        """,
        "pulse_animation": """
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.03); }
                100% { transform: scale(1); }
            }
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

def get_project_coordinates(project_name):
    """【新增】根据项目名称智能匹配坐标"""
    if not isinstance(project_name, str):
        return AppConfig.DEFAULT_CENTER
    
    # 随机微调因子（避免所有点重叠在一起）
    def jitter(coord):
        import random
        return [coord[0] + random.uniform(-0.03, 0.03), coord[1] + random.uniform(-0.03, 0.03)]

    # 遍历关键词库
    for key, coord in AppConfig.CITY_COORDINATES.items():
        if key in project_name:
            return jitter(coord)
            
    # 如果包含“成都”或者默认
    if "成都" in project_name or "华西" in project_name or "五冶" in project_name:
         return jitter(AppConfig.CITY_COORDINATES["成都"])
         
    return jitter(AppConfig.DEFAULT_CENTER)

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
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            padding: 8px 0;
            background: #f5f5f7;
            border-radius: 12px;
            margin: 1rem 0;
        }}
        .stTabs [data-baseweb="tab"] {{
            background: transparent !important;
            padding: 12px 24px !important;
            border: none !important;
            color: #86868b !important;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            border-radius: 8px;
            margin: 0 4px !important;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            background: rgba(0, 0, 0, 0.04) !important;
            color: #1d1d1f !important;
            transform: scale(1.02);
        }}
        .stTabs [aria-selected="true"] {{
            background: #ffffff !important;
            color: #1d1d1f !important;
            font-weight: 600;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08),
                        inset 0 0 0 1px rgba(0, 0, 0, 0.04);
        }}
        {AppConfig.CARD_STYLES['number_animation']}
        {AppConfig.CARD_STYLES['floating_animation']}
        {AppConfig.CARD_STYLES['pulse_animation']}

        .metric-container {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 1rem; 
            margin: 1rem 0; 
            animation: fadeIn 0.6s ease-out;
        }}
        .metric-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            transition: all 0.3s ease;
            padding: 1.5rem;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: {AppConfig.CARD_STYLES['hover_shadow']};
        }}
        .card-value {{
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: countup 0.8s ease-out;
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
        .stat-card {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 4px solid #FF6B6B;
        }}
        .stat-title {{
            font-size: 1.2rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #2c3e50;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        /* 地图容器样式 */
        .map-container-title {
            color: #00f2ea;
            font-family: 'Courier New', monospace;
            text-shadow: 0 0 10px #00f2ea;
            margin-bottom: 10px;
        }
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
        with st.spinner("正在加载基础数据..."):
            df = pd.read_excel(data_path, engine='openpyxl')

            for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
                for alt_col in alt_cols:
                    if alt_col in df.columns and std_col not in df.columns:
                        df.rename(columns={alt_col: std_col}, inplace=True)
                        break

            REQUIRED_COLS = ['标段名称', '物资名称', '下单时间', '需求量']
            missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
            if missing_cols:
                st.error(f"缺少必要列: {missing_cols}")
                return pd.DataFrame()

            df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
                "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})

            df[AppConfig.PROJECT_COLUMN] = df.iloc[:, 17].astype(str).str.strip().replace({
                "": "未指定项目部", "nan": "未指定项目部", "None": "未指定项目部", None: "未指定项目部"})

            df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
            df = df[~df["下单时间"].isna()]

            df["需求量"] = safe_convert_to_numeric(df["需求量"]).astype(int)
            df["已发量"] = safe_convert_to_numeric(df.get("已发量", 0)).astype(int)
            df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)
            
            try:
                df["超期天数"] = safe_convert_to_numeric(df.iloc[:, 15]).astype(int)
            except Exception:
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
        with st.spinner("正在加载物流数据..."):
            try:
                df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')
                if df.shape[1] > 6:
                    df["卸货地址"] = df.iloc[:, 6].astype(str).replace({"nan": "", "None": ""})
                else:
                    df["卸货地址"] = ""
            except Exception:
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

            if df.empty:
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

            for col in AppConfig.LOGISTICS_COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col != "数量" else 0

            df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
                "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})
            df["钢厂"] = df["钢厂"].astype(str).str.strip().replace({
                "": "未指定钢厂", "nan": "未指定钢厂", "None": "未指定钢厂", None: "未指定钢厂"})
            df["项目部"] = df["项目部"].astype(str).str.strip().replace({
                "未指定项目部": "", "nan": "", "None": "", None: ""})

            df = df[df["项目部"] != ""]

            def safe_convert_numeric(series):
                if series.dtype == 'object':
                    cleaned = series.astype(str).str.replace(r'[^\d.-]', '', regex=True)
                    cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0', ' ': '0'})
                    return pd.to_numeric(cleaned, errors='coerce').fillna(0)
                else:
                    return pd.to_numeric(series, errors='coerce').fillna(0)

            df["数量"] = safe_convert_numeric(df["数量"])
            df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")
            df["联系方式"] = df["联系方式"].astype(str)
            if "卸货地址" in df.columns:
                df["卸货地址"] = df["卸货地址"].astype(str).replace({"nan": "", "None": ""})

            df["record_id"] = df.apply(generate_record_id, axis=1)

            return df[AppConfig.LOGISTICS_COLUMNS + ["record_id"]]

    except Exception as e:
        st.error(f"物流数据加载失败: {str(e)}")
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])


# ==================== 物流状态管理 ====================
def load_logistics_status():
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        try:
            status_df = pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
            if "record_id" not in status_df.columns:
                status_df["record_id"] = ""
            if "update_time" not in status_df.columns:
                status_df["update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
            if "物流信息" in status_df.columns:
                status_df = status_df.drop(columns=["物流信息"])
            return status_df
        except Exception:
            return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])


def save_logistics_status(status_df):
    try:
        status_df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
        return True
    except Exception:
        return False


def merge_logistics_with_status(logistics_df):
    if logistics_df.empty:
        return logistics_df

    status_df = load_logistics_status()
    current_date = datetime.now().date()
    three_days_ago = current_date - timedelta(days=3)
    
    if status_df.empty:
        logistics_df["到货状态"] = logistics_df.apply(
            lambda row: "已到货" if (
                pd.notna(row["交货时间"]) and 
                row["交货时间"].date() < three_days_ago
            ) else "钢厂已接单",
            axis=1
        )
        return logistics_df

    required_status_cols = ["record_id", "到货状态"]
    for col in required_status_cols:
        if col not in status_df.columns:
            status_df[col] = ""
    
    merged = pd.merge(
        logistics_df,
        status_df[required_status_cols],
        on="record_id",
        how="left",
        suffixes=("", "_status")
    )
    
    if "到货状态_status" in merged.columns:
        mask_no_status = merged["到货状态_status"].isna()
        mask_old_delivery = merged["交货时间"].apply(
            lambda x: pd.notna(x) and x.date() < three_days_ago
        )
        
        merged.loc[mask_no_status & mask_old_delivery, "到货状态"] = "已到货"
        merged.loc[mask_no_status & ~mask_old_delivery, "到货状态"] = "钢厂已接单"
        merged.loc[~mask_no_status, "到货状态"] = merged.loc[~mask_no_status, "到货状态_status"]
        merged = merged.drop(columns=["到货状态_status"])
    else:
        merged["到货状态"] = merged.apply(
            lambda row: "已到货" if (
                pd.notna(row["交货时间"]) and 
                row["交货时间"].date() < three_days_ago
            ) else "钢厂已接单",
            axis=1
        )
    
    return merged


def update_logistics_status(record_id, new_status, original_row=None):
    try:
        status_df = load_logistics_status()
        new_status = str(new_status).strip() if new_status else "公司统筹中"

        send_notification = False
        if new_status == "未到货":
            existing_status = status_df.loc[status_df["record_id"] == record_id, "到货状态"]
            if len(existing_status) == 0 or existing_status.iloc[0] != "未到货":
                send_notification = True

        if record_id in status_df["record_id"].values:
            status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
        else:
            new_record = pd.DataFrame([{
                "record_id": record_id,
                "到货状态": new_status,
                "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)
            }])
            status_df = pd.concat([status_df, new_record], ignore_index=True)

        if save_logistics_status(status_df):
            if send_notification and original_row is not None:
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
    except Exception:
        return False


def batch_update_logistics_status(record_ids, new_status, original_rows=None):
    try:
        status_df = load_logistics_status()
        new_status = str(new_status).strip() if new_status else "公司统筹中"
        success_count = 0
        error_count = 0
        
        for i, record_id in enumerate(record_ids):
            try:
                original_row = original_rows[i] if original_rows and i < len(original_rows) else None
                send_notification = False
                if new_status == "未到货":
                    existing_status = status_df.loc[status_df["record_id"] == record_id, "到货状态"]
                    if len(existing_status) == 0 or existing_status.iloc[0] != "未到货":
                        send_notification = True

                if record_id in status_df["record_id"].values:
                    status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
                    status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
                else:
                    new_record = pd.DataFrame([{
                        "record_id": record_id,
                        "到货状态": new_status,
                        "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)
                    }])
                    status_df = pd.concat([status_df, new_record], ignore_index=True)

                if send_notification and original_row is not None:
                    material_info = {
                        "物资名称": original_row["物资名称"],
                        "规格型号": original_row["规格型号"],
                        "数量": original_row["数量"],
                        "交货时间": original_row["交货时间"].strftime("%Y-%m-%d %H:%M") if pd.notna(original_row["交货时间"]) else "未知",
                        "项目部": original_row["项目部"]
                    }
                    send_feishu_notification(material_info)
                success_count += 1
            except Exception:
                error_count += 1
                continue

        if save_logistics_status(status_df):
            return success_count, error_count
        return 0, len(record_ids)
    except Exception:
        return 0, len(record_ids)


# ==================== URL参数处理 ====================
def handle_url_parameters():
    query_params = st.query_params
    if 'project' in query_params:
        project_key = query_params['project']
        if isinstance(project_key, list):
            project_key = project_key[0].lower()
        else:
            project_key = project_key.lower()
            
        project_name = AppConfig.PROJECT_MAPPING.get(project_key, "中铁物贸成都分公司")
        valid_projects = get_valid_projects()
        
        if project_name in valid_projects:
            st.session_state.project_selected = True
            st.session_state.selected_project = project_name
            if project_name == "中铁物贸成都分公司":
                st.session_state.need_password = True
            else:
                if 'need_password' in st.session_state: del st.session_state['need_password']
                if 'temp_selected_project' in st.session_state: del st.session_state['temp_selected_project']


def get_valid_projects():
    logistics_df = load_logistics_data()
    valid_projects = ["中铁物贸成都分公司"]
    if not logistics_df.empty:
        current_date = datetime.now().date()
        start_date = current_date - timedelta(days=15)
        end_date = current_date + timedelta(days=15)
        logistics_df = logistics_df.dropna(subset=['交货时间'])
        logistics_df['交货日期'] = logistics_df['交货时间'].dt.date
        mask = (logistics_df['交货日期'] >= start_date) & (logistics_df['交货日期'] <= end_date)
        project_list = sorted([p for p in logistics_df[mask]["项目部"].unique() if p != ""])
        valid_projects.extend(project_list)
    return valid_projects


# ==================== 页面组件 ====================
def show_logistics_tab(project):
    yesterday = datetime.now().date() - timedelta(days=1)
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("开始日期", yesterday, key="logistics_start")
    with col2:
        end = st.date_input("结束日期", yesterday, key="logistics_end")

    if start > end:
        st.error("结束日期不能早于开始日期")
        return

    with st.spinner("加载物流信息..."):
        df = load_logistics_data()
        if project != "中铁物贸成都分公司":
            df = df[df["项目部"] == project]

        if not df.empty:
            df = merge_logistics_with_status(df)
            mask = (df["交货时间"] >= pd.to_datetime(start)) & (df["交货时间"] < pd.to_datetime(end) + timedelta(days=1))
            filtered = df[mask].copy()

            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            
            overdue = filtered['到货状态'].eq('未到货').sum()
            total = len(filtered)
            arrived = filtered['到货状态'].eq('已到货').sum()
            progress = total - arrived - overdue

            cols = st.columns(4)
            metrics = [
                ("📦", "总物流单数", total, "单"),
                ("✅", "已到货单数", arrived, "单"),
                ("🔄", "进行中订单", progress, "单"),
                ("⚠️", "未到货订单", overdue, "单")
            ]

            for i, m in enumerate(metrics):
                with cols[i]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="display:flex;align-items:center;gap:5px">
                            <span style="font-size:1.2rem">{m[0]}</span>
                            <strong>{m[1]}</strong>
                        </div>
                        <div class="card-value">{m[2]}</div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # 批量更新
            st.markdown("""<div class="batch-update-card"><div class="batch-update-title">📦 批量更新到货状态</div></div>""", unsafe_allow_html=True)
            b_col1, b_col2, b_col3 = st.columns([2, 2, 1])
            with b_col1:
                record_map = {f"{r['物资名称']} - {r['规格型号']} - {r['钢厂']} - {r['数量']}吨": r['record_id'] for _, r in filtered.iterrows()}
                sel_recs = st.multiselect("选择记录", options=list(record_map.keys()))
            with b_col2:
                new_st = st.selectbox("新状态", AppConfig.STATUS_OPTIONS)
            with b_col3:
                st.write("")
                st.write("")
                if st.button("🚀 批量更新", type="primary") and sel_recs:
                    ids = [record_map[k] for k in sel_recs]
                    rows = [filtered[filtered['record_id'] == i].iloc[0] for i in ids]
                    s, e = batch_update_logistics_status(ids, new_st, rows)
                    if s > 0: st.success(f"已更新 {s} 条")
                    st.rerun()

            disp_cols = [c for c in filtered.columns if c not in ["record_id", "收货地址"]]
            disp_df = filtered[disp_cols].reset_index(drop=True)
            
            st.markdown("**物流明细表** (修改自动保存)")
            edited = st.data_editor(
                disp_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "到货状态": st.column_config.SelectboxColumn("到货状态", options=AppConfig.STATUS_OPTIONS, required=True),
                    "数量": st.column_config.NumberColumn("数量", format="%d"),
                    "交货时间": st.column_config.DatetimeColumn("交货时间", format="YYYY-MM-DD HH:mm"),
                    "卸货地址": st.column_config.TextColumn("卸货地址"),
                    "备注": st.column_config.TextColumn("备注", width="large"),
                },
                key=f"logistics_editor_{project}"
            )
            auto_process_logistics_changes(edited, filtered, project)
            
            st.markdown('<div class="remark-card logistics-remark"><div class="remark-content">📢 以上数据为公司已安排的发货情况</div></div>', unsafe_allow_html=True)
        else:
            st.info("📭 当前没有物流数据")


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

def display_metrics_cards(filtered_df):
    if filtered_df.empty:
        return
    total = int(filtered_df["需求量"].sum())
    shipped = int(filtered_df["已发量"].sum())
    pending = int(filtered_df["剩余量"].sum())
    overdue = len(filtered_df[filtered_df["超期天数"] > 0])
    max_overdue = filtered_df["超期天数"].max() if overdue > 0 else 0

    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
    cols = st.columns(4)
    metrics = [
        ("📦", "总需求量", f"{total:,}", "吨", "total"),
        ("🚚", "已发货量", f"{shipped:,}", "吨", "shipped"),
        ("⏳", "待发货量", f"{pending:,}", "吨", "pending"),
        ("⚠️", "超期订单", f"{overdue}", "单", "overdue", f"最大超期: {max_overdue}天" if overdue > 0 else "")
    ]
    for idx, metric in enumerate(metrics):
        with cols[idx]:
            st.markdown(f"""
            <div class="metric-card {metric[4]}">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <span style="font-size:1.2rem">{metric[0]}</span>
                    <span style="font-weight:600">{metric[1]}</span>
                </div>
                <div class="card-value">{metric[2]}</div>
                <div class="card-unit">{metric[3]}</div>
                {f'<div style="font-size:0.8rem; color:#666;">{metric[5]}</div>' if len(metric) > 5 else ''}
            </div>
            """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def show_plan_tab(df, project):
    col1, col2 = st.columns(2)
    with col1: start = st.date_input("开始", datetime.now(), key="ps")
    with col2: end = st.date_input("结束", datetime.now(), key="pe")
    
    filtered = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    mask = (filtered["下单时间"].dt.date >= start) & (filtered["下单时间"].dt.date <= end)
    res = filtered[mask]
    
    if not res.empty:
        display_metrics_cards(res)
        target_cols = {
            "标段名称": "工程标段", "物资名称": "材料名称", "规格型号": "规格型号",
            "需求量": "需求(吨)", "已发量": "已发(吨)", "剩余量": "待发(吨)",
            "超期天数": "超期天数", "下单时间": "下单", "计划进场时间": "计划进场"
        }
        available = {k: v for k, v in target_cols.items() if k in res.columns}
        disp = res[list(available.keys())].rename(columns=available)
        
        st.dataframe(
            disp.style.format({'需求(吨)': '{:,}', '已发(吨)': '{:,}', '待发(吨)': '{:,}'}).apply(
                lambda row: ['background-color: #ffdddd' if '超期天数' in row and row.get('超期天数', 0) > 0 else '' for _ in row],
                axis=1
            ),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("无数据")


def show_statistics_tab(df):
    st.subheader("📊 数据统计")
    log_df = load_logistics_data()
    if log_df.empty: return
    
    grp = log_df.groupby(['项目部', '钢厂'])['数量'].sum().reset_index()
    st.dataframe(grp, use_container_width=True)


# ==================== 【新增】3D 智能驾驶舱 ====================
def show_cockpit_tab():
    st.markdown('<h3 class="map-container-title">🛸 G.L.M.S - 3D 战术指挥地图</h3>', unsafe_allow_html=True)
    
    # 1. 准备数据
    logistics_df = load_logistics_data()
    if logistics_df.empty:
        st.info("暂无物流数据，无法展示地图")
        return

    # 聚合数据：每个项目部的总发货量
    map_data = logistics_df.groupby("项目部")["数量"].sum().reset_index()
    
    # 2. 映射坐标
    # 使用 apply 逐行获取坐标
    map_data["coord"] = map_data["项目部"].apply(get_project_coordinates)
    map_data["lon"] = map_data["coord"].apply(lambda x: x[0])
    map_data["lat"] = map_data["coord"].apply(lambda x: x[1])
    
    # 3. 交互控制器（放在地图上方）
    col_sel, col_info = st.columns([1, 2])
    with col_sel:
        # 下拉选择框：选择一个项目来点亮/聚焦
        selected_project_name = st.selectbox(
            "🔭 选择目标阵地 (Focus Target)", 
            options=["全部显示"] + list(map_data["项目部"].unique())
        )
    
    # 确定地图视角
    view_state = pdk.ViewState(
        latitude=30.5,
        longitude=104.5,
        zoom=7,
        pitch=45,
    )
    
    # 如果选择了具体项目，改变视角
    if selected_project_name != "全部显示":
        target_row = map_data[map_data["项目部"] == selected_project_name].iloc[0]
        view_state = pdk.ViewState(
            latitude=target_row["lat"],
            longitude=target_row["lon"],
            zoom=10,
            pitch=55,
        )
        # 在右侧显示该项目的详细信息
        with col_info:
            detail_df = logistics_df[logistics_df["项目部"] == selected_project_name]
            total_tons = detail_df["数量"].sum()
            trucks = len(detail_df)
            st.info(f"📍 **{selected_project_name}**\n\n🚚 累计发货：{total_tons} 吨 | 📦 车次：{trucks} 车")

    # 4. 构建地图图层
    
    # 图层1：3D 柱状图 (ColumnLayer) - 代表发货量
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=map_data,
        get_position=["lon", "lat"],
        get_elevation="数量",
        elevation_scale=50,  # 高度缩放
        radius=2000,         # 柱子半径（米）
        get_fill_color=[0, 242, 234, 140],  # 赛博青色，带透明度
        pickable=True,
        auto_highlight=True,
    )

    # 图层2：文字标签 (TextLayer) - 显示项目名
    text_layer = pdk.Layer(
        "TextLayer",
        data=map_data,
        get_position=["lon", "lat"],
        get_text="项目部",
        get_color=[255, 255, 255],
        get_size=16,
        get_alignment_baseline="'bottom'",
        get_text_anchor="'middle'",
        pickable=False,
    )

    # 5. 渲染地图
    tooltip = {
        "html": "<b>{项目部}</b><br/>📊 总发货量: <b>{数量}</b> 吨",
        "style": {"backgroundColor": "steelblue", "color": "white"}
    }

    r = pdk.Deck(
        layers=[column_layer, text_layer],
        initial_view_state=view_state,
        map_style=pdk.map_styles.DARK, # 深色地图基底
        tooltip=tooltip,
    )
    
    st.pydeck_chart(r)
    
    # 下方显示选中项目的具体明细
    if selected_project_name != "全部显示":
        st.markdown("#### 📝 目标阵地发货明细")
        detail_view = logistics_df[logistics_df["项目部"] == selected_project_name][
            ["交货时间", "物资名称", "规格型号", "钢厂", "数量", "车牌号" if "车牌号" in logistics_df.columns else "数量"]
        ].sort_values("交货时间", ascending=False)
        st.dataframe(detail_view, use_container_width=True, hide_index=True)


def show_data_panel(df, project):
    st.title(f"{project} - 发货数据")
    
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("🔄 刷新"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("🏠 返回首页"):
            st.session_state.project_selected = False
            st.rerun()

    if project == "中铁物贸成都分公司":
        # 总部视图：包含智能驾驶舱
        tabs = ["🚀 智能驾驶舱", "📋 发货计划", "🚛 物流明细", "📊 数据统计"]
        selected_tabs = st.tabs(tabs)
        
        with selected_tabs[0]:
            show_cockpit_tab()
        with selected_tabs[1]:
            show_plan_tab(df, project)
        with selected_tabs[2]:
            show_logistics_tab(project)
        with selected_tabs[3]:
            show_statistics_tab(df)
            
    else:
        # 项目部视图：不显示3D地图，只关注自己的数据
        tabs = ["📋 发货计划", "🚛 物流明细"]
        selected_tabs = st.tabs(tabs)
        with selected_tabs[0]:
            show_plan_tab(df, project)
        with selected_tabs[1]:
            show_logistics_tab(project)


def show_project_selection(df):
    st.markdown("<h1 style='text-align: center;'>钢筋发货监控系统</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>中铁物贸成都分公司</p>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("🏗️ **项目监控**\n\n实时查看各项目进度")
    with c2:
        st.success("🚚 **物流跟踪**\n\n掌握物资发运状态")
        
    st.divider()
    
    log_df = load_logistics_data()
    projs = []
    if not log_df.empty:
        projs = sorted([p for p in log_df["项目部"].unique() if p])
        
    sel = st.selectbox("选择项目部", ["中铁物贸成都分公司"] + projs)
    
    if st.button("进入系统", type="primary", use_container_width=True):
        if sel == "中铁物贸成都分公司":
            st.session_state.temp = sel
            st.session_state.pwd = True
        else:
            st.session_state.project_selected = True
            st.session_state.selected_project = sel
            st.rerun()
            
    if st.session_state.get('pwd', False):
        p = st.text_input("密码", type="password")
        if st.button("确认"):
            if p == "123456":
                st.session_state.project_selected = True
                st.session_state.selected_project = st.session_state.temp
                del st.session_state['pwd']
                st.rerun()
            else:
                st.error("密码错误")


def main():
    st.set_page_config(layout="wide", page_title="发货监控", page_icon="🏗️")
    apply_card_styles()
    
    if 'project_selected' not in st.session_state: st.session_state.project_selected = False
    handle_url_parameters()
    
    df = load_data()
    
    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)

if __name__ == "__main__":
    main()
