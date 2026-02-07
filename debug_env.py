from dotenv import load_dotenv
import os
import tkinter as tk
import sys

print("Loading dotenv...")
try:
    load_dotenv()
    print("Dotenv loaded.")
except Exception as e:
    print(f"Dotenv failed: {e}")

print("GOOGLE_API_KEY:", os.getenv("GOOGLE_API_KEY"))

print("Initializing Tk...")
try:
    root = tk.Tk()
    print("Tk initialized.")
    root.destroy()
    print("Tk destroyed.")
except Exception as e:
    print("Tk failed:", e)
    sys.exit(1)
