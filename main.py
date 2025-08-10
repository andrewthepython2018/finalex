import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date, timedelta
import json
import os

# --- Настройки страницы ---
st.set_page_config(page_title="Финансовый дашборд", layout="wide")

SAVE_FILE = "savings_data.json"

# --- Загрузка онлайн-курса валют ---
def fetch_exchange_rates():
    try:
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js")
        data = response.json()
        usd = data['Valute']['USD']['Value']
        uzs = data['Valute'].get('UZS', {}).get('Value', None)
        return usd, uzs
    except:
        return None, None

# --- Загрузка из файла ---
def load_savings(month_labels):
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for m in month_labels:
                if m not in data:
                    data[m] = 0
            return data
        except:
            return {m: 0 for m in month_labels}
    else:
        return {m: 0 for m in month_labels}

# --- Сохранение в файл ---
def save_savings(data):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Пересчёт данных ---
def recalculate_progress(goal_rub, start_capital, monthly_plan_rub, start_date):
    pie_labels = list(st.session_state.savings_by_month.keys())
    pie_values = list(st.session_state.savings_by_month.values())
    accumulated = start_capital + sum(pie_values)
    remaining_to_goal = max(0, goal_rub - accumulated)
    estimated_months = int(remaining_to_goal / monthly_plan_rub) if monthly_plan_rub else 1
    estimated_finish_date = start_date + timedelta(days=estimated_months * 30)
    percent_complete = accumulated / goal_rub * 100 if goal_rub else 0
    return pie_labels, pie_values, accumulated, remaining_to_goal, estimated_finish_date, percent_complete

# --- Основная функция ---
def main():
    st.title("\U0001F4B0 Финансовый дашборд")

    usd_rate, uzs_rate = fetch_exchange_rates()
    if usd_rate is None or uzs_rate is None:
        st.error("Не удалось загрузить курс валют")
        return

    # --- Ввод значений пользователем ---
    st.sidebar.header("Ввод исходных данных")
    usd_saved = st.sidebar.number_input("Накоплено (USD)", value=12000.0)
    uzs_saved = st.sidebar.number_input("Накоплено (UZS)", value=51000000.0)
    goal_rub = st.sidebar.number_input("Итоговая целевая сумма (₽)", value=4498000.0)
    monthly_plan_rub = st.sidebar.number_input("Цель по накоплению в месяц (₽)", value=271634.0)
    monthly_plan_usd = st.sidebar.number_input("Цель по накоплению в месяц ($)", value=3528.0)
    start_date = st.sidebar.date_input("Дата начала", value=date(2025, 7, 13))

    # --- Перевод в рубли ---
    rub_from_usd = usd_saved * usd_rate
    rub_from_uzs = (uzs_saved * uzs_rate) / 10000
    start_capital = rub_from_usd + rub_from_uzs

    month_labels = [(start_date + timedelta(days=30 * i)).strftime('%B %Y') for i in range(12)]

    if 'savings_by_month' not in st.session_state:
        st.session_state.savings_by_month = load_savings(month_labels)

    # --- Диаграмма плана ---
    fig_plan = px.pie(
        names=month_labels,
        values=[monthly_plan_rub for _ in month_labels],
        title="План по накоплениям на 12 месяцев",
        hole=0.4
    )
    st.plotly_chart(fig_plan, use_container_width=True)

    pie_labels, pie_values, accumulated, remaining_to_goal, estimated_finish_date, percent_complete = recalculate_progress(goal_rub, start_capital, monthly_plan_rub, start_date)

    # --- Диаграмма накоплений ---
    filtered_labels = [label for label, value in zip(pie_labels, pie_values) if value > 0]
    filtered_values = [value for value in pie_values if value > 0]
    fig_pie = px.pie(
        names=["Начальный капитал"] + filtered_labels + ["Остаток"],
        values=[start_capital] + filtered_values + [remaining_to_goal],
        title="Круговая диаграмма: выполнено и план по месяцам",
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    # --- Сброс данных ---
    with st.expander("⚙️ Дополнительно"):
        if st.button("🔁 Сбросить накопления до начальных значений"):
            st.session_state.savings_by_month = {label: 0 for label in month_labels}
            save_savings(st.session_state.savings_by_month)
            st.success("Данные накоплений сброшены")

    # --- Форма добавления накоплений ---
    st.subheader("Добавить накопления за месяц")
    with st.form(key="add_savings_form"):
        col1, col2, col3, col4 = st.columns(4)
        input_usd = col1.number_input("Сумма в USD", min_value=0.0, value=0.0, step=10.0)
        input_uzs = col2.number_input("Сумма в UZS", min_value=0.0, value=0.0, step=10000.0)
        input_rub = col3.number_input("Сумма в RUB", min_value=0.0, value=0.0, step=1000.0)
        selected_month = col4.selectbox("Месяц", month_labels)
        submitted = st.form_submit_button("Добавить")

    if submitted:
        added_total = input_rub + input_usd * usd_rate + (input_uzs * uzs_rate) / 10000
        st.session_state.savings_by_month[selected_month] += added_total
        save_savings(st.session_state.savings_by_month)
        st.success(f"Добавлено {added_total:,.2f} ₽ в {selected_month}")

    # --- Таблица накоплений ---
    st.markdown("### Таблица накоплений по месяцам")
    savings_table = pd.DataFrame({
        "Месяц": month_labels,
        "План (₽)": [monthly_plan_rub for _ in month_labels],
        "Накоплено (₽)": [st.session_state.savings_by_month[label] for label in month_labels]
    })
    st.dataframe(savings_table.style.format({"План (₽)": "{:.2f}", "Накоплено (₽)": "{:.2f}"}), use_container_width=True)

if __name__ == "__main__":
    main()
