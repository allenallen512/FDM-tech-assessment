from flask import Flask, request, jsonify
import os
from helper_functions import upsert_steel_grade, upsert_product_group, detect_month_columns, process_production_data, save_to_steel_grade_production, process_product_group_data, save_product_group_monthly
import pandas as pd
from supabase_client import supabase_client
from datetime import datetime
import json
import math
import re
# set up flask app 

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 1 heat = 100 tons
tons_per_heat = 100.0


#  ---- endpoint: upload steel_grade_production
@app.route("/upload/steel_grades", methods=["POST"])
def upload_steel_grades():
    """
    for uploading the steel_grade_production.xlsx file.
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

    # Check for the right columns . hard coded for now
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

    records = process_production_data(df, month_cols) #records to save, returns records as a list dict
      
    # save 
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
    for uploading the product_groups_monthly.xlsx file.
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
    save_product_group_monthly(records, tons_per_heat)
    
    return jsonify({
        "status": "product_group_monthly data processed and saved",
        "csv_path": csv_path,
        "records_processed": len(records)
    }), 200



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
    number_months = 3  # number of months to average

    # get grades and group names
    all_grades_resp = supabase_client.table("steel_grades").select("id, name, product_group_id").execute()
    all_groups_resp = supabase_client.table("product_groups").select("id, name").execute()
    
    grades = all_grades_resp.data
    groups = all_groups_resp.data
    group_map = {g["id"]: g["name"] for g in groups} #map the id to a name for easy view
 
    if not grades or not groups:
        return jsonify({"error": "No steel grades or product groups found"}), 404
    
    results = []
    for g in grades:
        grade_id = g["id"]
        grade_name = g["name"]
        group_id = g.get("product_group_id", None)
        group_name = group_map.get(group_id, None)
        print(f"Processing Grade: {grade_name}, Group: {group_name}")

        prod_resp = (
            supabase_client
            .table("steel_grade_production")
            .select("year_month, tons")
            .eq("steel_grade_id", grade_id)
            .order("year_month", desc=True)
            .limit(number_months)
            .execute()
        )
        rows = prod_resp.data
        if not rows: #if no response
            continue
        
        tons_list = [r["tons"] for r in rows]
        avg_tons = sum(tons_list) / len(tons_list)
        print(f"Grade: {grade_name}, Avg Tons: {avg_tons}")
        forecast_tons = avg_tons
        forecast_heats = math.ceil(forecast_tons / tons_per_heat) #rounding up
        results.append({
            "steel_grade": grade_name,
            "steel_group": group_name,  
            "heats": forecast_heats,
            "tons": forecast_tons,
        })
        
        save_path = os.path.join(UPLOAD_FOLDER, "september_forecast.json")
        with open(save_path, "w") as f:
            json.dump(results, f, indent=2)
        
    return jsonify(results), 200

# ─── Run the Flask App ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)


