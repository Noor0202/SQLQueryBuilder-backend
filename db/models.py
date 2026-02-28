# backend/db/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base

# --- EXISTING USER MODEL ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to connections
    connections = relationship("DBConnection", back_populates="owner")

# --- NEW MODELS ---
class DBConnection(Base):
    __tablename__ = "db_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)  # e.g., "My Prod DB"
    
    # Target DB Connection Details
    host = Column(String, nullable=False)
    port = Column(String, default="5432")
    db_name = Column(String, nullable=False)
    username = Column(String, nullable=False)
    encrypted_password = Column(String, nullable=False) # Stored securely
    ssl_mode = Column(String, default="prefer")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="connections")
    metadata_store = relationship("DBMetadata", back_populates="connection", uselist=False)

class DBMetadata(Base):
    __tablename__ = "db_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("db_connections.id"), unique=True)
    
    # Stores the generated JSON of tables/columns
    schema_json = Column(JSON, nullable=True)
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    connection = relationship("DBConnection", back_populates="metadata_store")