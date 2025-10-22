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

    # 可能的物流工作表名称
    LOGISTICS_SHEET_NAMES = ["物流明细", "物流信息", "发货明细", "运输明细", "物流数据"]
    LOGISTICS_COLUMNS = [
        "钢厂", "物资名称", "规格型号", "单位", "数量",
        "交货时间", "收货地址", "联系人", "联系方式", "项目部",
        "到货状态", "物流信息"
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
    # 更新状态选项，包含完整的发货流程
    STATUS_OPTIONS = ["公司统筹中", "钢厂已接单", "运输中", "已到货", "未到货"]
    PROJECT_COLUMN = "项目部名称"

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
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)

    try:
        with st.spinner("正在加载物流数据..."):
            # 尝试读取所有可能的工作表名称
            df = None
            found_sheet = None
            
            # 首先尝试获取所有工作表名称
            try:
                excel_file = pd.ExcelFile(data_path, engine='openpyxl')
                sheet_names = excel_file.sheet_names
                st.info(f"发现的工作表: {', '.join(sheet_names)}")
                
                # 尝试匹配物流工作表
                for sheet_name in sheet_names:
                    for possible_name in AppConfig.LOGISTICS_SHEET_NAMES:
                        if possible_name in sheet_name:
                            found_sheet = sheet_name
                            st.success(f"找到物流工作表: {found_sheet}")
                            break
                    if found_sheet:
                        break
                
                # 如果没有找到匹配的工作表，使用第一个工作表
                if not found_sheet and sheet_names:
                    found_sheet = sheet_names[0]
                    st.warning(f"未找到标准物流工作表，使用第一个工作表: {found_sheet}")
                
            except Exception as e:
                st.error(f"读取Excel文件结构失败: {str(e)}")
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])
            
            if not found_sheet:
                st.error("Excel文件中没有找到任何工作表")
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])
            
            # 读取选定的工作表
            try:
                df = pd.read_excel(data_path, sheet_name=found_sheet, engine='openpyxl')
                st.success(f"成功读取工作表: {found_sheet}")
            except Exception as e:
                st.error(f"读取工作表 {found_sheet} 失败: {str(e)}")
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

            # 如果找不到物流明细表，返回空DataFrame
            if df.empty:
                st.warning("物流明细表为空")
                return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

            # 显示原始列名以便调试
            st.info(f"原始列名: {list(df.columns)}")

            # 列名映射 - 处理可能的列名变体
            column_mapping = {}
            expected_columns = AppConfig.LOGISTICS_COLUMNS
            
            for expected_col in expected_columns:
                # 尝试精确匹配
                if expected_col in df.columns:
                    column_mapping[expected_col] = expected_col
                    continue
                
                # 尝试模糊匹配
                found = False
                for actual_col in df.columns:
                    # 忽略大小写和空格差异
                    if (expected_col.lower().replace(" ", "") in actual_col.lower().replace(" ", "") or
                        actual_col.lower().replace(" ", "") in expected_col.lower().replace(" ", "")):
                        column_mapping[expected_col] = actual_col
                        found = True
                        st.info(f"列名映射: '{actual_col}' -> '{expected_col}'")
                        break
                
                if not found:
                    st.warning(f"未找到匹配 '{expected_col}' 的列")
                    # 添加空列
                    df[expected_col] = "" if expected_col != "数量" else 0

            # 重命名列
            df = df.rename(columns={v: k for k, v in column_mapping.items() if k != v})

            # 确保所有必要的列都存在
            for col in AppConfig.LOGISTICS_COLUMNS:
                if col not in df.columns:
                    if col == "物流信息":
                        df[col] = ""  # 物流信息列默认为空字符串
                    elif col == "数量":
                        df[col] = 0   # 数量列默认为0
                    else:
                        df[col] = ""   # 其他文本列默认为空字符串

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
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        try:
            with st.spinner("加载物流状态..."):
                status_df = pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
                # 确保必要的列存在
                if "record_id" not in status_df.columns:
                    status_df["record_id"] = ""
                if "到货状态" not in status_df.columns:
                    status_df["到货状态"] = "公司统筹中"  # 默认状态
                if "物流信息" not in status_df.columns:
                    status_df["物流信息"] = ""  # 新增物流信息列
                if "update_time" not in status_df.columns:
                    status_df["update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
                return status_df
        except Exception as e:
            st.error(f"加载物流状态文件失败: {str(e)}")
            return pd.DataFrame(columns=["record_id", "到货状态", "物流信息", "update_time"])
    return pd.DataFrame(columns=["record_id", "到货状态", "物流信息", "update_time"])


def save_logistics_status(status_df):
    try:
        with st.spinner("保存状态..."):
            status_df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
            return True
    except Exception as e:
        st.error(f"状态保存失败: {str(e)}")
        return False


def merge_logistics_with_status(logistics_df):
    if logistics_df.empty:
        return logistics_df

    status_df = load_logistics_status()
    if status_df.empty:
        logistics_df["到货状态"] = "公司统筹中"  # 默认状态
        logistics_df["物流信息"] = ""  # 新增物流信息列
        return logistics_df

    merged = pd.merge(
        logistics_df,
        status_df[["record_id", "到货状态", "物流信息"]],
        on="record_id",
        how="left",
        suffixes=("", "_status")
    )
    # 填充缺失值
    merged["到货状态"] = merged["到货状态_status"].fillna("公司统筹中")
    merged["物流信息"] = merged["物流信息_status"].fillna("")
    return merged.drop(columns=["到货状态_status", "物流信息_status"])


def update_logistics_status(record_id, new_status, logistics_info="", original_row=None):
    """更新物流状态和物流信息（带错误处理）"""
    try:
        status_df = load_logistics_status()

        if new_status is None:
            new_status = "公司统筹中"  # 默认状态
        new_status = str(new_status).strip()
        
        if logistics_info is None:
            logistics_info = ""
        logistics_info = str(logistics_info).strip()

        send_notification = False
        if new_status == "未到货":
            existing_status = status_df.loc[status_df["record_id"] == record_id, "到货状态"]
            if len(existing_status) == 0 or existing_status.iloc[0] != "未到货":
                send_notification = True

        if record_id in status_df["record_id"].values:
            if new_status == "":
                status_df = status_df[status_df["record_id"] != record_id]
            else:
                status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
                status_df.loc[status_df["record_id"] == record_id, "物流信息"] = logistics_info
                status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(
                    AppConfig.DATE_FORMAT)
        elif new_status != "":
            new_record = pd.DataFrame([{
                "record_id": record_id,
                "到货状态": new_status,
                "物流信息": logistics_info,
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


# ==================== 页面组件 ====================
def show_logistics_tab(project):
    # 日期选择器布局调整
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        logistics_start_date = st.date_input(
            "开始日期",
            datetime.now().date() - timedelta(days=AppConfig.LOGISTICS_DATE_RANGE_DAYS),
            key="logistics_start"
        )
    with date_col2:
        logistics_end_date = st.date_input(
            "结束日期",
            datetime.now().date(),
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

            total_count = len(filtered_df)
            arrived_count = len(filtered_df[filtered_df['到货状态'] == '已到货'])
            not_arrived_count = len(filtered_df[filtered_df['到货状态'] == '未到货'])
            coordinating_count = len(filtered_df[filtered_df['到货状态'] == '公司统筹中'])
            accepted_count = len(filtered_df[filtered_df['到货状态'] == '钢厂已接单'])
            transporting_count = len(filtered_df[filtered_df['到货状态'] == '运输中'])

            cols = st.columns(5)
            metrics = [
                ("📦", "总物流单数", f"{total_count}", "单"),
                ("🏢", "公司统筹中", f"{coordinating_count}", "单"),
                ("✅", "钢厂已接单", f"{accepted_count}", "单"),
                ("🚚", "运输中", f"{transporting_count}", "单"),
                ("📬", "已到货", f"{arrived_count}", "单")
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
                        default="公司统筹中",  # 设置默认状态
                        required=True,
                        width="medium"
                    ),
                    "数量": st.column_config.NumberColumn(
                        "数量",
                        format="%d",
                        width=100  # 设置数量列宽为10个字符宽度
                    ),
                    "物流信息": st.column_config.TextColumn(
                        "物流信息",
                        width="large",  # 物流信息列可以宽一些
                        help="可输入物流跟踪号、备注等信息"
                    ),
                    "交货时间": st.column_config.DatetimeColumn(
                        "交货时间",
                        format="YYYY-MM-DD HH:mm",
                        width="medium"
                    ),
                    **{col: {"width": "auto"} for col in display_columns if
                       col not in ["到货状态", "数量", "物流信息", "交货时间"]}
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
        change_hash = f"{row_index_str}_{changes.get('到货状态', '')}_{changes.get('物流信息', '')}"
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

            # 获取原始行数据
            original_row = original_filtered_df.iloc[row_index]
            record_id = original_row["record_id"]

            # 获取更改后的状态和物流信息
            new_status = changes.get("到货状态", original_row["到货状态"])
            new_logistics_info = changes.get("物流信息", original_row.get("物流信息", ""))

            # 获取当前状态和物流信息
            current_status = original_row["到货状态"]
            current_logistics_info = original_row.get("物流信息", "")

            # 只有当状态或物流信息真正改变时才更新
            if new_status != current_status or new_logistics_info != current_logistics_info:
                # 更新状态
                if update_logistics_status(record_id, new_status, new_logistics_info, original_row):
                    success_count += 1
                    # 使用toast显示成功消息
                    status_msg = f"状态: {new_status}" if new_status != current_status else ""
                    info_msg = f"物流信息已更新" if new_logistics_info != current_logistics_info else ""
                    msg = " | ".join([part for part in [status_msg, info_msg] if part])
                    if msg:
                        st.toast(f"✅ {original_row['物资名称']} - {msg}", icon="✅")
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
        st.success(f"已自动保存 {success_count} 条更改")

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


def show_data_panel(df, project):
    st.title(f"{project} - 发货数据")

    if st.button("🔄 刷新数据"):
        with st.spinner("刷新数据中..."):
            st.cache_data.clear()
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

    # 从URL参数获取项目名称
    query_params = st.experimental_get_query_params()
    project_name = query_params.get("project", ["中铁物贸成都分公司"])[0]
    
    # 设置默认项目
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = project_name

    with st.spinner('加载数据中...'):
        df = load_data()

    # 直接显示数据面板，无需选择
    show_data_panel(df, st.session_state.selected_project)


if __name__ == "__main__":
    main()
