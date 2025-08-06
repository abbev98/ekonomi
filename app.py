import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pdfplumber
import re

# Alternativen
PERSONER = ['Albin', 'Nathalie', 'Gemensamt']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

# Parserfunktion
def robust_extract_transactions(pdf_file, start_date, end_date):
    transactions = []
    current = {}

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            for line in lines:
                date_match = re.match(r"(\d{2}\.\d{2}\.\d{2})\s+\d{2}\.\d{2}\.\d{2}\s+(.*)", line.strip())
                if date_match:
                    if current.get('Datum') and current.get('Vart') and current.get('Summa') is not None:
                        transactions.append(current)
                    datum_str = date_match.group(1)
                    try:
                        datum = datetime.strptime(datum_str, "%d.%m.%y").date()
                    except ValueError:
                        continue
                    text = date_match.group(2).strip()
                    current = {'Datum': datum, 'Vart': text, 'Summa': None}
                else:
                    if current:
                        line = line.strip()
                        match_amount = re.search(r"(-?\d{1,3}(?:[ \.]\d{3})*(?:,\d{2})?)\s*$", line)
                        if match_amount:
                            try:
                                amount_str = match_amount.group(1).replace('.', '').replace(' ', '').replace(',', '.')
                                current['Summa'] = float(amount_str)
                                line = re.sub(r"(-?\d{1,3}(?:[ \.]\d{3})*(?:,\d{2})?)\s*$", '', line).strip()
                            except ValueError:
                                continue
                        if line:
                            current['Vart'] += f" {line}"

    if current.get('Datum') and current.get('Vart') and current.get('Summa') is not None:
        transactions.append(current)

    for tx in transactions:
        if tx['Datum'] < start_date:
            tx['Datum'] = start_date
    transactions = [tx for tx in transactions if tx['Datum'] <= end_date]
    return sorted(transactions, key=lambda x: x['Datum'])


# Streamlit-start
st.set_page_config(page_title="Kategorisera Utgifter", layout="centered")
st.title("📄 Kategorisera Utgifter")

# Initiera state
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
        st.session_state.transactions = robust_extract_transactions(uploaded_file, start_date, end_date)
        st.session_state.resultat = []
        st.session_state.index = 0
        st.session_state.started = True
        st.rerun()

# Visa transaktioner en i taget
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
