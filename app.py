# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="社團服裝借用系統（雲端版）", layout="wide")

# ====== 設定 ======
SPREADSHEET_ID = "1rwiSSLJQaoBTH8Std8IBW03deOJ9RpkSA6rhxWiqmH8"
WORKSHEET_NAME = "工作表1"
COLUMNS = ["時間", "姓名", "學號", "動作", "服裝名稱", "數量", "備註"]

# ====== Google Sheets 連線 ======
@st.cache_resource
def get_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    client = gspread.authorize(creds)
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    return ws

def load_data(ws):
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    return pd.DataFrame(records)

def append_row(ws, row):
    ws.append_row(row, value_input_option="USER_ENTERED")

# ====== UI 開始 ======
st.title("社團服裝借用 / 歸還系統")

try:
    ws = get_worksheet()
    df = load_data(ws)

    st.caption(f"✅ 已連線試算表：{ws.spreadsheet.title}")
    st.caption(f"🔗 {ws.spreadsheet.url}")

except Exception as e:
    st.error("❌ 無法連線到 Google Sheets")
    st.code(str(e))
    st.stop()

# ====== 表單 ======
with st.form("borrow_form"):
    action = st.selectbox("動作", ["借用", "歸還"])
    name = st.text_input("姓名")
    student_id = st.text_input("學號")
    clothes = st.text_input("服裝名稱")
    qty = st.number_input("數量", min_value=1, step=1)
    note = st.text_input("備註（活動名稱 / 用途）")

    submitted = st.form_submit_button("送出")

    if submitted:
        if not name or not clothes:
            st.warning("⚠️ 姓名與服裝名稱必填")
        else:
            append_row(ws, [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                name,
                student_id,
                action,
                clothes,
                int(qty),
                note
            ])
            st.success("✅ 紀錄完成！")
            df = load_data(ws)

#switch to google sheets version
