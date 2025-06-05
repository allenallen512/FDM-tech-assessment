import os
from datetime import datetime
from flask import Flask, request, jsonify
import pandas as pd
from supabase import create_client, Client 
from dotenv import load_dotenv


load_dotenv()  

SUPABASE_URL = os.getenv("SUPABASE_PROJECT_URL")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLIC_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY) 


