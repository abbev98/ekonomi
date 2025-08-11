import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime, date

# ---- Alternativ för val ----
PERSONER = ['Gemensamt', 'Albin', 'Nathalie']
KATEGORIER = ['Mat', 'Hushåll', 'Nöje', 'Resa', 'Restaurang', 'Kläder', 'Hälsa', 'Annat']

# ---- Kandidater (sv/eng & varianter) ----
CAND_DATE   = [
    "Transaktionsdatum", "Transaktions-datum", "Datum", "Bokföringsdatum",
    "Transaction Date", "Date", "Posted Date"
]
CAND_DESC   = [
    "Transaktionsuppgifter", "Uppgifter", "Butik", "Beskrivning",
    "Transaction Details", "Description", "Merchant", "Details"
]
CAND_AMOUNT = [
    "Belopp i SEK", "Belopp", "SEK", "Amount", "Amount (SEK)", "Belopp (SEK)",
    "Debet", "Kredit"
]

# Fråserader/sektioner att ignorera
NOISE_PHRASES = [
    "betalning mottagen", "inbetalningar", "summa nya inbetalningar",
    "summan av alla nya köp", "periodens del av årsavgift", "kategori saldo",
    "gällande räntesatser", "sas amex premium", "transaktionsspecifikationer"
]

# ---- Normaliseringshjälpare ----
def norm_colname(s: str) -> str:
    s = (str(s) if s is not None else "").strip().lower()
    s = re.sub(r"[^a-z0-9åäö]+", "", s)
    return s

def parse_date_any(x):
    if pd.isna(x):
        return None
    if isinstance(x, (pd.Timestamp, datetime, date)):
        try:
            return pd.to_datetime(x).date()
        except Exception:
            return None
    s = str(x).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
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
    # Hantera t.ex. "CR" och textrester
    s = re.sub(r"[^0-9\.-]", "", s)
    if s in ("", "-", ".", "-.", ".-"):
        return None
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return None

def clean_noise(desc: str) -> bool:
    d = (desc or "").strip().lower()
    if not d:
        return False
    for phrase in NOISE_PHRASES:
        if phrase in d:
            return False
    # Enstaka "CR" som rad = brus
    if d == "cr":
        return False
    return True

# ---- Hitta tabell i "rapport-Excel" ----
def find_header_row(df_no_header: pd.DataFrame, max_scan_rows: int = 50):
    """
    Returnerar (header_row_index) där rubrikerna sannolikt finns,
    annars None om ingen bra match hittas.
    """
    def score_row(vals):
        labels = [norm_colname(v) for v in vals]
        hits = 0
        # räkna träffar mot kandidater
        def has_any(cands):
            for c in cands:
                n = norm_colname(c)
                for lab in labels:
                    if lab == n or lab.startswith(n) or n in lab:
                        return True
            return False
        if has_any(CAND_DATE):   hits += 1
        if has_any(CAND_DESC):   hits += 1
        if has_any(CAND_AMOUNT): hits += 1
        return hits

    best_row, best_score = None, -1
    n = min(len(df_no_header), max_scan_rows)
    for i in range(n):
        vals = list(df_no_header.iloc[i, :])
        sc = score_row(vals)
        if sc > best_score:
            best_score = sc
            best_row = i
    return best_row if best_score >= 2 else None  # kräver minst 2 kategorier matchade

def load_transactions_table(uploaded_file) -> pd.DataFrame:
    # Läs utan header för att kunna hitta rubrikrad
    if uploaded_file.name.lower().endswith(".csv"):
        try:
            df0 = pd.read_csv(uploaded_file, header=None)
        except UnicodeDecodeError:
            df0 = pd.read_csv(uploaded_file, header=None, encoding="latin-1", sep=";")
    else:
        df0 = pd.read_excel(uploaded_file, header=None)

    header_row = find_header_row(df0)
    if header_row is None:
        raise ValueError(
            "Kunde inte lokalisera rubrikraden i Excel-arket. "
            "Kontrollera att filen är Amex-exporten med kolumner som Transaktionsdatum / Transaktionsuppgifter / Belopp i SEK."
        )

    headers = df0.iloc[header_row].tolist()
    data = df0.iloc[header_row + 1:].copy()
    data.columns = headers

    # Ta bort helt tomma rader och tomma kolumner
    data = data.dropna(how="all")
    data = data.loc[:, data.columns.notna()]
    # Rensa bort "Unnamed" och kolumner som nästan bara är NaN (rubrikskräp)
    keep_cols = []
    for c in data.columns:
        cname = str(c)
        if cname.lower().startswith("unnamed"):
            # behåll bara om den faktiskt har mycket data
            if data[c].notna().sum() > 5:
                keep_cols.append(c)
        else:
            keep_cols.append(c)
    data = data[keep_cols]

    return data

def find_col(df: pd.DataFrame, candidates):
    norm_map = {norm_colname(c): c for c in df.columns if c is not None}
    for cand in candidates:
        n = norm_colname(cand)
        if n in norm_map:
            return norm_map[n]
    # Fuzzy fallback
    for cand in candidates:
        n = norm_colname(cand)
        for col in df.columns:
            if col is None: 
                continue
            cn = norm_colname(col)
            if cn.startswith(n) or n in cn:
                return col
    return None

def normalize_df_autodetect(df_any: pd.DataFrame) -> pd.DataFrame:
    # df_any är nu själva tabellen med "riktiga" headers
    col_date = find_col(df_any, CAND_DATE)
    col_desc = find_col(df_any, CAND_DESC)
    col_amt  = find_col(df_any, CAND_AMOUNT)

    missing = []
    if not col_desc: missing.append("Transaktionsuppgifter/Description")
    if not col_date: missing.append("Transaktionsdatum/Date")
    if not col_amt:  missing.append("Belopp i SEK/Amount")
    if missing:
        raise ValueError(
            "Hittade inte följande kolumner i tabellen: " + ", ".join(missing) +
            f".\nUpptäckta rubriker: {', '.join(map(str, df_any.columns))}"
        )

    # Om både Debet och Kredit finns, slå ihop till en "Belopp" (Debet positivt, Kredit negativt)
    if norm_colname(col_amt) in [norm_colname("Debet"), norm_colname("Kredit")]:
        col_debet = find_col(df_any, ["Debet"])
        col_kredit = find_col(df_any, ["Kredit"])
        if col_debet and col_kredit:
            amt_series = df_any[col_debet].apply(parse_amount).fillna(0) - df_any[col_kredit].apply(parse_amount).fillna(0)
        elif col_debet:
            amt_series = df_any[col_debet].apply(parse_amount)
        else:
            amt_series = -df_any[col_kredit].apply(parse_amount)
    else:
        amt_series = df_any[col_amt].apply(parse_amount)

    out = pd.DataFrame({
        "Vart":  df_any[col_desc].astype(str).str.strip(),
        "Datum": df_any[col_date].apply(parse_date_any),
        "Summa": amt_series,
    })

    # Brusfilter
    out = out[out["Vart"].apply(clean_noise)]
    out = out.dropna(subset=["Datum", "Summa"]).copy()
    out["Vart"] = out["Vart"].str.replace(r"\s+", " ", regex=True).str.strip()
    return out

# ---- Streamlit UI ----
st.set_page_config(page_title="Kategorisera Utgifter – Amex Excel", layout="centered")
st.title("📄 Kategorisera Utgifter – Amex Excel (robust rubrikdetektering)")

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
        # Läs rapportfil och hitta tabellen
        try:
            df_table = load_transactions_table(uploaded)
            df = normalize_df_autodetect(df_table)
        except Exception as e:
            st.error(str(e))
            st.stop()

        # Datumskift & filter
        df["Datum"] = df["Datum"].apply(lambda d: start_date if d < start_date else d)
        df = df[df["Datum"] <= end_date].copy()
        df = df.sort_values("Datum").reset_index(drop=True)

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

        excel_buffer = io.BytesIO()
        df_out.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        st.download_button(
            label="📥 Ladda ner Excel-fil",
            data=excel_buffer,
            file_name="kategoriserade_utgifter.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
