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

## Deploy na Render

1. Wgraj kod na GitHub

2. Utwórz nową aplikację na [render.com](https://render.com):
   - **New → Web Service** → połącz repo z GitHub
   - Render wykryje `render.yaml` automatycznie
   - Region: Frankfurt
   - Plan: Free

3. Dodaj zmienną środowiskową:
   - Key: `ANTHROPIC_API_KEY`
   - Value: twój klucz API

4. Deploy! 🚀

## Zmienne środowiskowe

| Zmienna | Opis |
|---------|------|
| `ANTHROPIC_API_KEY` | Klucz API Anthropic (wymagany do kategoryzacji AI) |

## Struktura projektu

```
cashflow-analyzer/
├── app.py                        # Główna aplikacja Streamlit
├── requirements.txt              # Zależności Python
├── render.yaml                   # Konfiguracja deploy (Render)
├── .streamlit/
│   ├── config.toml               # Ustawienia motywu i serwera
│   └── secrets.toml.example      # Przykład pliku z kluczem API
└── README.md
```

## Monetyzacja

Sugerowany model sprzedaży:
- Jednorazowy zakup: 149 zł (Gumroad / kod źródłowy)
- SaaS subskrypcja: 29 zł/msc (deploy na własnym serwerze)

## Licencja

Komercyjna — właściciel: [Twoje imię]
