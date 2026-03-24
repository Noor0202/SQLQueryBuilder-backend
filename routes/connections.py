# backend/connections.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from psycopg2.extras import RealDictCursor
from typing import List, Any, Dict
from types import SimpleNamespace 

from db.database import get_db
from db.models import DBConnection, DBMetadata, User
from schemas import DBConnectionCreate, DBConnectionResponse, QueryRequest
from auth.routes import get_current_user
from auth.encryption import decrypt_password, encrypt_password
from services.metadata import get_target_db_connection, transform_metadata_to_json, QUERY_TABLES, QUERY_COLUMNS, QUERY_FKS

# IMPORT FIX: Add logger
from logger import logger

router = APIRouter(prefix="/api/db-connections", tags=["connections"])

@router.post("/test")
def test_connection(creds: DBConnectionCreate, current_user: User = Depends(get_current_user)):
    try:
        conn = get_target_db_connection(creds, creds.password)
        conn.close()
        logger.info(f"User '{current_user.username}' successfully tested connection to '{creds.host}'.")
        return {"status": "success", "message": "Connected successfully!"}
    except Exception as e:
        logger.error(f"Connection test failed for user '{current_user.username}' to '{creds.host}': {str(e)}")
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")

@router.post("/save", response_model=DBConnectionResponse)
def save_connection(creds: DBConnectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Test External Connection and Fetch Metadata
    try:
        conn = get_target_db_connection(creds, creds.password)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(QUERY_TABLES)
        tables = cursor.fetchall()
        
        cursor.execute(QUERY_COLUMNS)
        columns = cursor.fetchall()
        
        cursor.execute(QUERY_FKS)
        fks = cursor.fetchall()
        
        conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch metadata during save for host '{creds.host}': {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch schema metadata: {str(e)}")

    # 2. Transform Metadata and Save to Database
    try:
        metadata_json = transform_metadata_to_json(tables, columns, fks)
        encrypted_pw = encrypt_password(creds.password)
        
        new_conn = DBConnection(
            user_id=current_user.id,
            name=creds.name,
            host=creds.host,
            port=creds.port,
            db_name=creds.db_name,
            username=creds.username,
            encrypted_password=encrypted_pw,
            ssl_mode=creds.ssl_mode
        )
        db.add(new_conn)
        db.flush() 

        new_metadata = DBMetadata(connection_id=new_conn.id, schema_json=metadata_json)
        db.add(new_metadata)
        db.commit()
        db.refresh(new_conn)
        
        logger.info(f"Connection '{creds.name}' (ID: {new_conn.id}) successfully saved for user '{current_user.username}'.")
        return new_conn
    except Exception as e:
        db.rollback()
        logger.error(f"Database error while saving connection '{creds.name}': {str(e)}") 
        raise HTTPException(status_code=500, detail="An internal error occurred while saving the connection.")

@router.get("", response_model=List[DBConnectionResponse])
def get_user_connections(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return db.query(DBConnection).filter(DBConnection.user_id == current_user.id).order_by(DBConnection.created_at.desc()).all()
    except Exception as e:
        logger.error(f"Failed to retrieve connections for user '{current_user.username}': {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve database connections.")

@router.get("/{conn_id}")
def get_connection_metadata(conn_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        conn = db.query(DBConnection).filter(DBConnection.id == conn_id, DBConnection.user_id == current_user.id).first()
        if not conn:
            logger.warning(f"Metadata requested for non-existent or unauthorized connection ID: {conn_id} by user '{current_user.username}'")
            raise HTTPException(status_code=404, detail="Connection not found")
        
        meta = db.query(DBMetadata).filter(DBMetadata.connection_id == conn_id).first()
        return {
            "connection": conn,
            "schema": meta.schema_json if meta else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error retrieving metadata for connection {conn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve connection metadata.")

@router.delete("/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(conn_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        conn = db.query(DBConnection).filter(DBConnection.id == conn_id, DBConnection.user_id == current_user.id).first()
        if not conn:
            logger.warning(f"Delete requested for non-existent or unauthorized connection ID: {conn_id} by user '{current_user.username}'")
            raise HTTPException(status_code=404, detail="Connection not found")

        db.query(DBMetadata).filter(DBMetadata.connection_id == conn_id).delete()
        db.delete(conn)
        db.commit()
        
        logger.info(f"Connection ID {conn_id} successfully deleted by user '{current_user.username}'.")
        return
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete connection {conn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete connection.")

# --- EXECUTE QUERY ENDPOINT (Updated for Pagination) ---
@router.post("/{conn_id}/execute")
def execute_query(
    conn_id: int, 
    query_req: QueryRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    logger.info(f"User '{current_user.username}' executing query on Connection ID {conn_id} (Page {query_req.page})")
    
    try:
        conn_record = db.query(DBConnection).filter(
            DBConnection.id == conn_id, 
            DBConnection.user_id == current_user.id
        ).first()
    except Exception as e:
        logger.error(f"Failed to fetch connection record {conn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error fetching connection.")

    if not conn_record:
        logger.warning(f"Query execution blocked: Connection {conn_id} not found or unauthorized.")
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        try:
            real_password = decrypt_password(conn_record.encrypted_password)
        except ValueError:
            logger.error(f"Decryption failed for connection ID {conn_id}.")
            raise HTTPException(status_code=500, detail="Cannot decrypt password. Please delete and re-add this connection.")

        creds = SimpleNamespace(
            host=conn_record.host,
            port=conn_record.port,
            db_name=conn_record.db_name,
            username=conn_record.username,
            ssl_mode=conn_record.ssl_mode
        )

        conn = get_target_db_connection(creds, real_password)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Clean SQL (remove trailing semicolon)
        clean_sql = query_req.sql.strip().rstrip(';')
        
        # 2. Get Total Count (Wrapping in subquery is safest way to count arbitrary SQL results)
        count_sql = f"SELECT COUNT(*) as total_count FROM ({clean_sql}) AS count_wrapper"
        cursor.execute(count_sql)
        count_result = cursor.fetchone()
        total_rows = count_result['total_count'] if count_result else 0

        # 3. Calculate Offset
        offset = (query_req.page - 1) * query_req.limit

        # 4. Fetch Paginated Data
        paginated_sql = f"{clean_sql} LIMIT {query_req.limit} OFFSET {offset}"
        logger.info(f"Running paginated SQL for Conn ID {conn_id}: LIMIT {query_req.limit} OFFSET {offset}")
        
        cursor.execute(paginated_sql)
        
        rows = []
        if cursor.description:
            rows = cursor.fetchall()
            rows = [dict(row) for row in rows]

        conn.close()
        
        return {
            "rows": rows,
            "total_rows": total_rows,
            "page": query_req.page,
            "limit": query_req.limit
        }

    except HTTPException:
        raise
    except Exception as e:
        # Expected errors here are typically user SQL syntax errors
        logger.error(f"Query execution failed for Conn ID {conn_id}: {str(e)}")
        # Return simple error message to the frontend without the full traceback stack
        raise HTTPException(status_code=400, detail=str(e).split('\n')[0])