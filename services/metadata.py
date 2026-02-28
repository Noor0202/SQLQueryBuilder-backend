# backend/services/metadata.py
import psycopg2
from psycopg2.extras import RealDictCursor

# Raw SQL Queries
QUERY_TABLES = """
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_type = 'BASE TABLE' 
  AND table_schema NOT IN ('information_schema', 'pg_catalog')
"""

QUERY_COLUMNS = """
SELECT table_schema, table_name, column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
"""

QUERY_FKS = """
SELECT
    tc.table_schema, tc.table_name, kcu.column_name,
    ccu.table_schema AS foreign_table_schema,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM
    information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema NOT IN ('information_schema', 'pg_catalog');
"""

def get_target_db_connection(creds, decrypted_password):
    """Connects to the User's Target DB."""
    return psycopg2.connect(
        host=creds.host,
        port=creds.port,
        dbname=creds.db_name,
        user=creds.username,
        password=decrypted_password,
        sslmode=creds.ssl_mode,
        connect_timeout=5
    )

def transform_metadata_to_json(tables_raw, columns_raw, fks_raw):
    """Converts raw SQL rows into the nested JSON structure."""
    tables_map = {}
    
    # 1. Init Tables
    for t in tables_raw:
        full_id = f"{t['table_schema']}.{t['table_name']}"
        tables_map[full_id] = {
            "Id": full_id,
            "TableName": t['table_name'],
            "Schema": t['table_schema'],
            "Columns": [],
            "Joins": []
        }

    # 2. Add Columns
    for c in columns_raw:
        table_id = f"{c['table_schema']}.{c['table_name']}"
        if table_id in tables_map:
            tables_map[table_id]["Columns"].append({
                "Id": f"{table_id}.{c['column_name']}",
                "ColumnName": c['column_name'],
                "DataType": c['data_type'].upper(),
                "IsNullable": c['is_nullable'] == 'YES'
            })

    # 3. Add Joins
    for fk in fks_raw:
        parent_id = f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}"
        child_id = f"{fk['table_schema']}.{fk['table_name']}"
        
        if parent_id in tables_map:
             tables_map[parent_id]["Joins"].append({
                "ChildTableId": child_id,
                "ParentColumnId": f"{parent_id}.{fk['foreign_column_name']}",
                "ChildColumnId": f"{child_id}.{fk['column_name']}",
                "JoinType": "INNER"
            })

    return {"Tables": list(tables_map.values())}