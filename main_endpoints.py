from flask import Flask, request, jsonify
import os
from helper_functions import upsert_steel_grade, upsert_product_group, detect_month_columns, process_production_data, save_to_steel_grade_production, process_product_group_data, save_product_group_monthly
import pandas as pd
from supabase_client import supabase_client
from datetime import datetime
import re
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

    Excel format with columns: ['Quality group', 'Grade', 'Jun 24', 'Jul 24', ...]
    skips the first row (title)
    """
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    # Save original Excel file
    excel_path = os.path.join(UPLOAD_FOLDER, "og_steel_grade_production.xlsx")
    file.save(excel_path)

    # skip row one
    df = pd.read_excel(excel_path, header=1)
    print("Columns found:", df.columns.tolist())
    df['Quality group'].ffill(inplace=True)

    # Check for the right columns 
    if 'Quality group' not in df.columns or 'Grade' not in df.columns:
        return jsonify({
            "error": "Required columns not found, is this the right file?",
            "columns_found": df.columns.tolist()
        }), 400
    
    # get the month columns 
    month_cols = detect_month_columns(df)
    print("Month columns detected:", month_cols)
    
    if not month_cols:
        return jsonify({
            "error": "No month columns found in the format 'Mon YY'",
            "columns_found": df.columns.tolist()
        }), 400

    records = process_production_data(df, month_cols) #construct the records that we want to save
      
    # Save as CSV
    print(f"Total records: {len(records)}")
    new_df = pd.DataFrame(records)
    csv_path = os.path.join(UPLOAD_FOLDER, "steel_grade_production.csv")
    new_df.to_csv(csv_path, index=False)
    
    save_to_steel_grade_production(records)

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
    The first row is a title and should be skipped.
    """
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400
    excel_path = os.path.join(UPLOAD_FOLDER, "og_product_groups_monthly.xlsx")
    file.save(excel_path)
    
    df = pd.read_excel(excel_path, header=1)
    print("Columns found:", df.columns.tolist())
    
    # Check clumns
    if 'Quality:' not in df.columns:
        return jsonify({
            "error": "Required column 'Quality' not found",
            "columns_found": df.columns.tolist()
        }), 400
    
    month_cols = detect_month_columns(df)
    if not month_cols:
        return jsonify({
            "error": "No month columns found",
            "columns_found": df.columns.tolist()
        }), 400
    
    records = process_product_group_data(df, month_cols)
    if not records:
        return jsonify({"error": "No valid data found to process"}), 400
    
    # save new csv
    new_df = pd.DataFrame(records)
    csv_path = os.path.join(UPLOAD_FOLDER, "product_groups_monthly.csv")
    new_df.to_csv(csv_path, index=False)
    
    # Save to db
    save_product_group_monthly(records, HEAT_TONNAGE)
    
    return jsonify({
        "status": "product_group_monthly data processed and saved",
        "csv_path": csv_path,
        "records_processed": len(records)
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


