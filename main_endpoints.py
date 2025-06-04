from flask import Flask, request, jsonify
import os
from helper_functions import upsert_steel_grade, upsert_product_group
import pandas as pd
from supabase_client import supabase_client
from datetime import datetime
# set up flask app 

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 1 heat = 100 tons
HEAT_TONNAGE = 100.0


#  ---- endpoint: upload steel_grade_production
@app.route("/upload/steel_grades", methods=["POST"])
def upload_steel_grades():
    """
    Expects multipart/form-data with 'file'.
    Excel format with columns: ['Quality group', 'Grade', 'Jun 24', 'Jul 24', ...]
    The first row is a title and should be skipped.
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400

    # Save original Excel file
    excel_path = os.path.join(UPLOAD_FOLDER, "steel_grade_production.xlsx")
    f.save(excel_path)

    # Skip the first row (title), use the second row as header
    df = pd.read_excel(excel_path, header=1)
    print("Columns found:", df.columns.tolist())

    # Forward-fill product group names
    df['Quality group'].ffill(inplace=True)

    # Check required columns
    if 'Quality group' not in df.columns or 'Grade' not in df.columns:
        return jsonify({
            "error": "Required columns not found",
            "columns_found": df.columns.tolist()
        }), 400

    # Only process columns that look like 'Mon YY'
    import re
    
    # Debug: Print all column types
    print("Column types:")
    for col in df.columns:
        print(f"{col}: {type(col)}")
    
    # Modified approach for handling column names
    month_cols = []
    for col in df.columns:
        if col in ['Quality group', 'Grade']:
            continue
            
        col_str = str(col)
        print(f"Processing column: {col_str}")
        
        # First try to extract month/year from datetime objects
        if isinstance(col, pd.Timestamp) or isinstance(col, datetime):
            # For datetime objects like '2024-06-01', extract month name and year
            month_num = col.month
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_name = month_names[month_num - 1]
            year_short = str(col.year)[2:]  # Get last 2 digits of year
            print(f"  - Extracted from datetime: {month_name} {year_short}")
            month_cols.append(col)
        # Or try regex pattern for 'Mon YY' format
        else:
            month_col_pattern = re.compile(r"^[A-Za-z]{3}\s+\d{2}$")
            if month_col_pattern.match(col_str.strip()):
                print(f"  - Matched pattern: {col_str}")
                month_cols.append(col)
    
    print(f"Found {len(month_cols)} month columns: {month_cols}")
    
    if not month_cols:
        return jsonify({
            "error": "No month columns found in the format 'Mon YY'",
            "columns_found": df.columns.tolist()
        }), 400

    records = []
    for idx, row in df.iterrows():
        product_group = row['Quality group']
        grade = row['Grade']
        
        print(f"Processing row {idx}: {product_group} - {grade}")

        for col in month_cols:
            # Convert column name to year_month format
            if isinstance(col, pd.Timestamp) or isinstance(col, datetime):
                # Handle datetime column names
                month_num = str(col.month).zfill(2)
                full_year = str(col.year)
                year_month = f"{full_year}-{month_num}"
                print(f"  - Converting datetime {col} to {year_month}")
            else:
                # Handle string column names 
                col_str = str(col).strip()
                parts = col_str.split()
                if len(parts) != 2:
                    print(f"  - Skipping column {col_str}: Invalid format")
                    continue
                
                month_name, year = parts
                month_mapping = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                month_num = month_mapping.get(month_name, '00')
                full_year = f"20{year}"
                year_month = f"{full_year}-{month_num}"
                print(f"  - Converting {col_str} to {year_month}")

            try:
                tons = float(row[col]) if not pd.isna(row[col]) else 0.0
                print(f"    Value: {tons}")
                if tons > 0:
                    records.append({
                        'YearMonth': year_month,
                        'ProductGroup': product_group,
                        'SteelGrade': grade,
                        'Tons': tons
                    })
            except Exception as e:
                print(f"    Error processing value: {e}")

    # Save as CSV
    print(f"Total records: {len(records)}")
    new_df = pd.DataFrame(records)
    csv_path = os.path.join(UPLOAD_FOLDER, "steel_grade_production.csv")
    new_df.to_csv(csv_path, index=False)

    return jsonify({
        "status": "steel_grade_production data processed and saved",
        "csv_path": csv_path,
        "records_processed": len(records)
    }), 200

# ─── End point: Upload product_groups_monthly.xlsx 
# this is the main input for product groups
@app.route("/upload/product_groups", methods=["POST"])
def upload_product_groups():
    """
    Expects multipart/form-data with 'file'.
    Excel format with columns: ['Quality group', 'Grade', 'Jun 24', 'Jul 24', 'Aug 24', etc.]
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400

    local_path = os.path.join(UPLOAD_FOLDER, "product_groups_monthly.xlsx")
    f.save(local_path)

    # Read with pandas
    df = pd.read_excel(local_path)

    # Process data into database
    for idx, row in df.iterrows():
        # Get product group name and ensure it exists
        pg_name = row["Quality group"]
        pg_id = upsert_product_group(pg_name)
        
        # Get grade name and link it to product group
        grade_name = row["Grade"]
        grade_id = upsert_steel_grade(grade_name, pg_id)
        
        # Process each month column (Jun 24, Jul 24, etc.)
        for col in df.columns:
            # Skip non-month columns
            if col in ['Quality group', 'Grade']:
                continue
                
            # Convert column name to year_month format (e.g., 'Jun 24' -> '2024-06')
            month_parts = col.split()
            if len(month_parts) != 2:
                continue
                
            month_name, year = month_parts
            # Convert month name to number (Jun -> 06)
            month_mapping = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
            }
            month_num = month_mapping.get(month_name, '00')
            
            # Format year (24 -> 2024)
            full_year = f"20{year}"
            
            # Final format: 2024-06
            year_month = f"{full_year}-{month_num}"
            
            # Get tonnage value
            tons = float(row[col]) if not pd.isna(row[col]) else 0.0
            
            # Upsert into product_group_monthly
            supabase_client.table("product_group_monthly")\
                .upsert({
                    "year_month": year_month,
                    "product_group_id": pg_id,
                    "steel_grade_id": grade_id,
                    "tons": tons
                },
                on_conflict="year_month,product_group_id,steel_grade_id")\
                .execute()

    # Save as CSV for reference
    csv_path = os.path.join(UPLOAD_FOLDER, "product_groups_monthly.csv")
    df.to_csv(csv_path, index=False)

    return jsonify({
        "status": "product_group_monthly data processed and saved",
        "csv_path": csv_path
    }), 200

# ─── endpoint : Upload daily_charge_schedule.xlsx 
@app.route("/upload/daily_schedule", methods=["POST"])
def upload_daily_schedule():
    """
    Expects multipart/form-data with 'file'.
    Excel columns: ['Date', 'SequenceOrder', 'SteelGrade'].
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400

    local_path = os.path.join(UPLOAD_FOLDER, "daily_charge_schedule.xlsx")
    f.save(local_path)

    df = pd.read_excel(local_path)
    # Ensure 'Date' is a datetime or string in 'YYYY-MM-DD'
    for idx, row in df.iterrows():
        date_val = row["Date"]
        # Convert to ISO format if it’s a datetime
        if pd.isna(date_val):
            continue
        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.date().isoformat()
        else:
            date_str = str(date_val)  # assume 'YYYY-MM-DD'

        seq = int(row["SequenceOrder"])
        grade_name = row["SteelGrade"]

        # 1) Ensure steel grade exists
        grade_id = upsert_steel_grade(grade_name, None)

        # 2) Upsert into daily_charge_schedule
        supabase_client.table("daily_charge_schedule")\
            .upsert({
                "run_date": date_str,
                "sequence_order": seq,
                "steel_grade_id": grade_id
            },
            on_conflict="run_date,sequence_order")\
            .execute()

    return jsonify({"status": "daily_charge_schedule ingested"}), 200

# ─── Endpoint: Forecast September Production ──────────────────────────────────
@app.route("/forecast/september", methods=["GET"])
def forecast_september():
    """
    Returns JSON array: [ { "steel_grade": str, "heats": int }, ... ].
    Forecast logic:
      - Look up each steel_grade.id + name
      - For each, grab the last 3 months of production (ordered by year_month DESC)
      - Compute avg_tons = mean(tons)
      - forecast_tons = avg_tons
      - heats = round(forecast_tons / 100)
    """
    N = 3  # number of months to average

    # 1) Fetch all steel grades
    grades_resp = supabase_client.table("steel_grades").select("id, name").execute()
    grades = grades_resp.data

    results = []
    for g in grades:
        grade_id = g["id"]
        grade_name = g["name"]

        # 2) Fetch last N months for this grade
        #    Note: supabase_client/PostgREST orders by lexicographic on 'year_month' if stored as 'YYYY-MM'.
        prod_resp = (
            supabase_client
            .table("steel_grade_production")
            .select("year_month, tons")
            .eq("steel_grade_id", grade_id)
            .order("year_month", desc=True)
            .limit(N)
            .execute()
        )
        rows = prod_resp.data

        if not rows:
            continue

        tons_list = [r["tons"] for r in rows]
        avg_tons = sum(tons_list) / len(tons_list)
        forecast_tons = avg_tons
        forecast_heats = int(round(forecast_tons / HEAT_TONNAGE))

        results.append({
            "steel_grade": grade_name,
            "steel_group": g.get("product_group_id", None),  # Optional product group ID
            "heats": forecast_heats
        })

    return jsonify(results), 200

# ─── Run the Flask App ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)


