"""
data_loader.py
Loads and normalises all sheets from Google Sheets (or a local xlsx fallback).
All DataFrames returned are clean, forward-filled, and ready for analysis.
"""

import os
import pandas as pd
import streamlit as st

# ── Google Sheets helpers ──────────────────────────────────────────────────────

def _get_gc():
    """Return an authenticated gspread client using st.secrets."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=300, show_spinner=False)
def load_from_sheets(spreadsheet_id: str) -> dict[str, pd.DataFrame]:
    """Fetch every sheet and return a dict of DataFrames."""
    gc = _get_gc()
    sh = gc.open_by_key(spreadsheet_id)
    sheets = {}
    for ws in sh.worksheets():
        data = ws.get_all_values()
        if not data or len(data) < 2:
            continue
        df = pd.DataFrame(data[1:], columns=data[0])
        # Replace empty strings with NaN
        df.replace("", pd.NA, inplace=True)
        sheets[ws.title.strip()] = df
    return sheets


# ── Local xlsx fallback (dev / demo) ─────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_from_xlsx(path: str) -> dict[str, pd.DataFrame]:
    xl = pd.ExcelFile(path)
    return {s: xl.parse(s) for s in xl.sheet_names}


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def _normalise_product(s: pd.Series) -> pd.Series:
    return s.str.strip().str.lower().str.title()


# ── Public loader ─────────────────────────────────────────────────────────────

def load_data() -> dict[str, pd.DataFrame]:
    """
    Entry point.  Returns a dict with cleaned DataFrames:
      sales, purchase, payments, outstanding, inventory, batch, pricelist
    """
    use_sheets = (
        "gcp_service_account" in st.secrets
        and "spreadsheet_id" in st.secrets
    )

    if use_sheets:
        raw = load_from_sheets(st.secrets["spreadsheet_id"])
    else:
        xlsx_path = os.environ.get("XLSX_PATH", "data.xlsx")
        raw = load_from_xlsx(xlsx_path)

    return {
        "sales":       _clean_sales(raw.get("Sales", raw.get("Sales ", pd.DataFrame()))),
        "purchase":    _clean_purchase(raw.get("Purchase", pd.DataFrame())),
        "payments":    _clean_payments(raw.get("Payments", pd.DataFrame())),
        "outstanding": _clean_outstanding(raw.get("Outstanding", pd.DataFrame())),
        "inventory":   _clean_inventory(raw.get("Inventory Control", pd.DataFrame())),
        "batch":       _clean_batch(raw.get("Batch", pd.DataFrame())),
        "pricelist":   _clean_pricelist(raw.get("Price list", pd.DataFrame())),
    }


# ── Sheet-specific cleaners ───────────────────────────────────────────────────

def _clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]
    # Rename 'Product ' → 'Product'
    df.rename(columns={"Product ": "Product"}, inplace=True)

    # Forward-fill grouped columns
    for col in ["Date", "Invoice no", "Customer name", "Payment status", "Inv date"]:
        if col in df.columns:
            df[col] = df[col].ffill()

    df["Date"]     = _to_date(df["Date"])
    df["Inv date"] = _to_date(df.get("Inv date", df["Date"]))

    for col in ["Nos", "Rate", "Gst 18%", "Unit price",
                "Exl Gst", "Incl Gst", "Profit", "Margin%", "Payments"]:
        if col in df.columns:
            df[col] = _to_num(df[col])

    # Drop rows with no product
    df = df[df["Product"].notna() & (df["Product"] != "")].copy()

    # Normalise product name casing
    df["Product"] = _normalise_product(df["Product"])

    # Exclude future / data-entry-error rows (beyond today)
    today = pd.Timestamp.today().normalize()
    df = df[df["Date"] <= today].copy()

    # Derive month label
    df["Month"] = df["Date"].dt.to_period("M").astype(str)

    return df.reset_index(drop=True)


def _clean_purchase(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]
    df["Date"] = _to_date(df["Date"].ffill())
    df["Inv no"] = df["Inv no"].ffill()

    for col in ["Nos", "Rate", "Gst 18%", "Dis allowed %",
                "Discounted rate", "Total value"]:
        if col in df.columns:
            df[col] = _to_num(df[col])

    df = df[df["Products"].notna()].copy()
    df["Products"] = _normalise_product(df["Products"])
    return df.reset_index(drop=True)


def _clean_payments(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]
    df = df[["Date", "Invoice no", "Cust name", "Credit"]].copy()
    df["Date"]   = _to_date(df["Date"])
    df["Credit"] = _to_num(df["Credit"])
    df = df[df["Credit"].notna() & (df["Credit"] > 0)].copy()
    return df.reset_index(drop=True)


def _clean_outstanding(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]

    # Forward fill customer name
    df["Cust"] = df["Cust"].ffill()

    # Drop subtotal/grand-total rows and blank rows
    mask_total = df["Cust"].str.contains("Total|Grand", case=False, na=False)
    df = df[~mask_total].copy()
    df = df[df["Inv no"].notna()].copy()

    df["Inv date"]          = _to_date(df["Inv date"])
    df["Sum of Incl Gst"]   = _to_num(df["Sum of Incl Gst"])
    df["Sum of Payments"]   = _to_num(df["Sum of Payments"])
    df["Sum of balance"]    = _to_num(df["Sum of balance"])

    # Days outstanding from invoice date
    today = pd.Timestamp.today().normalize()
    df["Days outstanding"] = (today - df["Inv date"]).dt.days

    return df.reset_index(drop=True)


def _clean_inventory(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]
    df = df[df["Products"].notna()].copy()
    df["Products"] = _normalise_product(df["Products"])
    for col in ["Opening Stock", "Sales", "Closing Stock", "Inventory value"]:
        if col in df.columns:
            df[col] = _to_num(df[col])
    return df.reset_index(drop=True)


def _clean_batch(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]
    df = df[df["Products"].notna()].copy()
    df["Products"]        = _normalise_product(df["Products"])
    df["Discounted rate"] = _to_num(df["Discounted rate"])
    df["Inventory days"]  = _to_num(df["Inventory days"])
    return df.reset_index(drop=True)


def _clean_pricelist(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]
    df = df[["Product", "Weighted avg price"]].dropna(subset=["Product"]).copy()
    df["Product"]            = _normalise_product(df["Product"])
    df["Weighted avg price"] = _to_num(df["Weighted avg price"])
    return df.reset_index(drop=True)
