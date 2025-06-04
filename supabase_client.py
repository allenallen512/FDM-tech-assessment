import os
from datetime import datetime
from flask import Flask, request, jsonify
import pandas as pd
from supabase import create_client, Client  # Import from 'supabase', not 'supabase_client'
from dotenv import load_dotenv


load_dotenv()  # Loads SUPABASE_URL and SUPABASE_KEY from .env

SUPABASE_URL = os.getenv("SUPABASE_PROJECT_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)  # Name this variable 'supabase_client'


