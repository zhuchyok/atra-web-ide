"""CI gate — enforces minimum test count."""
import xml.etree.ElementTree as ET

tree = ET.parse("test-results/junit.xml")
total = int(tree.getroot().get("tests", 0))
print(f"Tests run: {total}")
if total < 65:
    print(f"FAIL: expected >= 65 tests, got {total}")
    exit(1)
print("OK")
