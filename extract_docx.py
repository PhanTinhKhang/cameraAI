import docx
import sys
import os

def extract(filepath, outpath):
    try:
        doc = docx.Document(filepath)
        text = []
        for p in doc.paragraphs:
            text.append(p.text)
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(text))
        print(f"Extracted {filepath} to {outpath}")
    except Exception as e:
        print(f"Error extracting {filepath}: {e}")

if __name__ == "__main__":
    extract("THT2026_ThuyetminhSPST.docx", "sample_template.txt")
    extract("THTVKH-THT2026_ThuyetminhSPST.docx", "version1.txt")
