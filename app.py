
import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from datetime import datetime

PERSONER = ['Albin', 'Nathalie', 'Gemensamt']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

st.set_page_config(page_title="Kategorisera Utgifter", layout="centered")
st.title("📄 Kategorisera Utgifter")

# Session state initialization
for key in ['index', 'resultat', 'transactions', 'started', 'start_date', 'end_date']:
    if key not in st.session_state:
        st.session_state[key] = None if key in ['start_date', 'end_date'] else []

# Step 1: Upload and start
if not st.session_state.started:
    uploaded_file = st.file_uploader("Ladda upp PDF-kontoutdrag", type=["pdf"])
    start_date = st.date_input("Från datum", value=datetime.today(), key="start_date_input")
    end_date = st.date_input("Till datum", value=datetime.today(), key="end_date_input")

    if uploaded_file and st.button("🚀 Starta"):
        # Save dates
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date

        # Extract and sort transactions
        def extract_transactions(pdf_file, start_date, end_date):
            transactions = []
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue
                    lines = text.split("\n")
                    for line in lines:
                        match = re.match(r"(\d{2}\.\d{2}\.\d{2})\s+\d{2}\.\d{2}\.\d{2}\s+(.*?)\s+([\d\s.,]+)$", line.strip())
                        if match:
                            datum_str = match.group(1)
                            try:
                                datum = datetime.strptime(datum_str, "%d.%m.%y").date()
                            except:
                                continue
                            namn = match.group(2).strip()
                            summa = float(match.group(3).replace('.', '').replace(',', '.').replace(' ', ''))
                            if datum < start_date:
                                datum = start_date
                            if datum > end_date:
                                continue
                            transactions.append({"Datum": datum, "Vart": namn, "Summa": summa})
            # Sort by date
            return sorted(transactions, key=lambda x: x['Datum'])

        st.session_state.transactions = extract_transactions(uploaded_file, start_date, end_date)
        st.session_state.resultat = []
        st.session_state.index = 0
        st.session_state.started = True
        st.rerun()

# Step 2: Show one transaction at a time
elif st.session_state.started:
    index = st.session_state.index
    transactions = st.session_state.transactions
    resultat = st.session_state.resultat

    if index < len(transactions):
        t = transactions[index]
        st.subheader(f"Transaktion {index + 1} av {len(transactions)}")
        st.markdown(f"**Datum**: {t['Datum']}")
        st.markdown(f"**Vart**: {t['Vart']}")
        st.markdown(f"**Summa**: {t['Summa']} kr")

        col1, col2 = st.columns(2)

        with col1:
            vem = st.radio("Vem?", PERSONER, key=f"vem_{index}", horizontal=True)

        with col2:
            kategori = st.radio("Kategori?", KATEGORIER, key=f"kat_{index}", horizontal=True)

        if st.button("Spara & Nästa ➡️"):
            t['Vem'] = vem
            t['Kategori'] = kategori
            st.session_state.resultat.append(t)
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
