
import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from datetime import datetime

PERSONER = ['Albin', 'Nathalie', 'Gemensamt']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

st.set_page_config(page_title="Kategorisera Utgifter", layout="centered")
st.title("📄 Kategorisera Utgifter från PDF")

# Session state
if 'index' not in st.session_state:
    st.session_state.index = 0
if 'resultat' not in st.session_state:
    st.session_state.resultat = []
if 'transactions' not in st.session_state:
    st.session_state.transactions = []

uploaded_file = st.file_uploader("Ladda upp PDF-kontoutdrag", type=["pdf"])
start_date = st.date_input("Från datum", value=datetime.today())
end_date = st.date_input("Till datum", value=datetime.today())

# Extract transactions
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
    return transactions

# Load and prepare transactions
if uploaded_file and start_date and end_date and not st.session_state.transactions:
    st.session_state.transactions = extract_transactions(uploaded_file, start_date, end_date)
    st.success(f"{len(st.session_state.transactions)} transaktioner laddade.")

# Show one transaction at a time
if st.session_state.transactions:
    if st.session_state.index < len(st.session_state.transactions):
        t = st.session_state.transactions[st.session_state.index]
        st.subheader(f"Transaktion {st.session_state.index + 1} av {len(st.session_state.transactions)}")
        st.markdown(f"**Datum**: {t['Datum']}")
        st.markdown(f"**Vart**: {t['Vart']}")
        st.markdown(f"**Summa**: {t['Summa']} kr")

        vem = st.radio("Vem?", PERSONER, key=f"vem_{st.session_state.index}")
        kategori = st.radio("Kategori?", KATEGORIER, key=f"kat_{st.session_state.index}")

        if st.button("Spara & Nästa ➡️"):
            t['Vem'] = vem
            t['Kategori'] = kategori
            st.session_state.resultat.append(t)
            st.session_state.index += 1
            st.experimental_rerun()
    else:
        st.success("🎉 Alla transaktioner är kategoriserade.")

# Show table of categorized results
if st.session_state.resultat:
    df = pd.DataFrame(st.session_state.resultat)
    st.subheader("📊 Resultat (kopiera till Google Kalkylark):")
    st.dataframe(df, use_container_width=True)

    # Optional download button
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    st.download_button("📥 Ladda ner Excel-fil", data=excel_buffer, file_name="kategoriserade_utgifter.xlsx")
