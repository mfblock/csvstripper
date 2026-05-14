# CSV Trimmer

A small Streamlit app that trims a CSV down to the last N days based on a date column.

Upload a CSV, pick the date column, set how many days to keep, download the result. That's it.

**What it handles:**
- Auto-detects delimiter (`,` `;` `\t` `|`)
- Auto-detects which columns look like dates
- Preserves original column order and text formatting
- Works with any timezone-naive or timezone-aware datetime format pandas can parse

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501).

## Run with Docker

```bash
docker build -t csvstripper .
docker run -p 8501:8501 csvstripper
```

## Stack

- [Streamlit](https://streamlit.io) — UI
- [pandas](https://pandas.pydata.org) — CSV parsing and date filtering
- Python 3.11+
