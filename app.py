import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

# --- Konstanter ---
PERSONER = ['Gemensamt', 'Albin', 'Nathalie']  # Gemensamt först/förvalt
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

# Fasta Amex-kolumner
COL_DESC = "Transaktionsuppgifter"
COL_DATE = "Transaktionsdatum"
COL_AMOUNT = "Belopp i SEK"

# --- Hjälpare ---
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
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        val = float(s)
        return -val if negative else val
    except Exception:
        return None

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Säkerställ att kolumnerna finns
    missing = [c for c in [COL_DESC, COL_DATE, COL_AMOUNT] if c not in df.columns]
    if missing:
        raise ValueError(f"Saknar kolumner i filen: {', '.join(missing)}")

    out = pd.DataFrame({
        "Vart": df[COL_DESC].astype(str).str.strip(),
        "Datum": df[COL_DATE].apply(parse_date_any),
        "Summa": df[COL_AMOUNT].apply(parse_amount),
    })
    out = out.dropna(subset=["Datum", "Summa"]).copy()
    out["Vart"] = out["Vart"].str.replace(r"\s+", " ", regex=True).str.strip()
    return out

# --- Streamlit UI ---
st.set_page_config(page_title="Kategorisera Utgifter – Amex Excel", layout="centered")
st.title("📄 Kategorisera Utgifter – Amex Excel")

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
        # Läs fil (utan förhandsvisning eller mappning)
        if uploaded.name.lower().endswith(".csv"):
            try:
                df_raw = pd.read_csv(uploaded)
            except UnicodeDecodeError:
                df_raw = pd.read_csv(uploaded, encoding="latin-1", sep=";")
        else:
            df_raw = pd.read_excel(uploaded)

        # Normalisera
        df = normalize_df(df_raw)

        # Datumskift & filter
        df["Datum"] = df["Datum"].apply(lambda d: start_date if d < start_date else d)
        df = df[df["Datum"] <= end_date].copy()

        # Sortera på datum (äldst först)
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
