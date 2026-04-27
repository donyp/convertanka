import pdfplumber
import re

def clean_number(num_str):
    if not num_str:
        return 0.0
    
    val_str = str(num_str).strip().upper()
    val_str = val_str.replace('DB', '').replace('CR', '').strip()
    
    if not val_str: return 0.0

    if re.search(r',\d{2}$', val_str):
        val_str = val_str.replace('.', '').replace(',', '.')
    elif re.search(r'\.\d{2}$', val_str):
        val_str = val_str.replace(',', '')
    else:
        if val_str.count(',') > 0 and val_str.count('.') > 0:
            if val_str.find(',') < val_str.find('.'): val_str = val_str.replace(',', '')
            else: val_str = val_str.replace('.', '').replace(',', '.')
        elif val_str.count(',') > 1: val_str = val_str.replace(',', '')
        elif val_str.count('.') > 1: val_str = val_str.replace('.', '')

    try: return float(val_str)
    except ValueError:
        clean = re.sub(r'[^\d.]', '', val_str)
        try: return float(clean)
        except: return 0.0

def parse_bsi(pdf_path):
    data = []
    metadata = {
        "bank": "Bank BSI",
        "account_no": "Unknown",
        "period": "Unknown",
        "headers": ["Date", "FT Number", "Deskripsi", "Mata Uang", "Jumlah", "DB", "CR", "Saldo"]
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                acc_match = re.search(r"Rekening\s*:\s*(\d+)", text)
                if acc_match: metadata["account_no"] = acc_match.group(1)
                period_match = re.search(r"Date\s*:\s*([\d\w\-\s]+)", text)
                if period_match: metadata["period"] = period_match.group(1).strip()

            # Attempt to extract explicit table first (New BSI Format)
            tables = page.extract_tables()
            processed_from_table = False
            for table in tables:
                if not table or not table[0]: continue
                header_row = [str(cell).replace('\n', ' ').strip().upper() for cell in table[0] if cell]
                if "TANGGAL" in header_row and "MUTASI" in header_row and "SALDO" in header_row:
                    processed_from_table = True
                    headers = [str(c).replace('\n', ' ').strip().upper() if c else "" for c in table[0]]
                    try:
                        date_idx = headers.index("TANGGAL")
                        try: time_idx = headers.index("TRX TIME")
                        except: time_idx = -1
                        dk_idx = headers.index("D/K")
                        mutasi_idx = headers.index("MUTASI")
                        saldo_idx = headers.index("SALDO")
                        desc_idx = headers.index("KETERANGAN")
                        try: trxid_idx = headers.index("TRXID")
                        except: trxid_idx = -1
                    except ValueError:
                        processed_from_table = False
                        break # Header mismatch, fallback
                    
                    for row in table[1:]:
                        if not row or not row[date_idx]: continue
                        raw_date = str(row[date_idx]).replace('\n', '').strip()
                        raw_time = str(row[time_idx]).replace('\n', '').strip().replace(".", ":") if time_idx != -1 else ""
                        
                        if len(raw_date) == 8 and raw_date.isdigit():
                            dt = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                        else:
                            dt = raw_date
                        if raw_time:
                            dt = f"{dt} {raw_time}"
                            
                        ft = str(row[trxid_idx]).replace('\n', ' ').strip() if trxid_idx != -1 else ""
                        desc = str(row[desc_idx]).replace('\n', ' ').strip()
                        dk = str(row[dk_idx]).strip().upper()
                        mutasi = clean_number(row[mutasi_idx])
                        saldo = clean_number(row[saldo_idx])
                        
                        db = "DB" if dk == "D" else ""
                        cr = "CR" if dk == "K" else ""
                        
                        # Fix metadata for alternative DK format
                        if dk == "D" and not db: db = "DB"
                        if dk == "K" and not cr: cr = "CR"
                        
                        data.append([dt.strip(), ft, desc, "IDR", mutasi, db, cr, saldo])
            
            if processed_from_table:
                continue

            all_words = page.extract_words()
            if not all_words: continue
            
            # 1. Word Pre-splitting for Fused Words
            words = []
            for w in all_words:
                txt = w['text']
                
                # Case: Time + FT fused (e.g. 11:07:25FT...)
                match_ft = re.match(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})(FT.*)", txt)
                if match_ft:
                    w1 = w.copy(); w1['text'] = match_ft.group(1); words.append(w1)
                    w2 = w.copy(); w2['text'] = match_ft.group(2); w2['x0'] += 50; words.append(w2)
                    continue

                # Case: Amount + DB/CR fused
                match_amt = re.match(r"([\d\.,]+)(DB|CR)$", txt)
                if match_amt:
                    w1 = w.copy(); w1['text'] = match_amt.group(1); words.append(w1)
                    w2 = w.copy(); w2['text'] = match_amt.group(2); w2['x0'] += 20; words.append(w2)
                    continue
                
                match_desc_amt = re.match(r"([A-Za-z]+)([\d\.,]+DB|[\d\.,]+CR)?$", txt)
                if match_desc_amt and match_desc_amt.group(2):
                    w1 = w.copy(); w1['text'] = match_desc_amt.group(1); words.append(w1)
                    w2 = w.copy(); w2['text'] = match_desc_amt.group(2); w2['x0'] += 50; words.append(w2)
                    continue

                words.append(w)

            # 2. Robust Center-line Grouping
            words.sort(key=lambda w: w['x0'])
            words.sort(key=lambda w: w['top']) # stable sort
            
            lines = []
            if words:
                curr_line = [words[0]]
                line_center_y = (words[0]['top'] + words[0]['bottom']) / 2
                for i in range(1, len(words)):
                    w = words[i]
                    wy = (w['top'] + w['bottom']) / 2
                    # 6 points tolerance for being on the same line
                    if abs(wy - line_center_y) < 6:
                        curr_line.append(w)
                    else:
                        curr_line.sort(key=lambda x: x['x0'])
                        lines.append(curr_line)
                        curr_line = [w]
                        line_center_y = (w['top'] + w['bottom']) / 2
                curr_line.sort(key=lambda x: x['x0'])
                lines.append(curr_line)

            # 3. Dynamic boundaries and extraction
            current_row = None
            for line in lines:
                l_text = " ".join([w['text'] for w in line])
                if "FT NUMBER" in l_text.upper() or "DESKRIPSI" in l_text.upper(): continue
                
                # Check for row start: Any Date or Time representation
                is_row_start = False
                for w in line[:4]:
                    if re.match(r"\d{4}-\d{2}-\d{2}", w['text']) or re.search(r"\d{2}:\d{2}:\d{2}FT", w['text']):
                        is_row_start = True; break
                
                if is_row_start:
                    if current_row:
                        data.append(current_row)
                    
                    dt_p = []; ft = ""; ds_p = []; curr = ""; amt = ""; db = ""; cr = ""; bal = ""
                    numbers_found = []
                    
                    for w in line:
                        t = w['text']; x = w['x0']
                        
                        if "FT" in t.upper() and not re.match(r"^\d{4}-\d{2}-\d{2}$", t):
                            sp = re.split(r"(FT.*)", t)
                            if sp[0]: 
                                if re.search(r"\d{2}:\d{2}:\d{2}", sp[0]): dt_p.append(sp[0])
                                else: ds_p.append(sp[0])
                            if len(sp) > 1: ft = sp[1]
                            continue
                        
                        if re.match(r"^\d{4}-\d{2}-\d{2}", t) or re.match(r"^\d{2}:\d{2}:\d{2}", t):
                            dt_p.append(t); continue
                        
                        # Identify numbers (Amounts and Balances)
                        amt_match = re.search(r"([\d\.,]+)(DB|CR)?$", t)
                        if amt_match and len(t) > 3 and x > 400: # Only on the right half
                            v = amt_match.group(1); m = amt_match.group(2)
                            numbers_found.append((x, v, m))
                            if t[:amt_match.start()]: ds_p.append(t[:amt_match.start()])
                            continue

                        if t == "IDR": curr = "IDR"; continue
                        if t == "DB": db = "DB"; continue
                        if t == "CR": cr = "CR"; continue
                        
                        ds_p.append(t)

                    # Determine Amount vs Balance purely by left-to-right order (x coordinate)
                    numbers_found.sort(key=lambda p: p[0])
                    if len(numbers_found) == 1:
                        # Fallback heuristic if only one is present
                        nx, nv, nm = numbers_found[0]
                        if nx > 580:
                            bal = nv; db = nm if nm == "DB" else db; cr = nm if nm == "CR" else cr
                        else:
                            amt = nv; db = nm if nm == "DB" else db; cr = nm if nm == "CR" else cr
                    elif len(numbers_found) >= 2:
                        # Index -2 is Amount, Index -1 is Balance (to handle stray numbers safely)
                        amt_x, amt, nm_amt = numbers_found[-2]
                        bal_x, bal, nm_bal = numbers_found[-1]
                        
                        if nm_amt == "DB": db = "DB"
                        if nm_amt == "CR": cr = "CR"
                        if nm_bal == "DB": db = "DB"
                        if nm_bal == "CR": cr = "CR"

                    current_row = [
                        " ".join(dt_p).strip(), ft.strip(), " ".join(ds_p).strip(), curr,
                        clean_number(amt), db, cr, clean_number(bal)
                    ]
                elif current_row:
                    # Append description lines efficiently
                    tmp_ds = []
                    numbers_found = []
                    
                    for w in line:
                        t = w['text']; x = w['x0']
                        if any(k in t.upper() for k in ["PAGE", "COPYRIGHT", "REKENING", "DATE", "PERIODE"]): continue
                        
                        m = re.search(r"([\d\.,]+)(DB|CR)?$", t)
                        if m and len(t) > 3 and x > 400:
                            v = m.group(1); mark = m.group(2)
                            numbers_found.append((x, v, mark))
                            continue
                        
                        # Only add to description if it's generally in the desc box (x < ~450)
                        if x < 450: tmp_ds.append(t)
                    
                    if tmp_ds:
                        current_row[2] += " " + " ".join(tmp_ds)
                    
                    if numbers_found:
                        numbers_found.sort(key=lambda p: p[0])
                        # Generally multi-line descriptions only have an Amount missing
                        if current_row[4] == 0:
                            n = numbers_found[0]
                            current_row[4] = clean_number(n[1])
                            if n[2] == "DB": current_row[5] = "DB"
                            if n[2] == "CR": current_row[6] = "CR"
            
            if current_row: data.append(current_row)

    # 4. Global Validation Pass
    for row in data:
        if not row[5] and not row[6]:
            if row[2].upper().endswith(" DB"): row[5] = "DB"; row[2] = row[2][:-3].strip()
            elif row[2].upper().endswith(" CR"): row[6] = "CR"; row[2] = row[2][:-3].strip()

    clean_data = [r for r in data if r[0] and (r[2] or r[4] != 0)]
    return clean_data, metadata
