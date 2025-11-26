# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 战术雷达动画版"""
import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests
import hashlib
import json
import plotly.express as px
import plotly.graph_objects as go

# ==================== 系统配置 ====================
class AppConfig:
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsm"),
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]

    LOGISTICS_SHEET_NAME = "物流明细"
    
    # 调整列顺序，"卸货地址" 放在 "联系人" 左边
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

    # 清爽的卡片样式
    CARD_STYLES = {
        "glass_effect": """
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 1px solid #f0f2f6;
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


def apply_card_styles():
    st.markdown(f"""
    <style>
        .remark-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            border-left: 4px solid;
            color: #444;
        }}
        .plan-remark {{ border-color: #3498db; }}
        .logistics-remark {{ border-color: #2ecc71; }}
        .remark-content {{
            font-size: 1rem;
            text-align: center;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            padding: 8px 0;
            border-radius: 8px;
        }}
        .metric-container {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 1rem; 
            margin: 1rem 0; 
        }}
        .metric-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            transition: transform 0.2s;
        }}
        .metric-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        }}
        .card-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #2c3e50;
            margin: 0.5rem 0;
        }}
        .card-unit {{
            font-size: 0.9rem;
            color: #666;
        }}
        div[data-testid="stDataEditor"] table td {{
            font-size: 13px !important;
        }}
        
        /* 首页样式 */
        .home-card {{
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            text-align: center;
            transition: all 0.3s ease;
            border: 1px solid #eee;
            margin-bottom: 20px;
        }}
        .home-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }}
        .home-card-title {{
            font-size: 1.4rem;
            font-weight: bold;
            margin: 1rem 0;
            color: #2c3e50;
        }}
        .home-card-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
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

            if "计划进场时间" in df.columns:
                df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)
            
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
                
                # 强制从 G列 (索引6) 读取数据作为 "卸货地址"
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
                if send_feishu_notification(material_info):
                    st.toast("已发送物流异常通知", icon="📨")
            return True
        return False
    except Exception:
        return False


def batch_update_logistics_status(record_ids, new_status, original_rows=None):
    try:
        status_df = load_logistics_status()
        new_status = str(new_status).strip() if new_status else "公司统筹中"
        success_count = 0
        
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
                continue

        if save_logistics_status(status_df):
            return success_count, 0
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

            st.markdown("##### 📦 批量状态更新")
            b_col1, b_col2, b_col3 = st.columns([2, 2, 1])
            with b_col1:
                record_map = {f"{r['物资名称']} - {r['规格型号']} - {r['钢厂']} - {r['数量']}吨": r['record_id'] for _, r in filtered.iterrows()}
                sel_recs = st.multiselect("选择记录", options=list(record_map.keys()))
            with b_col2:
                new_st = st.selectbox("新状态", AppConfig.STATUS_OPTIONS)
            with b_col3:
                st.write("")
                st.write("")
                if st.button("🚀 更新", type="primary") and sel_recs:
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


def show_interactive_analysis(df):
    """战术雷达：供需脉冲矩阵 (Tactical Pulse Matrix)"""
    
    # 1. 标题与风格定义
    st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem;">
            <h1 style="
                background: linear-gradient(to right, #00f260, #0575e6);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.5rem;
                font-weight: 800;
                letter-spacing: 2px;
            ">TACTICAL SUPPLY RADAR</h1>
            <p style="color: #888; font-family: monospace; letter-spacing: 3px; font-size: 0.9rem;">
                >>> SUPPLY-DEMAND MATRIX MONITORING SYSTEM <<<
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # 2. 筛选器
    with st.expander("⚙️ 雷达参数设置 / 筛选", expanded=False):
        all_factories = ["全部"] + sorted(list(df["钢厂"].unique()))
        # 优先使用卸货地址，如果没有则使用项目部
        if "卸货地址" in df.columns:
            # 填充空地址为项目部名称
            df["显示地址"] = df["卸货地址"].replace("", None).fillna(df["项目部"])
        else:
            df["显示地址"] = df["项目部"]
            
        all_addresses = ["全部"] + sorted(list(df["显示地址"].unique()))
        
        c1, c2 = st.columns(2)
        with c1:
            sel_factories = st.multiselect("🏭 供方 (钢厂)", all_factories, default="全部")
        with c2:
            sel_addresses = st.multiselect("📍 需方 (卸货地址)", all_addresses, default="全部")

    # 3. 数据过滤
    filtered_df = df.copy()
    if "全部" not in sel_factories and sel_factories:
        filtered_df = filtered_df[filtered_df["钢厂"].isin(sel_factories)]
    if "全部" not in sel_addresses and sel_addresses:
        filtered_df = filtered_df[filtered_df["显示地址"].isin(sel_addresses)]
        
    if filtered_df.empty:
        st.warning("⚠️ 暂无监控数据")
        return

    # 4. 动画数据准备
    anim_df = filtered_df[["交货时间", "钢厂", "显示地址", "数量", "物资名称"]].copy()
    anim_df["日期"] = anim_df["交货时间"].dt.date
    
    # 按天、钢厂、地址汇总 (每天可能有多个物资，这里按物资类型着色)
    grouped = anim_df.groupby(["日期", "钢厂", "显示地址", "物资名称"])["数量"].sum().reset_index()
    
    # 确保日期连续 (为了动画流畅，即使某天没数据也要有帧)
    if not grouped.empty:
        min_date = grouped["日期"].min()
        max_date = grouped["日期"].max()
        # 如果跨度太大，限制一下，避免渲染太慢
        if (max_date - min_date).days > 60:
            min_date = max_date - timedelta(days=60)
            grouped = grouped[grouped["日期"] >= min_date]
            
        grouped["日期Str"] = grouped["日期"].astype(str)
        
        # 5. 绘制脉冲矩阵
        fig = px.scatter(
            grouped,
            x="钢厂",
            y="显示地址",
            size="数量",
            color="物资名称",
            animation_frame="日期Str",
            animation_group="显示地址",
            size_max=50, # 气泡最大尺寸
            hover_name="物资名称",
            range_x=[-0.5, len(grouped["钢厂"].unique()) - 0.5], # 稍微留边
            # 使用鲜艳的霓虹配色
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        
        # 6. 高科技暗黑风格定制
        fig.update_layout(
            template="plotly_dark", # 暗黑底色
            height=700,
            paper_bgcolor='rgba(0,0,0,0)', # 透明背景融入网页
            plot_bgcolor='rgba(10,10,20,0.8)', # 深蓝黑绘图区
            xaxis=dict(
                title="SUPPLIER (SOURCE)",
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)', # 隐约的网格
                tickfont=dict(size=12, color="#00f260")
            ),
            yaxis=dict(
                title="DESTINATION (TARGET)",
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                tickfont=dict(size=12, color="#00f260")
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=0, r=0, t=50, b=0),
            # 播放按钮样式
            updatemenus=[{
                "type": "buttons",
                "showactive": False,
                "x": 0.05, "y": 1.15,
                "buttons": [{
                    "label": "▶ ACTIVATE RADAR",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 300, "redraw": True}, "fromcurrent": True}]
                }]
            }]
        )
        
        # 去掉X/Y轴的零线，让网格更纯粹
        fig.update_xaxes(zeroline=False)
        fig.update_yaxes(zeroline=False)
        
        # 时间滑块样式
        fig.layout.sliders[0].currentvalue = {
            "prefix": "MONITORING DATE: ", 
            "font": {"size": 20, "color": "#00f260", "family": "monospace"}
        }
        fig.layout.sliders[0].pad = {"t": 50}
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("""
            <div style="text-align: center; margin-top: -10px; color: #666; font-size: 12px; font-family: monospace;">
                [SYSTEM STATUS: ONLINE] • DATA REFRESH RATE: REAL-TIME
            </div>
        """, unsafe_allow_html=True)
        
    else:
        st.info("📉 当前时间段内无发货记录")


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
        analysis_df = load_logistics_data()
        tabs = ["📋 发货计划", "🚛 物流明细", "📊 静态统计", "🚀 数据驾驶舱"]
    else:
        full = load_logistics_data()
        analysis_df = full[full["项目部"] == project]
        tabs = ["📋 发货计划", "🚛 物流明细", "🚀 数据驾驶舱"]
    
    if not analysis_df.empty:
        analysis_df = merge_logistics_with_status(analysis_df)

    selected_tabs = st.tabs(tabs)

    with selected_tabs[0]:
        show_plan_tab(df, project)
    
    with selected_tabs[1]:
        show_logistics_tab(project)
        
    if project == "中铁物贸成都分公司":
        with selected_tabs[2]:
            show_statistics_tab(df)
        with selected_tabs[3]:
            show_interactive_analysis(analysis_df)
    else:
        with selected_tabs[2]:
            show_interactive_analysis(analysis_df)


def show_plan_tab(df, project):
    col1, col2 = st.columns(2)
    with col1: start = st.date_input("开始", datetime.now(), key="ps")
    with col2: end = st.date_input("结束", datetime.now(), key="pe")
    
    filtered = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    mask = (filtered["下单时间"].dt.date >= start) & (filtered["下单时间"].dt.date <= end)
    res = filtered[mask]
    
    if not res.empty:
        cols = {
            "标段名称": "工程标段", "物资名称": "材料名称", "规格型号": "规格型号",
            "需求量": "需求(吨)", "已发量": "已发(吨)", "剩余量": "待发(吨)",
            "超期天数": "超期天数", "下单时间": "下单", "计划进场时间": "计划进场"
        }
        disp = res[list(cols.keys())].rename(columns=cols)
        st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.info("无数据")


def show_statistics_tab(df):
    st.subheader("📊 数据统计")
    log_df = load_logistics_data()
    if log_df.empty: return
    
    grp = log_df.groupby(['项目部', '钢厂'])['数量'].sum().reset_index()
    st.dataframe(grp, use_container_width=True)


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
