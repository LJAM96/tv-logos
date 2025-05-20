import os
import tkinter as tk
from tkinter import filedialog, messagebox, Text, Scrollbar, Frame

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
    
    # Build a list of potential country folder names to check
    country_variations = []
    
    # 1. Try exact folder name from country code mapping
    if country_code in country_map:
        country_variations.append(country_map[country_code])
        if debug_callback:
            debug_callback(f"Mapped country code '{country_code}' to folder '{country_map[country_code]}'")
    
    # 2. Try using the original group_title as a folder name
    if group_title:
        # Original approach with country name normalization
        norm_country = group_title.strip().lower().replace(' ', '-').replace('_', '-')
        if norm_country not in country_variations:
            country_variations.append(norm_country)
        
        # Add version without special characters
        import re
        clean_country = re.sub(r'[^a-z0-9]', '-', group_title.lower())
        if clean_country not in country_variations:
            country_variations.append(clean_country)
    
    # 3. Check all country folders if the above doesn't find anything
    # This is a fallback strategy
    all_countries = False
    if not country_variations:
        all_countries = True
        # List all directories in the countries folder
        try:
            for folder in [f for f in os.listdir(countries_dir) if os.path.isdir(os.path.join(countries_dir, f))]:
                country_variations.append(folder)
            if debug_callback:
                debug_callback(f"No specific country identified. Will check all {len(country_variations)} country folders")
        except Exception as e:
            if debug_callback:
                debug_callback(f"Error listing country folders: {str(e)}")
    
    # For each possible country folder name
    for country_name in country_variations:
        country_path = os.path.join(countries_dir, country_name)
        
        if not os.path.isdir(country_path):
            if debug_callback and not all_countries:  # Don't log this for the all-countries fallback to avoid spam
                debug_callback(f"Country folder not found: {country_path}")
            continue
        
        if debug_callback:
            debug_callback(f"Checking country folder: {country_path}")
        
        # Process tvg_name for matching
        def normalize_name(name):
            # Make lowercase, replace spaces/underscores with hyphens
            return re.sub(r'[^a-z0-9]', '-', name.strip().lower())
        
        # Clean up the tvg_name
        tvg_norm = normalize_name(tvg_name)
        if debug_callback:
            debug_callback(f"Normalized channel name: '{tvg_norm}'")
        
        # Break tvg_name into words for partial matching
        tvg_words = [w for w in re.split(r'[^a-zA-Z0-9]', tvg_name.lower()) if w]
        
        # First try to find an exact match of the full channel name
        if tvg_words:
            try:
                files = os.listdir(country_path)
                
                # Sort files by potential relevance (using file name length as a heuristic)
                # This helps match shorter file names first which are often the main logos
                files.sort(key=len)
                
                # STAGE 1: Try exact full filename match
                for fname in files:
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]  # Remove extension
                    
                    # Check if filename exactly matches the normalized tvg_name
                    if base_name == tvg_norm and any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        if debug_callback:
                            debug_callback(f"EXACT MATCH: {fname}")
                        return os.path.join(country_path, fname)
                
                # STAGE 2: Try if filename starts with the channel name
                for fname in files:
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]  # Remove extension
                    
                    if base_name.startswith(tvg_norm) and any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        if debug_callback:
                            debug_callback(f"PREFIX MATCH: {fname}")
                        return os.path.join(country_path, fname)
                
                # STAGE 3: Try if the channel name contains all words from tvg_name in the right order
                if len(tvg_words) > 1:  # Only if we have multiple words
                    for fname in files:
                        fname_lower = fname.lower()
                        base_name = os.path.splitext(fname_lower)[0]  # Remove extension
                        
                        # Check if all words appear in the filename in the right order
                        all_words_found = True
                        last_pos = 0
                        for word in tvg_words:
                            if word and len(word) > 1:  # Only consider meaningful words
                                pos = base_name.find(word, last_pos)
                                if pos == -1:
                                    all_words_found = False
                                    break
                                last_pos = pos + len(word)
                        
                        if all_words_found and any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                            if debug_callback:
                                debug_callback(f"WORDS ORDER MATCH: {fname}")
                            return os.path.join(country_path, fname)
                
                # STAGE 4: Calculate similarity scores based on word matching
                best_match = None
                best_score = 0
                
                for fname in files:
                    if not any(fname.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        continue
                        
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Count words from tvg_name that appear in the filename
                    score = 0
                    for word in tvg_words:
                        if word and len(word) > 1:  # Only consider meaningful words
                            if word in base_name:
                                # Longer words get higher scores
                                score += len(word)
                    
                    # Bonus if the first word matches (channel names often start the same)
                    if tvg_words and tvg_words[0] in base_name:
                        score += 5
                        
                    # Penalize very different lengths
                    length_diff = abs(len(base_name) - len(tvg_norm))
                    score -= min(length_diff, 10)  # Cap the penalty
                    
                    if score > best_score:
                        best_score = score
                        best_match = fname
                
                if best_match and best_score > 5:  # Threshold to avoid poor matches
                    if debug_callback:
                        debug_callback(f"BEST MATCH (score {best_score}): {best_match}")
                    return os.path.join(country_path, best_match)
                    
            except Exception as e:
                if debug_callback:
                    debug_callback(f"Error searching files: {str(e)}")
                
        # If no match by name, try a default logo
        try:
            for default_name in [f"{country_name}.png", "flag.png", "logo.png"]:
                default_path = os.path.join(country_path, default_name)
                if os.path.exists(default_path):
                    if debug_callback:
                        debug_callback(f"Using default logo: {default_name}")
                    return default_path
        except Exception as e:
            if debug_callback:
                debug_callback(f"Error checking default logos: {str(e)}")
    
    if debug_callback:
        debug_callback(f"No logo found for '{tvg_name}' in any country folder")
    return ''

# Main GUI Application
class M3UParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title('M3U Channel Logo Matcher')
        self.m3u_path = ''
        self.countries_dir = os.path.join(os.getcwd(), 'countries')
        self.github_base_url = "https://raw.githubusercontent.com/LJAM96/tv-logos/refs/heads/white/countries"

        # Add frame for better layout
        main_frame = Frame(root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.label = tk.Label(main_frame, text='Select M3U file:')
        self.label.pack(pady=5, anchor="w")
        
        # Add a frame for buttons
        btn_frame = Frame(main_frame)
        btn_frame.pack(fill="x", pady=5)
        
        self.select_btn = tk.Button(btn_frame, text='Browse M3U', command=self.browse_m3u)
        self.select_btn.pack(side="left", padx=5)
        
        self.process_btn = tk.Button(btn_frame, text='Process', command=self.process, state='disabled')
        self.process_btn.pack(side="left", padx=5)
        
        # Add a debug log text area
        log_frame = Frame(main_frame)
        log_frame.pack(fill="both", expand=True, pady=10)
        
        log_label = tk.Label(log_frame, text="Debug Log:")
        log_label.pack(anchor="w")
        
        self.log_text = Text(log_frame, height=15, width=80)
        self.log_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="Ready")
        self.status_label.pack(pady=5, anchor="w")

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def browse_m3u(self):
        path = filedialog.askopenfilename(filetypes=[('M3U files', '*.m3u'), ('All files', '*.*')])
        if path:
            self.m3u_path = path
            self.log(f"Selected M3U file: {path}")
            self.status_label.config(text=f"M3U: {os.path.basename(path)}")
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
            
        self.log(f"Processing M3U file: {self.m3u_path}")
        self.log(f"Looking for logos in: {self.countries_dir}")
        
        channels = parse_m3u(self.m3u_path)
        self.log(f"Found {len(channels)} channels in the M3U file")
        
        output_lines = []
        matches = 0
        
        for ch in channels:
            self.log(f"\nProcessing: group_title='{ch['group_title']}', tvg_name='{ch['tvg_name']}'")
            local_logo_path = match_logo(ch['group_title'], ch['tvg_name'], self.countries_dir, self.log)
            
            # Convert local path to GitHub URL
            github_logo_url = self.convert_to_github_url(local_logo_path)
            
            if local_logo_path:
                matches += 1
                
            output_lines.append(f"group title='{ch['group_title']}' - tvg-name='{ch['tvg_name']}' logo path='{github_logo_url}'")
            
        output_path = os.path.join(os.path.dirname(self.m3u_path), 'output.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
            
        self.log(f"\nMatched {matches} out of {len(channels)} channels")
        self.log(f"Output written to {output_path}")
        messagebox.showinfo('Done', f'Matched {matches} out of {len(channels)} channels.\nOutput written to {output_path}')

if __name__ == '__main__':
    root = tk.Tk()
    app = M3UParserApp(root)
    root.geometry("800x600")
    root.mainloop()
