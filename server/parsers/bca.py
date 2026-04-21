import pdfplumber
import re

def clean_number(num_str):
    """
    Converts number strings to float, handling both ID (1.234,56) and US (1,234.56) formats.
    """
    if not num_str:
        return 0.0, False
    
    val_str = num_str.strip().upper()
    is_db = 'DB' in val_str
    val_str = val_str.replace('DB', '').replace('CR', '').strip()
    
    if not val_str:
        return 0.0, is_db

    # Heuristic to detect ID vs US format
    # If there's a comma that looks like a decimal separator (comma followed by 2 digits at end)
    if re.search(r',\d{2}$', val_str):
        # ID format: 1.234,56 -> 1234.56
        val_str = val_str.replace('.', '').replace(',', '.')
    elif re.search(r'\.\d{2}$', val_str):
        # US format: 1,234.56 -> 1234.56
        val_str = val_str.replace(',', '')
    else:
        # Fallback: remove all non-numeric except dot/comma and try to guess
        # Remove thousands separators
        if val_str.count(',') > 0 and val_str.count('.') > 0:
            if val_str.find(',') < val_str.find('.'):
                val_str = val_str.replace(',', '') # US
            else:
                val_str = val_str.replace('.', '').replace(',', '.') # ID
        elif val_str.count(',') > 1:
            val_str = val_str.replace(',', '') # Likely US thousands
        elif val_str.count('.') > 1:
            val_str = val_str.replace('.', '') # Likely ID thousands

    try:
        return float(val_str), is_db
    except ValueError:
        return 0.0, is_db

def parse_bca(pdf_path):
    data = []
    metadata = {
        "bank": "BCA",
        "account_no": "Unknown",
        "period": "Unknown",
        "headers": ["Tanggal", "Keterangan", "CBG", "Mutasi", "DB/CR Flag", "Saldo"]
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            width = float(page.width)
            text = page.extract_text()
            if text:
                acc_match = re.search(r"NO\. REKENING\s*:\s*(\d+)", text)
                if acc_match: metadata["account_no"] = acc_match.group(1)
                period_match = re.search(r"PERIODE\s*:\s*([A-Za-z\s\d]+)", text)
                if period_match: metadata["period"] = period_match.group(1).strip()

            words = page.extract_words()
            if not words: continue
            words.sort(key=lambda w: (w['top'], w['x0']))
            
            lines = []
            current_line = [words[0]]
            for i in range(1, len(words)):
                if abs(words[i]['top'] - current_line[-1]['top']) < 3:
                    current_line.append(words[i])
                else:
                    lines.append(current_line)
                    current_line = [words[i]]
            lines.append(current_line)

            # Detect column boundaries from headers
            boundaries = {
                "TANGGAL": 30,
                "KETERANGAN": 60,
                "CBG": 320,
                "MUTASI": 400,
                "SALDO": 530
            }
            
            for line in lines:
                combined = " ".join([w['text'].upper() for w in line])
                if "TANGGAL" in combined and "KETERANGAN" in combined:
                    for w in line:
                        txt = w['text'].upper()
                        if "TANGGAL" in txt: boundaries["TANGGAL"] = w['x0']
                        elif "KETERANGAN" in txt: boundaries["KETERANGAN"] = w['x0']
                        elif "CBG" in txt: boundaries["CBG"] = w['x0']
                        elif "MUTASI" in txt: boundaries["MUTASI"] = w['x0']
                        elif "SALDO" in txt: boundaries["SALDO"] = w['x0']
                    break

            current_row = None
            for line in lines:
                line_text = " ".join([w['text'] for w in line])
                if "TANGGAL" in line_text.upper() or "KETERANGAN" in line_text.upper(): continue
                if any(x in line_text.upper() for x in ["MUTASI CR", "MUTASI DB", "SALDO AKHIR"]): continue
                
                # Use boundaries for mapping
                first_word = line[0]
                if first_word['x0'] < boundaries["KETERANGAN"] + 20 and re.match(r"\d{2}/\d{2}", first_word['text']):
                    if current_row: data.append(current_row)
                    
                    tanggal = first_word['text']
                    keterangan = []
                    cbg = ""
                    mutasi_parts = []
                    saldo_parts = []
                    
                    for w in line[1:]:
                        x = w['x0']
                        # More generous boundaries
                        if x < boundaries["CBG"] - 15: keterangan.append(w['text'])
                        elif x < boundaries["MUTASI"] - 15: cbg = w['text']
                        elif x < boundaries["SALDO"] - 15: mutasi_parts.append(w['text'])
                        else: saldo_parts.append(w['text'])
                    
                    mutasi_val, is_db = clean_number(" ".join(mutasi_parts))
                    saldo_val, _ = clean_number(" ".join(saldo_parts))
                    current_row = [tanggal, " ".join(keterangan), cbg, mutasi_val, "DB" if is_db else "CR", saldo_val]
                
                elif current_row:
                    desc_words = []
                    for w in line:
                        x = w['x0']
                        if x < boundaries["CBG"] - 15: desc_words.append(w['text'])
                        elif boundaries["MUTASI"] - 25 <= x < boundaries["SALDO"] - 15:
                            m_val, m_db = clean_number(w['text'])
                            if m_val:
                                current_row[3] = m_val
                                current_row[4] = "DB" if m_db else "CR"
                    if desc_words:
                        content = " ".join(desc_words)
                        if not any(x in content.upper() for x in ["SALDO", "HALAMAN"]):
                            current_row[1] += " " + content
            
            if current_row: data.append(current_row)
            current_row = None

    return data, metadata
