import importlib.resources
import kraken.blla

print(f"__name__ of kraken.blla: {kraken.blla.__name__}")

try:
    print("Attempting resources.files('kraken.blla')...")
    f = importlib.resources.files('kraken.blla')
    print(f"Success: {f}")
except Exception as e:
    print(f"Failed resources.files('kraken.blla'): {e}")

try:
    print("Attempting resources.files('kraken')...")
    f = importlib.resources.files('kraken')
    print(f"Success: {f}")
except Exception as e:
    print(f"Failed resources.files('kraken'): {e}")
