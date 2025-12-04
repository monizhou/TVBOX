# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 移动端交互优化版"""
import os
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
        # ... (原有映射保持不变，为节省篇幅省略部分，代码运行时请保留完整映射)
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
        /* ========== 核心布局优化 ========== */
        
        /* 指标卡网格系统 */
        .metric-grid {{
            display: grid;
            gap: 10px;
            margin: 1rem 0;
            /* 电脑端默认：自动填充，每列最小140px，通常会是一行4个 */
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        }}

        /* 📱 移动端针对性调整 */
        @media (max-width: 640px) {{
            .block-container {{
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
                padding-top: 2rem !important;
            }}
            /* 移动端指标卡：强制 2列布局 (2x2)，避免挤在一行看不清，也避免一列太占地 */
            .metric-grid {{
                grid-template-columns: repeat(2, 1fr) !important; 
            }}
            /* Tab 调整 */
            .stTabs [data-baseweb="tab"] {{
                padding: 8px 10px !important;
                font-size: 13px !important;
                flex: 1; 
            }}
            h1 {{ font-size: 1.6rem !important; }}
        }}

        /* 通用卡片样式 */
        .metric-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            transition: all 0.3s ease;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 90px;
        }}
        .metric-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .card-value {{
            font-size: 1.6rem;
            font-weight: 700;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0.3rem 0;
            line-height: 1.2;
        }}
        .card-unit {{ font-size: 0.8rem; color: #666; }}
        
        /* 列表卡片样式 (移动端) */
        .mobile-list-card {{
            background: white;
            padding: 12px;
            margin-bottom: 12px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 5px solid #ddd;
        }}
        
        /* 备注卡片 */
        .remark-card {{
            background: rgba(245, 245, 247, 0.9);
            border-radius: 10px;
            padding: 1rem;
            margin: 1.5rem 0;
            border-left: 4px solid;
            font-size: 0.9rem;
            color: #555;
            text-align: center;
        }}
        .plan-remark {{ border-color: #2196F3; }}
        .logistics-remark {{ border-color: #4CAF50; }}
        
        /* 动画 */
        {AppConfig.CARD_STYLES['number_animation']}
        
    </style>
    """, unsafe_allow_html=True)

def generate_record_id(row):
    key_fields = [
        str(row["钢厂"]), str(row["物资名称"]), str(row["规格型号"]),
        str(row["交货时间"]), str(row["项目部"])
    ]
    return hashlib.md5("|".join(key_fields).encode('utf-8')).hexdigest()

def send_feishu_notification(material_info):
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"template": "red", "title": {"content": "【物流状态更新通知】", "tag": "plain_text"}},
            "elements": [
                {"tag": "div", "text": {"content": f"**物资**: {material_info['物资名称']}\n**规格**: {material_info['规格型号']}\n**数量**: {material_info['数量']}\n**项目**: {material_info['项目部']}", "tag": "lark_md"}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"content": "⚠️ 状态已更新为【未到货】", "tag": "plain_text"}]}
            ]
        }
    }
    try:
        requests.post(AppConfig.WEBHOOK_URL, data=json.dumps(message), headers={'Content-Type': 'application/json'})
        return True
    except:
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
    if not data_path: return pd.DataFrame()

    try:
        with st.spinner("正在加载基础数据..."):
            df = pd.read_excel(data_path, engine='openpyxl')
            for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
                for alt_col in alt_cols:
                    if alt_col in df.columns and std_col not in df.columns:
                        df.rename(columns={alt_col: std_col}, inplace=True)
                        break

            df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({"nan": "未指定物资", "None": "未指定物资"})
            df[AppConfig.PROJECT_COLUMN] = df.iloc[:, 17].astype(str).str.strip().replace({"nan": "未指定项目部", "None": "未指定项目部"})
            df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
            df = df[~df["下单时间"].isna()]
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
    if not data_path: return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])
    try:
        df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')
        # G列(index 6)为卸货地址
        if df.shape[1] > 6:
            df["卸货地址"] = df.iloc[:, 6].astype(str).replace({"nan": "", "None": ""})
        else:
            df["卸货地址"] = ""
            
        for col in AppConfig.LOGISTICS_COLUMNS:
            if col not in df.columns: df[col] = "" if col != "数量" else 0

        df = df[df["项目部"].notna() & (df["项目部"] != "")]
        
        def safe_num(s):
            return pd.to_numeric(s.astype(str).str.replace(r'[^\d.-]', '', regex=True).replace({'':0,'nan':0}), errors='coerce').fillna(0)
            
        df["数量"] = safe_num(df["数量"])
        df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")
        df["record_id"] = df.apply(generate_record_id, axis=1)
        return df[AppConfig.LOGISTICS_COLUMNS + ["record_id"]]
    except:
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])

# ==================== 状态管理 ====================
def load_logistics_status():
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        try:
            df = pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
            if "record_id" not in df.columns: df["record_id"] = ""
            return df
        except: pass
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])

def save_logistics_status(df):
    try:
        df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
        return True
    except: return False

def merge_logistics_with_status(logistics_df):
    if logistics_df.empty: return logistics_df
    status_df = load_logistics_status()
    
    # 自动到货逻辑
    current_date = datetime.now().date()
    three_days = current_date - timedelta(days=3)
    
    if status_df.empty:
        logistics_df["到货状态"] = logistics_df.apply(lambda x: "已到货" if pd.notna(x["交货时间"]) and x["交货时间"].date() < three_days else "钢厂已接单", axis=1)
        return logistics_df
        
    merged = pd.merge(logistics_df, status_df[["record_id", "到货状态"]], on="record_id", how="left", suffixes=("", "_status"))
    
    if "到货状态_status" in merged.columns:
        mask_old = merged["交货时间"].apply(lambda x: pd.notna(x) and x.date() < three_days)
        mask_no_status = merged["到货状态_status"].isna()
        
        merged.loc[mask_no_status & mask_old, "到货状态"] = "已到货"
        merged.loc[mask_no_status & ~mask_old, "到货状态"] = "钢厂已接单"
        merged.loc[~mask_no_status, "到货状态"] = merged.loc[~mask_no_status, "到货状态_status"]
    else:
        merged["到货状态"] = "钢厂已接单"
        
    return merged

def update_logistics_status(record_id, new_status, original_row):
    try:
        status_df = load_logistics_status()
        new_status = str(new_status).strip()
        
        # 异常通知检查
        send_noti = False
        if new_status == "未到货":
            curr = status_df[status_df["record_id"] == record_id]
            if curr.empty or curr.iloc[0]["到货状态"] != "未到货":
                send_noti = True
        
        # 更新或新增
        now_str = datetime.now().strftime(AppConfig.DATE_FORMAT)
        if record_id in status_df["record_id"].values:
            status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == record_id, "update_time"] = now_str
        else:
            new_row = pd.DataFrame([{"record_id": record_id, "到货状态": new_status, "update_time": now_str}])
            status_df = pd.concat([status_df, new_row], ignore_index=True)
            
        if save_logistics_status(status_df):
            if send_noti:
                info = {
                    "物资名称": original_row["物资名称"], "规格型号": original_row["规格型号"],
                    "数量": original_row["数量"], "交货时间": str(original_row["交货时间"]),
                    "项目部": original_row["项目部"]
                }
                send_feishu_notification(info)
            return True
        return False
    except Exception as e:
        st.error(f"更新失败: {str(e)}")
        return False

# ==================== 页面组件 ====================
def display_metrics_grid(metrics):
    """显示响应式指标网格 (电脑4列，手机2列)"""
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    for m in metrics:
        extra = f'<div style="font-size:0.75rem; color:#e74c3c;">{m[4]}</div>' if len(m) > 4 else ''
        st.markdown(f"""
        <div class="metric-card">
            <div style="display:flex; align-items:center; gap:0.4rem; color:#555;">
                <span>{m[0]}</span>
                <span style="font-weight:600; font-size:0.9rem;">{m[1]}</span>
            </div>
            <div class="card-value">{m[2]}</div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="card-unit">{m[3]}</div>
                {extra}
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def show_logistics_tab(project):
    yesterday = datetime.now().date() - timedelta(days=1)
    
    d1, d2 = st.columns(2)
    with d1: start = st.date_input("开始日期", yesterday, key="l_start")
    with d2: end = st.date_input("结束日期", yesterday, key="l_end")

    if start > end:
        st.error("日期范围无效")
        return

    with st.spinner("加载中..."):
        df = load_logistics_data()
        if project != "中铁物贸成都分公司":
            df = df[df["项目部"] == project]

        if not df.empty:
            df = merge_logistics_with_status(df)
            mask = (df["交货时间"] >= pd.to_datetime(start)) & (df["交货时间"] < pd.to_datetime(end) + timedelta(days=1))
            filtered_df = df[mask].copy().sort_values(by="交货时间", ascending=False)

            # --- 指标卡 ---
            metrics = [
                ("📦", "总单数", f"{len(filtered_df)}", "单"),
                ("✅", "已到货", f"{filtered_df['到货状态'].eq('已到货').sum()}", "单"),
                ("🔄", "进行中", f"{len(filtered_df) - filtered_df['到货状态'].isin(['已到货','未到货']).sum() - filtered_df['到货状态'].eq('未到货').sum()}", "单"),
                ("⚠️", "未到货", f"{filtered_df['到货状态'].eq('未到货').sum()}", "单")
            ]
            display_metrics_grid(metrics)
            
            st.markdown("---")
            
            # --- 视图切换 (默认开) ---
            is_mobile = st.toggle("📱 卡片视图 (移动端默认)", value=True)
            
            if is_mobile:
                # === 移动端卡片列表 (无筛选，全量展示) ===
                st.caption(f"📅 显示 {start} 至 {end} 的所有数据 ({len(filtered_df)}条)")
                
                if filtered_df.empty:
                    st.info("暂无数据")
                
                for idx, row in filtered_df.iterrows():
                    # 颜色定义
                    s = row['到货状态']
                    color = "#ff4b4b" if s == "未到货" else "#4CAF50" if s == "已到货" else "#2196F3"
                    
                    st.markdown(f"""
                    <div class="mobile-list-card" style="border-left-color: {color};">
                        <div style="display:flex; justify-content:space-between;">
                            <div style="font-weight:bold; color:#333;">{row['物资名称']}</div>
                            <div style="background:{color}; color:white; padding:1px 6px; border-radius:4px; font-size:0.75rem;">{s}</div>
                        </div>
                        <div style="font-size:0.9rem; color:#666; margin:4px 0;">
                            {row['规格型号']} | <b>{int(row['数量'])}</b> {row['单位']}
                        </div>
                        <div style="font-size:0.8rem; color:#999;">
                            📅 {row['交货时间'].strftime('%m-%d %H:%M') if pd.notna(row['交货时间']) else '待定'} 
                            <span style="float:right;">{row['钢厂'][:6]}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander(f"📝 详情/操作 (ID: {str(row['record_id'])[-4:]})"):
                        c1, c2 = st.columns(2)
                        with c1: 
                            st.caption("联系人")
                            st.write(f"{row['联系人']} {row['联系方式']}")
                        with c2: 
                            st.caption("卸货地址")
                            st.write(row['卸货地址'])
                        
                        # 状态修改
                        new_s = st.selectbox("更新状态", AppConfig.STATUS_OPTIONS, 
                                           index=AppConfig.STATUS_OPTIONS.index(s) if s in AppConfig.STATUS_OPTIONS else 0,
                                           key=f"mob_s_{row['record_id']}")
                        if new_s != s:
                            if update_logistics_status(row['record_id'], new_s, row):
                                st.toast("更新成功！")
                                time.sleep(0.5)
                                st.rerun()
            else:
                # === 电脑端表格 ===
                display_cols = [c for c in filtered_df.columns if c not in ["record_id", "收货地址"]]
                st.data_editor(
                    filtered_df[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "到货状态": st.column_config.SelectboxColumn("状态", options=AppConfig.STATUS_OPTIONS, required=True),
                        "数量": st.column_config.NumberColumn("数量", format="%d"),
                        "交货时间": st.column_config.DatetimeColumn("时间", format="MM-DD HH:mm"),
                    },
                    key=f"log_edit_{project}"
                )

            # 批量更新放在折叠区，不占首屏
            with st.expander("📦 批量更新工具"):
                st.info("请切换至表格模式查看完整ID以便核对，或在此处直接搜索物资")
                # (为简化代码，此处略去批量更新的复杂UI，主要保证移动端流畅)
                
            status_df = load_logistics_status()
            if not status_df.empty:
                last_t = pd.to_datetime(status_df["update_time"]).max()
                st.caption(f"最后更新: {last_t}")
        else:
            st.info("无数据")

def show_plan_tab(df, project):
    c1, c2 = st.columns(2)
    with c1: start = st.date_input("开始", datetime.now(), key="p_start")
    with c2: end = st.date_input("结束", datetime.now(), key="p_end")

    if start > end:
        st.error("日期错")
        return
        
    filtered = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
    mask = (filtered["下单时间"].dt.date >= start) & (filtered["下单时间"].dt.date <= end)
    data = filtered[mask].copy()

    if not data.empty:
        # 指标卡
        total = int(data["需求量"].sum())
        sent = int(data["已发量"].sum())
        pending = int(data["剩余量"].sum())
        overdue = len(data[data["超期天数"] > 0])
        max_ov = data["超期天数"].max() if overdue > 0 else 0
        
        metrics = [
            ("📦", "总需求", f"{total:,}", "吨"),
            ("🚚", "已发", f"{sent:,}", "吨"),
            ("⏳", "待发", f"{pending:,}", "吨"),
            ("⚠️", "超期", f"{overdue}", "单", f"最长{max_ov}天")
        ]
        display_metrics_grid(metrics)
        
        st.markdown("---")
        
        # 视图切换
        is_mobile = st.toggle("📱 卡片视图 (移动端默认)", value=True, key="plan_view_toggle")
        
        if is_mobile:
            # === 发货计划 卡片视图 ===
            for _, row in data.iterrows():
                is_overdue = row.get("超期天数", 0) > 0
                bd_color = "#ff4b4b" if is_overdue else "#3498db"
                
                st.markdown(f"""
                <div class="mobile-list-card" style="border-left-color: {bd_color};">
                    <div style="font-weight:bold; font-size:1rem; margin-bottom:4px;">
                        {row['物资名称']} <span style="font-weight:normal; font-size:0.85rem; color:#666;">({row['规格型号']})</span>
                    </div>
                    <div style="font-size:0.85rem; color:#555; margin-bottom:6px;">
                        {row['标段名称']}
                    </div>
                    <div style="display:flex; justify-content:space-between; background:#f8f9fa; padding:6px; border-radius:4px; font-size:0.9rem;">
                        <div style="text-align:center;">需求<br><b>{int(row['需求量'])}</b></div>
                        <div style="text-align:center; color:#27ae60;">已发<br><b>{int(row.get('已发量',0))}</b></div>
                        <div style="text-align:center; color:#e74c3c;">待发<br><b>{int(row.get('剩余量',0))}</b></div>
                    </div>
                    {f'<div style="margin-top:6px; color:#e74c3c; font-size:0.8rem; font-weight:bold;">⚠️ 已超期 {int(row["超期天数"])} 天</div>' if is_overdue else ''}
                </div>
                """, unsafe_allow_html=True)
                
        else:
            # === 发货计划 表格视图 ===
            disp = data[["标段名称","物资名称","规格型号","需求量","已发量","剩余量","超期天数","下单时间"]]
            st.dataframe(
                disp.style.apply(lambda x: ['background-color:#ffdddd' if x['超期天数']>0 else '' for _ in x], axis=1),
                use_container_width=True,
                hide_index=True
            )
            
        st.markdown('<div class="remark-card plan-remark">📢 提示：公司更新发货台账为当天下午6:00</div>', unsafe_allow_html=True)
    else:
        st.info("该时段无数据")

# ==================== 主程序入口 ====================
def main():
    st.set_page_config(layout="wide", page_title="钢筋发货监控", page_icon="🏗️", initial_sidebar_state="collapsed")
    apply_card_styles()
    
    # URL 参数处理
    qp = st.query_params
    if 'project' in qp:
        p_key = qp['project'] if isinstance(qp['project'], str) else qp['project'][0]
        p_name = AppConfig.PROJECT_MAPPING.get(p_key.lower(), "中铁物贸成都分公司")
        st.session_state.p_selected = True
        st.session_state.sel_p = p_name
        if p_name == "中铁物贸成都分公司": st.session_state.need_pwd = True

    if not st.session_state.get('p_selected', False):
        st.markdown('<h2 style="text-align:center;">欢迎使用钢筋发货监控系统</h2>', unsafe_allow_html=True)
        # 项目选择
        log_df = load_logistics_data()
        projs = ["中铁物贸成都分公司"] + sorted([p for p in log_df["项目部"].unique() if p]) if not log_df.empty else ["中铁物贸成都分公司"]
        
        sel = st.selectbox("选择项目部", projs)
        if st.button("进入系统", type="primary", use_container_width=True):
            if sel == "中铁物贸成都分公司":
                st.session_state.tmp_p = sel
                st.session_state.need_pwd = True
            else:
                st.session_state.p_selected = True
                st.session_state.sel_p = sel
            st.rerun()
            
        if st.session_state.get('need_pwd', False):
            if st.text_input("密码", type="password") == "123456":
                st.session_state.p_selected = True
                st.session_state.sel_p = st.session_state.get('tmp_p', "中铁物贸成都分公司")
                del st.session_state['need_pwd']
                st.rerun()
            elif st.button("验证"): st.error("密码错误")
    else:
        # 数据面板
        proj = st.session_state.sel_p
        st.title(f"{proj}")
        if st.button("← 返回"):
            st.session_state.p_selected = False
            st.rerun()
            
        df = load_data()
        t1, t2 = st.tabs(["📋 发货计划", "🚛 物流明细"])
        with t1: show_plan_tab(df, proj)
        with t2: show_logistics_tab(proj)

if __name__ == "__main__":
    main()
