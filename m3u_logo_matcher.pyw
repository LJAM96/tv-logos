import os
import tkinter as tk
from tkinter import filedialog, messagebox, Text, Scrollbar, Frame, ttk
from tkinter.ttk import Progressbar

# Set dark mode colors
DARK_BG = "#2d2d2d"
DARK_TEXT = "#ffffff"
DARK_BUTTON = "#444444"
DARK_ACCENT = "#007acc"  # Blue accent color
DARK_FIELD = "#3d3d3d"
LOG_BG = "#1e1e1e"
LOG_TEXT = "#d4d4d4"

# Function to parse M3U and extract tvg-name and group-title
def parse_m3u(m3u_path):
    channels = []
    with open(m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('#EXTINF'):
                tvg_name = None
                group_title = None
                # Extract tvg-name and group-title
                if 'tvg-name="' in line:
                    tvg_name = line.split('tvg-name="')[1].split('"')[0]
                if 'group-title="' in line:
                    group_title = line.split('group-title="')[1].split('"')[0]
                channels.append({'tvg_name': tvg_name, 'group_title': group_title})
    return channels

# Function to match channel with logo
def match_logo(group_title, tvg_name, countries_dir, debug_callback=None):
    if not tvg_name:
        if debug_callback:
            debug_callback(f"Missing tvg_name for group_title='{group_title}'")
        return ''
        
    # Import regex at the top level
    import re
        
    # Extract country code from the beginning of group_title
    # Examples: "UK Entertainment", "US Sports", "DE Movies"
    country_code = ""
    if group_title:
        parts = group_title.strip().split(" ", 1)
        if parts:
            country_code = parts[0].lower()  # Get the first part as potential country code
            if debug_callback:
                debug_callback(f"Extracted potential country code: '{country_code}' from '{group_title}'")
    
    # Map common country codes to folder names
    country_map = {
        # Country codes to folder names mapping
        'uk': 'united-kingdom',
        'gb': 'united-kingdom',
        'us': 'united-states',
        'usa': 'united-states',
        'de': 'germany',
        'ger': 'germany',
        'fr': 'france',
        'es': 'spain',
        'it': 'italy',
        'jp': 'japan',
        'ca': 'canada',
        'au': 'australia',
        'br': 'brazil',
        'mx': 'mexico',
        'nl': 'netherlands',
        'pl': 'poland',
        'ru': 'russia',
        'se': 'sweden',
        'za': 'south-africa',
        'cn': 'china',
        'in': 'india',
        'ar': 'argentina',
        'ch': 'switzerland',
        'at': 'austria',
        'be': 'belgium',
        'dk': 'denmark',
        'fi': 'finland',
        'no': 'norway',
        'pt': 'portugal',
        'tr': 'turkey',
        'gr': 'greece',
        'ie': 'ireland',
        'nz': 'new-zealand',
        'sg': 'singapore',
        'th': 'thailand',
        'ae': 'united-arab-emirates',
        'int': 'international',
        'eu': 'world-europe',
        'asia': 'world-asia',
        'africa': 'world-africa',
        'latam': 'world-latin-america',
        'me': 'world-middle-east'
    }
    
    # Process tvg_name for matching - we'll need this for all searches
    def normalize_name(name):
        # Make lowercase, replace spaces/underscores with hyphens
        return re.sub(r'[^a-z0-9]', '-', name.strip().lower())
    
    # Alternative normalizations for common formats
    def get_normalized_variations(name):
        if not name:
            return []
            
        variations = []
        name_lower = name.lower()
        
        # Original normalization
        norm1 = normalize_name(name)
        variations.append(norm1)
        
        # Special cases for channel numbers in names
        # Convert "ITV2" to "itv-2" and "4Seven" to "4-seven"
        number_pattern = re.compile(r'([a-z]+)(\d+)', re.IGNORECASE)
        match = number_pattern.search(name)
        if match:
            channel_name = match.group(1).lower()
            channel_number = match.group(2)
            variations.append(f"{channel_name}-{channel_number}")
        
        # For names starting with numbers like "4Seven"
        number_prefix_pattern = re.compile(r'(\d+)([A-Z][a-z]+)')
        match = number_prefix_pattern.search(name)
        if match:
            number = match.group(1)
            text = match.group(2).lower()
            variations.append(f"{number}-{text}")
        
        # Handle special cases like "Five USA" -> "5usa"
        if "five" in name_lower or "5" in name_lower:
            variations.append("5" + re.sub(r'[^a-z0-9]', '', name_lower.replace("five", "")))
            
        # Add hyphenated version
        hyphenated = re.sub(r'(\w)([A-Z])', r'\1-\2', name).lower()
        if hyphenated != name_lower and hyphenated not in variations:
            variations.append(hyphenated)
            
        # Add fully expanded version
        expanded = name_lower.replace(" ", "-")
        if expanded not in variations:
            variations.append(expanded)
            
        # Remove the articles from the name (the, a, an)
        if name_lower.startswith("the "):
            variations.append(normalize_name(name_lower[4:]))
        
        return variations
    
    # Get all normalized variations of the channel name
    tvg_variations = get_normalized_variations(tvg_name)
    tvg_norm = tvg_variations[0] if tvg_variations else ""
    
    # Break tvg_name into words for partial matching
    tvg_words = [w for w in re.split(r'[^a-zA-Z0-9]', tvg_name.lower()) if w and len(w) > 1]
    
    # Flag to indicate if we should search all country folders
    search_all = False
    
    # Build a list of potential country folder names to check
    country_variations = []
    
    # 1. Try exact folder name from country code mapping
    if country_code in country_map:
        country_variations.append(country_map[country_code])
        if debug_callback:
            debug_callback(f"Mapped country code '{country_code}' to folder '{country_map[country_code]}'")
    
    # 2. Try using the original group_title as a folder name
    if group_title:
        norm_country = group_title.strip().lower().replace(' ', '-').replace('_', '-')
        if norm_country not in country_variations:
            country_variations.append(norm_country)
        
        # Add version without special characters
        clean_country = re.sub(r'[^a-z0-9]', '-', group_title.lower())
        if clean_country not in country_variations:
            country_variations.append(clean_country)
    
    # 3. Always search all folders as a fallback
    search_all = True
    all_countries = []
    try:
        for folder in [f for f in os.listdir(countries_dir) if os.path.isdir(os.path.join(countries_dir, f))]:
            all_countries.append(folder)
        if not country_variations:
            if debug_callback:
                debug_callback(f"No specific country identified. Will check all {len(all_countries)} country folders")
    except Exception as e:
        if debug_callback:
            debug_callback(f"Error listing country folders: {str(e)}")
    
    # Function to search for matching logo in a specific country folder
    def find_logo_in_folder(country_path, country_name):
        if not os.path.isdir(country_path):
            return None
            
        if debug_callback:
            debug_callback(f"Checking country folder: {country_path}")
            debug_callback(f"Looking for normalized channel variations: {tvg_variations}")
        
        try:
            files = os.listdir(country_path)
            # Sort files to prioritize shorter filenames (often main logos)
            files.sort(key=len)
            
            # First try country-specific patterns (e.g., itv-2-uk.png)
            country_suffix = f"-{country_code}"
            
            # STAGE 1: Try exact filename match with any variation
            for variation in tvg_variations:
                for fname in files:
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Check different patterns:
                    # 1. Exact match: "itv-2" == "itv-2"
                    # 2. With country suffix: "itv-2-uk" 
                    if (base_name == variation or 
                        base_name == f"{variation}{country_suffix}" or
                        variation == base_name.replace(f"{country_suffix}", "")) and \
                        any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        if debug_callback:
                            debug_callback(f"EXACT VARIATION MATCH: {fname} (matched {variation})")
                        return os.path.join(country_path, fname)
            
            # STAGE 2: Try if filename starts with any variation
            for variation in tvg_variations:
                for fname in files:
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    if (base_name.startswith(variation) or variation.startswith(base_name)) and \
                        any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        if debug_callback:
                            debug_callback(f"PREFIX VARIATION MATCH: {fname} (matched {variation})")
                        return os.path.join(country_path, fname)
            
            # STAGE 3: Try word matching
            if tvg_words:
                # Find files where all significant words from tvg_name appear in order
                for fname in files:
                    fname_lower = fname.lower()
                    if not any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        continue
                        
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Check if all words appear in the filename in the right order
                    all_words_found = True
                    last_pos = 0
                    for word in tvg_words:
                        if len(word) > 1:  # Only consider meaningful words
                            pos = base_name.find(word, last_pos)
                            if pos == -1:
                                all_words_found = False
                                break
                            last_pos = pos + len(word)
                    
                    if all_words_found:
                        if debug_callback:
                            debug_callback(f"WORDS ORDER MATCH: {fname}")
                        return os.path.join(country_path, fname)
                
                # STAGE 4: Calculate similarity scores
                best_match = None
                best_score = 0
                
                for fname in files:
                    if not any(fname.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        continue
                        
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Count words from tvg_name that appear in the filename
                    score = 0
                    
                    # Check if any variation appears in the filename
                    for variation in tvg_variations:
                        if variation in base_name:
                            score += len(variation) * 2  # Double points for variation matches
                            break
                    
                    # Count word matches
                    for word in tvg_words:
                        if word in base_name:
                            # Longer words get higher scores
                            score += len(word)
                    
                    # Bonus if first word matches (channel names often start the same)
                    if tvg_words and tvg_words[0] in base_name:
                        score += 5
                    
                    # Huge bonus if country code appears in the filename
                    if country_code and f"-{country_code}" in base_name:
                        score += 10
                        
                    # Penalize very different lengths
                    length_diff = abs(len(base_name) - len(tvg_norm))
                    score -= min(length_diff, 10)  # Cap the penalty
                    
                    if score > best_score:
                        best_score = score
                        best_match = fname
                
                # Consider a match good if score is above threshold
                if best_match and best_score > 5:
                    if debug_callback:
                        debug_callback(f"BEST MATCH (score {best_score}): {best_match}")
                    return os.path.join(country_path, best_match)
                    
            # Try default logos
            for default_name in [f"{country_name}.png", "flag.png", "logo.png"]:
                default_path = os.path.join(country_path, default_name)
                if os.path.exists(default_path):
                    if debug_callback:
                        debug_callback(f"Using default logo: {default_name}")
                    return default_path
                    
        except Exception as e:
            if debug_callback:
                debug_callback(f"Error searching in {country_path}: {str(e)}")
                
        return None
    
    # First search in the most likely country folders
    for country_name in country_variations:
        country_path = os.path.join(countries_dir, country_name)
        result = find_logo_in_folder(country_path, country_name)
        if result:
            return result
    
    # If no match or told to search all, try all country folders
    if search_all:
        if debug_callback:
            debug_callback("Searching all country folders as fallback...")
            
        # Try specific countries first based on common patterns in the tvg_name
        priority_countries = []
        
        # Look for country hints in the channel name
        for suffix in ['-uk', '-us', '-ca', '-au', '-jp', '-de', '-fr', '-it', '-es']:
            if any(variation.endswith(suffix) for variation in tvg_variations):
                country_code_hint = suffix[1:]  # Remove the '-'
                if country_code_hint in country_map:
                    priority_countries.append(country_map[country_code_hint])
                    if debug_callback:
                        debug_callback(f"Found country hint in channel name: {suffix} -> {country_map[country_code_hint]}")
        
        # Try priority countries first
        for country_name in priority_countries:
            if country_name not in country_variations:  # Skip if already searched
                country_path = os.path.join(countries_dir, country_name)
                result = find_logo_in_folder(country_path, country_name)
                if result:
                    return result
        
        # Last resort - try ALL countries
        for country_name in all_countries:
            if country_name not in country_variations and country_name not in priority_countries:
                country_path = os.path.join(countries_dir, country_name)
                result = find_logo_in_folder(country_path, country_name)
                if result:
                    return result
    
    if debug_callback:
        debug_callback(f"No logo found for '{tvg_name}' in any country folder")
    return ''

# Main GUI Application
class M3UParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title('M3U Logo Matcher')
        self.m3u_path = ''
        self.countries_dir = os.path.join(os.getcwd(), 'countries')
        
        # Apply dark theme to the main window
        self.root.configure(bg=DARK_BG)
        
        # Configure styles for ttk widgets
        style = ttk.Style()
        style.theme_use('clam')  # Base theme
        
        # Configure ttk styles for dark mode
        style.configure('TButton', background=DARK_BUTTON, foreground=DARK_TEXT, borderwidth=0)
        style.map('TButton', 
            background=[('active', DARK_ACCENT), ('disabled', '#555555')],
            foreground=[('disabled', '#aaaaaa')])
            
        style.configure('TLabel', background=DARK_BG, foreground=DARK_TEXT)
        style.configure('TFrame', background=DARK_BG)
        style.configure('TProgressbar', 
            background=DARK_ACCENT, 
            troughcolor=DARK_FIELD,
            borderwidth=0)
        
        # URL style variables
        self.url_styles = {
            "Colour": "https://raw.githubusercontent.com/LJAM96/tv-logos/refs/heads/colour/countries",
            "White": "https://raw.githubusercontent.com/LJAM96/tv-logos/refs/heads/white/countries"
        }
        self.selected_style = tk.StringVar(value="White")  # Default to white
        self.github_base_url = self.url_styles[self.selected_style.get()]

        # Create a more compact layout
        main_frame = ttk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Top control panel - all on one row
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill="x", pady=5)
        
        # File selection and process buttons
        self.select_btn = ttk.Button(control_frame, text='Browse', command=self.browse_m3u)
        self.select_btn.pack(side="left", padx=2)
        
        self.file_label = ttk.Label(control_frame, text="No file selected")
        self.file_label.pack(side="left", padx=5)
        
        # Add a style selector dropdown
        ttk.Label(control_frame, text="Style:").pack(side="left", padx=(10, 2))
        
        # Use a regular tk.OptionMenu instead of ttk for better dark mode compatibility
        # and to make sure dropdown items are visible
        style_dropdown = tk.OptionMenu(control_frame, self.selected_style, 
                                     *self.url_styles.keys(), 
                                     command=self.update_style)
        # Style the dropdown to match dark theme
        style_dropdown.configure(bg=DARK_BUTTON, fg=DARK_TEXT, 
                               activebackground=DARK_ACCENT, activeforeground=DARK_TEXT,
                               highlightbackground=DARK_BG, highlightthickness=0,
                               relief="flat", bd=0)
        # Make sure dropdown menu appears correctly
        style_dropdown["menu"].configure(bg=DARK_FIELD, fg=DARK_TEXT,
                                      activebackground=DARK_ACCENT, activeforeground=DARK_TEXT)
        style_dropdown.pack(side="left")
        
        self.process_btn = ttk.Button(control_frame, text='Process', command=self.process, state='disabled')
        self.process_btn.pack(side="right", padx=5)
        
        # Progress section
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill="x", pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(side="left", padx=5)
        
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress.pack(side="right", fill="x", expand=True, padx=5)
        
        # Log area - more compact
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill="both", expand=True, pady=5)
        
        # Configure Text widget colors for dark mode
        self.log_text = Text(log_frame, height=12, width=70, 
                            bg=LOG_BG, fg=LOG_TEXT, 
                            insertbackground=DARK_TEXT,
                            borderwidth=1, relief="solid")
        self.log_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Match stats at the bottom
        self.stats_label = ttk.Label(main_frame, text="")
        self.stats_label.pack(pady=2, anchor="w")

    def update_style(self, *args):
        """Update the GitHub base URL when the style changes"""
        selected = self.selected_style.get()
        self.github_base_url = self.url_styles[selected]
        self.log(f"Logo style changed to: {selected}")

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def browse_m3u(self):
        path = filedialog.askopenfilename(filetypes=[('M3U files', '*.m3u'), ('All files', '*.*')])
        if path:
            self.m3u_path = path
            filename = os.path.basename(path)
            self.log(f"Selected: {filename}")
            self.file_label.config(text=filename)
            self.process_btn.config(state='normal')
    
    def convert_to_github_url(self, local_path):
        """Convert local file path to GitHub raw URL"""
        if not local_path:
            return ''
            
        # Extract the portion of the path after "countries/"
        try:
            countries_index = local_path.find('countries' + os.sep)
            if countries_index != -1:
                # Skip 'countries/' part and use the rest
                relative_path = local_path[countries_index + len('countries' + os.sep):]
                # Replace backslashes with forward slashes for URL
                relative_path = relative_path.replace('\\', '/')
                return f"{self.github_base_url}/{relative_path}"
            return local_path  # Return unchanged if pattern not found
        except:
            return local_path
            
    def process(self):
        self.log_text.delete(1.0, tk.END)  # Clear log
        
        if not os.path.exists(self.countries_dir):
            messagebox.showerror('Error', f'Countries folder not found: {self.countries_dir}')
            return
            
        self.log(f"Processing M3U file: {os.path.basename(self.m3u_path)}")
        self.log(f"Using {self.selected_style.get()} logos")
        
        # Parse the channels first
        channels = parse_m3u(self.m3u_path)
        total_channels = len(channels)
        self.log(f"Found {total_channels} channels in the M3U file")
        
        # Reset progress bar
        self.progress["value"] = 0
        self.progress["maximum"] = total_channels
        
        output_lines = []
        matches = 0
        
        # Process each channel
        for i, ch in enumerate(channels):
            # Update progress
            self.progress["value"] = i + 1
            progress_pct = int((i + 1) / total_channels * 100)
            self.status_label.config(text=f"Processing: {progress_pct}% complete")
            self.root.update()
            
            # Process the channel
            self.log(f"\nChannel {i+1}/{total_channels}: '{ch['tvg_name']}'")
            local_logo_path = match_logo(ch['group_title'], ch['tvg_name'], self.countries_dir, self.log)
            
            # Convert local path to GitHub URL
            github_logo_url = self.convert_to_github_url(local_logo_path)
            
            if local_logo_path:
                matches += 1
                
            output_lines.append(f"group title='{ch['group_title']}' - tvg-name='{ch['tvg_name']}' logo path='{github_logo_url}'")
            
        # Write output file
        output_path = os.path.join(os.path.dirname(self.m3u_path), 'output.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
            
        # Update final status
        match_percent = int(matches / total_channels * 100) if total_channels > 0 else 0
        self.status_label.config(text=f"Complete: {match_percent}% matches found")
        self.stats_label.config(text=f"Matched {matches} out of {total_channels} channels. Output written to {os.path.basename(output_path)}")
        
        self.log(f"\nMatched {matches} out of {total_channels} channels ({match_percent}%)")
        self.log(f"Output written to {output_path}")
        messagebox.showinfo('Done', f'Matched {matches} out of {total_channels} channels.\nOutput written to {output_path}')

if __name__ == '__main__':
    root = tk.Tk()
    app = M3UParserApp(root)
    root.geometry("700x450")
    root.minsize(650, 400)
    root.mainloop()
