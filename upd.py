import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date, timedelta, datetime
import gspread
from google.oauth2.service_account import Credentials

# ---------------- Настройки ----------------
st.set_page_config(page_title="Финансовый дашборд", layout="wide")

# ID твоей таблицы (из URL между /d/ и /edit)
SPREADSHEET_ID = "1-D2RvWH5WUP00KqA18mAfj3kDOpedMkOwo8UI_Xd_A4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Авторизация
try:
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
except gspread.SpreadsheetNotFound:
    st.error(
        "❌ Google Sheet не найден.\n\n"
        "Проверь, что:\n"
        "1. ID таблицы указан верно.\n"
        "2. Таблица доступна для сервисного аккаунта:\n"
        f"   `{st.secrets['gcp_service_account']['client_email']}`\n"
        "   (Добавь его как 'Редактор' через 'Поделиться')."
    )
    st.stop()
except Exception as e:
    st.error(f"Ошибка при подключении к Google Sheets: {e}")
    st.stop()

# ---------------- Обновлённые функции ----------------
@st.cache_data(ttl=3600)
def fetch_exchange_rates():
    """
    Возвращает:
      usd, usd_prev — текущий и вчерашний курс USD→₽
      uzs, uzs_prev — текущий и вчерашний курс UZS→₽ за 1 сум
      ts            — время обновления (из ответа ЦБ или now)
    """
    try:
        r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        d = r.json()
        ts = d.get("Date", None)
        usd = d["Valute"]["USD"]["Value"]
        usd_prev = d["Valute"]["USD"]["Previous"]
        uzs = d["Valute"].get("UZS", {}).get("Value", None)
        uzs_prev = d["Valute"].get("UZS", {}).get("Previous", None)
        return usd, usd_prev, uzs, uzs_prev, ts
    except Exception:
        return None, None, None, None, None

def render_rates_board(usd, usd_prev, uzs, uzs_prev, ts):
    st.markdown("### Актуальные курсы валют")
    board = st.container()
    with board:
        c1, c2, c3 = st.columns([1,1,2])
        # USD→₽
        if usd is not None:
            delta_usd = None if usd_prev is None else (usd - usd_prev)
            c1.metric("USD → ₽", f"{usd:.2f} ₽", f"{delta_usd:+.2f} ₽" if delta_usd is not None else None)
        else:
            c1.warning("USD курс недоступен")

        # UZS→₽ за 10 000
        if uzs is not None:
            uzs_10k = uzs 
            delta_uzs = None
            if uzs_prev is not None:
                delta_uzs = (uzs - uzs_prev) * 10000
            c2.metric("UZS → ₽ за 10 000", f"{uzs_10k:.2f} ₽", f"{delta_uzs:+.2f} ₽" if delta_uzs is not None else None)
        else:
            c2.warning("UZS курс недоступен")

        # Время обновления
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now()
            c3.caption(f"Обновлено: {dt:%Y-%m-%d %H:%M} (по данным ЦБ РФ)")
        except Exception:
            c3.caption("Обновлено: сейчас")

def load_savings(month_labels):
    records = sheet.get_all_records()
    data = {m: 0 for m in month_labels}
    for row in records:
        if row.get("Месяц") in data:
            try:
                data[row["Месяц"]] = float(row["Накоплено (₽)"])
            except:
                data[row["Месяц"]] = 0
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

# ---------------- Основное приложение ----------------
def main():
    st.title("💰 Финансовый дашборд")

    usd, usd_prev, uzs, uzs_prev, ts = fetch_exchange_rates()
    if usd is None or uzs is None:
        st.error("Не удалось загрузить курсы валют")
        return

    # ✅ Верхнее табло с курсами
    render_rates_board(usd, usd_prev, uzs, uzs_prev, ts)
    st.divider()

    # Ввод исходных данных
    st.sidebar.header("Ввод исходных данных")
    usd_saved = st.sidebar.number_input("Накоплено (USD)", value=12000.0)
    uzs_saved = st.sidebar.number_input("Накоплено (UZS)", value=51000000.0)
    goal_rub = st.sidebar.number_input("Итоговая цель (₽)", value=4498000.0)
    monthly_plan_rub = st.sidebar.number_input("План в месяц (₽)", value=271634.0)
    start_date = st.sidebar.date_input("Дата начала", value=date(2025, 7, 13))

    # Конвертации
    rub_from_usd = usd_saved * usd
    rub_from_uzs = (uzs_saved * uzs) / 10000  # UZS→₽ за 10k учтён
    start_capital = rub_from_usd + rub_from_uzs

    # Верхний блок с исходными суммами/конвертацией
    left, right = st.columns(2)
    with left:
        st.markdown("#### Исходные накопления")
        st.write(f"**USD:** {usd_saved:,.0f} $")
        st.write(f"**UZS:** {uzs_saved:,.0f} сум")
    with right:
        st.markdown("#### Перевод в рубли")
        st.write(f"Из USD: {rub_from_usd:,.2f} ₽")
        st.write(f"Из UZS: {rub_from_uzs:,.2f} ₽")
        st.write(f"**Начальный капитал:** {start_capital:,.2f} ₽")

    # Месяцы
    month_labels = [(start_date + timedelta(days=30 * i)).strftime('%B %Y') for i in range(12)]
    if "savings_by_month" not in st.session_state:
        st.session_state.savings_by_month = load_savings(month_labels)

    # 🔄 Диаграмма прогресса (оставляем только одну — как просил)
    pie_labels, pie_values, accumulated, remaining_to_goal, finish_date, percent_complete = recalculate_progress(
        goal_rub, start_capital, monthly_plan_rub, start_date
    )
    # показываем только месяцы с вкладом > 0
    active_labels = [m for m, v in zip(pie_labels, pie_values) if v > 0]
    active_values = [v for v in pie_values if v > 0]

    fig_pie = px.pie(
        names=["Начальный капитал"] + active_labels + ["Остаток"],
        values=[start_capital] + active_values + [remaining_to_goal],
        title="Выполнено и план по месяцам",
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    # БЫСТРЫЕ ПОКАЗАТЕЛИ
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Цель", f"{goal_rub:,.0f} ₽")
    c2.metric("Накоплено всего", f"{accumulated:,.0f} ₽")
    c3.metric("Осталось", f"{remaining_to_goal:,.0f} ₽")
    c4.metric("Достижение", f"{percent_complete:.2f} %")
    st.caption(f"Оценочная дата завершения: {finish_date.strftime('%d.%m.%Y')}")

    # Сброс
    with st.expander("⚙️ Дополнительно"):
        if st.button("Сбросить накопления"):
            st.session_state.savings_by_month = {m: 0 for m in month_labels}
            save_savings(st.session_state.savings_by_month)
            st.success("Данные сброшены")

    # Добавление накоплений
    st.subheader("Добавить накопления")
    with st.form("add_savings_form"):
        col1, col2, col3, col4 = st.columns(4)
        input_usd = col1.number_input("USD", min_value=0.0, value=0.0)
        input_uzs = col2.number_input("UZS", min_value=0.0, value=0.0, step=10000.0)
        input_rub = col3.number_input("RUB", min_value=0.0, value=0.0, step=1000.0)
        selected_month = col4.selectbox("Месяц", month_labels)
        submitted = st.form_submit_button("Добавить")
    if submitted:
        added_total = input_rub + input_usd * usd + (input_uzs * uzs) / 10000
        st.session_state.savings_by_month[selected_month] += added_total
        save_savings(st.session_state.savings_by_month)
        st.success(f"Добавлено {added_total:,.2f} ₽ в {selected_month}")

        # Мгновенная перерисовка (пересчитанные значения)
        pie_labels, pie_values, accumulated, remaining_to_goal, finish_date, percent_complete = recalculate_progress(
            goal_rub, start_capital, monthly_plan_rub, start_date
        )
        active_labels = [m for m, v in zip(pie_labels, pie_values) if v > 0]
        active_values = [v for v in pie_values if v > 0]
        fig_pie = px.pie(
            names=["Начальный капитал"] + active_labels + ["Остаток"],
            values=[start_capital] + active_values + [remaining_to_goal],
            title="Выполнено и план по месяцам (обновлено)",
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Таблица
    st.markdown("### Таблица накоплений")
    df = pd.DataFrame({
        "Месяц": month_labels,
        "План (₽)": [monthly_plan_rub] * len(month_labels),
        "Накоплено (₽)": [st.session_state.savings_by_month[m] for m in month_labels]
    })
    st.dataframe(df.style.format({"План (₽)": "{:.2f}", "Накоплено (₽)": "{:.2f}"}), use_container_width=True)

if __name__ == "__main__":
    main()
