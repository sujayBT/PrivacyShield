"""
Parse content.xml from friend's ODT and extract key formatting info:
- Page margins
- Table structures and column widths
- Font sizes
- Image dimensions
"""
import re, xml.etree.ElementTree as ET

with open(r"C:\PrivacyExposureProject\_odt_inspect\content.xml", encoding="utf-8") as f:
    raw = f.read()

# Extract page layout info from styles
with open(r"C:\PrivacyExposureProject\_odt_inspect\styles.xml", encoding="utf-8") as f:
    sraw = f.read()

# Page margins
margin_pat = re.findall(r'fo:margin-(top|bottom|left|right)="([^"]+)"', sraw)
print("=== PAGE MARGINS from styles.xml ===")
for k, v in margin_pat[:20]:
    print(f"  {k}: {v}")

# Page size
size_pat = re.findall(r'fo:page-(width|height)="([^"]+)"', sraw)
print("\n=== PAGE SIZE ===")
for k, v in size_pat:
    print(f"  {k}: {v}")

# Table column widths in content.xml
col_widths = re.findall(r'style:column-width="([^"]+)"', raw)
print("\n=== TABLE COLUMN WIDTHS ===")
for w in col_widths[:30]:
    print(f"  {w}")

# Table widths
tbl_widths = re.findall(r'style:width="([^"]+)".*?style:family="table"', raw)
print("\n=== TABLE WIDTHS ===")
for w in tbl_widths[:10]:
    print(f"  {w}")

# Image sizes
img_sizes = re.findall(r'svg:width="([^"]+)" svg:height="([^"]+)"', raw)
print("\n=== IMAGE SIZES ===")
for w, h in img_sizes[:10]:
    print(f"  {w} x {h}")

# Font sizes used
font_sizes = re.findall(r'fo:font-size="([^"]+)"', raw)
from collections import Counter
print("\n=== FONT SIZES (frequency) ===")
for sz, cnt in Counter(font_sizes).most_common(15):
    print(f"  {sz}: {cnt}x")

# Line heights
line_heights = re.findall(r'fo:line-height="([^"]+)"', raw)
print("\n=== LINE HEIGHTS ===")
for lh in set(line_heights):
    print(f"  {lh}")

# Border styles in tables
borders = re.findall(r'fo:border="([^"]+)"', raw)
border_set = set(borders)
print("\n=== BORDER STYLES ===")
for b in border_set:
    print(f"  {b}")

# Table cell padding
padding = re.findall(r'fo:padding="([^"]+)"', raw)
padding_set = set(padding)
print("\n=== CELL PADDING ===")
for p in padding_set:
    print(f"  {p}")

# Check if there's background color in table header
bg_colors = re.findall(r'fo:background-color="([^"]+)"', raw)
print("\n=== BACKGROUND COLORS ===")
for c in set(bg_colors):
    print(f"  {c}")

print("\n=== FIRST 3000 chars of content.xml (body area) ===")
# Find the text:body section
body_start = raw.find("<office:text>")
if body_start > -1:
    print(raw[body_start:body_start+3000])
