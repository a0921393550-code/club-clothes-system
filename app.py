# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="社團管理系統", layout="wide")

# =========================
# 基本設定
# =========================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1rwiSSLJQaoBTH8Std8lBW03deOJ9RpksA6rhxWiqmH8/edit?gid=1365718203#gid=1365718203"

CLOTHES_SHEET = "服裝紀錄"
MEMBERS_SHEET = "社員名單"
FEE_SHEET = "費用紀錄"

ADMIN_PASSWORD = "mingwu2026"

CLOTHES_COLUMNS = ["時間", "姓名", "學號", "動作", "服裝名稱", "數量", "備註"]
MEMBERS_COLUMNS = ["姓名", "應繳社費", "備註"]
FEE_COLUMNS = ["時間", "姓名", "項目", "金額", "備註"]


# =========================
# Google Sheets 連線
# =========================
@st.cache_resource
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_client()
    return client.open_by_url(SPREADSHEET_URL)


def get_worksheet(sheet_name):
    spreadsheet = get_spreadsheet()

    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception:
        if sheet_name == CLOTHES_SHEET:
            columns = CLOTHES_COLUMNS
        elif sheet_name == MEMBERS_SHEET:
            columns = MEMBERS_COLUMNS
        elif sheet_name == FEE_SHEET:
            columns = FEE_COLUMNS
        else:
            columns = []

        ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

        if columns:
            ws.update("A1", [columns])

        return ws


def reset_header_if_needed(ws, correct_columns):
    values = ws.get_all_values()

    if not values:
        ws.update("A1", [correct_columns])
        return

    current_header = values[0]

    if current_header != correct_columns:
        ws.delete_rows(1)
        ws.insert_row(correct_columns, 1)


def ensure_headers():
    sheet_info = [
        (CLOTHES_SHEET, CLOTHES_COLUMNS),
        (MEMBERS_SHEET, MEMBERS_COLUMNS),
        (FEE_SHEET, FEE_COLUMNS),
    ]

    for sheet_name, columns in sheet_info:
        ws = get_worksheet(sheet_name)
        reset_header_if_needed(ws, columns)


def load_data(sheet_name, columns):
    ws = get_worksheet(sheet_name)
    records = ws.get_all_records()

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    return df[columns]


def append_row(sheet_name, row):
    ws = get_worksheet(sheet_name)
    ws.append_row(row, value_input_option="USER_ENTERED")


# =========================
# 初始化
# =========================
st.title("社團管理系統")

try:
    ensure_headers()

    clothes_df = load_data(CLOTHES_SHEET, CLOTHES_COLUMNS)
    members_df = load_data(MEMBERS_SHEET, MEMBERS_COLUMNS)
    fee_df = load_data(FEE_SHEET, FEE_COLUMNS)

except Exception as e:
    st.error("❌ 無法連線到 Google Sheets")
    st.write("錯誤類型：", type(e).__name__)
    st.code(repr(e))
    st.stop()

member_names = []
if not members_df.empty:
    member_names = (
        members_df["姓名"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    member_names = [name for name in member_names if name]


# =========================
# 分頁
# =========================
tab1, tab2, tab3 = st.tabs(["服裝借還", "社費管理", "管理員"])


# =========================
# Tab 1：服裝借還
# =========================
with tab1:
    st.subheader("服裝借用 / 歸還")

    with st.form("clothes_form"):
        action = st.selectbox("動作", ["借用", "歸還"])
        name = st.text_input("姓名")
        student_id = st.text_input("學號")
        clothes = st.text_input("服裝名稱")
        qty = st.number_input("數量", min_value=1, step=1)
        note = st.text_input("備註（活動名稱 / 用途）")

        submitted = st.form_submit_button("送出")

        if submitted:
            if not name.strip() or not clothes.strip():
                st.warning("⚠️ 姓名與服裝名稱必填")
            else:
                append_row(CLOTHES_SHEET, [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    name.strip(),
                    student_id.strip(),
                    action,
                    clothes.strip(),
                    int(qty),
                    note.strip()
                ])
                st.success("✅ 紀錄完成！")
                st.rerun()

    st.divider()

    st.subheader("📌 目前未歸還清單")

    calc = clothes_df.copy()
    if not calc.empty:
        calc["數量"] = pd.to_numeric(calc["數量"], errors="coerce").fillna(0)
        calc["實際數量"] = calc.apply(
            lambda r: r["數量"] if r["動作"] == "借用" else -r["數量"],
            axis=1
        )

        unreturned = (
            calc.groupby(["姓名", "服裝名稱"], as_index=False)["實際數量"]
            .sum()
        )
        unreturned = unreturned[unreturned["實際數量"] > 0]
        unreturned = unreturned.rename(columns={"實際數量": "尚未歸還數量"})

        if unreturned.empty:
            st.info("目前沒有未歸還服裝。")
        else:
            st.dataframe(unreturned, use_container_width=True)

        st.subheader("📦 各服裝目前外借數量")
        if not unreturned.empty:
            clothes_summary = (
                unreturned.groupby("服裝名稱", as_index=False)["尚未歸還數量"]
                .sum()
                .sort_values("尚未歸還數量", ascending=False)
            )
            st.dataframe(clothes_summary, use_container_width=True)
        else:
            st.info("目前沒有外借中的服裝。")
    else:
        st.info("目前沒有借還紀錄。")

    st.divider()

    st.subheader("🔍 借用 / 歸還紀錄查詢")
    name_kw = st.text_input("依姓名搜尋", key="clothes_name_search")
    note_kw = st.text_input("依備註搜尋", key="clothes_note_search")

    filtered = clothes_df.copy()

    if name_kw:
        filtered = filtered[
            filtered["姓名"].astype(str).str.contains(name_kw, case=False, na=False)
        ]

    if note_kw:
        filtered = filtered[
            filtered["備註"].astype(str).str.contains(note_kw, case=False, na=False)
        ]

    st.dataframe(filtered, use_container_width=True)


# =========================
# Tab 2：社費管理
# =========================
with tab2:
    st.subheader("社費 / 收入管理")

    if not member_names:
        st.warning("⚠️ 目前沒有社員資料，請先到「管理員」分頁新增社員。")
    else:
        with st.form("fee_form"):
            member_name = st.selectbox("姓名", member_names)
            fee_type = st.text_input("項目（例如：社費 / 表演服費 / 活動費）")
            amount = st.number_input("金額", min_value=0, step=1)
            fee_note = st.text_input("備註")

            fee_submitted = st.form_submit_button("送出")

            if fee_submitted:
                if not member_name:
                    st.warning("⚠️ 請選擇社員")
                elif not fee_type.strip():
                    st.warning("⚠️ 請輸入項目名稱")
                elif amount <= 0:
                    st.warning("⚠️ 金額必須大於 0")
                else:
                    append_row(FEE_SHEET, [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        member_name,
                        fee_type.strip(),
                        int(amount),
                        fee_note.strip()
                    ])
                    st.success("✅ 收入紀錄完成！")
                    st.rerun()

    st.divider()

    st.subheader("📌 未繳社費名單")

    if not members_df.empty:
        member_fee_df = members_df.copy()
        member_fee_df["應繳社費"] = pd.to_numeric(
            member_fee_df["應繳社費"], errors="coerce"
        ).fillna(0)

        fee_calc = fee_df.copy()

        if not fee_calc.empty:
            fee_calc["金額"] = pd.to_numeric(fee_calc["金額"], errors="coerce").fillna(0)
            club_fee_df = fee_calc[fee_calc["項目"].astype(str).str.strip() == "社費"]

            paid_summary = (
                club_fee_df.groupby("姓名", as_index=False)["金額"]
                .sum()
                .rename(columns={"金額": "已繳社費"})
            )
        else:
            paid_summary = pd.DataFrame(columns=["姓名", "已繳社費"])

        unpaid_df = member_fee_df.merge(paid_summary, on="姓名", how="left")
        unpaid_df["已繳社費"] = unpaid_df["已繳社費"].fillna(0)
        unpaid_df["尚差金額"] = unpaid_df["應繳社費"] - unpaid_df["已繳社費"]

        unpaid_members = unpaid_df[unpaid_df["尚差金額"] > 0].copy()

        if unpaid_members.empty:
            st.success("🎉 目前沒有未繳社費的社員")
        else:
            st.dataframe(
                unpaid_members[["姓名", "應繳社費", "已繳社費", "尚差金額", "備註"]],
                use_container_width=True
            )

    st.divider()

    st.subheader("💰 收入紀錄查詢")

    fee_name_kw = st.text_input("依姓名搜尋", key="fee_name_search")
    fee_item_kw = st.text_input("依項目搜尋", key="fee_item_search")

    filtered_fee = fee_df.copy()

    if fee_name_kw:
        filtered_fee = filtered_fee[
            filtered_fee["姓名"].astype(str).str.contains(fee_name_kw, case=False, na=False)
        ]

    if fee_item_kw:
        filtered_fee = filtered_fee[
            filtered_fee["項目"].astype(str).str.contains(fee_item_kw, case=False, na=False)
        ]

    st.dataframe(filtered_fee, use_container_width=True)

    st.divider()

    st.subheader("📊 收入統計")

    if not fee_df.empty:
        fee_stat = fee_df.copy()
        fee_stat["金額"] = pd.to_numeric(fee_stat["金額"], errors="coerce").fillna(0)

        total_income = fee_stat["金額"].sum()
        st.metric("總收入", f"{int(total_income)} 元")

        fee_summary = (
            fee_stat.groupby("項目", as_index=False)["金額"]
            .sum()
            .sort_values("金額", ascending=False)
        )
        st.dataframe(fee_summary, use_container_width=True)
    else:
        st.info("目前沒有收入紀錄。")


# =========================
# Tab 3：管理員
# =========================
with tab3:
    st.subheader("管理員區")

    admin_pw = st.text_input("請輸入管理員密碼", type="password")

    if admin_pw == ADMIN_PASSWORD:
        st.success("✅ 已進入管理員區")

        st.markdown("### 新增社員")
        with st.form("member_form"):
            new_member_name = st.text_input("社員姓名")
            new_member_fee = st.number_input("應繳社費", min_value=0, step=1, value=500)
            new_member_note = st.text_input("備註")
            member_submitted = st.form_submit_button("新增社員")

            if member_submitted:
                clean_name = new_member_name.strip()

                if not clean_name:
                    st.warning("⚠️ 請輸入社員姓名")
                elif clean_name in member_names:
                    st.warning("⚠️ 此社員已存在")
                else:
                    append_row(MEMBERS_SHEET, [
                        clean_name,
                        int(new_member_fee),
                        new_member_note.strip()
                    ])
                    st.success("✅ 新增社員成功！")
                    st.rerun()

        st.divider()

        st.markdown("### 社員名單")
        if members_df.empty:
            st.info("目前沒有社員。")
        else:
            st.dataframe(members_df, use_container_width=True)

    elif admin_pw:
        st.error("❌ 密碼錯誤")
