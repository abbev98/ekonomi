import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pdfplumber
import re

# Alternativ för flervalsval
PERSONER = ['Albin', 'Nathalie', 'Gemensamt']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

# Bättre parser som tolkar hela transaktionsblock
def extract_transactions(pdf_file, start_date, end_date):
    transactions = []
    current_lines = []
    pattern_datum = re.compile(r"(\d{2}\.\d{2}\.\d{2})\s+\d{2}\.\d{2}\.\d{2}")

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            for line in lines:
                if pattern_datum.match(line.strip()):
                    if current_lines:
                        transactions.append(current_lines)
                    current_lines = [line.strip()]
                else:
                    if current_lines is not None:
                        current_lines.append(line.strip())
        if current_lines:
            transactions.append(current_lines)

    parsed = []
    for group in transactions:
        datum_match = re.match(r"(\d{2}\.\d{2}\.\d{2})", group[0])
        if not datum_match:
            continue
        datum = datetime.strptime(datum_match.group(1), "%d.%m.%y").date()

        text_block = " ".join(group)
        amount_match = re.findall(r"(\d{1,3}(?:[ \.]\d{3})*(?:,\d{2}))", text_block)
        if not amount_match:
            continue

        try:
            amount_str = amount_match[-1].replace(".", "").replace(" ", "").replace(",", ".")
            summa = float(amount_str)
        except:
            continue

        text_clean = re.sub(r"(\d{1,3}(?:[ \.]\d{3})*(?:,\d{2}))", "", text_block)
        text_clean = re.sub(r"\s{2,}", " ", text_clean).strip()

        parsed.append({
            "Datum": max(datum, start_date),
            "Vart": text_clean,
            "Summa": summa
        })

    parsed = [tx for tx in parsed if tx["Datum"] <= end_date]
    return sorted(parsed, key=lambda x: x["Datum"])

# Streamlit UI
st.set_page_config(page_title="Kategorisera Utgifter", layout="centered")
st.title("📄 Kategorisera Utgifter")

# Initiera session state
for key in ['index', 'resultat', 'transactions', 'started', 'start_date', 'end_date']:
    if key not in st.session_state:
        st.session_state[key] = None if key in ['start_date', 'end_date'] else []

# Startformulär
if not st.session_state.started:
    uploaded_file = st.file_uploader("Ladda upp PDF-kontoutdrag", type=["pdf"])
    start_date = st.date_input("Från datum", value=datetime.today(), key="start_date_input")
    end_date = st.date_input("Till datum", value=datetime.today(), key="end_date_input")

    if uploaded_file and st.button("🚀 Starta"):
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        st.session_state.transactions = extract_transactions(uploaded_file, start_date, end_date)
        st.session_state.resultat = []
        st.session_state.index = 0
        st.session_state.started = True
        st.rerun()

# Visar en transaktion i taget
elif st.session_state.started:
    index = st.session_state.index
    transactions = st.session_state.transactions
    resultat = st.session_state.resultat

    if index < len(transactions):
        t = transactions[index]
        st.subheader(f"Transaktion {index + 1} av {len(transactions)}")
        st.markdown(f"**Datum:** {t['Datum']}")

        edited_name = st.text_input("🛍️ Namn (Vart)", value=t['Vart'], key=f"namn_{index}")
        edited_sum = st.number_input("💰 Summa", value=float(t['Summa']), step=0.01, key=f"summa_{index}")

        col1, col2 = st.columns(2)
        with col1:
            vem = st.radio("👤 Vem?", PERSONER, horizontal=True, key=f"vem_{index}")
        with col2:
            kategori = st.radio("📂 Kategori?", KATEGORIER, horizontal=True, key=f"kat_{index}")

        if st.button("Spara & Nästa ➡️"):
            resultat.append({
                'Datum': t['Datum'],
                'Vart': edited_name,
                'Summa': edited_sum,
                'Vem': vem,
                'Kategori': kategori
            })
            st.session_state.index += 1
            st.rerun()
    else:
        st.success("🎉 Alla transaktioner är kategoriserade.")
        df = pd.DataFrame(resultat)
        st.subheader("📊 Resultat (kopiera till Google Kalkylark):")
        st.dataframe(df, use_container_width=True)

        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        st.download_button("📥 Ladda ner Excel-fil", data=excel_buffer, file_name="kategoriserade_utgifter.xlsx")
