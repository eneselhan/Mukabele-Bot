import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    import kraken
    print(f"Kraken file: {kraken.__file__}")
except ImportError as e:
    print(f"Failed to import kraken: {e}")

try:
    from kraken import blla
    print(f"Successfully imported blla: {blla}")
    print(f"Type of blla: {type(blla)}")
except ImportError as e:
    print(f"Failed 'from kraken import blla': {e}")
except Exception as e:
    print(f"Error during 'from kraken import blla': {e}")

try:
    import kraken.blla
    print(f"Successfully imported kraken.blla: {kraken.blla}")
except ImportError as e:
    print(f"Failed 'import kraken.blla': {e}")
