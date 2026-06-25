import win32com.client
import os

orig_path = os.path.abspath(r"C:\Users\sujay\OneDrive\Documents\MR1_Sujay_PrivacyExposureTool.docx")
fmt_path = os.path.abspath(r"C:\Users\sujay\OneDrive\Documents\MR1_Sujay_PrivacyExposureTool_Formatted.docx")

word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = False

try:
    doc_src = word.Documents.Open(orig_path, ReadOnly=True)
    doc_dest = word.Documents.Open(fmt_path, ReadOnly=False)
    
    # wdHeaderFooterPrimary = 1
    # Check all sections and copy footers
    for i in range(1, doc_src.Sections.Count + 1):
        if i <= doc_dest.Sections.Count:
            src_footer = doc_src.Sections(i).Footers(1)
            dest_footer = doc_dest.Sections(i).Footers(1)
            
            src_footer.Range.Copy()
            dest_footer.Range.Paste()
            
            # Also copy Header just in case
            src_header = doc_src.Sections(i).Headers(1)
            dest_header = doc_dest.Sections(i).Headers(1)
            src_header.Range.Copy()
            dest_header.Range.Paste()
            
    doc_dest.Save()
    print("Successfully restored headers and footers (page numbers).")
    
    doc_src.Close(SaveChanges=False)
    doc_dest.Close()

except Exception as e:
    print(f"COM Error: {e}")
finally:
    word.Quit()
