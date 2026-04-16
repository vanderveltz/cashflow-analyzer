# 📊 CashFlow Analyzer

Narzędzie Streamlit do analizy wyciągów bankowych z kategoryzacją AI (Claude).

## Funkcje

- 🏦 Auto-detekcja formatu banku (mBank, PKO BP, Santander, inne)
- 🤖 Kategoryzacja transakcji przez Claude AI
- 📈 Wizualizacja cashflow miesięcznego (Plotly)
- 🥧 Rozkład wydatków wg kategorii
- 📄 Export raportu PDF (ReportLab)

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

## Deploy na DigitalOcean App Platform

1. Wgraj kod na GitHub (repo: cashflow-analyzer)

2. Utwórz nową aplikację w DigitalOcean App Platform:
   - Region: Frankfurt (fra)
   - Source: GitHub repo
   - Build command: `pip install -r requirements.txt`
   - Run command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

3. Dodaj zmienną środowiskową:
   - Key: `ANTHROPIC_API_KEY`
   - Value: twój klucz API

4. Deploy! 🚀

## Zmienne środowiskowe

| Zmienna | Opis |
|---------|------|
| `ANTHROPIC_API_KEY` | Klucz API Anthropic (wymagany) |

## Struktura projektu

```
cashflow_analyzer/
├── app.py              # Główna aplikacja Streamlit
├── requirements.txt    # Zależności Python
└── README.md          # Dokumentacja
```

## Monetyzacja

Sugerowany model sprzedaży:
- Jednorazowy zakup: 149 zł (Gumroad / kod źródłowy)
- SaaS subskrypcja: 29 zł/msc (deploy na własnym serwerze)

## Licencja

Komercyjna — właściciel: [Twoje imię]
