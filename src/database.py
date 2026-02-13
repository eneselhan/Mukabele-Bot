import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.config import PROJECTS_DIR

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages SQLite database connections and schema.
    Uses a hybrid approach: Relational columns for querying, JSON for flexible data.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Global DB in projects dir? Or per-project DB?
            # Implementation Plan said "tahkik.db per project or global".
            # Global is better for cross-project search. Per-project is better for portability.
            # Let's go with Global key-value store for now, but `lines` table is huge.
            # Actually, let's keep it simple: One global DB for metadata, 
            # and maybe per-project DBs for lines if needed? 
            # No, SQLite can handle single file fine. Let's try Global DB at:
            self.db_path = PROJECTS_DIR / "tahkik_global.db"
        else:
            self.db_path = db_path
            
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes the database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Projects
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT -- Stores authors, language, description etc.
            )
        """)
        
        # 2. Files/Nushas (Metadata level)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nushas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                nusha_index INTEGER,
                name TEXT,
                config_json TEXT, -- Stores DPI, filename etc.
                UNIQUE(project_id, nusha_index),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)

        # 3. Aligned Lines (The Core Data)
        # This replaces alignment.json content
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aligned_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                nusha_index INTEGER,
                line_no INTEGER,
                
                ref_text TEXT,  -- Word text (Corrected)
                ocr_text TEXT,  -- Original OCR
                image_path TEXT, -- Relative path to line image
                
                meta_json TEXT, -- Stores bbox, confidences, detailed matches
                
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted BOOLEAN DEFAULT 0,
                deleted_at TIMESTAMP,
                
                UNIQUE(project_id, nusha_index, line_no),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)

        # Migration: Check if 'is_deleted' exists, if not add it
        try:
            cursor.execute("SELECT is_deleted FROM aligned_lines LIMIT 1")
        except sqlite3.OperationalError:
            # Column missing, add it
            logger.info("Migrating DB: Adding is_deleted to aligned_lines")
            try:
                cursor.execute("ALTER TABLE aligned_lines ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
                cursor.execute("ALTER TABLE aligned_lines ADD COLUMN deleted_at TIMESTAMP")
            except Exception as e:
                logger.error(f"Migration failed: {e}")
        
        # 4. Footnotes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS footnotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fn_id TEXT, -- UUID from frontend
                project_id TEXT,
                line_no INTEGER,
                fn_index INTEGER, -- Index within the line text
                content TEXT,
                type TEXT,
                
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)
        
        conn.commit()
        conn.close()

    # --- CRUD Helpers ---

    def get_nushas(self, project_id: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT nusha_index, name, config_json, is_base
                FROM nushas
                WHERE project_id=?
                ORDER BY nusha_index
            """, (project_id,))
            rows = cursor.fetchall()
            
            nushas = []
            for row in rows:
                config = json.loads(row["config_json"]) if row["config_json"] else {}
                nushas.append({
                    "nusha_index": row["nusha_index"],
                    "name": row["name"],
                    "config": config,
                    "is_base": bool(row["is_base"])
                })
            return nushas
        finally:
            conn.close()

    def upsert_project(self, project_id: str, name: str, metadata: Dict):
        conn = self.get_connection()
        try:
            conn.execute("""
                INSERT INTO projects (id, name, metadata_json) 
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    metadata_json=excluded.metadata_json
            """, (project_id, name, json.dumps(metadata, ensure_ascii=False)))
            conn.commit()
        finally:
            conn.close()

    def upsert_nusha(self, project_id: str, nusha_index: int, name: str, config: Dict):
        conn = self.get_connection()
        try:
            conn.execute("""
                INSERT INTO nushas (project_id, nusha_index, name, config_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, nusha_index) DO UPDATE SET
                    name=excluded.name,
                    config_json=excluded.config_json
            """, (project_id, nusha_index, name, json.dumps(config, ensure_ascii=False)))
            conn.commit()
        finally:
            conn.close()

    def set_base_nusha(self, project_id: str, nusha_index: int):
        """Sets the given nusha as base and others as not base."""
        conn = self.get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")
            # Set all to 0
            conn.execute("UPDATE nushas SET is_base=0 WHERE project_id=?", (project_id,))
            # Set target to 1
            conn.execute("UPDATE nushas SET is_base=1 WHERE project_id=? AND nusha_index=?", (project_id, nusha_index))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def upsert_footnotes(self, project_id: str, footnotes: List[Dict]):
        conn = self.get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")
            # Create a simple mapping of line_no + index to identify uniqueness?
            # Or just delete all for project and re-insert (easiest for full sync)
            conn.execute("DELETE FROM footnotes WHERE project_id=?", (project_id,))
            
            sql = """
                INSERT INTO footnotes (project_id, line_no, fn_index, content, type, fn_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = []
            for fn in footnotes:
                params.append((
                    project_id,
                    fn.get("line_no", 0),
                    fn.get("index", 0),
                    fn.get("content", ""),
                    fn.get("type", "normal"),
                    fn.get("id", "") # Store frontend UUID
                ))
            
            conn.executemany(sql, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_footnotes(self, project_id: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fn_id, line_no, fn_index, content, type 
                FROM footnotes 
                WHERE project_id=?
                ORDER BY line_no, fn_index
            """, (project_id,))
            rows = cursor.fetchall()
            
            footnotes = []
            for row in rows:
                footnotes.append({
                    "id": row["fn_id"], # Return as 'id'
                    "line_no": row["line_no"],
                    "index": row["fn_index"],
                    "content": row["content"],
                    "type": row["type"]
                })
            return footnotes
        finally:
            conn.close()

    def upsert_lines_batch(self, project_id: str, nusha_index: int, lines: List[Dict]):
        """
        Batch upsert for alignment lines. 
        Expects lines to be in alignment.json format (dict).
        """
        conn = self.get_connection()
        try:
            # Use transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Clear existing lines for this nusha/project to avoid duplicates/ghosts? 
            # Or just upsert? If we removed lines in JSON, we should remove here too.
            # Strategy: Delete all for nusha, then insert all. Safest sync.
            conn.execute("DELETE FROM aligned_lines WHERE project_id=? AND nusha_index=?", (project_id, nusha_index))
            
            sql = """
                INSERT INTO aligned_lines (project_id, nusha_index, line_no, ref_text, ocr_text, image_path, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            params = []
            for line in lines:
                line_no = line.get("line_no")
                ocr_text = line.get("ocr_text", "")
                image_path = line.get("line_image", "")
                
                best = line.get("best", {})
                ref_text = best.get("raw", "")
                
                # Meta includes everything else
                meta = {k: v for k, v in line.items() if k not in ["line_no", "ocr_text", "line_image"]}
                
                params.append((
                    project_id, 
                    nusha_index, 
                    line_no, 
                    ref_text, 
                    ocr_text, 
                    image_path, 
                    json.dumps(meta, ensure_ascii=False)
                ))
                
            conn.executemany(sql, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_aligned_lines(self, project_id: str, nusha_index: int) -> List[Dict]:
        """
        Reconstructs the alignment.json 'aligned' list from DB.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT line_no, ref_text, ocr_text, image_path, meta_json
            FROM aligned_lines
            WHERE project_id=? AND nusha_index=?
            ORDER BY line_no ASC
        """, (project_id, nusha_index))
        
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
             result.append(self._row_to_dict(row))
            
        conn.close()
        return result

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """
        Helper to convert DB row to line object (expanding meta_json).
        """
        line_obj = json.loads(row["meta_json"]) if row["meta_json"] else {}
        
        # Re-inject primary fields
        line_obj["line_no"] = row["line_no"]
        line_obj["ocr_text"] = row["ocr_text"]
        
        # Handle new columns if present
        if "is_deleted" in row.keys():
             line_obj["is_deleted"] = bool(row["is_deleted"])
        if "deleted_at" in row.keys():
             line_obj["deleted_at"] = row["deleted_at"]

        # Ensure image_path is correct relative path
        if row["image_path"]:
             line_obj["line_image"] = row["image_path"]
        
        if "best" not in line_obj:
            line_obj["best"] = {}
        line_obj["best"]["raw"] = row["ref_text"]
        
        return line_obj

    def get_deleted_lines(self, project_id: str, nusha_index: int) -> List[Dict]:
        """
        Retrieves only soft-deleted lines.
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM aligned_lines 
                WHERE project_id=? AND nusha_index=? AND is_deleted=1
                ORDER BY deleted_at DESC, line_no ASC
            """, (project_id, nusha_index))
            
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def soft_delete_aligned_line(self, project_id: str, nusha_index: int, line_no: int):
        """
        Soft deletes a line by setting is_deleted=1.
        """
        conn = self.get_connection()
        try:
            conn.execute("""
                UPDATE aligned_lines 
                SET is_deleted=1, deleted_at=CURRENT_TIMESTAMP 
                WHERE project_id=? AND nusha_index=? AND line_no=?
            """, (project_id, nusha_index, line_no))
            conn.commit()
        finally:
            conn.close()

    def restore_aligned_line(self, project_id: str, nusha_index: int, line_no: int):
        """
        Restores a line by setting is_deleted=0.
        """
        conn = self.get_connection()
        try:
            conn.execute("""
                UPDATE aligned_lines 
                SET is_deleted=0, deleted_at=NULL 
                WHERE project_id=? AND nusha_index=? AND line_no=?
            """, (project_id, nusha_index, line_no))
            conn.commit()
        finally:
            conn.close()

    def delete_aligned_line(self, project_id: str, nusha_index: int, line_no: int):
        """
        Hard deletes a line (Legacy/Admin use).
        """
        conn = self.get_connection()
        try:
            conn.execute("""
                DELETE FROM aligned_lines 
                WHERE project_id=? AND nusha_index=? AND line_no=?
            """, (project_id, nusha_index, line_no))
            conn.commit()
        finally:
            conn.close()

    def delete_nusha(self, project_id: str, nusha_index: int):
        """Deletes a nusha and all its aligned lines from DB."""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM aligned_lines WHERE project_id=? AND nusha_index=?", (project_id, nusha_index))
            conn.execute("DELETE FROM nushas WHERE project_id=? AND nusha_index=?", (project_id, nusha_index))
            conn.commit()
        finally:
            conn.close()
