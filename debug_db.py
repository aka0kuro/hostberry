#!/usr/bin/env python3
import sqlite3
import sys

try:
    conn = sqlite3.connect("/var/lib/hostberry/hostberry.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT username, role, created_at FROM users")
    users = cursor.fetchall()
    
    print("Usuarios en la base de datos:")
    for user in users:
        print(f"  - Usuario: {user[0]}, Rol: {user[1]}, Creado: {user[2]}")
    
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    
    print("\nEstructura de la tabla users:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
