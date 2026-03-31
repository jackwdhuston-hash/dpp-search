"""
DPP Text Extractor
------------------
Reads every PDF in dpp_papers/ and extracts the plain text.
Saves one .txt file per paper into dpp_texts/
Run with: python3 dpp_extract.py
"""

import os
import pdfplumber

INPUT_DIR  = "dpp_papers"
OUTPUT_DIR = "dpp_texts"

def extract():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdfs = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.pdf')])
    total = len(pdfs)
    ok = 0
    failed = []

    print(f"Extracting text from {total} PDFs...\n")

    for i, filename in enumerate(pdfs, 1):
        pdf_path  = os.path.join(INPUT_DIR, filename)
        txt_path  = os.path.join(OUTPUT_DIR, filename.replace('.pdf', '.txt'))

        # Skip if already done
        if os.path.exists(txt_path) and os.path.getsize(txt_path) > 100:
            print(f"  [{i:3}/{total}] skip  {filename}")
            ok += 1
            continue

        try:
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text.strip())

            full_text = "\n\n".join(pages)

            if len(full_text) < 100:
                raise ValueError("Extracted text too short — may be a scanned image PDF")

            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(full_text)

            words = len(full_text.split())
            print(f"  [{i:3}/{total}] ok    {filename}  ({words:,} words)")
            ok += 1

        except Exception as e:
            print(f"  [{i:3}/{total}] FAIL  {filename}  — {e}")
            failed.append((filename, str(e)))

    print(f"\n--- Done ---")
    print(f"Extracted: {ok}")
    print(f"Failed:    {len(failed)}")

    if failed:
        print("\nFailed files:")
        for filename, reason in failed:
            print(f"  {filename}: {reason}")

    print(f"\nText files saved to: {os.path.abspath(OUTPUT_DIR)}/")

if __name__ == "__main__":
    extract()
