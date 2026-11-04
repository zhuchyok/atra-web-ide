"""CI gate — enforces minimum test count."""
import xml.etree.ElementTree as ET

root = ET.parse("test-results/junit.xml").getroot()
# junit может класть атрибут tests на корень (testsuites) или на вложенные testsuite
total = int(root.get("tests", 0))
if total == 0:
    total = sum(int(ts.get("tests", 0)) for ts in root.iter("testsuite"))
print(f"Tests run: {total}")
if total < 65:
    print(f"FAIL: expected >= 65 tests, got {total}")
    exit(1)
print("OK")
