from dotenv import load_dotenv
load_dotenv()
print("Importing src.gui...")
try:
    from src.gui import start_gui
    print("Import success")
    print("Starting gui...")
    start_gui()
    print("GUI finished.")
except Exception as e:
    import traceback
    traceback.print_exc()
