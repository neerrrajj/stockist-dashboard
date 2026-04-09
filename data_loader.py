"""
data_loader.py
Loads and normalises all sheets from Google Sheets (or a local xlsx fallback).
All DataFrames returned are clean, forward-filled, and ready for analysis.
"""

import os
import pandas as pd
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────

# Customers to exclude from Outstanding list (e.g., gifts to friends/family)
# These entries are still in Google Sheets for accounting but hidden from dashboard
EXCLUDED_CUSTOMERS = [
    "pavithra",
    "priya",
    # Add more names here as needed
]

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

import re

def _clean_number(val):
    """Clean a single number value by removing currency symbols, commas, and % signs."""
    if pd.isna(val):
        return val
    s = str(val)
    # Remove currency symbols, commas, % signs, and whitespace using regex
    s = re.sub(r'[₹$,%\s]', '', s)
    # Replace unicode minus with regular minus
    s = s.replace('−', '-')
    # Check for invalid values
    if s in ['', 'nan', 'NaN', 'None', '#DIV/0!', '#VALUE!', '#REF!', '#N/A', 'inf', '-inf']:
        return pd.NA
    try:
        return float(s)
    except:
        return pd.NA

def _to_num(series: pd.Series) -> pd.Series:
    """Convert to numeric, handling currency symbols, commas, and other formatting."""
    return series.apply(_clean_number)


def _to_date(series: pd.Series) -> pd.Series:
    """Parse dates, handling multiple formats including '16-Dec' style dates."""
    from datetime import datetime
    
    current_year = datetime.now().year
    
    def parse_date(val):
        if pd.isna(val):
            return pd.NaT
        s = str(val).strip()
        if s in ['', 'nan', 'NaN', 'None']:
            return pd.NaT
        
        # Try to parse various formats - Data is in MM/DD/YYYY format
        formats_to_try = [
            ("%d-%b-%Y", None),     # 16-Dec-2025
            ("%d-%b", "infer"),     # 16-Dec (infer year from month)
            ("%m/%d/%Y", None),     # 4/1/2026 -> April 1, 2026 (MONTH FIRST - US format)
            ("%m/%d/%y", None),     # 4/1/26 -> April 1, 2026
            ("%d/%m/%Y", None),     # 1/4/2026 -> Jan 4, 2026 (fallback - IN format)
            ("%d/%m/%y", None),     # 1/4/26 -> Jan 4, 2026 (fallback)
            ("%Y-%m-%d", None),     # 2025-12-16
        ]
        
        for fmt, year_handling in formats_to_try:
            try:
                parsed = datetime.strptime(s, fmt)
                
                # Infer year for dates without year specified
                if year_handling == "infer":
                    # December dates are likely from previous year
                    # Jan-Mar dates are likely from current year
                    if parsed.month == 12:
                        parsed = parsed.replace(year=current_year - 1)
                    else:
                        parsed = parsed.replace(year=current_year)
                
                return parsed
            except ValueError:
                continue
        
        # Fallback to pandas parser with dayfirst=False (US format)
        try:
            return pd.to_datetime(s, dayfirst=False)
        except:
            return pd.NaT
    
    return series.apply(parse_date)


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
        "inventory":   _clean_inventory(raw.get("Inventory", pd.DataFrame())),
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
    
    # Handle different column name variations (SUM vs Sum)
    col_mapping = {}
    for col in df.columns:
        if col.lower() == "cust":
            col_mapping["Cust"] = col
        elif col.lower() == "inv no":
            col_mapping["Inv no"] = col
        elif col.lower() in ["sum of incl gst", "sum of incl Gst".lower()]:
            col_mapping["Sum of Incl Gst"] = col
        elif col.lower() == "sum of payments":
            col_mapping["Sum of Payments"] = col
        elif col.lower() in ["sum of balance", "total outstanding"]:
            col_mapping["Sum of balance"] = col
        elif col.lower() == "inv date":
            col_mapping["Inv date"] = col
        elif col.lower() == "debtor days":
            col_mapping["Debtor days"] = col
    
    # Forward fill customer name
    cust_col = col_mapping.get("Cust", "Cust")
    df[cust_col] = df[cust_col].ffill()

    # Drop subtotal/grand-total rows and blank rows
    mask_total = df[cust_col].str.contains("Total|Grand", case=False, na=False)
    df = df[~mask_total].copy()
    
    # Exclude customers in the exclusion list (case-insensitive)
    if EXCLUDED_CUSTOMERS:
        mask_excluded = df[cust_col].str.lower().isin([c.lower() for c in EXCLUDED_CUSTOMERS])
        df = df[~mask_excluded].copy()
    
    inv_no_col = col_mapping.get("Inv no", "Inv no")
    df = df[df[inv_no_col].notna()].copy()

    # Parse numeric columns
    sum_gst_col = col_mapping.get("Sum of Incl Gst", "Sum of Incl Gst")
    sum_pay_col = col_mapping.get("Sum of Payments", "Sum of Payments")
    sum_bal_col = col_mapping.get("Sum of balance", "Sum of balance")
    
    df[sum_gst_col] = _to_num(df[sum_gst_col])
    df[sum_pay_col] = _to_num(df[sum_pay_col])
    df[sum_bal_col] = _to_num(df[sum_bal_col])
    
    # Rename columns to standard names
    df = df.rename(columns={
        cust_col: "Cust",
        inv_no_col: "Inv no",
        sum_gst_col: "Sum of Incl Gst",
        sum_pay_col: "Sum of Payments",
        sum_bal_col: "Sum of balance",
    })
    
    # Handle days outstanding - use Debtor days if available, otherwise calculate
    if "Debtor days" in col_mapping:
        df["Days outstanding"] = _to_num(df[col_mapping["Debtor days"]])
    elif "Inv date" in col_mapping:
        df["Inv date"] = _to_date(df[col_mapping["Inv date"]])
        today = pd.Timestamp.today().normalize()
        df["Days outstanding"] = (today - df["Inv date"]).dt.days
    else:
        # If no date info, set to 0 or NaN
        df["Days outstanding"] = 0

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
