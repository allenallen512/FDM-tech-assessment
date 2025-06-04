
from supabase_client import supabase_client
from typing import Optional

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
    if result.data and len(result.data) == 1:
        # Optionally update product_group_id if it was previously NULL
        existing = result.data[0]
        if pg_id is not None:
            supabase_client.table("steel_grades")\
                .update({"product_group_id": pg_id})\
                .eq("id", existing["id"])\
                .execute()
        return existing["id"]

    # Insert new
    payload = {"name": grade_name, "product_group_id": pg_id}
    ins = supabase_client.table("steel_grades").insert(payload).execute()
    return ins.data[0]["id"]