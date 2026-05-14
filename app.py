import io
import csv
from datetime import datetime, timezone
from typing import Optional, Tuple, List

import pandas as pd
import streamlit as st

APP_TITLE = "CSV Trimmer — Keep Last N Days"

def sniff_delimiter(sample_text: str) -> str:
    sample_lines = [line for line in sample_text.splitlines() if line.strip()]
    if not sample_lines:
        return ','

    # Limit to a manageable number of lines for scoring
    sample_lines = sample_lines[:50]
    candidate_delimiters = [';', ',', '\t', '|']
    best_delim = ','
    best_score = (0, 0, 0)  # (consistent_rows, modal_columns, -priority_index)

    for idx, candidate in enumerate(candidate_delimiters):
        buf = io.StringIO("\n".join(sample_lines))
        try:
            reader = csv.reader(buf, delimiter=candidate)
            column_counts = [len(row) for row in reader if row]
        except csv.Error:
            continue

        if not column_counts:
            continue

        modal_columns = max(set(column_counts), key=column_counts.count)
        if modal_columns <= 1:
            continue

        consistent_rows = sum(1 for count in column_counts if count == modal_columns)
        score = (consistent_rows, modal_columns, -idx)
        if score > best_score:
            best_score = score
            best_delim = candidate

    if best_score[0] == 0:
        try:
            dialect = csv.Sniffer().sniff(sample_text, delimiters=';,\t|')
            return dialect.delimiter
        except Exception:
            return ','

    return best_delim

def read_csv_safely(file: io.BytesIO) -> Tuple[pd.DataFrame, str]:
    """
    Return (df_as_read, delimiter_used). We read once to text for sniffing,
    then read again with pandas using that delimiter. We preserve the *original*
    string values for structure fidelity.
    """
    # Keep original bytes for second read
    raw_bytes = file.read()
    # Try UTF-8 first, then fallback
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
        encoding_used = "utf-8"
    except UnicodeDecodeError:
        # Fallback—errors ignored since we only need a sniff sample
        text = raw_bytes.decode("utf-8", errors="ignore")
        encoding_used = "utf-8"

    # Sniff delimiter from a small sample
    sample = text[:5000]
    delimiter = sniff_delimiter(sample)

    # Reconstruct a fresh buffer for pandas
    buf = io.BytesIO(raw_bytes)

    # Use dtype=str to preserve exact cell text (structure intact)
    df = pd.read_csv(buf, sep=delimiter, dtype=str, keep_default_na=False)
    return df, delimiter

def autodetect_datetime_columns(df: pd.DataFrame, sample_rows: int = 1000) -> List[str]:
    """Return a list of columns that look like datetimes for at least ~50% of sampled rows."""
    candidates = []
    sample = df.head(sample_rows)
    for col in df.columns:
        # to_datetime with errors='coerce' on the sample
        parsed = pd.to_datetime(sample[col], errors="coerce", utc=True)
        ratio = parsed.notna().mean()
        if ratio >= 0.5:
            candidates.append(col)
    return candidates

def build_date_mask_from_strings(series: pd.Series, days: int) -> pd.Series:
    """
    Parse a *string* series to datetime for comparison, but return a mask to
    filter the ORIGINAL df (so original text stays untouched).
    """
    # Use UTC to avoid timezone headaches; “last N days” relative to now UTC is usually fine.
    now = pd.Timestamp.now(tz="UTC")
    cutoff = now - pd.Timedelta(days=days)
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed >= cutoff

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Upload a CSV, choose the date column, and download a trimmed CSV with only the last N days. "
               "Column order and text formatting are preserved.")

    uploaded = st.file_uploader("CSV file", type=["csv"])
    days = st.number_input("Days to keep (N)", min_value=1, max_value=365, value=7, step=1)

    if not uploaded:
        st.info("⬆️ Drop a CSV above to begin.")
        return

    # Read CSV while preserving text (no type inference)
    try:
        df, delimiter = read_csv_safely(uploaded)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
        return

    st.write(f"Detected delimiter: `{delimiter}`")
    st.write(f"Rows: **{len(df)}** · Columns: **{len(df.columns)}**")

    # Auto-detect potential date columns
    candidates = autodetect_datetime_columns(df)
    date_col: Optional[str] = None
    if candidates:
        date_col = st.selectbox("Choose the date/time column", options=candidates, index=0)
    else:
        date_col = st.selectbox("Choose the date/time column (none detected)", options=list(df.columns))

    # Preview
    with st.expander("Preview (first 50 rows)"):
        st.dataframe(df.head(50))

    if st.button("Trim CSV"):
        if date_col is None or date_col not in df.columns:
            st.error("Please select a valid date/time column.")
            return

        mask = build_date_mask_from_strings(df[date_col], days)
        trimmed = df[mask].copy()

        st.success(f"Kept {len(trimmed)} of {len(df)} rows (last {days} days).")
        with st.expander("Preview trimmed (first 50 rows)"):
            st.dataframe(trimmed.head(50))

        # Prepare download—write back exactly as CSV with same delimiter, no extra index
        out_buf = io.StringIO()
        trimmed.to_csv(out_buf, index=False, sep=delimiter)
        out_bytes = out_buf.getvalue().encode("utf-8")
        base_name = uploaded.name.rsplit(".csv", 1)[0]
        out_name = f"{base_name}_last_{days}_days.csv"

        st.download_button(
            label="⬇️ Download trimmed CSV",
            data=out_bytes,
            file_name=out_name,
            mime="text/csv",
        )

    st.caption("Tip: If auto-detection chose the wrong column, pick another and click **Trim CSV** again.")

if __name__ == "__main__":
    main()
