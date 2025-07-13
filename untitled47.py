import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, date, timedelta
import time

# --- Настройки страницы ---
st.set_page_config(page_title="Финансовый дашборд", layout="wide")

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

# --- Блок с актуальными курсами валют ---
def display_exchange_rates(usd_rate, uzs_rate):
    st.subheader("Актуальные курсы валют")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Курс доллара (USD → ₽)", f"{usd_rate:.2f} ₽")
    with col2:
        if uzs_rate:
            st.metric("Курс сума (UZS → ₽ за 10,000)", f"{uzs_rate:.6f} ₽")
        else:
            st.warning("Курс сума недоступен")

# --- Основная функция отображения ---

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

        # --- Блок с курсами ---
    display_exchange_rates(usd_rate, uzs_rate)

    # --- Перевод в рубли ---
    rub_from_usd = usd_saved * usd_rate
    rub_from_uzs = (uzs_saved * uzs_rate) / 10000
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Исходные накопления")
        st.write(f"**USD:** {usd_saved:,.0f} USD")
        st.write(f"**UZS:** {uzs_saved:,.0f} UZS")
    with col2:
        st.markdown("### Перевод в рубли")
        st.write(f"Из USD: {rub_from_usd:,.2f} ₽")
        st.write(f"Из UZS: {rub_from_uzs:,.2f} ₽")

    start_capital = rub_from_usd + rub_from_uzs

        # --- Расчёт месяцев и накоплений ---
    month_labels = [(start_date + timedelta(days=30 * i)).strftime('%B %Y') for i in range(12)]

    if 'savings_by_month' not in st.session_state:
        st.session_state.savings_by_month = {label: 0 for label in month_labels}

    # Диаграмма планов по месяцам (без накопленного)
    fig_plan = px.pie(
        names=month_labels,
        values=[monthly_plan_rub for _ in month_labels],
        title="План по накоплениям на 12 месяцев",
        hole=0.4
    )
    st.plotly_chart(fig_plan, use_container_width=True)

    pie_labels, pie_values, accumulated, remaining_to_goal, estimated_finish_date, percent_complete = recalculate_progress(goal_rub, start_capital, monthly_plan_rub, start_date)

    chart_placeholder = st.empty()
    filtered_labels = [label for label, value in zip(pie_labels, pie_values) if value > 0]
    filtered_values = [value for value in pie_values if value > 0]

    fig_pie = px.pie(
        names=["Начальный капитал"] + [label for label, value in zip(filtered_labels, filtered_values) if value > 0] + ["Остаток"],
        values=[start_capital] + [value for value in filtered_values if value > 0] + [remaining_to_goal],
        title="Круговая диаграмма: выполнено и план по месяцам",
        hole=0.4
    )
    chart_placeholder.plotly_chart(fig_pie, use_container_width=True)

    
    goal_placeholder = st.empty()
    goal_placeholder.markdown(...)

    
    # --- Блок сброса данных ---
    with st.expander("⚙️ Дополнительно"):
        if st.button("🔁 Сбросить накопления до начальных значений"):
            st.session_state.savings_by_month = {label: 0 for label in month_labels}
            st.success("Данные накоплений сброшены")
            pie_labels, pie_values, accumulated, remaining_to_goal, estimated_finish_date, percent_complete = recalculate_progress(goal_rub, start_capital, monthly_plan_rub, start_date)
            fig_pie_reset = px.pie(
            names=["Начальный капитал"] + [label for label, value in zip(pie_labels, pie_values) if value > 0] + ["Остаток"],
            values=[start_capital] + [value for label, value in zip(pie_labels, pie_values) if value > 0] + [remaining_to_goal],
                title="Круговая диаграмма: выполнено и план по месяцам (после сброса)",
                hole=0.4
            )
            chart_placeholder.plotly_chart(fig_pie_reset, use_container_width=True)
            goal_placeholder.markdown("""
            <div style='font-size:24px; font-weight:600; margin-top: 1.5rem;'>
                🎯 <b>Цель:</b> {:,.2f} ₽ &nbsp;&nbsp;&nbsp;
                💼 <b>Осталось:</b> {:,.2f} ₽ &nbsp;&nbsp;&nbsp;
                📈 <b>Достижение:</b> {:.2f}% &nbsp;&nbsp;&nbsp;
                🗓️ <b>Завершение:</b> {}
            </div>
            """.format(goal_rub, remaining_to_goal, percent_complete, estimated_finish_date), unsafe_allow_html=True)

    # --- Блок внесения накоплений за месяц ---
    st.subheader("Добавить накопления за месяц")
    with st.form(key="add_savings_form"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            input_usd = st.number_input("Сумма в USD", min_value=0.0, value=0.0, step=10.0)
        with col2:
            input_uzs = st.number_input("Сумма в UZS", min_value=0.0, value=0.0, step=10000.0)
        with col3:
            input_rub = st.number_input("Сумма в RUB", min_value=0.0, value=0.0, step=1000.0)
        with col4:
            selected_month = st.selectbox("Месяц", month_labels)
        submitted = st.form_submit_button("Добавить")

    if submitted:
        added_total = input_rub + input_usd * usd_rate + (input_uzs * uzs_rate) / 10000

        if selected_month in st.session_state.savings_by_month:
            st.session_state.savings_by_month[selected_month] += added_total

        st.success(f"Добавлено {added_total:,.2f} ₽ в {selected_month}")

        pie_labels, pie_values, accumulated, remaining_to_goal, estimated_finish_date, percent_complete = recalculate_progress(goal_rub, start_capital, monthly_plan_rub, start_date)

        fig_pie_updated = px.pie(
            names=["Начальный капитал"] + [label for label, value in zip(pie_labels, pie_values) if value > 0] + ["Остаток"],
            values=[start_capital] + [value for label, value in zip(pie_labels, pie_values) if value > 0] + [remaining_to_goal],
            title="Круговая диаграмма: выполнено и план по месяцам (обновлено)",
            hole=0.4
        )
        chart_placeholder.plotly_chart(fig_pie_updated, use_container_width=True)
        goal_placeholder.markdown("""
            <div style='font-size:24px; font-weight:600; margin-top: 1.5rem;'>
                🎯 <b>Цель:</b> {:,.2f} ₽ &nbsp;&nbsp;&nbsp;
                💼 <b>Осталось:</b> {:,.2f} ₽ &nbsp;&nbsp;&nbsp;
                📈 <b>Достижение:</b> {:.2f}% &nbsp;&nbsp;&nbsp;
                🗓️ <b>Завершение:</b> {}
            </div>
            """.format(goal_rub, remaining_to_goal, percent_complete, estimated_finish_date), unsafe_allow_html=True)

        
        

# --- Таблица с накоплениями по месяцам ---
    st.markdown("### Таблица накоплений по месяцам")
    savings_table = pd.DataFrame({
        "Месяц": month_labels,
        "План (₽)": [monthly_plan_rub for _ in month_labels],
        "Накоплено (₽)": [st.session_state.savings_by_month[label] for label in month_labels]
    })
    st.dataframe(savings_table.style.format({"План (₽)": "{:.2f}", "Накоплено (₽)": "{:.2f}"}), use_container_width=True)

if __name__ == "__main__":
    main()
