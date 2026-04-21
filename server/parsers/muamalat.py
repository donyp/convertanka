import pdfplumber
import re

def clean_number(num_str):
    if not num_str:
        return 0.0
    
    val_str = num_str.strip().upper()
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

    try:
        return float(val_str)
    except ValueError:
        return 0.0

def parse_muamalat(pdf_path):
    data = []
    metadata = {
        "bank": "Bank Muamalat",
        "account_no": "Unknown",
        "period": "Unknown",
        "headers": ["Reference Number", "Transaction Date", "Effective Date", "Debit", "Credit", "Balance", "Description"]
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                acc_match = re.search(r"Account No\.\s*:\s*(\d+)", text)
                if acc_match: metadata["account_no"] = acc_match.group(1)
                period_match = re.search(r"Period\s*:\s*([\d\w\-\s]+)", text)
                if period_match: metadata["period"] = period_match.group(1).strip()

            words = page.extract_words()
            if not words: continue
            words.sort(key=lambda w: (w['top'], w['x0']))
            
            lines = []
            if words:
                current_line = [words[0]]
                for i in range(1, len(words)):
                    if abs(words[i]['top'] - current_line[-1]['top']) < 3:
                        current_line.append(words[i])
                    else:
                        lines.append(current_line)
                        current_line = [words[i]]
                lines.append(current_line)

            # Detect headers
            boundaries = {
                "REFERENCE": 0,
                "TRANSACTION": 150,
                "EFFECTIVE": 220,
                "DEBIT": 300,
                "CREDIT": 400,
                "BALANCE": 500,
                "DESCRIPTION": 640
            }
            for line in lines:
                combined = " ".join([w['text'].upper() for w in line])
                if "REFERENCE" in combined and "TRANSACTION" in combined:
                    for w in line:
                        txt = w['text'].upper()
                        if "REFERENCE" in txt: boundaries["REFERENCE"] = w['x0']
                        elif "TRANSACTION" in txt: boundaries["TRANSACTION"] = w['x0']
                        elif "EFFECTIVE" in txt: boundaries["EFFECTIVE"] = w['x0']
                        elif "DEBIT" in txt: boundaries["DEBIT"] = w['x0']
                        elif "CREDIT" in txt: boundaries["CREDIT"] = w['x0']
                        elif "BALANCE" in txt: boundaries["BALANCE"] = w['x0']
                        elif "DESCRIPTION" in txt: boundaries["DESCRIPTION"] = w['x0']
                    break

            current_row = None
            for line in lines:
                line_text = " ".join([w['text'] for w in line])
                if "REFERENCE NUMBER" in line_text.upper() or "TRANSACTION DATE" in line_text.upper(): continue
                
                has_date = False
                for w in line[:4]:
                    if re.match(r"\d{2}-[A-Za-z]{3}-\d{4}", w['text']):
                        has_date = True
                        break
                
                if has_date:
                    ref_list = []
                    tdate = ""
                    edate = ""
                    debit = ""
                    credit = ""
                    balance = ""
                    desc_list = []
                    
                    for w in line:
                        x = w['x0']
                        if x < boundaries["TRANSACTION"] - 10: ref_list.append(w['text'])
                        elif x < boundaries["EFFECTIVE"] - 10: tdate = w['text']
                        elif x < boundaries["DEBIT"] - 10: edate = w['text']
                        elif x < boundaries["CREDIT"] - 10: debit = w['text']
                        elif x < boundaries["BALANCE"] - 10: credit = w['text']
                        elif x < boundaries["DESCRIPTION"] - 10: balance = w['text']
                        else: desc_list.append(w['text'])
                    
                    # Strict Verification: The date must be in the Transaction/Effective date columns
                    if not tdate and not edate:
                        continue

                    ref_text = "".join(ref_list).strip()
                    desc_text = " ".join(desc_list).strip()
                    debit_val = clean_number(debit)
                    credit_val = clean_number(credit)
                    balance_val = clean_number(balance)
                    
                    # Extensive Junk filter
                    junk_keywords = ["COPYRIGHT", "DESCRIPTION", "PERIOD", "PERIODE", "PAGE", "ALL RIGHTS RESERVED", "ACCOUNT", "CURRENCY", "TOTAL", "SALDO AWAL", "SALDO AKHIR", " TO "]
                    if any(k in desc_text.upper() for k in junk_keywords) or any(k in ref_text.upper() for k in junk_keywords):
                        continue
                    
                    # Transaction Signature: must have Ref OR Mutation
                    if not ref_text and not debit_val and not credit_val:
                        continue

                    if current_row: data.append(current_row)
                    current_row = [ref_text, tdate, edate, debit_val, credit_val, balance_val, desc_text]
                
                elif current_row:
                    desc_cont = []
                    for w in line:
                        if w['x0'] >= boundaries["DESCRIPTION"] - 10: desc_cont.append(w['text'])
                    if desc_cont:
                        content = " ".join(desc_cont)
                        # Don't append junk to descriptions
                        junk_keywords = ["COPYRIGHT", "PAGE", "ALL RIGHTS RESERVED", "ACCOUNT", "CURRENCY", " TO ", "PERIODE"]
                        if not any(k in content.upper() for k in junk_keywords):
                            current_row[6] += " " + content
            
            if current_row: 
                # Final validation: must have Date and either Ref or Mutation
                if current_row[1] and (current_row[0] or current_row[3] or current_row[4]):
                    data.append(current_row)
            current_row = None

    return data, metadata
