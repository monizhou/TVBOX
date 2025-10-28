# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 物流状态独立存储版"""
import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests
import hashlib
import json


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
        "交货时间", "收货地址", "联系人", "联系方式", "项目部",
        "到货状态", "备注"  # 保留到货状态和备注列
    ]

    DATE_FORMAT = "%Y-%m-%d"
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '物资名称': ['材料名称', '品名', '名称'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }
    WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dcf16af3-78d2-433f-9c3d-b4cd108c7b60"
    LOGISTICS_DATE_RANGE_DAYS = 5

    LOGISTICS_STATUS_FILE = "logistics_status.csv"
    # 扩展状态选项
    STATUS_OPTIONS = ["公司统筹中", "钢厂已接单", "运输装货中", "已到货", "未到货"]
    PROJECT_COLUMN = "项目部名称"

    # 项目名称映射（拼音标识）
    PROJECT_MAPPING = {
        "ztwm": "中铁物贸成都分公司",
        "sdtjdzzyykjy": "商投建工达州中医药科技园",
        # 可以继续添加其他项目部的映射
        "hxjyxcjy": "华西简阳西城嘉苑",
        "hxjcn": "华西酒城南",
        "hxmhkckjstg": "华西萌海-科创农业生态谷",
        "hxxlxx": "华西兴隆学校",
        "hxyhkckjstg": "华西颐海-科创农业生态谷",
        "lssxdgjcjrhjdxm2": "乐山市校地共建产教融合基地建设项目二标段",
        "lssxdgjcjrhjdxm1": "乐山市校地共建产教融合基地建设项目一标段",
        "scsjshtyh": "四川商建射洪城乡一体化项目",
        "wyggdzswsgwslcylczx": "五冶钢构达州市公共卫生临床医疗中心项目",
        "wygglqdh70m2": "五冶钢构龙泉东洪片区70亩住宅、商业及配套工程项目二标段",
        "wygglqdh70m3": "五冶钢构龙泉东洪片区70亩住宅、商业及配套工程项目三标段",
        "wygglqdh70m1": "五冶钢构龙泉东洪片区70亩住宅、商业及配套工程项目一标段",
        "wygglqdh85m2": "五冶钢构龙泉东洪片区85亩住宅、商业及配套工程项目二标段",
        "wygglqdh85m3": "五冶钢构龙泉东洪片区85亩住宅、商业及配套工程项目三标段",
        "wygglqdh85m1": "五冶钢构龙泉东洪片区85亩住宅、商业及配套工程项目一标段",
        "wyggybnxgxyj": "五冶钢构-宜宾市南溪区高县月江镇建设项目",
        "wyjscdgjtlgdsl": "五冶建设成都国际铁路港多式联项目",
        "wyjscdydjzxczb2": "五冶建设成都盐道街中学初中部改扩建工程-二标",
        "wyjscdydjzxczb1": "五冶建设成都盐道街中学初中部改扩建工程-一标",
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
    """查找数据文件，增强版本"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            st.success(f"✅ 找到数据文件: {os.path.basename(path)}")
            return path

    # 如果没有找到配置的文件，列出当前目录下的所有Excel文件供选择
    current_dir = os.path.dirname(__file__)
    if current_dir:
        excel_files = [f for f in os.listdir(current_dir) if f.endswith(('.xlsx', '.xls', '.xlsm'))]
        if excel_files:
            st.warning(f"未找到配置的数据文件，但发现以下Excel文件: {', '.join(excel_files)}")
            # 尝试使用第一个Excel文件
            first_excel = os.path.join(current_dir, excel_files[0])
            st.info(f"尝试使用: {excel_files[0]}")
            return first_excel

    st.error("❌ 未找到任何Excel数据文件")
    return None


def apply_card_styles():
    st.markdown(f"""
    <style>
        /* 新增备注卡片样式 */
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

        /* 苹果风格标签页 */
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

        .stTabs [aria-selected="true"]:hover {{
            transform: none;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1),
                        inset 0 0 0 1px rgba(0, 0, 0, 0.06);
        }}

        /* 适配移动端 */
        @media (max-width: 768px) {{
            .stTabs [data-baseweb="tab-list"] {{
                flex-wrap: wrap;
            }}
            .stTabs [data-baseweb="tab"] {{
                flex: 1 1 45%;
                margin: 4px !important;
                text-align: center;
            }}
        }}
        {AppConfig.CARD_STYLES['number_animation']}
        {AppConfig.CARD_STYLES['floating_animation']}
        {AppConfig.CARD_STYLES['pulse_animation']}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

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
        .card-unit {{
            font-size: 0.9rem;
            color: #666;
        }}
        .overdue-row {{ background-color: #ffdddd !important; }}
        .status-arrived {{ background-color: #ddffdd !important; }}
        .status-not-arrived {{ background-color: #ffdddd !important; }}
        .status-empty {{ background-color: transparent !important; }}

        .home-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: all 0.3s ease;
            animation: floating 4s ease-in-out infinite;
        }}
        .home-card:hover {{
            animation: pulse 1.5s infinite;
            box-shadow: {AppConfig.CARD_STYLES['hover_shadow']};
        }}
        .home-card-title {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #2c3e50;
            border-bottom: 2px solid rgba(44, 62, 80, 0.1);
            padding-bottom: 0.5rem;
        }}
        .home-card-content {{
            font-size: 1rem;
            line-height: 1.6;
            color: #555;
        }}
        .home-card-icon {{
            font-size: 2.5rem;
            margin-bottom: 1rem;
            color: #3498db;
        }}
        .project-selector {{
            margin-top: 2rem;
            margin-bottom: 2rem;
        }}
        .welcome-header {{
            font-size: 3.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
        }}
        .welcome-subheader {{
            font-size: 1.5rem;
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
            position: relative;
            padding-bottom: 0.5rem;
        }}
        .dataframe {{
            animation: fadeIn 0.6s ease-out;
        }}
        
        /* 批量更新样式 */
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
        response = requests.post(
            AppConfig.WEBHOOK_URL,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )
        return response.status_code == 200
    except Exception as e:
        st.error(f"飞书通知发送失败: {str(e)}")
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

            if "计划进场时间" in df.columns:
                df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)
                df["超期天数"] = ((pd.Timestamp.now() - df["计划进场时间"]).dt.days.clip(lower=0).fillna(0).astype(int))
            else:
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
            # 尝试读取物流明细表
            try:
                df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')
            except Exception as e:
                st.warning(f"未找到'{AppConfig.LOGISTICS_SHEET_NAME}'工作表: {str(e)}")
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

            # 如果找不到物流明细表，返回空DataFrame
            if df.empty:
                st.warning("物流明细表为空")
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

            # 确保所有必要的列都存在
            for col in AppConfig.LOGISTICS_COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col != "数量" else 0

            # 数据清洗和格式化
            df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
                "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})
            df["钢厂"] = df["钢厂"].astype(str).str.strip().replace({
                "": "未指定钢厂", "nan": "未指定钢厂", "None": "未指定钢厂", None: "未指定钢厂"})
            df["项目部"] = df["项目部"].astype(str).str.strip().replace({
                "未指定项目部": "", "nan": "", "None": "", None: ""})

            # 安全转换数值列
            def safe_convert_numeric(series):
                if series.dtype == 'object':
                    # 处理字符串中的通配符和非数字字符
                    cleaned = series.astype(str).str.replace(r'[^\d.-]', '', regex=True)
                    cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0', ' ': '0'})
                    return pd.to_numeric(cleaned, errors='coerce').fillna(0)
                else:
                    return pd.to_numeric(series, errors='coerce').fillna(0)

            df["数量"] = safe_convert_numeric(df["数量"])

            # 处理日期列
            df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")

            # 处理文本列
            df["联系方式"] = df["联系方式"].astype(str)

            # 生成唯一记录ID
            df["record_id"] = df.apply(generate_record_id, axis=1)

            return df[AppConfig.LOGISTICS_COLUMNS + ["record_id"]]

    except Exception as e:
        st.error(f"物流数据加载失败: {str(e)}")
        # 返回一个空的DataFrame，包含必要的列
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])


# ==================== 物流状态管理 ====================
def load_logistics_status():
    """加载物流状态，只包含到货状态"""
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        try:
            with st.spinner("加载物流状态..."):
                status_df = pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
                # 确保必要的列存在
                if "record_id" not in status_df.columns:
                    status_df["record_id"] = ""
                if "update_time" not in status_df.columns:
                    status_df["update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
                # 移除物流信息列
                if "物流信息" in status_df.columns:
                    status_df = status_df.drop(columns=["物流信息"])
                return status_df
        except Exception as e:
            st.error(f"加载物流状态文件失败: {str(e)}")
            return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])


def save_logistics_status(status_df):
    try:
        with st.spinner("保存状态..."):
            status_df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
            return True
    except Exception as e:
        st.error(f"状态保存失败: {str(e)}")
        return False


def merge_logistics_with_status(logistics_df):
    """合并物流数据和状态数据，添加3天自动到货逻辑，默认状态为钢厂已接单"""
    if logistics_df.empty:
        return logistics_df

    status_df = load_logistics_status()
    
    # 计算3天前的日期
    current_date = datetime.now().date()
    three_days_ago = current_date - timedelta(days=3)
    
    if status_df.empty:
        # 如果没有状态数据，根据交货时间设置默认状态
        logistics_df["到货状态"] = logistics_df.apply(
            lambda row: "已到货" if (
                pd.notna(row["交货时间"]) and 
                row["交货时间"].date() < three_days_ago
            ) else "钢厂已接单",  # 修改：默认状态改为钢厂已接单
            axis=1
        )
        return logistics_df

    # 确保status_df包含必要的列
    required_status_cols = ["record_id", "到货状态"]
    for col in required_status_cols:
        if col not in status_df.columns:
            status_df[col] = ""
    
    # 执行合并
    merged = pd.merge(
        logistics_df,
        status_df[required_status_cols],
        on="record_id",
        how="left",
        suffixes=("", "_status")
    )
    
    # 安全地填充默认值，并应用3天规则
    if "到货状态_status" in merged.columns:
        # 对于没有状态的记录，应用3天规则
        mask_no_status = merged["到货状态_status"].isna()
        mask_old_delivery = merged["交货时间"].apply(
            lambda x: pd.notna(x) and x.date() < three_days_ago
        )
        
        # 对于交货时间超过3天且没有状态的记录，设置为"已到货"
        merged.loc[mask_no_status & mask_old_delivery, "到货状态"] = "已到货"
        # 其他没有状态的记录保持默认状态"钢厂已接单"
        merged.loc[mask_no_status & ~mask_old_delivery, "到货状态"] = "钢厂已接单"  # 修改
        # 对于已有状态的记录，保持原状态
        merged.loc[~mask_no_status, "到货状态"] = merged.loc[~mask_no_status, "到货状态_status"]
        merged = merged.drop(columns=["到货状态_status"])
    else:
        # 如果没有状态列，全部应用3天规则
        merged["到货状态"] = merged.apply(
            lambda row: "已到货" if (
                pd.notna(row["交货时间"]) and 
                row["交货时间"].date() < three_days_ago
            ) else "钢厂已接单",  # 修改：默认状态改为钢厂已接单
            axis=1
        )
    
    return merged


def update_logistics_status(record_id, new_status, original_row=None):
    """更新物流状态（带错误处理）"""
    try:
        status_df = load_logistics_status()

        if new_status is None:
            new_status = "公司统筹中"
        new_status = str(new_status).strip()

        send_notification = False
        if new_status == "未到货":
            existing_status = status_df.loc[status_df["record_id"] == record_id, "到货状态"]
            if len(existing_status) == 0 or existing_status.iloc[0] != "未到货":
                send_notification = True

        if record_id in status_df["record_id"].values:
            status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(
                AppConfig.DATE_FORMAT)
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
                    "交货时间": original_row["交货时间"].strftime("%Y-%m-%d %H:%M") if pd.notna(
                        original_row["交货时间"]) else "未知",
                    "项目部": original_row["项目部"]
                }
                if send_feishu_notification(material_info):
                    st.toast("已发送物流异常通知到相关负责人", icon="📨")
            return True
        return False

    except Exception as e:
        st.error(f"更新状态时出错: {str(e)}")
        return False


def batch_update_logistics_status(record_ids, new_status, original_rows=None):
    """批量更新物流状态"""
    try:
        status_df = load_logistics_status()
        
        if new_status is None:
            new_status = "公司统筹中"
        new_status = str(new_status).strip()

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
                    status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(
                        AppConfig.DATE_FORMAT)
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
                        "交货时间": original_row["交货时间"].strftime("%Y-%m-%d %H:%M") if pd.notna(
                            original_row["交货时间"]) else "未知",
                        "项目部": original_row["项目部"]
                    }
                    send_feishu_notification(material_info)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                st.error(f"更新记录 {record_id} 时出错: {str(e)}")
                continue

        if save_logistics_status(status_df):
            return success_count, error_count
        else:
            return 0, len(record_ids)
            
    except Exception as e:
        st.error(f"批量更新状态时出错: {str(e)}")
        return 0, len(record_ids)


# ==================== URL参数处理 ====================
def handle_url_parameters():
    """处理URL参数，使用拼音标识"""
    query_params = st.experimental_get_query_params()
    
    if 'project' in query_params:
        project_key = query_params['project'][0].lower()  # 转为小写
        project_name = AppConfig.PROJECT_MAPPING.get(project_key, "中铁物贸成都分公司")
        
        # 验证项目部名称是否有效
        valid_projects = get_valid_projects()
        
        if project_name in valid_projects:
            # 直接设置选定的项目部
            st.session_state.project_selected = True
            st.session_state.selected_project = project_name
            
            # 如果是总部，需要密码验证
            if project_name == "中铁物贸成都分公司":
                st.session_state.need_password = True
            else:
                # 项目部直接进入，清除可能的密码状态
                if 'need_password' in st.session_state:
                    del st.session_state['need_password']
                if 'temp_selected_project' in st.session_state:
                    del st.session_state['temp_selected_project']


def get_valid_projects():
    """获取有效的项目部列表"""
    logistics_df = load_logistics_data()
    valid_projects = ["中铁物贸成都分公司"]  # 总部始终有效
    
    if not logistics_df.empty:
        current_date = datetime.now().date()
        start_date = current_date - timedelta(days=15)
        end_date = current_date + timedelta(days=15)

        logistics_df = logistics_df.dropna(subset=['交货时间'])
        logistics_df['交货日期'] = logistics_df['交货时间'].dt.date

        mask = (logistics_df['交货日期'] >= start_date) & (logistics_df['交货日期'] <= end_date)
        filtered_logistics = logistics_df[mask]

        project_list = sorted([p for p in filtered_logistics["项目部"].unique() if p != ""])
        valid_projects.extend(project_list)
    
    return valid_projects


# ==================== 页面组件 ====================
def show_logistics_tab(project):
    # 日期选择器布局调整 - 修改默认值为当天
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        logistics_start_date = st.date_input(
            "开始日期",
            datetime.now().date(),  # 修改：默认当天
            key="logistics_start"
        )
    with date_col2:
        logistics_end_date = st.date_input(
            "结束日期",
            datetime.now().date(),  # 修改：默认当天
            key="logistics_end"
        )

    if logistics_start_date > logistics_end_date:
        st.error("结束日期不能早于开始日期")
        return

    with st.spinner("加载物流信息..."):
        logistics_df = load_logistics_data()
        if project != "中铁物贸成都分公司":
            logistics_df = logistics_df[logistics_df["项目部"] == project]

        if not logistics_df.empty:
            logistics_df = merge_logistics_with_status(logistics_df)

            # 修复日期比较问题 - 确保类型一致
            start_date_pd = pd.to_datetime(logistics_start_date)
            end_date_pd = pd.to_datetime(logistics_end_date) + timedelta(days=1)  # 包含结束日期的全天

            mask = (
                    (logistics_df["交货时间"] >= start_date_pd) &
                    (logistics_df["交货时间"] < end_date_pd)
            )
            filtered_df = logistics_df[mask].copy()

            # =============== 统一卡片样式 ===============
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)

            overdue_count = filtered_df['到货状态'].eq('未到货').sum()
            total_count = len(filtered_df)
            arrived_count = filtered_df['到货状态'].eq('已到货').sum()
            in_progress_count = total_count - arrived_count - overdue_count

            cols = st.columns(4)
            metrics = [
                ("📦", "总物流单数", f"{total_count}", "单"),
                ("✅", "已到货单数", f"{arrived_count}", "单"),
                ("🔄", "进行中订单", f"{in_progress_count}", "单"),
                ("⚠️", "未到货订单", f"{overdue_count}", "单")
            ]

            for idx, metric in enumerate(metrics):
                with cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <span style="font-size:1.2rem">{metric[0]}</span>
                            <span style="font-weight:600">{metric[1]}</span>
                        </div>
                        <div class="card-value">{metric[2]}</div>
                        <div class="card-unit">{metric[3]}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

            st.caption(f"显示 {logistics_start_date} 至 {logistics_end_date} 的数据（共 {len(filtered_df)} 条记录）")

            # =============== 批量更新功能 ===============
            st.markdown("""
            <div class="batch-update-card">
                <div class="batch-update-title">📦 批量更新到货状态</div>
            </div>
            """, unsafe_allow_html=True)
            
            batch_col1, batch_col2, batch_col3 = st.columns([2, 2, 1])
            
            with batch_col1:
                # 多选下拉框选择记录
                record_options = []
                record_mapping = {}
                for idx, row in filtered_df.iterrows():
                    display_text = f"{row['物资名称']} - {row['规格型号']} - {row['钢厂']} - {row['数量']}吨"
                    record_options.append(display_text)
                    record_mapping[display_text] = row['record_id']
                
                selected_records = st.multiselect(
                    "选择要批量更新的记录",
                    options=record_options,
                    placeholder="选择多条记录进行批量更新..."
                )
            
            with batch_col2:
                # 选择新状态
                new_status = st.selectbox(
                    "选择新的到货状态",
                    options=AppConfig.STATUS_OPTIONS,
                    index=0,
                    key="batch_status"
                )
            
            with batch_col3:
                st.write("")  # 空行用于对齐
                st.write("")  # 空行用于对齐
                batch_update_btn = st.button(
                    "🚀 批量更新",
                    type="primary",
                    use_container_width=True,
                    key="batch_update_btn"
                )
            
            # 处理批量更新
            if batch_update_btn and selected_records:
                if not selected_records:
                    st.warning("请先选择要更新的记录")
                else:
                    record_ids = [record_mapping[record] for record in selected_records]
                    original_rows = [filtered_df[filtered_df['record_id'] == record_id].iloc[0] for record_id in record_ids]
                    
                    with st.spinner(f"正在批量更新 {len(record_ids)} 条记录..."):
                        success_count, error_count = batch_update_logistics_status(
                            record_ids, 
                            new_status,
                            original_rows
                        )
                    
                    if success_count > 0:
                        st.success(f"✅ 成功更新 {success_count} 条记录的状态为【{new_status}】")
                        if error_count > 0:
                            st.error(f"❌ 有 {error_count} 条记录更新失败")
                        
                        # 清空选择
                        st.rerun()
                    else:
                        st.error("❌ 批量更新失败，请重试")

            # 准备显示的列（排除record_id）
            display_columns = [col for col in filtered_df.columns if col != "record_id"]
            display_df = filtered_df[display_columns].copy()

            # 重置索引以确保一致性
            display_df = display_df.reset_index(drop=True)

            # 使用自动保存的数据编辑器
            st.markdown("**物流明细表** (状态更改会自动保存)")
            edited_df = st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "到货状态": st.column_config.SelectboxColumn(
                        "到货状态",
                        options=AppConfig.STATUS_OPTIONS,
                        default="公司统筹中",
                        required=True,
                        width="medium"
                    ),
                    "备注": st.column_config.TextColumn(
                        "备注",
                        help="可自由编辑的备注信息",
                        width="large"
                    ),
                    "数量": st.column_config.NumberColumn(
                        "数量",
                        format="%d",
                        width=90  # 设置列宽为9
                    ),
                    "交货时间": st.column_config.DatetimeColumn(
                        "交货时间",
                        format="YYYY-MM-DD HH:mm",
                        width="medium"
                    ),
                    **{col: {"width": "auto"} for col in display_columns if
                       col not in ["到货状态", "备注", "数量", "交货时间"]}
                },
                key=f"logistics_editor_{project}"
            )

            # 自动处理状态更改
            auto_process_logistics_changes(edited_df, filtered_df, project)

            st.markdown("""
            <div class="remark-card logistics-remark">
                <div class="remark-content">
                    📢 以上数据为公司已安排的发货情况
                </div>
            </div>
            """, unsafe_allow_html=True)

            status_df = load_logistics_status()
            if not status_df.empty:
                last_update = pd.to_datetime(status_df["update_time"]).max()
                st.caption(f"状态最后更新时间: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("📭 当前没有物流数据")


def auto_process_logistics_changes(edited_df, original_filtered_df, project):
    """自动处理物流状态更改"""
    if f'logistics_editor_{project}' not in st.session_state:
        return

    changed_rows = st.session_state[f'logistics_editor_{project}'].get('edited_rows', {})

    if not changed_rows:
        return

    # 使用session_state记录已处理的更改，避免重复处理
    processed_key = f"processed_changes_{project}"
    if processed_key not in st.session_state:
        st.session_state[processed_key] = set()

    # 处理新的更改
    new_changes = []
    for row_index_str, changes in changed_rows.items():
        # 生成唯一标识符，包含所有可能更改的字段
        change_hash = f"{row_index_str}_{changes.get('到货状态', '')}"
        if change_hash not in st.session_state[processed_key]:
            new_changes.append((row_index_str, changes))
            st.session_state[processed_key].add(change_hash)

    if not new_changes:
        return

    # 处理新的更改
    success_count = 0
    error_count = 0

    for row_index_str, changes in new_changes:
        try:
            # 确保行索引在有效范围内
            row_index = int(row_index_str)
            if row_index < 0 or row_index >= len(original_filtered_df):
                st.warning(f"跳过无效的行索引: {row_index}")
                error_count += 1
                continue

            record_id = original_filtered_df.iloc[row_index]["record_id"]
            original_row = original_filtered_df.iloc[row_index]

            # 获取新的状态
            new_status = changes.get("到货状态", original_row["到货状态"])

            # 只有当状态真正改变时才更新
            status_changed = new_status != original_row["到货状态"]
            
            if status_changed:
                # 更新状态
                if update_logistics_status(record_id, new_status, original_row):
                    success_count += 1
                    # 使用toast显示成功消息
                    st.toast(f"✅ 已自动保存: {original_row['物资名称']} - 状态: {original_row['到货状态']} → {new_status}", icon="✅")
                else:
                    error_count += 1
                    st.toast(f"❌ 保存失败: {original_row['物资名称']}", icon="❌")

        except (ValueError, KeyError, IndexError) as e:
            st.warning(f"处理行 {row_index_str} 时出错: {str(e)}")
            error_count += 1
            continue

    # 显示处理结果摘要
    if success_count > 0:
        # 使用成功消息但不阻塞界面
        st.success(f"已自动保存 {success_count} 条状态更改")

        # 3秒后清除成功消息
        time.sleep(3)
        st.empty()

    if error_count > 0:
        st.error(f"有 {error_count} 条记录保存失败")


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


def show_project_selection(df):
    st.markdown("""
    <div class="welcome-header">
        欢迎使用钢筋发货监控系统
    </div>
    <div class="welcome-subheader">
        中铁物贸成都分公司 - 四川经营中心
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="home-card">
            <div class="home-card-icon">🏗️</div>
            <div class="home-card-title">项目监控</div>
            <div class="home-card-content">
                实时监控各项目钢筋发货情况，确保工程进度顺利推进。
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="home-card">
            <div class="home-card-icon">🚚</div>
            <div class="home-card-title">物流跟踪</div>
            <div class="home-card-content">
                跟踪钢材物流状态，及时掌握物资到货情况。
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="project-selector">', unsafe_allow_html=True)

    with st.spinner("加载项目部信息..."):
        logistics_df = load_logistics_data()
        valid_projects = []

        if not logistics_df.empty:
            current_date = datetime.now().date()
            start_date = current_date - timedelta(days=15)
            end_date = current_date + timedelta(days=15)

            logistics_df = logistics_df.dropna(subset=['交货时间'])
            logistics_df['交货日期'] = logistics_df['交货时间'].dt.date

            mask = (logistics_df['交货日期'] >= start_date) & (logistics_df['交货日期'] <= end_date)
            filtered_logistics = logistics_df[mask]

            valid_projects = sorted([p for p in filtered_logistics["项目部"].unique() if p != ""])

    selected = st.selectbox(
        "选择项目部",
        ["中铁物贸成都分公司"] + valid_projects,
        key="project_selector"
    )

    if st.button("确认进入", type="primary"):
        if selected == "中铁物贸成都分公司":
            st.session_state.temp_selected_project = selected
            st.session_state.need_password = True
        else:
            st.session_state.project_selected = True
            st.session_state.selected_project = selected
        st.rerun()

    if st.session_state.get('need_password', False):
        password = st.text_input("请输入密码",
                                 type="password",
                                 key="password_input")
        if st.button("验证密码"):
            if password == "123456":
                st.session_state.project_selected = True
                st.session_state.selected_project = st.session_state.temp_selected_project
                keys_to_remove = ['need_password', 'temp_selected_project']
                for key in keys_to_remove:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            else:
                st.error("密码错误，请重新输入")

    st.markdown('</div>', unsafe_allow_html=True)


def show_data_panel(df, project):
    st.title(f"{project} - 发货数据")

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新数据"):
            with st.spinner("刷新数据中..."):
                st.cache_data.clear()
                st.rerun()
    with col2:
        if st.button("← 返回首页"):
            st.session_state.project_selected = False
            st.rerun()

    tab1, tab2 = st.tabs(["📋 发货计划", "🚛 物流明细"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", datetime.now() - timedelta(days=0))
        with col2:
            end_date = st.date_input("结束日期", datetime.now())

        if start_date > end_date:
            st.error("日期范围无效")
        else:
            with st.spinner("筛选数据..."):
                filtered_df = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
                date_range_df = filtered_df[
                    (filtered_df["下单时间"].dt.date >= start_date) &
                    (filtered_df["下单时间"].dt.date <= end_date)
                    ]

                if not date_range_df.empty:
                    display_metrics_cards(date_range_df)

                    display_cols = {
                        "标段名称": "工程标段",
                        "物资名称": "材料名称",
                        "规格型号": "规格型号",
                        "需求量": "需求(吨)",
                        "已发量": "已发(吨)",
                        "剩余量": "待发(吨)",
                        "超期天数": "超期天数",
                        "下单时间": "下单时间",
                        "计划进场时间": "计划进场时间"
                    }

                    available_cols = {k: v for k, v in display_cols.items() if k in date_range_df.columns}
                    display_df = date_range_df[available_cols.keys()].rename(columns=available_cols)

                    if "材料名称" in display_df.columns:
                        display_df["材料名称"] = display_df["材料名称"].fillna("未指定物资")

                    st.dataframe(
                        display_df.style.format({
                            '需求(吨)': '{:,}',
                            '已发(吨)': '{:,}',
                            '待发(吨)': '{:,}',
                            '超期天数': '{:,}',
                            '下单时间': lambda x: x.strftime('%Y-%m-%d') if not pd.isnull(x) else '',
                            '计划进场时间': lambda x: x.strftime('%Y-%m-%d') if not pd.isnull(x) else ''
                        }).apply(
                            lambda row: ['background-color: #ffdddd' if row.get('超期天数', 0) > 0 else ''
                                         for _ in row],
                            axis=1
                        ),
                        use_container_width=True,
                        height=min(600, 35 * len(display_df) + 40),
                        hide_index=True
                    )

                    st.markdown("""
                    <div class="remark-card plan-remark">
                        <div class="remark-content">
                            📢 以上计划已全部提报给公司
                            📢 温馨提示：公司更新发货台账为当天下午6:00 ！！！
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.download_button(
                        "⬇️ 导出数据",
                        display_df.to_csv(index=False).encode('utf-8-sig'),
                        f"{project}_发货数据_{start_date}_{end_date}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                else:
                    st.info("该时间段无数据")

    with tab2:
        show_logistics_tab(project)


# ==================== 主程序 ====================
def main():
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )
    apply_card_styles()

    # 初始化session state
    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = "中铁物贸成都分公司"

    # 处理URL参数
    handle_url_parameters()

    with st.spinner('加载数据中...'):
        df = load_data()

    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)


if __name__ == "__main__":
    main()


