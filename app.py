# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime

# 需要這兩個套件：gspread、google-auth
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="社團服裝借用系統", layout="wide")

# ===== 你可以改這裡 =====
SPREADSHEET_NAME = "社團服裝借用紀錄"   # 你的 Google Sheet 試算表名稱
WORKSHEET_NAME = "Sheet1"             # 工作表名稱（預設通常是 Sheet1）
COLUMNS = ["時間", "姓名", "學號", "動作", "服裝名稱", "數量", "備註"]


# ===== Google Sheets 連線（用 Streamlit Secrets）=====
@st.cache_resource
def get_gsheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    client = gspread.authorize(creds)
    ws = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)
    return ws


def ensure_header(ws):
    """如果表是空的，補上標題列。"""
    values = ws.get_all_values()
    if len(values) == 0:
        ws.append_row(COLUMNS, value_input_option="USER_ENTERED")
    else:
        # 如果第一列不是我們要的欄位，仍提示（避免學弟妹手改標題）
        header = values[0]
        if header != COLUMNS:
            st.warning(
                "⚠️ Google Sheet 的第一列標題和系統預期不一致。\n"
                f"預期：{COLUMNS}\n"
                f"目前：{header}\n"
                "請把第一列改回正確欄位（順序也要一致），避免資料錯亂。"
            )


def load_df(ws) -> pd.DataFrame:
    """讀取整張表（去掉標題列），回傳 DataFrame。"""
    ensure_header(ws)
    records = ws.get_all_records()  # 會把第一列當標題
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(records)
    # 防呆：缺欄補欄、欄位順序固定
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]
    return df


def append_log(ws, row_dict: dict):
    """把一筆紀錄寫進 Google Sheet"""
    # 依照欄位順序寫入
    row = [row_dict.get(col, "") for col in COLUMNS]
    ws.append_row(row, value_input_option="USER_ENTERED")


# ===== UI 開始 =====
st.title("社團服裝借用 / 歸還系統（雲端版）")

# 如果你還沒在 Streamlit Cloud 設定 Secrets，這裡會提示而不是爆掉
try:
    ws = get_gsheet()
    df = load_df(ws)
except Exception as e:
    st.error("❌ 目前尚未連上 Google Sheets。")
    st.info(
        "請確認：\n"
        "1) Streamlit Cloud 已設定 Secrets（gcp_service_account）\n"
        "2) 試算表已分享給 Service Account 的 email（編輯者）\n"
        "3) 試算表名稱/工作表名稱是否正確\n"
        f"\n錯誤訊息：{e}"
    )
    st.stop()

# ========= 表單區 =========
with st.form("clothes_form"):
    action = st.selectbox("動作", ["借用", "歸還"])
    name = st.text_input("姓名")
    student_id = st.text_input("學號")
    clothes = st.text_input("服裝名稱（可自由輸入）")
    qty = st.number_input("數量", min_value=1, step=1)
    note = st.text_input("備註（活動名稱 / 用途）")

    submitted = st.form_submit_button("送出")

    if submitted:
        if not name.strip() or not clothes.strip():
            st.warning("⚠️ 請至少填「姓名」和「服裝名稱」")
        else:
            new_row = {
                "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "姓名": name.strip(),
                "學號": student_id.strip(),
                "動作": action,
                "服裝名稱": clothes.strip(),
                "數量": int(qty),
                "備註": note.strip(),
            }
            append_log(ws, new_row)
            # 重新讀取最新資料
            df = load_df(ws)
            st.success("紀錄完成！")

st.divider()

# =========================================================
# ✅ 區塊一：目前未歸還清單（#1）
# =========================================================
st.subheader("📌 目前未歸還清單")

calc_df = df.copy()
# 數量轉數字（防止 Google Sheet 讀進來變字串）
calc_df["數量"] = pd.to_numeric(calc_df["數量"], errors="coerce").fillna(0)

calc_df["實際數量"] = calc_df.apply(
    lambda r: r["數量"] if r["動作"] == "借用" else -r["數量"],
    axis=1
)

# 依「姓名 + 服裝名稱」加總（你如果想把備註也算進去，我也可以幫你改）
unreturned = (
    calc_df
    .groupby(["姓名", "學號", "服裝名稱"], as_index=False)["實際數量"]
    .sum()
)

unreturned = unreturned[unreturned["實際數量"] > 0].rename(columns={"實際數量": "尚未歸還數量"})

st.dataframe(unreturned, use_container_width=True)

# =========================================================
# ✅ 區塊二：各服裝目前外借數量（#2）
# =========================================================
st.subheader("📦 各服裝目前外借數量")

if unreturned.empty:
    st.info("目前沒有外借中的服裝。")
else:
    clothes_summary = (
        unreturned
        .groupby("服裝名稱", as_index=False)["尚未歸還數量"]
        .sum()
        .sort_values("尚未歸還數量", ascending=False)
    )
    st.dataframe(clothes_summary, use_container_width=True)

st.divider()

# =========================================================
# 🔍 區塊三：歷史紀錄查詢（#3）
# =========================================================
st.subheader("🔍 借用 / 歸還歷史紀錄查詢")

name_keyword = st.text_input("依人名搜尋")
note_keyword = st.text_input("依活動 / 備註搜尋")

filtered_df = df.copy()

if name_keyword:
    filtered_df = filtered_df[
        filtered_df["姓名"].astype(str).str.contains(name_keyword, case=False, na=False)
    ]

if note_keyword:
    filtered_df = filtered_df[
        filtered_df["備註"].astype(str).str.contains(note_keyword, case=False, na=False)
    ]

st.dataframe(filtered_df, use_container_width=True)

switch to google sheets version
