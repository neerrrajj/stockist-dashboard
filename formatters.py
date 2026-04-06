"""Formatting utilities for numbers and dates."""
import pandas as pd
from datetime import datetime


def format_indian_number(num, decimal_places=0):
    """Format number in Indian style: x,xx,xx,xxx"""
    if pd.isna(num) or num is None:
        return ""
    
    try:
        num = float(num)
    except (ValueError, TypeError):
        return str(num)
    
    # Handle negative numbers
    negative = num < 0
    num = abs(num)
    
    # Format with appropriate decimal places
    if decimal_places == 0:
        num_str = f"{num:.0f}"
    else:
        num_str = f"{num:.{decimal_places}f}"
    
    # Split integer and decimal parts
    if '.' in num_str:
        int_part, dec_part = num_str.split('.')
    else:
        int_part, dec_part = num_str, None
    
    # Apply Indian comma formatting
    if len(int_part) <= 3:
        result = int_part
    else:
        # Last 3 digits
        last_three = int_part[-3:]
        # Remaining digits grouped in 2s
        remaining = int_part[:-3]
        if remaining:
            remaining = ','.join([remaining[max(0, i-2):i] for i in range(len(remaining), 0, -2)][::-1])
            result = remaining + ',' + last_three
        else:
            result = last_three
    
    # Add decimal part back
    if dec_part:
        result = result + '.' + dec_part
    
    # Add negative sign if needed
    if negative:
        result = '-' + result
    
    return result


def format_indian_currency(num, decimal_places=0, symbol="₹"):
    """Format number as Indian currency: ₹x,xx,xx,xxx"""
    return f"{symbol}{format_indian_number(num, decimal_places)}"


def format_date_long(date_val):
    """Format date as 'August 5, 2026'"""
    if pd.isna(date_val) or date_val is None:
        return ""
    if isinstance(date_val, str):
        date_val = pd.to_datetime(date_val)
    if isinstance(date_val, pd.Timestamp):
        return date_val.strftime("%B %d, %Y")
    return str(date_val)


def format_date_no_year(date_val):
    """Format date as 'August 5'"""
    if pd.isna(date_val) or date_val is None:
        return ""
    if isinstance(date_val, str):
        date_val = pd.to_datetime(date_val)
    if isinstance(date_val, pd.Timestamp):
        return date_val.strftime("%B %d")
    return str(date_val)


def format_date_short(date_val):
    """Format date as 'Aug 5'"""
    if pd.isna(date_val) or date_val is None:
        return ""
    if isinstance(date_val, str):
        date_val = pd.to_datetime(date_val)
    if isinstance(date_val, pd.Timestamp):
        return date_val.strftime("%b %d")
    return str(date_val)


def format_percentage(num, decimal_places=1):
    """Format percentage with % symbol"""
    if pd.isna(num) or num is None:
        return ""
    try:
        return f"{float(num):.{decimal_places}f}%"
    except:
        return str(num)
