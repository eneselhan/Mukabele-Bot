import threading
import json
from src.config import ALIGNMENT_JSON

class AlignmentService:
    def __init__(self):
        self.lock = threading.Lock()

    def _load_data(self):
        try:
            if not ALIGNMENT_JSON.exists():
                return None, None

            with ALIGNMENT_JSON.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                return data, data
            elif isinstance(data, dict) and "aligned" in data:
                return data["aligned"], data
            
            return None, None

        except Exception as e:
            print(f"Error loading data from {ALIGNMENT_JSON}: {e}")
            return None, None

    def update_line(self, line_no, new_text):
        with self.lock:
            aligned_list, full_data = self._load_data()
            if aligned_list is None:
                return False

            found = False
            for item in aligned_list:
                if item.get("line_no") == line_no:
                    if "best" not in item:
                        item["best"] = {}
                    item["best"]["raw"] = new_text
                    found = True
                    break
            
            if not found:
                return False

            try:
                with ALIGNMENT_JSON.open("w", encoding="utf-8") as f:
                    json.dump(full_data, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"Error saving data to {ALIGNMENT_JSON}: {e}")
                return False
