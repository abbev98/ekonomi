
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

uploaded_file = st.file_uploader("Ladda upp PDF-kontoutdrag", type=["pdf"])
start_date = st.date_input("Från datum", value=datetime.today())
end_date = st.date_input("Till datum", value=datetime.today())

if uploaded_file and start_date and end_date:
    st.success("PDF uppladdad. Bearbetar...")

    # Extract transactions
    transactions = []
    with pdfplumber.open(uploaded_file) as pdf:
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

    st.info(f"{len(transactions)} transaktioner hittade i valt datumintervall.")

    if transactions:
        resultat = []
        for i, t in enumerate(transactions):
            st.subheader(f"Transaktion {i + 1} av {len(transactions)}")
            st.text(f"{t['Datum']} | {t['Vart']} | {t['Summa']} kr")
            t['Vem'] = st.selectbox("Vem?", PERSONER, key=f"vem_{i}")
            t['Kategori'] = st.selectbox("Kategori?", KATEGORIER, key=f"kat_{i}")
            resultat.append(t)

        if st.button("✅ Exportera till Excel"):
            df = pd.DataFrame(resultat)
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            st.download_button("📥 Ladda ner Excel-fil", data=excel_buffer, file_name="kategoriserade_utgifter.xlsx")
