import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime, date

# --- Konstanter ---
PERSONER = ['Gemensamt', 'Albin', 'Nathalie']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

# Kandidatnamn (lägg till fler om din export skiljer sig)
CAND_DATE   = ["Transaktionsdatum", "Transaktions-datum", "Datum", "Transaction Date", "Date"]
CAND_DESC   = ["Transaktionsuppgifter", "Uppgifter", "Butik", "Beskrivning", "Description", "Merchant"]
CAND_AMOUNT = ["Belopp i SEK", "Belopp", "Amount", "SEK", "Belopp (SEK)"]

# --- Hjälpare ---
def norm_colname(s: str) -> str:
    # normalisera kolumnnamn för matchning (små bokstäver, ta bort icke-bokstav/siffra)
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9åäö]+", "", s)
    return s

def find_col(df: pd.DataFrame, candidates):
    norm_map = {norm_colname(c): c for c in df.columns}
    for cand in candidates:
        n = norm_colname(cand)
        if n in norm_map:
            return norm_map[n]
    # Lite generös fuzzy: testa startswith/contains
    for cand in candidates:
        n = norm_colname(cand)
        for col in df.columns:
            if norm_colname(col).startswith(n) or n in norm_colname(col):
                return col
    return None

def parse_date_any(x):
    if pd.isna(x):
        return None
    if isinstance(x, (pd.Timestamp, datetime, date)):
        try:
            return pd.to_datetime(x).date()
        except Exception:
            return None
    s = str(x).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce").date()
    except Exception:
        return None

def parse_amount(x):
    if pd.isna(x):
        return None
    s = str(x).strip().replace(" ", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return None

def normalize_df_autodetect(df: pd.DataFrame) -> pd.DataFrame:
    col_date = find_col(df, CAND_DATE)
    col_desc = find_col(df, CAND_DESC)
    col_amt  = find_col(df, CAND_AMOUNT)

    missing = []
    if not col_desc: missing.append("Transaktionsuppgifter")
    if not col_date: missing.append("Transaktionsdatum")
    if not col_amt:  missing.append("Belopp i SEK")
    if missing:
        cols_list = ", ".join(map(str, df.columns))
        raise ValueError(
            "Hittade inte följande kolumner: "
            + ", ".join(missing)
            + f".\nRubriker i din fil: {cols_list}\n"
            "Lägg till rätt rubriker i exporten eller be mig lägga till fler kandidater i appen."
        )

    out = pd.DataFrame({
        "Vart":  df[col_desc].astype(str).str.strip(),
        "Datum": df[col_date].apply(parse_date_any),
        "Summa": df[col_amt].apply(parse_amount),
    })
    out = out.dropna(subset=["Datum", "Summa"]).copy()
    out["Vart"] = out["Vart"].str.replace(r"\s+", " ", regex=True).str.strip()
    return out

# --- Streamlit UI ---
st.set_page_config(page_title="Kategorisera Utgifter – Amex Excel", layout="centered")
st.title("📄 Kategorisera Utgifter – Amex Excel (autodetektion)")

# State
defaults = {'index': 0, 'resultat': [], 'transactions': [], 'started': False, 'start_date': None, 'end_date': None}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.started:
    uploaded = st.file_uploader("Ladda upp Amex Excel (.xlsx) eller CSV", type=["xlsx", "csv"])
    today = datetime.today().date()
    start_date = st.date_input("Från datum", value=today, key="start_date_input")
    end_date   = st.date_input("Till datum", value=today, key="end_date_input")

    if uploaded is not None and st.button("🚀 Starta"):
        # Läs fil
        if uploaded.name.lower().endswith(".csv"):
            try:
                df_raw = pd.read_csv(uploaded)
            except UnicodeDecodeError:
                df_raw = pd.read_csv(uploaded, encoding="latin-1", sep=";")
        else:
            df_raw = pd.read_excel(uploaded)

        # Normalisera med autodetektion
        try:
            df = normalize_df_autodetect(df_raw)
        except ValueError as e:
            st.error(str(e))
            st.stop()

        # Datumskift & filter
        df["Datum"] = df["Datum"].apply(lambda d: start_date if d < start_date else d)
        df = df[df["Datum"] <= end_date].copy()

        # Sortera på datum
        df = df.sort_values("Datum").reset_index(drop=True)

        # Spara i state
        st.session_state.transactions = df.to_dict(orient="records")
        st.session_state.resultat = []
        st.session_state.index = 0
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        st.session_state.started = True
        st.rerun()

else:
    index = st.session_state.index
    txs = st.session_state.transactions
    res = st.session_state.resultat

    if index < len(txs):
        t = txs[index]
        st.subheader(f"Transaktion {index + 1} av {len(txs)}")
        st.markdown(f"**Datum:** {t['Datum']}")

        edited_name = st.text_input("🛍️ Namn (Vart)", value=str(t['Vart']), key=f"namn_{index}")
        edited_sum  = st.number_input("💰 Summa", value=float(t['Summa']), step=0.01, key=f"summa_{index}")

        col1, col2 = st.columns(2)
        with col1:
            vem = st.radio("👤 Vem?", PERSONER, index=0, horizontal=True, key=f"vem_{index}")
        with col2:
            kategori = st.radio("📂 Kategori?", KATEGORIER, horizontal=True, key=f"kat_{index}")

        if st.button("Spara & Nästa ➡️"):
            res.append({
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
        df_out = pd.DataFrame(res, columns=["Vart", "Datum", "Summa", "Vem", "Kategori"])
        st.subheader("📊 Resultat (kopiera till Google Kalkylark):")
        st.dataframe(df_out, use_container_width=True)

        # Excel-nedladdning
        excel_buffer = io.BytesIO()
        df_out.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        st.download_button(
            label="📥 Ladda ner Excel-fil",
            data=excel_buffer,
            file_name="kategoriserade_utgifter.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
