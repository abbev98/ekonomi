import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

# App options
PERSONER = ['Gemensamt', 'Albin', 'Nathalie']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

st.set_page_config(page_title="Kategorisera Utgifter (Excel)", layout="centered")
st.title("📄 Kategorisera Utgifter – från Excel/CSV")

# ---------- Helpers ----------
def _parse_date_any(x):
    if pd.isna(x):
        return None
    if isinstance(x, (pd.Timestamp, datetime, date)):
        return pd.to_datetime(x).date()
    s = str(x).strip()
    # Try common Swedish formats
    for fmt in ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    # Fall back to pandas
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce").date()
    except Exception:
        return None

def _to_float_amount(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    # if comma decimals, normalize
    s = s.replace(" ", "")
    # if both '.' and ',', assume '.' is thousands and ',' is decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def _clean_df(df, col_vart, col_datum, col_summa):
    out = pd.DataFrame({
        "Vart": df[col_vart].astype(str).str.strip(),
        "Datum": df[col_datum].apply(_parse_date_any),
        "Summa": df[col_summa].apply(_to_float_amount)
    })
    out = out.dropna(subset=["Datum", "Summa"]).copy()
    return out

# ---------- State ----------
defaults = {
    'index': 0,
    'resultat': [],
    'transactions': [],
    'started': False,
    'start_date': None,
    'end_date': None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------- Upload & Setup ----------
if not st.session_state.started:
    uploaded = st.file_uploader("Ladda upp Excel (.xlsx) eller CSV", type=["xlsx", "csv"])

    # Choose date range
    today = datetime.today().date()
    start_date = st.date_input("Från datum", value=today, key="start_date_input")
    end_date = st.date_input("Till datum", value=today, key="end_date_input")

    # If file uploaded, read and let user map columns
    if uploaded is not None:
        if uploaded.name.lower().endswith(".csv"):
            try:
                df_raw = pd.read_csv(uploaded)
            except UnicodeDecodeError:
                df_raw = pd.read_csv(uploaded, encoding="latin-1", sep=";")
        else:
            df_raw = pd.read_excel(uploaded)

        st.write("### Förhandsgranskning")
        st.dataframe(df_raw.head(20), use_container_width=True)

        cols = list(df_raw.columns)

        st.write("### Mappa kolumner")
        col1, col2, col3 = st.columns(3)
        with col1:
            col_vart = st.selectbox("Kolumn för **Vart** (namn)", options=cols, index=0 if "Vart" in cols else 0)
        with col2:
            # Försök auto-välja en datumkolumn om möjligt
            date_guess = next((c for c in cols if c.lower() in ["datum", "date"]), 0)
            col_datum = st.selectbox("Kolumn för **Datum**", options=cols, index=cols.index(date_guess) if date_guess in cols else 0)
        with col3:
            sum_guess = next((c for c in cols if c.lower() in ["summa", "belopp", "amount"]), 0)
            col_summa = st.selectbox("Kolumn för **Summa**", options=cols, index=cols.index(sum_guess) if sum_guess in cols else 0)

        if st.button("🚀 Starta"):
            df = _clean_df(df_raw, col_vart, col_datum, col_summa)

            # Justera datum: allt före start_date flyttas upp till start_date
            df["Datum"] = df["Datum"].apply(lambda d: start_date if d < start_date else d)
            # Filtrera bort efter end_date
            df = df[df["Datum"] <= end_date].copy()

            # Sortera på datum stigande
            df = df.sort_values("Datum").reset_index(drop=True)

            # Skapa transaktionslista
            st.session_state.transactions = df.to_dict(orient="records")
            st.session_state.resultat = []
            st.session_state.index = 0
            st.session_state.start_date = start_date
            st.session_state.end_date = end_date
            st.session_state.started = True
            st.rerun()

# ---------- One-by-one labeling ----------
elif st.session_state.started:
    index = st.session_state.index
    transactions = st.session_state.transactions
    resultat = st.session_state.resultat

    if index < len(transactions):
        t = transactions[index]
        st.subheader(f"Transaktion {index + 1} av {len(transactions)}")
        st.markdown(f"**Datum:** {t['Datum']}")

        edited_name = st.text_input("🛍️ Namn (Vart)", value=str(t['Vart']), key=f"namn_{index}")
        edited_sum = st.number_input("💰 Summa", value=float(t['Summa']), step=0.01, key=f"summa_{index}")

        col1, col2 = st.columns(2)
        with col1:
            vem = st.radio("👤 Vem?", PERSONER, horizontal=True, key=f"vem_{index}")
        with col2:
            kategori = st.radio("📂 Kategori?", KATEGORIER, horizontal=True, key=f"kat_{index}")

        if st.button("Spara & Nästa ➡️"):
            resultat.append({
                'Vart': edited_name.strip(),
                'Datum': t['Datum'],
                'Summa': edited_sum,
                'Vem': vem,
                'Kategori': kategori
            })
            st.session_state.index += 1
            st.rerun()
    else:
        st.success("🎉 Alla transaktioner är kategoriserade.")
        df_out = pd.DataFrame(resultat, columns=["Vart", "Datum", "Summa", "Vem", "Kategori"])
        st.subheader("📊 Resultat (kopiera till Google Kalkylark):")
        st.dataframe(df_out, use_container_width=True)

        # Excel-download
        excel_buffer = io.BytesIO()
        df_out.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        st.download_button(
            label="📥 Ladda ner Excel-fil",
            data=excel_buffer,
            file_name="kategoriserade_utgifter.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              )
