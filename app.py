import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pdfplumber
import re

# Alternativ för val
PERSONER = ['Albin', 'Nathalie', 'Gemensamt']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

# Parser som identifierar transaktioner och ignorerar "betalning mottagen"
def parse_transactions(pdf_file, start_date, end_date):
    transactions = []
    pattern = re.compile(r"^(\d{2}\.\d{2}\.\d{2})\s+(\d{2}\.\d{2}\.\d{2})\s+(.*?)(-?\d{1,3}(?:[ \.]\d{3})*,\d{2})?$")
    current = None

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            for line in lines:
                line = line.strip()
                match = pattern.match(line)

                if match:
                    if current:
                        transactions.append(current)

                    datum = datetime.strptime(match.group(1), "%d.%m.%y").date()
                    vart = match.group(3).strip()
                    summa_str = match.group(4)
                    summa = None
                    if summa_str:
                        try:
                            summa = float(summa_str.replace(" ", "").replace(".", "").replace(",", "."))
                        except:
                            pass
                    current = {"Datum": datum, "Vart": vart, "Summa": summa}
                elif current:
                    if re.match(r"^\d{2}\.\d{2}\.\d{2}", line):
                        if current:
                            transactions.append(current)
                        current = None
                    else:
                        current["Vart"] += " " + line.strip()

        if current:
            transactions.append(current)

    # Filtrera bort ogiltiga och irrelevanta transaktioner
    filtered = []
    for t in transactions:
        if t["Summa"] is None:
            continue
        if "betalning mottagen" in t["Vart"].lower():
            continue
        t["Datum"] = max(t["Datum"], start_date)
        if t["Datum"] > end_date:
            continue
        filtered.append(t)

    return sorted(filtered, key=lambda x: x["Datum"])

# UI start
st.set_page_config(page_title="Kategorisera Utgifter", layout="centered")
st.title("📄 Kategorisera Utgifter")

# Initiera session state
for key in ['index', 'resultat', 'transactions', 'started', 'start_date', 'end_date']:
    if key not in st.session_state:
        st.session_state[key] = None if key in ['start_date', 'end_date'] else []

# Laddningsvy
if not st.session_state.started:
    uploaded_file = st.file_uploader("Ladda upp PDF-kontoutdrag", type=["pdf"])
    start_date = st.date_input("Från datum", value=datetime.today(), key="start_date_input")
    end_date = st.date_input("Till datum", value=datetime.today(), key="end_date_input")

    if uploaded_file and st.button("🚀 Starta"):
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        st.session_state.transactions = parse_transactions(uploaded_file, start_date, end_date)
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
