import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(
    page_title="Semanalyzer – LOT SEM Tools",
    page_icon="✈️",
    layout="wide",
)

# ── Negative keyword dictionary ──────────────────────────────────────────────
# Each category: list of regex patterns (case-insensitive, match on full term)

NEGATIVE_CATEGORIES = {
    "Praca / Rekrutacja": [
        r"\bprac[aąę]\b", r"\bjob[s]?\b", r"\bcareer[s]?\b", r"\brekrutacj[ai]\b",
        r"\bzatrudni(enie|ć)\b", r"\bofert[ay] prac[yi]\b", r"\bpilot training\b",
        r"\bstewardes[as]?\b", r"\bsteward\b", r"\bcabin crew\b", r"\bhostess[a]?\b",
        r"\bpraca pilot\b", r"\bhiring\b", r"\bvacancy\b", r"\bvacancies\b",
        r"\brecruitment\b", r"\bstellen\b", r"\bjob offer\b", r"\bpraktyk[ai]\b",
        r"\bstaż\b", r"\binternship\b",
    ],
    "Nocleg / Hotel": [
        r"\bhotel[u]?\b", r"\bhostel[u]?\b", r"\bnoclegi?\b", r"\bapartament[u]?\b",
        r"\bapartment[s]?\b", r"\bairbnb\b", r"\bbnb\b", r"\bbed and breakfast\b",
        r"\bkwater[ay]\b", r"\bpensjonat\b", r"\bmotel\b", r"\baccommodation\b",
        r"\bübernachtung\b", r"\bhôtel\b", r"\bhotel reservation\b",
    ],
    "Wynajem samochodu / Transfer": [
        r"\bwynajem\b", r"\brent[ -]?a[ -]?car\b", r"\bcar hire\b", r"\bcar rental\b",
        r"\btaxi\b", r"\buber\b", r"\bbolt\b", r"\btransfer\b", r"\blimuzyn[ay]\b",
        r"\bauto\b(?! ?pil)", r"\bsamochód\b", r"\bmietoauto\b", r"\bmietauto\b",
    ],
    "Cargo / Freight": [
        r"\bcargo\b", r"\bfreight\b", r"\bładunek\b", r"\bspedycj[ai]\b",
        r"\bprzesyłk[ai]\b", r"\bpaczk[ai]\b", r"\bcourier\b", r"\bkuriersk[ai]\b",
    ],
    "Darmowe / Promocje bez intencji zakupu": [
        r"\bdarmow[ya]\b", r"\bfree\b", r"\bgratis\b", r"\bza darmo\b",
        r"\bbez opłat\b", r"\bkostenlos\b", r"\bgratuit\b", r"\bkostenfrei\b",
    ],
    "Konkurencja – LCC / inne linie": [
        r"\bryanair\b", r"\bwizz\b", r"\beasyjet\b", r"\blufthansa\b",
        r"\baustrian\b", r"\bsas\b(?! lot)", r"\bnorwegian\b", r"\btransavia\b",
        r"\bvueling\b", r"\bturkish airlines\b", r"\bthy\b", r"\baeroflot\b",
        r"\bair france\b", r"\bklm\b", r"\balitalia\b", r"\bits2\b",
        r"\bfinnair\b", r"\bjet2\b", r"\bsmartavia\b", r"\bflydubai\b",
        r"\bemirates\b(?! mile)", r"\betihad\b", r"\bqatar airways\b",
    ],
    "Informacyjne / brak intencji zakupu": [
        r"\bhistoria\b", r"\bhistory\b", r"\bwikipedia\b", r"\bmuseum\b",
        r"\bpogoda\b", r"\bweather\b", r"\bwetter\b", r"\bmapa\b", r"\bmap[s]?\b",
        r"\bgoogle maps\b", r"\bfilm\b", r"\bmovie\b", r"\bserial\b",
        r"\bfoto\b", r"\bphoto[s]?\b", r"\bzdjęci[ae]\b",
        r"\bdownload\b", r"\baplikacj[ai]\b(?! lot)", r"\bapp\b(?! lot)",
        r"\bstreaming\b", r"\bnetflix\b", r"\bksiążk[ai]\b", r"\bbook review\b",
        r"\blyrics\b", r"\btekst piosenki\b",
    ],
    "Ubezpieczenia podróżne (jeśli nie w ofercie)": [
        r"\bubezpieczeni[ae]\b", r"\binsurance\b", r"\bversicherung\b",
        r"\bassurance\b", r"\btravel insurance\b",
    ],
    "Wiza / Dokumenty": [
        r"\bwiza\b", r"\bvisa\b", r"\bpassport\b", r"\bpaszport\b",
        r"\bwniosek\b", r"\bapplication form\b", r"\bconsulate\b",
        r"\bkonsulat\b", r"\bembassy\b", r"\bambassada\b",
    ],
    "Loty cargo / prywatne / czarter": [
        r"\bprivate jet\b", r"\bprywatny samolot\b", r"\bcharter[u]?\b",
        r"\bjacht\b", r"\byacht\b",
    ],
}

# ── Helper functions ──────────────────────────────────────────────────────────

def detect_columns(df: pd.DataFrame) -> dict:
    """Try to find Google Ads ST report columns regardless of language."""
    col_map = {}
    aliases = {
        "search_term": ["search term", "search terms", "zapytanie", "słowo kluczowe wyszukiwania",
                        "suchbegriff", "terme de recherche", "término de búsqueda"],
        "impressions":  ["impressions", "wyświetlenia", "impr", "impressionen"],
        "clicks":       ["clicks", "kliknięcia", "kliki", "klicks", "clics"],
        "cost":         ["cost", "koszt", "kosten", "coût", "costo", "spend"],
        "conversions":  ["conversions", "konwersje", "conv.", "konversionen"],
        "ctr":          ["ctr", "click-through rate", "wskaźnik klikalności"],
    }
    for key, names in aliases.items():
        for col in df.columns:
            if col.strip().lower() in names:
                col_map[key] = col
                break
    return col_map


def match_negatives(term: str) -> list[str]:
    """Return list of matched category names for a given search term."""
    term_lower = term.lower()
    matched = []
    for category, patterns in NEGATIVE_CATEGORIES.items():
        for pat in patterns:
            if re.search(pat, term_lower):
                matched.append(category)
                break
    return matched


def score_term(row: pd.Series, col_map: dict) -> str:
    """Return priority label based on performance metrics."""
    cost = float(str(row.get(col_map.get("cost", ""), "0")).replace(",", ".").replace(" ", "") or 0)
    conv = float(str(row.get(col_map.get("conversions", ""), "0")).replace(",", ".").replace(" ", "") or 0)
    clicks = float(str(row.get(col_map.get("clicks", ""), "0")).replace(",", ".").replace(" ", "") or 0)
    impr = float(str(row.get(col_map.get("impressions", ""), "0")).replace(",", ".").replace(" ", "") or 0)

    if cost > 0 and conv == 0:
        return "🔴 Wysoki koszt, 0 konwersji"
    if impr > 100 and clicks == 0:
        return "🟠 Dużo wyświetleń, 0 kliknięć"
    if clicks > 0 and conv == 0 and cost > 0:
        return "🟡 Kliknięcia bez konwersji"
    return "⚪ Brak danych metryk"


def to_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wykluczenia")
    return buf.getvalue()


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("✈️ Semanalyzer")
st.caption("Analiza Search Terms | PLL LOT SEM Tools")

st.markdown(
    """
Wgraj raport **Search Terms** z Google Ads (CSV lub Excel).
Aplikacja automatycznie wykryje potencjalne słowa kluczowe do wykluczenia
i posegreguje je według kategorii.
"""
)

uploaded = st.file_uploader(
    "Wgraj plik Search Terms Report (CSV / XLSX / XLS)",
    type=["csv", "xlsx", "xls"],
)

if uploaded is None:
    st.info("Czekam na plik… Eksportuj raport z Google Ads: **Słowa kluczowe → Search Terms → Pobierz**")
    st.stop()

# ── Load file ─────────────────────────────────────────────────────────────────
try:
    if uploaded.name.endswith(".csv"):
        # Google Ads CSVs often have 2-3 header rows
        raw = uploaded.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()
        # Find the actual header row (contains "Search term" or "Impressions")
        header_idx = 0
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["search term", "impressions", "zapytanie", "wyświetl"]):
                header_idx = i
                break
        from io import StringIO
        df = pd.read_csv(StringIO("\n".join(lines[header_idx:])), thousands=",")
    else:
        df = pd.read_excel(uploaded, header=None)
        # Find header row
        for i, row in df.iterrows():
            vals = [str(v).lower() for v in row.values]
            if any(k in " ".join(vals) for k in ["search term", "impressions", "zapytanie"]):
                df.columns = df.iloc[i]
                df = df.iloc[i + 1:].reset_index(drop=True)
                break
        else:
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
except Exception as e:
    st.error(f"Błąd wczytywania pliku: {e}")
    st.stop()

df.columns = [str(c).strip() for c in df.columns]
df = df.dropna(how="all")

col_map = detect_columns(df)
st.success(f"Wczytano {len(df):,} wierszy. Wykryte kolumny: {list(col_map.values())}")

if "search_term" not in col_map:
    st.error(
        "Nie znaleziono kolumny 'Search Term'. Upewnij się, że plik to raport ST z Google Ads. "
        "Możliwe kolumny w pliku: " + str(df.columns.tolist())
    )
    st.stop()

st_col = col_map["search_term"]

# ── Analysis ──────────────────────────────────────────────────────────────────
with st.spinner("Analizuję search terms…"):
    df["_categories"] = df[st_col].astype(str).apply(match_negatives)
    df["_has_neg"] = df["_categories"].apply(bool)
    df["_priority"] = df.apply(lambda r: score_term(r, col_map), axis=1)

neg_df = df[df["_has_neg"]].copy()
neg_df["Kategoria wykluczenia"] = neg_df["_categories"].apply(lambda x: ", ".join(x))

# Build display frame
display_cols = [st_col] + [col_map[k] for k in ["impressions", "clicks", "cost", "conversions"] if k in col_map]
display_df = neg_df[display_cols + ["Kategoria wykluczenia", "_priority"]].rename(
    columns={"_priority": "Priorytet"}
)

# ── Summary cards ─────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Wszystkich search terms", f"{len(df):,}")
c2.metric("Do wykluczenia", f"{len(neg_df):,}")
c3.metric("% do wykluczenia", f"{len(neg_df)/len(df)*100:.1f}%" if len(df) else "–")
wasted = 0
if "cost" in col_map:
    try:
        neg_df["_cost_num"] = pd.to_numeric(
            neg_df[col_map["cost"]].astype(str).str.replace(",", ".").str.replace(" ", ""),
            errors="coerce"
        ).fillna(0)
        wasted = neg_df["_cost_num"].sum()
    except Exception:
        pass
c4.metric("Zmarnowany budżet (est.)", f"{wasted:,.2f}" if wasted else "brak danych")

st.divider()

# ── Filter by category ────────────────────────────────────────────────────────
all_cats = sorted({cat for cats in neg_df["_categories"] for cat in cats})
selected_cats = st.multiselect(
    "Filtruj kategorie",
    options=all_cats,
    default=all_cats,
    help="Odznacz kategorie, których nie chcesz widzieć",
)

filtered_df = display_df[
    neg_df["_categories"].apply(lambda cats: any(c in selected_cats for c in cats))
].copy()

st.dataframe(
    filtered_df.reset_index(drop=True),
    use_container_width=True,
    height=500,
)

# ── Category breakdown chart ──────────────────────────────────────────────────
st.subheader("Rozkład według kategorii")
cat_counts = pd.Series(
    [cat for cats in neg_df["_categories"] for cat in cats]
).value_counts().reset_index()
cat_counts.columns = ["Kategoria", "Liczba search terms"]
st.bar_chart(cat_counts.set_index("Kategoria"))

# ── Export ────────────────────────────────────────────────────────────────────
st.subheader("Eksport")

col_a, col_b = st.columns(2)

# Export: unique negative keywords list (for Google Ads upload)
unique_negs = neg_df[st_col].dropna().unique()
neg_list_df = pd.DataFrame({"Keyword": unique_negs, "Match Type": "Negative Exact"})

with col_a:
    st.download_button(
        label="⬇️ Pobierz listę wykluczone (.xlsx) – do Google Ads",
        data=to_excel(neg_list_df),
        file_name="negative_keywords.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with col_b:
    st.download_button(
        label="⬇️ Pobierz pełny raport analizy (.xlsx)",
        data=to_excel(filtered_df.reset_index(drop=True)),
        file_name="semanalyzer_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

