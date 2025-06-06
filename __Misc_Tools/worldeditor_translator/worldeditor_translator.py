import re
import warnings
from time import sleep
from transformers import pipeline, set_seed
from pathlib import Path

# Disable unnecessary warnings
warnings.filterwarnings("ignore", message=".*sacremoses.*")

class WorldEditorTranslator:
    def __init__(self, region_code, progress_callback=None):
        self.region_code = region_code
        self.progress_callback = progress_callback
        self.lang_code = self.region_to_language_code(region_code)
        self.translator = self._initialize_translator()
    
    def _initialize_translator(self):
        """Load translation model with public alternatives for problematic languages"""
        # Updated model map with working public models
        model_map = {
            'fr': "Helsinki-NLP/opus-mt-en-fr",
            'de': "Helsinki-NLP/opus-mt-en-de",
            'es': "Helsinki-NLP/opus-mt-en-es",
            'it': "Helsinki-NLP/opus-mt-en-it",
            'ru': "Helsinki-NLP/opus-mt-en-ru",
            'zh': "Helsinki-NLP/opus-mt-en-zh",
            'ko': "facebook/m2m100_418M",  # Public multi-lingual model
            'cs': "Helsinki-NLP/opus-mt-en-cs",
            'pl': "facebook/m2m100_418M"   # Public multi-lingual model
        }

        lang_name = self.lang_code.upper()
        self.progress_callback(f"  | ⚙️ Initializing translation model for {lang_name}...")
        
        # Use the appropriate model
        model_name = model_map.get(self.lang_code, "Helsinki-NLP/opus-mt-en-fr")
        
        # Special initialization for multi-lingual model
        if model_name == "facebook/m2m100_418M":
            from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
            
            # Language code mapping for m2m100
            lang_targets = {
                'ko': 'ko',
                'pl': 'pl'
            }
            
            target_lang = lang_targets.get(self.lang_code, 'fr')
            
            self.progress_callback(f"  |   | Using multi-lingual model for {lang_name} → {target_lang}")
            
            # Initialize model components
            model = M2M100ForConditionalGeneration.from_pretrained(model_name)
            tokenizer = M2M100Tokenizer.from_pretrained(model_name)
            
            # Create a custom translation function
            def translate_fn(text):
                tokenizer.src_lang = "en"
                encoded = tokenizer(text, return_tensors="pt")
                generated_tokens = model.generate(
                    **encoded, 
                    forced_bos_token_id=tokenizer.get_lang_id(target_lang)
                )
                return tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
            
            return translate_fn
        
        # Standard pipeline for other languages
        return pipeline(
            "translation",
            model=model_name,
            device="cpu"
        )
    
    def region_to_language_code(self, region_code):
        """Convert region codes to language codes"""
        region_code = region_code.lower()
        conversions = {
            'cscz': 'cs',    # Czech
            'kokr': 'ko',    # Korean
            'plpl': 'pl',    # Polish
            'ruru': 'ru',    # Russian
            'zhtw': 'zh-tw', # Traditional Chinese
        }
        return conversions.get(region_code, region_code[:2])
    
    def translate_text(self, text):
        """Handle translation with model-specific logic"""
        if not text.strip() or self.translator is None:
            return text
        
        try:
            # Handle different translator types
            if callable(self.translator):
                # Custom translation function
                return self.translator(text)
            else:
                # Standard pipeline
                return self.translator(text, max_length=512)[0]['translation_text']
        except Exception as e:
            error_msg = f"Translation failed: {str(e)}"
            if self.progress_callback:
                self.progress_callback(error_msg)
            return f"[AUTO] {text}"
    
    def parse_localization_file(self, file_path):
        """Parse file into (variables, lines) with structure preserved"""
        variables = set()
        lines = []
        total_lines = 0
        
        # First count total lines
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                total_lines += 1
        
        # Reread and parse with progress
        processed = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                # Flexible matching for variables
                if match := re.match(r'^\s*([A-Z0-9_]+)\s*=.*$', line):
                    var = match.group(1)
                    variables.add(var)
                lines.append(line)
                
                processed += 1
                if self.progress_callback and processed % 10 == 0:
                    percent = int(processed / total_lines * 100)
                    self.progress_callback(f"  |   |   |  Progress: {processed}/{total_lines} ({percent}%)")
        
        return variables, lines

    def accurate_parse(self, lines, label=""):
        """Perform precise parsing of localization file lines"""
        vars = set()
        total = len(lines)
        
        for i, line in enumerate(lines):
            # More robust matching that handles various formatting cases
            if match := re.match(r'^\s*([A-Z0-9_]+)\s*=.*$', line):
                var = match.group(1)
                vars.add(var)
            
            # Progress reporting
            if self.progress_callback and i % 10 == 0:
                percent = int((i + 1) / total * 100)
                self.progress_callback(f"  |   |  🔍 Scan ({label}): {i+1}/{total} ({percent}%)")
        
        return vars

    def process_file(self, template_path, target_path):
        """Main processing function with verification and progress callbacks"""
        template_path = Path(template_path)
        target_path = Path(target_path)
        
        # Parse files with progress
        self.progress_callback("  |   |  📝 Analyzing template file...")
        template_vars, template_lines = self.parse_localization_file(template_path)
        
        self.progress_callback("  |   |  📝 Analyzing target file...")
        target_vars, target_lines = self.parse_localization_file(target_path)

        self.progress_callback("  |   |  🔍 Precise scan of target file...")
        target_vars = self.accurate_parse(target_lines, "target")
        
        missing_vars = template_vars - target_vars
        extra_vars = target_vars - template_vars
        self.progress_callback(f"  |   |  🔍 Precise scan: {len(missing_vars)} missing, {len(extra_vars)} extra")
        
        # Create new content for target file
        new_lines = []
        var_order = []
        total_template = len(template_lines)
        for i, line in enumerate(template_lines):
            if match := re.match(r'^\s*([A-Z0-9_]+)\s*=.*$', line):
                var_order.append(match.group(1))
            if self.progress_callback and i % 10 == 0:
                percent = int((i + 1) / total_template * 100)
                self.progress_callback(f"  |  |  📋 Preparing variable order: {i+1}/{total_template} ({percent}%)")
        
        # Build new file content
        output_vars = set()
        total_target = len(target_lines)
        for i, line in enumerate(target_lines):
            if match := re.match(r'^\s*([A-Z0-9_]+)\s*=.*$', line):
                var = match.group(1)
                if var in template_vars:
                    new_lines.append(line)
                    output_vars.add(var)
            else:
                new_lines.append(line)
                
            if self.progress_callback and i % 10 == 0:
                percent = int((i + 1) / total_target * 100)
                self.progress_callback(f"  |   |  📝 Building new content: {i+1}/{total_target} ({percent}%)")
        
        # Add missing variables with translations
        added_count = 0
        total_missing = len(missing_vars)
        
        self.progress_callback(f"  |   |  🌍 Translating {total_missing} missing variables...")
        
        for i, var in enumerate(var_order):
            if var not in output_vars and var in missing_vars:
                # Find original line in template
                original_line = next((line for line in template_lines 
                                    if re.match(rf'^\s*{var}\s*=.*$', line)), None)
                if original_line:
                    if match := re.match(r'^\s*[A-Z0-9_]+\s*=\s*"(.*)"\s*$', original_line):
                        text_to_translate = match.group(1)
                        # Progress callback
                        translated = self.translate_text(text_to_translate)
                        new_lines.append(f'{var}="{translated}"')
                    else:
                        new_lines.append(original_line)
                    added_count += 1
                    output_vars.add(var)
                
                if self.progress_callback and (i % 1 == 0 or i == total_missing - 1):
                    percent = int((i + 1) / total_missing * 100)
                    self.progress_callback(f"  |   |  🌍 Translation: {i+1}/{total_missing} ({percent}%)")
        
        # Write new file
        self.progress_callback(f"  |   |  💾 Writing updated file: {target_path.name}")
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines) + '\n')
        
        # Final verification
        # self.progress_callback("  |   |  🔍 Final verification...")
        final_vars = self.accurate_parse(new_lines, "final")
        remaining_missing = template_vars - final_vars
        remaining_extra = final_vars - template_vars
        
        summary = [
            f"  |   |  📊 Final results:",
            f"  |   |   |  Added {added_count} variables",
            f"  |   |   |  Removed {len(extra_vars)} extra variables",
            f"  |   |   |  Remaining missing: {len(remaining_missing)}",
            f"  |   |   |  Remaining extra: {len(remaining_extra)}"
        ]
        
        if self.progress_callback:
            self.progress_callback("\n".join(summary))
        
        if remaining_missing:
            missing_list = "\n".join([f"  {var}" for var in sorted(remaining_missing)])
            if self.progress_callback:
                self.progress_callback(f"  |   |  ⚠️ Missing variables (manual check needed):\n{missing_list}")
        
        if remaining_extra:
            extra_list = "\n".join([f"  {var}" for var in sorted(remaining_extra)])
            if self.progress_callback:
                self.progress_callback(f"  |   |  ⚠️ Unexpected extra variables:\n{extra_list}")  
