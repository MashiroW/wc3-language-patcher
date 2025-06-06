import re
from deep_translator import GoogleTranslator

def translate_fdf(english_fdf_template_path, language_fdf_path, output_path):
    """Translate FDF keys directly as a function with improved formatting"""
    # === Helpers ===
    def parse_fdf(file_path):
        # Read with UTF-8-sig to handle BOM
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
            
        # Extract header comment if present
        header_match = re.search(r'/\*(.*?)\*/', content, re.DOTALL)
        header = header_match.group(0).strip() + "\n\n" if header_match else ""
        
        # Extract StringList content
        stringlist_match = re.search(r'StringList\s*{([^}]*)}', content, re.DOTALL)
        if not stringlist_match:
            return {}, [], header, ""
            
        stringlist_content = stringlist_match.group(1).strip()
        entries = {}
        lines = []
        
        # Parse individual lines
        for line in stringlist_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'([A-Z0-9_]+)\s+"(.*)",', line)
            if match:
                key, value = match.groups()
                entries[key] = value
                lines.append(line)
        
        return entries, lines, header, stringlist_content

    # === Load files ===
    english_entries, english_lines, eng_header, _ = parse_fdf(english_fdf_template_path)
    french_entries, french_lines, fr_header, fr_content = parse_fdf(language_fdf_path)
    
    # Use English header if French header is empty
    header = fr_header if fr_header else eng_header

    # === Identify missing keys ===
    missing_keys = sorted(set(english_entries) - set(french_entries))
    translator = GoogleTranslator(source="en", target="fr")

    # === Translate and format missing lines ===
    translated_lines = []
    for key in missing_keys:
        english_text = english_entries[key]
        try:
            translated_text = translator.translate(english_text)
            # Replace problematic characters
            translated_text = translated_text.replace("ï»¿", "").strip()
        except Exception as e:
            print(f"Translation failed for key {key}: {e}")
            translated_text = english_text  # fallback
        line = f'    {key:<32}"{translated_text}", // Translated'
        translated_lines.append(line)

    # === Clean and format output ===
    # Combine existing and translated lines
    all_lines = french_lines + translated_lines
    
    # Remove duplicates while preserving order
    seen = set()
    unique_lines = []
    for line in all_lines:
        key_match = re.match(r'\s*([A-Z0-9_]+)', line)
        if key_match:
            key = key_match.group(1)
            if key not in seen:
                seen.add(key)
                unique_lines.append(line)
    
    # Create formatted StringList content
    formatted_content = "StringList {\n" + "\n".join(unique_lines) + "\n}"
    
    # Combine with header
    full_content = header + formatted_content

    # === Write output with proper encoding ===
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"  - ✅ Translation complete! Output saved to: {output_path}")
    return full_content

