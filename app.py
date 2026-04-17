import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from anthropic import Anthropic
import io
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

# ── API Key resolution (env var or Streamlit secrets) ─────────────────────────
def get_api_key() -> str | None:
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except FileNotFoundError:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CashFlow Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    .stApp { background-color: #020817; color: #f1f5f9; }
    
    .metric-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 8px;
    }
    .metric-label { font-size: 11px; color: #475569; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
    .metric-value { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
    .metric-green { color: #22c55e; }
    .metric-orange { color: #f97316; }
    .metric-blue { color: #3b82f6; }
    .metric-red { color: #f43f5e; }
    
    .section-title { font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
    
    .bank-badge {
        display: inline-block;
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        color: #94a3b8;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #6366f1);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
    }
    .stButton > button:hover { opacity: 0.9; }
    
    div[data-testid="stFileUploader"] {
        background: #0f172a;
        border: 2px dashed #1e293b;
        border-radius: 12px;
        padding: 16px;
    }
    
    .stDataFrame { background: #0f172a; }
    
    footer { display: none; }
    #MainMenu { display: none; }
    header { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Bank parsers ──────────────────────────────────────────────────────────────
BANK_CONFIGS = {
    "mBank": {
        "detect": lambda h: any("data operacji" in x.lower() for x in h),
        "date": lambda h: next((x for x in h if "data operacji" in x.lower()), None),
        "desc": lambda h: next((x for x in h if "opis operacji" in x.lower() or "tytuł" in x.lower()), None),
        "amount": lambda h: next((x for x in h if "kwota" in x.lower()), None),
        "sep": ";",
        "skip_rows": 25,
    },
    "PKO BP": {
        "detect": lambda h: any("data transakcji" in x.lower() for x in h),
        "date": lambda h: next((x for x in h if "data transakcji" in x.lower()), None),
        "desc": lambda h: next((x for x in h if "opis transakcji" in x.lower() or "tytuł" in x.lower()), None),
        "amount": lambda h: next((x for x in h if "kwota" in x.lower()), None),
        "sep": ",",
        "skip_rows": 0,
    },
    "Santander": {
        "detect": lambda h: any("data księgowania" in x.lower() for x in h),
        "date": lambda h: next((x for x in h if "data księgowania" in x.lower()), None),
        "desc": lambda h: next((x for x in h if "tytuł" in x.lower() or "opis" in x.lower()), None),
        "amount": lambda h: next((x for x in h if "kwota" in x.lower()), None),
        "sep": ";",
        "skip_rows": 0,
    },
}

def detect_bank_and_parse(content: str) -> tuple[pd.DataFrame, str]:
    """Auto-detect bank format and parse CSV."""
    lines = content.split("\n")
    
    # Try different separators and header positions
    for sep in [";", ","]:
        for skip in range(0, min(30, len(lines))):
            try:
                df = pd.read_csv(
                    io.StringIO("\n".join(lines[skip:])),
                    sep=sep,
                    encoding="utf-8",
                    on_bad_lines="skip",
                    nrows=5,
                )
                if len(df.columns) >= 3:
                    headers = [str(c) for c in df.columns]
                    
                    # Detect bank
                    bank_name = "Inny bank"
                    for name, cfg in BANK_CONFIGS.items():
                        if cfg["detect"](headers):
                            bank_name = name
                            break
                    
                    # Get config
                    cfg = BANK_CONFIGS.get(bank_name, {
                        "date": lambda h: next((x for x in h if "dat" in x.lower()), None),
                        "desc": lambda h: next((x for x in h if "opis" in x.lower() or "tytuł" in x.lower() or "nadawca" in x.lower()), None),
                        "amount": lambda h: next((x for x in h if "kwota" in x.lower()), None),
                    })
                    
                    date_col = cfg["date"](headers)
                    desc_col = cfg["desc"](headers)
                    amount_col = cfg["amount"](headers)
                    
                    if not (date_col and amount_col):
                        continue
                    
                    # Read full file
                    full_df = pd.read_csv(
                        io.StringIO("\n".join(lines[skip:])),
                        sep=sep,
                        encoding="utf-8",
                        on_bad_lines="skip",
                    )
                    
                    result = pd.DataFrame()
                    result["date"] = pd.to_datetime(full_df[date_col], dayfirst=True, errors="coerce")
                    result["desc"] = full_df[desc_col].fillna("—") if desc_col else "—"
                    
                    # Parse amount
                    amt = full_df[amount_col].astype(str).str.replace(r"\s", "", regex=True)
                    amt = amt.str.replace("PLN", "", regex=False).str.replace(",", ".", regex=False)
                    result["amount"] = pd.to_numeric(amt, errors="coerce")
                    result = result.dropna(subset=["amount", "date"])
                    result["category"] = ""
                    
                    if len(result) > 0:
                        return result, bank_name
                        
            except Exception:
                continue
    
    raise ValueError("Nie udało się rozpoznać formatu pliku CSV. Sprawdź czy to wyciąg bankowy.")


def categorize_with_ai(transactions: pd.DataFrame) -> list[str]:
    """Use Claude to categorize transactions."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Brak klucza ANTHROPIC_API_KEY. Ustaw zmienną środowiskową lub dodaj do Streamlit secrets.")
    client = Anthropic(api_key=api_key)

    CATEGORIES = [
        "Wynagrodzenia", "ZUS/Podatki", "Faktury/Kontrahenci",
        "Czynsz/Najem", "Paliwo/Transport", "Jedzenie/Restauracje",
        "Media/Telefon/Internet", "Usługi IT/Oprogramowanie",
        "Sprzęt/Wyposażenie", "Ubezpieczenia", "Inne przychody", "Inne wydatki"
    ]

    MAX_TX = 150
    sample = transactions.head(MAX_TX)
    if len(transactions) > MAX_TX:
        st.warning(f"AI skategoryzuje pierwsze {MAX_TX} z {len(transactions)} transakcji. Pozostałe dostaną kategorię 'Inne wydatki'.")
    tx_list = "\n".join([
        f"{i}: {row['desc']} | {row['amount']:.2f} PLN"
        for i, (_, row) in enumerate(sample.iterrows())
    ])
    
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Skategoryzuj transakcje bankowe polskiej firmy/osoby.
            
Dostępne kategorie: {', '.join(CATEGORIES)}

Zasady:
- Dodatnie kwoty to zazwyczaj przychody (Wynagrodzenia, Inne przychody, Faktury/Kontrahenci)
- Ujemne to wydatki
- Użyj kontekstu opisu transakcji

Odpowiedz TYLKO w JSON: {{"categories": ["kat0","kat1",...]}}
Liczba kategorii: {len(sample)} (dokładnie tyle samo co transakcji)

Transakcje:
{tx_list}"""
        }]
    )
    
    text = response.content[0].text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    cats = data.get("categories", [])
    
    # Fill remaining with default
    full_cats = list(cats) + ["Inne wydatki"] * (len(transactions) - len(cats))
    return full_cats[:len(transactions)]


def format_pln(value: float) -> str:
    return f"{value:,.2f} zł".replace(",", " ").replace(".", ",")


def generate_pdf_report(df: pd.DataFrame, bank_name: str, stats: dict) -> bytes:
    """Generate PDF report using reportlab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#1e40af"), spaceAfter=6)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#64748b"), spaceAfter=20)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#1e293b"), spaceBefore=16, spaceAfter=8)
    
    story = []
    
    # Header
    story.append(Paragraph("Raport CashFlow", title_style))
    story.append(Paragraph(f"Bank: {bank_name} | Wygenerowano: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Transakcji: {len(df)}", subtitle_style))
    
    # Summary table
    story.append(Paragraph("Podsumowanie", heading_style))
    summary_data = [
        ["Wskaźnik", "Wartość"],
        ["Przychody", format_pln(stats["income"])],
        ["Wydatki", format_pln(stats["expenses"])],
        ["Saldo", format_pln(stats["balance"])],
        ["Liczba transakcji", str(stats["count"])],
    ]
    summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))
    
    # Categories table
    story.append(Paragraph("Wydatki wg kategorii", heading_style))
    cat_summary = df[df["amount"] < 0].groupby("category")["amount"].sum().abs().sort_values(ascending=False)
    cat_data = [["Kategoria", "Kwota", "% całości"]]
    total_exp = cat_summary.sum()
    for cat, val in cat_summary.items():
        pct = (val / total_exp * 100) if total_exp > 0 else 0
        cat_data.append([cat, format_pln(val), f"{pct:.1f}%"])
    
    cat_table = Table(cat_data, colWidths=[9*cm, 5*cm, 3*cm])
    cat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 16))
    
    # Last 20 transactions
    story.append(Paragraph("Ostatnie transakcje (20)", heading_style))
    tx_data = [["Data", "Opis", "Kategoria", "Kwota"]]
    for _, row in df.head(20).iterrows():
        tx_data.append([
            row["date"].strftime("%d.%m.%Y") if pd.notna(row["date"]) else "—",
            str(row["desc"])[:40],
            str(row.get("category", "—"))[:25],
            format_pln(row["amount"]),
        ])
    
    tx_table = Table(tx_data, colWidths=[2.5*cm, 7*cm, 4*cm, 3.5*cm])
    tx_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
    ]))
    story.append(tx_table)
    
    doc.build(story)
    return buffer.getvalue()


# ── Session state ─────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = None
if "bank_name" not in st.session_state:
    st.session_state.bank_name = ""
if "categorized" not in st.session_state:
    st.session_state.categorized = False

# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_title, col_spacer = st.columns([0.06, 0.7, 0.24])
with col_logo:
    st.markdown("## 📊")
with col_title:
    st.markdown("### CashFlow Analyzer")
    st.markdown('<span style="color:#475569;font-size:13px">Analiza wyciągów bankowych · AI powered by Claude</span>', unsafe_allow_html=True)

st.divider()

# ── API key check ─────────────────────────────────────────────────────────────
if not get_api_key():
    st.warning(
        "**Brak klucza API Anthropic.**\n\n"
        "Możesz wczytać i przeglądać wyciąg, ale kategoryzacja AI będzie niedostępna.\n\n"
        "Ustaw zmienną `ANTHROPIC_API_KEY` lub dodaj ją do `.streamlit/secrets.toml`:\n"
        "```toml\nANTHROPIC_API_KEY = \"sk-ant-...\"\n```",
        icon="⚠️",
    )

# ── Upload ────────────────────────────────────────────────────────────────────
if st.session_state.df is None:
    st.markdown('<div class="section-title">Wgraj wyciąg bankowy (CSV)</div>', unsafe_allow_html=True)
    
    uploaded = st.file_uploader(
        "Przeciągnij plik lub kliknij aby wybrać",
        type=["csv"],
        label_visibility="collapsed",
    )
    
    st.markdown("""
    <div style="color:#475569;font-size:12px;margin-top:8px">
        ✅ Obsługiwane banki: <b style="color:#94a3b8">mBank · PKO BP · Santander · i inne</b><br>
        🤖 Opisy transakcji są wysyłane do Claude AI (Anthropic) wyłącznie w celu kategoryzacji
    </div>
    """, unsafe_allow_html=True)
    
    if uploaded:
        with st.spinner("Wczytuję i parsuję plik..."):
            try:
                content = uploaded.read().decode("utf-8", errors="replace")
                df, bank_name = detect_bank_and_parse(content)
                st.session_state.df = df
                st.session_state.bank_name = bank_name
                st.rerun()
            except Exception as e:
                st.error(f"❌ {str(e)}")

# ── Main dashboard ────────────────────────────────────────────────────────────
else:
    df = st.session_state.df
    bank_name = st.session_state.bank_name

    # AI categorize button
    if not st.session_state.categorized:
        col_info, col_btn = st.columns([0.7, 0.3])
        with col_info:
            st.markdown(f'<span class="bank-badge">🏦 {bank_name}</span> &nbsp; <span style="color:#475569;font-size:13px">{len(df)} transakcji wczytanych</span>', unsafe_allow_html=True)
        with col_btn:
            if st.button("🤖 Kategoryzuj przez AI", use_container_width=True):
                with st.spinner("Claude analizuje transakcje..."):
                    try:
                        cats = categorize_with_ai(df)
                        st.session_state.df["category"] = cats
                        st.session_state.categorized = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd AI: {e}")
    else:
        col_info, col_new = st.columns([0.7, 0.3])
        with col_info:
            st.markdown(f'<span class="bank-badge">🏦 {bank_name}</span> &nbsp; <span style="color:#475569;font-size:13px">{len(df)} transakcji · AI ✅</span>', unsafe_allow_html=True)
        with col_new:
            if st.button("↩ Nowy plik", use_container_width=True):
                st.session_state.df = None
                st.session_state.categorized = False
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Stats ────────────────────────────────────────────────────────────────
    income = df[df["amount"] > 0]["amount"].sum()
    expenses = df[df["amount"] < 0]["amount"].sum()
    balance = income + expenses

    c1, c2, c3 = st.columns(3)
    with c1:
        color = "metric-green"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">↑ Przychody</div>
            <div class="metric-value {color}">{format_pln(income)}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">↓ Wydatki</div>
            <div class="metric-value metric-orange">{format_pln(abs(expenses))}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        bal_color = "metric-blue" if balance >= 0 else "metric-red"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">= Saldo</div>
            <div class="metric-value {bal_color}">{format_pln(balance)}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ───────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Cashflow", "🥧 Kategorie", "📋 Transakcje", "📄 Raport PDF"])

    with tab1:
        df["month"] = df["date"].dt.to_period("M").astype(str)
        monthly = df.groupby("month").agg(
            przychody=("amount", lambda x: x[x > 0].sum()),
            wydatki=("amount", lambda x: x[x < 0].sum().abs()),
        ).reset_index().tail(12)

        fig = go.Figure()
        fig.add_bar(x=monthly["month"], y=monthly["przychody"], name="Przychody", marker_color="#22c55e")
        fig.add_bar(x=monthly["month"], y=monthly["wydatki"], name="Wydatki", marker_color="#f97316")
        fig.update_layout(
            barmode="group",
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#94a3b8",
            legend=dict(bgcolor="#0f172a"),
            xaxis=dict(gridcolor="#1e293b"),
            yaxis=dict(gridcolor="#1e293b"),
            height=360,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if st.session_state.categorized:
            cat_data = df[df["amount"] < 0].groupby("category")["amount"].sum().abs().sort_values(ascending=False).reset_index()
            cat_data.columns = ["Kategoria", "Kwota"]

            col_pie, col_bar = st.columns([0.45, 0.55])
            with col_pie:
                fig_pie = px.pie(cat_data, values="Kwota", names="Kategoria", hole=0.4,
                                  color_discrete_sequence=px.colors.qualitative.Set3)
                fig_pie.update_layout(
                    paper_bgcolor="#0f172a", font_color="#94a3b8",
                    showlegend=False, height=320,
                    margin=dict(l=0, r=0, t=20, b=0),
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_bar:
                fig_bar = px.bar(cat_data.head(8), x="Kwota", y="Kategoria", orientation="h",
                                  color="Kwota", color_continuous_scale="Blues")
                fig_bar.update_layout(
                    plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
                    font_color="#94a3b8", height=320,
                    margin=dict(l=0, r=0, t=20, b=0),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("💡 Kliknij **Kategoryzuj przez AI** aby zobaczyć podział wg kategorii.")

    with tab3:
        show_df = df[["date", "desc", "amount", "category"]].copy()
        show_df["date"] = show_df["date"].dt.strftime("%d.%m.%Y")
        show_df.columns = ["Data", "Opis", "Kwota (PLN)", "Kategoria"]
        show_df = show_df.sort_values("Data", ascending=False)

        st.dataframe(
            show_df,
            use_container_width=True,
            height=420,
            hide_index=True,
        )

    with tab4:
        st.markdown('<div class="section-title">Eksport raportu PDF</div>', unsafe_allow_html=True)
        st.markdown('<p style="color:#475569;font-size:13px">Raport zawiera podsumowanie, zestawienie kategorii i listę transakcji.</p>', unsafe_allow_html=True)

        if st.button("📄 Generuj PDF", use_container_width=False):
            with st.spinner("Generuję raport..."):
                stats = {
                    "income": income,
                    "expenses": abs(expenses),
                    "balance": balance,
                    "count": len(df),
                }
                pdf_bytes = generate_pdf_report(df, bank_name, stats)
                fname = f"cashflow_raport_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                st.download_button(
                    label="⬇️ Pobierz raport PDF",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    use_container_width=True,
                )
