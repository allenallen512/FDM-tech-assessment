
from supabase_client import supabase_client
from typing import Optional
import pandas as pd
from datetime import datetime
import re

def upsert_product_group(pg_name: str) -> int:
    """
    inserts a prod group if it doesn't exist returns the id 
    """
    # get first
    result = supabase_client.table("product_groups").select("id").eq("name", pg_name).limit(1).execute()
    if result.data and len(result.data) == 1:
        return result.data[0]["id"]
    # intsert if nothing returned
    ins = supabase_client.table("product_groups").insert({"name": pg_name}).execute()
    return ins.data[0]["id"]


def upsert_steel_grade(grade_name: str, pg_id: Optional[int] = None) -> int:
    """
    Inserts a steel grade if it doesn’t exist; returns its id.
    If product_group_id is None, we set it to NULL.
    """
    
    result = supabase_client.table("steel_grades").select("id").eq("name", grade_name).limit(1).execute()
    print("the result from steel_grades is", result)
    if result.data and len(result.data) == 1:
        existing = result.data[0]
        if pg_id is not None:
            supabase_client.table("steel_grades").update({"product_group_id": pg_id}).eq("id", existing["id"]).execute()
        return existing["id"]

    # Insert new
    payload = {"name": grade_name, "product_group_id": pg_id}
    insert_response = supabase_client.table("steel_grades").insert(payload).execute()
    print("the return from insert is", insert_response)
    return insert_response.data[0]["id"]


def detect_month_columns(df):
    """finds columns that represent months."""
    month_cols = []
    for col in df.columns:
        if col in ['Quality group', 'Grade'] or str(col).startswith('Unnamed'): #skipping the empty columns also
            continue
            
        # Handle datetime objects
        if isinstance(col, pd.Timestamp) or isinstance(col, datetime):
            month_cols.append(col)
        # Handle string columns with pattern 'Mon YY'
        else:
            col_str = str(col).strip()
            month_col_pattern = re.compile(r"^[A-Za-z]{3}\s+\d{2}$")
            if month_col_pattern.match(col_str):
                month_cols.append(col)
    
    return month_cols

def process_production_data(df, month_cols):
    """intakes dataframe and returns list of dicts"""
    records = []
    for idx, row in df.iterrows():
        product_group = row['Quality group']
        grade = row['Grade']
        
        for col in month_cols:
            # Get tonnage value (skip zero/missing values)
            tons = float(row[col])
            if tons > 0:
                records.append({
                    'Date': col if isinstance(col, pd.Timestamp) else None,
                    'MonthCol': str(col),
                    'ProductGroup': product_group,
                    'SteelGrade': grade,
                    'Tons': tons
                })
                
    return records

def save_to_steel_grade_production(records):
    #save to steel_grade_production table. 
    #reading in something thats in a df format
    for record in records:
        # insert prod group if it doesn't exist
        pg_id = upsert_product_group(record['ProductGroup'])
        # insert steel grade if it doesn't exist, and product group
        grade_id = upsert_steel_grade(record['SteelGrade'], pg_id)
        
        supabase_client.table("steel_grade_production")\
            .upsert({
                "year_month": record['MonthCol'],  # Keep original column name
                "steel_grade_id": grade_id,
                "tons": record['Tons']
            },
            on_conflict="year_month,steel_grade_id")\
            .execute()
            
            
def process_product_group_data(df, month_cols):
    """Process product group monthly data into records for database insertion."""
    records = []
    for idx, row in df.iterrows():
        product_group = row['Quality:']
        if pd.isna(product_group):
            # skip empty rows
            continue
            
        for col in month_cols:
            heats = float(row[col]) if not pd.isna(row[col]) else 0.0
            if heats > 0:
                records.append({
                    'ProductGroup': product_group,
                    'MonthCol': str(col),
                    'Tons': heats * 100.0,  # Assuming 100 tons per heat
                    'Heats': heats
                })
    
    return records


def save_product_group_monthly(records, heat_tonnage=100.0):
    """Save product group monthly records to database."""
    for record in records:
        # Get product group ID
        pg_id = upsert_product_group(record['ProductGroup'])
        
        # Calculate tons from heats
        heats = float(record['Heats'])
        tons = heats * heat_tonnage
        year_month = str(record['MonthCol']).strip()
        
    
        # Upsert into product_group_monthly
        supabase_client.table("product_group_monthly")\
            .upsert({
                "year_month": year_month,
                "product_group_id": pg_id,
                "tons": tons,
                "heats": heats
            },
            on_conflict="year_month,product_group_id")\
            .execute()