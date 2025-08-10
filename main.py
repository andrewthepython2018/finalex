import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Финансовый дашборд", layout="wide")

# Настройки Google Sheets
SHEET_NAME = "Nakop"  # Название документа
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPES
)
gc = gspread.authorize(credentials)
sheet = gc.open(SHEET_NAME).sheet1

def fetch_exchange_rates():
    try:
        r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js")
        d = r.json()
        usd = d['Valute']['USD']['Value']
        uzs = d['Valute'].get('UZS', {}).get('Value', None)
        return usd, uzs
    except:
        return None, None

def load_savings(month_labels):
    records = sheet.get_all_records()
    data = {m: 0 for m in month_labels}
    for row in records:
        if row["Месяц"] in data:
            data[row["Месяц"]] = float(row["Накоплено (₽)"])
    return data

def save_savings(data):
    rows = [["Месяц", "Накоплено (₽)"]]
    for m, v in data.items():
        rows.append([m, v])
    sheet.clear()
    sheet.update(rows)

def recalculate_progress(goal_rub, start_capital, monthly_plan_rub, start_date):
    pie_labels = list(st.session_state.savings_by_month.keys())
    pie_values = list(st.session_state.savings_by_month.values())
    accumulated = start_capital + sum(pie_values)
    remaining_to_goal = max(0, goal_rub - accumulated)
    estimated_months = int(remaining_to_goal / monthly_plan_rub) if monthly_plan_rub else 1
    estimated_finish_date = start_date + timedelta(days=estimated_months * 30)
    percent_complete = accumulated / goal_rub * 100 if goal_rub else 0
    return pie_labels, pie_values, accumulated, remaining_to_goal, estimated_finish_date, percent_complete

def main():
    st.title("💰 Финансовый дашборд")

    usd_rate, uzs_rate = fetch_exchange_rates()
    if usd_rate is None or uzs_rate is None:
        st.error("Не удалось загрузить курс валют")
        return

    st.sidebar.header("Ввод исходных данных")
    usd_saved = st.sidebar.number_input("Накоплено (USD)", value=12000.0)
    uzs_saved = st.sidebar.number_input("Накоплено (UZS)", value=51000000.0)
    goal_rub = st.sidebar.number_input("Итоговая цель (₽)", value=4498000.0)
    monthly_plan_rub = st.sidebar.number_input("План в месяц (₽)", value=271634.0)
    start_date = st.sidebar.date_input("Дата начала", value=date(2025, 7, 13))

    rub_from_usd = usd_saved * usd_rate
    rub_from_uzs = (uzs_saved * uzs_rate) / 10000
    start_capital = rub_from_usd + rub_from_uzs

    month_labels = [(start_date + timedelta(days=30 * i)).strftime('%B %Y') for i in range(12)]

    if "savings_by_month" not in st.session_state:
        st.session_state.savings_by_month = load_savings(month_labels)

    fig_plan = px.pie(names=month_labels, values=[monthly_plan_rub] * 12, hole=0.4)
    st.plotly_chart(fig_plan, use_container_width=True)

    pie_labels, pie_values, accumulated, remaining_to_goal, finish_date, percent_complete = recalculate_progress(
        goal_rub, start_capital, monthly_plan_rub, start_date
    )

    fig_pie = px.pie(
        names=["Начальный капитал"] + [m for m, v in zip(pie_labels, pie_values) if v > 0] + ["Остаток"],
        values=[start_capital] + [v for v in pie_values if v > 0] + [remaining_to_goal],
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("⚙️ Дополнительно"):
        if st.button("Сбросить"):
            st.session_state.savings_by_month = {m: 0 for m in month_labels}
            save_savings(st.session_state.savings_by_month)
            st.success("Данные сброшены")

    st.subheader("Добавить накопления")
    with st.form("add_savings_form"):
        col1, col2, col3, col4 = st.columns(4)
        input_usd = col1.number_input("USD", min_value=0.0, value=0.0)
        input_uzs = col2.number_input("UZS", min_value=0.0, value=0.0)
        input_rub = col3.number_input("RUB", min_value=0.0, value=0.0)
        selected_month = col4.selectbox("Месяц", month_labels)
        submitted = st.form_submit_button("Добавить")
    if submitted:
        added_total = input_rub + input_usd * usd_rate + (input_uzs * uzs_rate) / 10000
        st.session_state.savings_by_month[selected_month] += added_total
        save_savings(st.session_state.savings_by_month)
        st.success(f"Добавлено {added_total:,.2f} ₽ в {selected_month}")

    st.markdown("### Таблица накоплений")
    df = pd.DataFrame({
        "Месяц": month_labels,
        "План (₽)": [monthly_plan_rub] * 12,
        "Накоплено (₽)": [st.session_state.savings_by_month[m] for m in month_labels]
    })
    st.dataframe(df.style.format({"План (₽)": "{:.2f}", "Накоплено (₽)": "{:.2f}"}))

if __name__ == "__main__":
    main()
