import os
import re
import difflib
import tempfile
import urllib.request
import urllib.parse
import datetime
import threading
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

# Global cache and lock for thread safety
_logo_cache = {}
_cache_lock = threading.Lock()

# Global country code mapping
COUNTRY_MAP = {
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

# Function to parse M3U and extract tvg-name and group-title
def parse_m3u(m3u_path):
    channels = []
    m3u_content = []
    channel_index = -1
    
    with open(m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m3u_content.append(line.rstrip())
            if line.startswith('#EXTINF'):
                channel_index = len(m3u_content) - 1
                tvg_name = None
                group_title = None
                # Extract tvg-name and group-title
                if 'tvg-name="' in line:
                    tvg_name = line.split('tvg-name="')[1].split('"')[0]
                if 'group-title="' in line:
                    group_title = line.split('group-title="')[1].split('"')[0]
                channels.append({
                    'tvg_name': tvg_name, 
                    'group_title': group_title,
                    'line_index': channel_index
                })
            # Store the URL line after #EXTINF
            elif channel_index >= 0 and not line.startswith('#'):
                channels[-1]['url'] = line.strip()
                channel_index = -1
    
    return channels, m3u_content

# Function to match channel with logo
def match_logo(group_title, tvg_name, countries_dir, debug_callback=None):
    if not tvg_name:
        if debug_callback:
            debug_callback(f"Missing tvg_name for group_title='{group_title}'")
        return ''
    
    # Create cache key for this lookup
    cache_key = f"{tvg_name}|{group_title}|{countries_dir}"
    
    # Check cache with thread safety
    with _cache_lock:
        if cache_key in _logo_cache:
            if debug_callback:
                debug_callback(f"CACHE HIT: Using cached result for '{tvg_name}'")
            return _logo_cache[cache_key]
        
    # Enhanced country code extraction from group_title
    # Examples: "UK Entertainment", "US Sports", "DE Movies", "Sports - UK", "UK: Sports"
    def extract_country_from_category(group_title):
        if not group_title:
            return ""
        
        title_lower = group_title.strip().lower()
        
        # Pattern 1: Country code at the beginning ("UK Sports", "US News")
        parts = title_lower.split(" ", 1)
        if parts and len(parts[0]) in [2, 3]:  # 2-3 char country codes
            potential_code = parts[0]
            if potential_code in COUNTRY_MAP:
                return potential_code
        
        # Pattern 2: Country code at the end ("Sports UK", "News US")
        words = title_lower.split()
        if len(words) >= 2 and len(words[-1]) in [2, 3]:
            potential_code = words[-1]
            if potential_code in COUNTRY_MAP:
                return potential_code
        
        # Pattern 3: Country code after separators ("Sports - UK", "UK: Sports", "Sports (UK)")
        separators = [' - ', ': ', ' : ', '(', ')', '[', ']', ' | ']
        for sep in separators:
            if sep in title_lower:
                parts = title_lower.replace('(', ' ').replace(')', ' ').replace('[', ' ').replace(']', ' ').split()
                for part in parts:
                    clean_part = part.strip(' -:|()[]')
                    if len(clean_part) in [2, 3] and clean_part in COUNTRY_MAP:
                        return clean_part
        
        # Pattern 4: Full country names in category ("United Kingdom Sports", "Germany Movies")
        for code, country_name in COUNTRY_MAP.items():
            if country_name.replace('-', ' ') in title_lower:
                return code
        
        # Pattern 5: Common country name variations
        country_variations = {
            'uk': ['united kingdom', 'britain', 'british', 'england', 'english'],
            'us': ['united states', 'america', 'american', 'usa'],
            'de': ['germany', 'german', 'deutschland'],
            'fr': ['france', 'french'],
            'es': ['spain', 'spanish', 'espana'],
            'it': ['italy', 'italian', 'italia'],
            'ca': ['canada', 'canadian'],
            'au': ['australia', 'australian', 'aussie'],
            'nl': ['netherlands', 'dutch', 'holland'],
            'se': ['sweden', 'swedish'],
            'no': ['norway', 'norwegian'],
            'dk': ['denmark', 'danish'],
            'pl': ['poland', 'polish'],
            'ru': ['russia', 'russian']
        }
        
        for code, variations in country_variations.items():
            for variation in variations:
                if variation in title_lower:
                    return code
        
        return ""
    
    country_code = extract_country_from_category(group_title)
    if debug_callback and country_code:
        debug_callback(f"Extracted country code: '{country_code}' from category '{group_title}'")
    
    
    # Enhanced name normalization with better pattern recognition
    def normalize_name(name):
        # Make lowercase, replace spaces/underscores with hyphens
        return re.sub(r'[^a-z0-9]', '-', name.strip().lower())
    
    # Calculate fuzzy string similarity using difflib
    def calculate_similarity(str1, str2):
        return difflib.SequenceMatcher(None, str1, str2).ratio()
    
    # Simple phonetic similarity (Soundex-like algorithm)
    def get_phonetic_code(word):
        if not word:
            return ""
        
        word = word.lower().strip()
        if len(word) == 0:
            return ""
        
        # Simple phonetic transformations
        # Replace similar sounding letters
        phonetic_map = {
            'c': 'k', 'q': 'k', 'x': 'ks',
            'ph': 'f', 'gh': 'f',
            'ck': 'k', 'cc': 'k',
            'th': 't', 'sh': 's',
            'ch': 'k', 'tch': 'k',
            'dge': 'j', 'ge': 'j',
            'y': 'i', 'ie': 'i', 'ei': 'i',
            'oo': 'u', 'ou': 'u', 'ow': 'u',
            'tion': 'shun', 'sion': 'shun'
        }
        
        # Apply phonetic transformations
        for old, new in phonetic_map.items():
            word = word.replace(old, new)
        
        # Remove consecutive duplicate letters
        result = []
        prev_char = ''
        for char in word:
            if char != prev_char:
                result.append(char)
                prev_char = char
        
        return ''.join(result)
    
    # Calculate phonetic similarity between two words
    def calculate_phonetic_similarity(word1, word2):
        if not word1 or not word2:
            return 0.0
        
        phonetic1 = get_phonetic_code(word1)
        phonetic2 = get_phonetic_code(word2)
        
        if not phonetic1 or not phonetic2:
            return 0.0
        
        return calculate_similarity(phonetic1, phonetic2)
    
    # Comprehensive channel alias/synonym database
    def get_channel_aliases(name):
        if not name:
            return []
        
        name_lower = name.lower().strip()
        aliases = set([name_lower])
        
        # Comprehensive channel alias database
        channel_aliases = {
            # BBC Channels
            'bbc one': ['bbc1', 'bbcone', 'bbc-one', 'bbc 1'],
            'bbc two': ['bbc2', 'bbctwo', 'bbc-two', 'bbc 2'],
            'bbc three': ['bbc3', 'bbcthree', 'bbc-three', 'bbc 3'],
            'bbc four': ['bbc4', 'bbcfour', 'bbc-four', 'bbc 4'],
            'bbc news': ['bbcnews', 'bbc-news', 'bbc news 24', 'news24'],
            'bbc parliament': ['bbcparliament', 'bbc-parliament'],
            'cbbc': ['bbc cbbc', 'bbc-cbbc'],
            'cbeebies': ['bbc cbeebies', 'bbc-cbeebies'],
            
            # ITV Channels
            'itv': ['itv1', 'itv-1', 'itv one'],
            'itv2': ['itv 2', 'itv-2'],
            'itv3': ['itv 3', 'itv-3'],
            'itv4': ['itv 4', 'itv-4'],
            'itvbe': ['itv be', 'itv-be'],
            
            # Channel 4
            'channel 4': ['c4', 'ch4', 'channel4', 'four'],
            'e4': ['e 4', 'e-4'],
            'more4': ['more 4', 'more-4'],
            '4seven': ['4 seven', '4-seven', 'four seven'],
            'film4': ['film 4', 'film-4'],
            
            # Channel 5
            'channel 5': ['c5', 'ch5', 'channel5', 'five'],
            '5usa': ['5 usa', '5-usa', 'five usa'],
            '5star': ['5 star', '5-star', 'five star'],
            '5select': ['5 select', '5-select', 'five select'],
            
            # Sky Channels
            'sky sports': ['skysports', 'sky-sports'],
            'sky news': ['skynews', 'sky-news'],
            'sky one': ['skyone', 'sky-one', 'sky1'],
            'sky two': ['skytwo', 'sky-two', 'sky2'],
            'sky atlantic': ['skyatlantic', 'sky-atlantic'],
            'sky cinema': ['skycinema', 'sky-cinema', 'sky movies'],
            
            # Discovery
            'discovery channel': ['discovery', 'disc', 'dsc'],
            'discovery science': ['discovery sci', 'disc science'],
            'animal planet': ['animalplanet', 'animal-planet'],
            
            # Other Popular Channels
            'comedy central': ['comedycentral', 'comedy-central', 'cc'],
            'cartoon network': ['cartoonnetwork', 'cartoon-network', 'cn'],
            'nickelodeon': ['nick', 'nicktoons'],
            'national geographic': ['natgeo', 'nat geo', 'nationalgeographic'],
            'history channel': ['history', 'hist'],
            'food network': ['foodnetwork', 'food-network'],
            'travel channel': ['travelchannel', 'travel-channel'],
            
            # News Channels
            'cnn': ['cnn news', 'cnn international'],
            'fox news': ['foxnews', 'fox-news'],
            'sky news': ['skynews', 'sky-news'],
            'bbc news': ['bbcnews', 'bbc-news', 'news24'],
            'euronews': ['euro news', 'euro-news'],
            
            # Sports
            'espn': ['espn sports', 'espn-sports'],
            'eurosport': ['euro sport', 'euro-sports'],
            'bt sport': ['btsport', 'bt-sport'],
            
            # Entertainment
            'mtv': ['music tv', 'music-tv'],
            'vh1': ['vh 1', 'vh-1'],
            'e!': ['e entertainment', 'entertainment'],
            'tlc': ['the learning channel'],
            
            # International
            'cnn international': ['cnni', 'cnn-international'],
            'bbc world news': ['bbc world', 'bbcworld'],
            'france 24': ['france24', 'fr24'],
            'deutsche welle': ['dw', 'dw-tv'],
            'rt': ['russia today', 'rt-tv'],
            'al jazeera': ['aljazeera', 'al-jazeera', 'ajn'],
            
            # Multi-language aliases
            'televisión española': ['tve', 'rtve', 'la1', 'la2'],
            'rai uno': ['rai1', 'rai 1'],
            'rai due': ['rai2', 'rai 2'],
            'rai tre': ['rai3', 'rai 3'],
            'france 2': ['france2', 'fr2'],
            'france 3': ['france3', 'fr3'],
            'arte': ['arte france', 'arte deutschland'],
            'zdf': ['zweites deutsches fernsehen'],
            'ard': ['das erste'],
            'rtl': ['rtl television'],
            'sat.1': ['sat1', 'sat 1'],
            'pro7': ['prosieben', 'pro sieben'],
            'vox': ['vox tv'],
            'rtl2': ['rtl 2', 'rtl zwei'],
            'kabel eins': ['kabel1', 'kabel 1'],
            'super rtl': ['superrtl'],
            'ntv': ['n-tv', 'n tv'],
            'welt': ['welt tv', 'die welt'],
            'phoenix': ['phoenix tv'],
            '3sat': ['3 sat', 'dreisat'],
            'servus tv': ['servustv']
        }
        
        # Add multi-language character normalization
        def normalize_international_chars(text):
            char_map = {
                'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ã': 'a',
                'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
                'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i',
                'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'õ': 'o',
                'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u',
                'ñ': 'n', 'ç': 'c', 'ß': 'ss',
                'æ': 'ae', 'œ': 'oe', 'ø': 'o',
                'å': 'a', 'đ': 'd', 'ł': 'l'
            }
            for accented, normal in char_map.items():
                text = text.replace(accented, normal)
            return text
        
        # Normalize international characters in the name
        normalized_name = normalize_international_chars(name_lower)
        if normalized_name != name_lower:
            aliases.add(normalized_name)
        
        # Add aliases for this channel
        for canonical, alias_list in channel_aliases.items():
            if (name_lower == canonical or name_lower in alias_list or
                normalized_name == canonical or normalized_name in alias_list):
                aliases.add(canonical)
                aliases.update(alias_list)
                # Also add normalized versions
                for alias in alias_list:
                    aliases.add(normalize_international_chars(alias))
                break
        
        return list(aliases)
    
    # Enhanced channel name cleaning and abbreviation expansion
    def clean_channel_name(name):
        if not name:
            return ""
        
        name = name.strip().lower()
        
        # Common abbreviation expansions
        abbreviations = {
            'tv': 'television',
            'hd': 'high-definition',
            '+1': 'plus-one',
            'uk': 'united-kingdom',
            'us': 'united-states',
            'usa': 'united-states',
            'int': 'international',
            'news': 'news',
            'sport': 'sports',
            'movie': 'movies',
            'film': 'films',
            'music': 'music',
            'kids': 'children',
            'doc': 'documentary',
            'docu': 'documentary'
        }
        
        # Apply abbreviation expansions
        words = re.findall(r'\b\w+\b', name)
        expanded_words = []
        for word in words:
            expanded_words.append(abbreviations.get(word, word))
        
        return ' '.join(expanded_words)
    
    # Alternative normalizations for common formats
    def get_normalized_variations(name):
        if not name:
            return []
            
        variations = set()  # Use set to avoid duplicates
        name_lower = name.lower().strip()
        
        # Add original name variations
        variations.add(normalize_name(name))
        variations.add(name_lower.replace(' ', '-'))
        variations.add(name_lower.replace(' ', ''))
        
        # Clean and expand abbreviations
        cleaned = clean_channel_name(name)
        if cleaned != name_lower:
            variations.add(normalize_name(cleaned))
            variations.add(cleaned.replace(' ', '-'))
            variations.add(cleaned.replace(' ', ''))
        
        # Special cases for channel numbers in names
        # Convert "ITV2" to "itv-2" and "4Seven" to "4-seven"
        number_pattern = re.compile(r'([a-z]+)(\d+)', re.IGNORECASE)
        match = number_pattern.search(name)
        if match:
            channel_name = match.group(1).lower()
            channel_number = match.group(2)
            variations.add(f"{channel_name}-{channel_number}")
            variations.add(f"{channel_name}{channel_number}")
        
        # For names starting with numbers like "4Seven"
        number_prefix_pattern = re.compile(r'(\d+)([A-Z][a-z]+)')
        match = number_prefix_pattern.search(name)
        if match:
            number = match.group(1)
            text = match.group(2).lower()
            variations.add(f"{number}-{text}")
            variations.add(f"{number}{text}")
        
        # Handle special number words
        number_words = {
            'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
            'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'
        }
        
        for word, digit in number_words.items():
            if word in name_lower:
                variations.add(name_lower.replace(word, digit))
                variations.add(normalize_name(name_lower.replace(word, digit)))
        
        # Handle special cases like "Five USA" -> "5usa"
        if "five" in name_lower or "5" in name_lower:
            variations.add("5" + re.sub(r'[^a-z0-9]', '', name_lower.replace("five", "")))
            
        # Add hyphenated version
        hyphenated = re.sub(r'(\w)([A-Z])', r'\1-\2', name).lower()
        variations.add(hyphenated)
        variations.add(hyphenated.replace('-', ''))
            
        # Remove articles from the name (the, a, an)
        for article in ['the ', 'a ', 'an ']:
            if name_lower.startswith(article):
                without_article = name_lower[len(article):]
                variations.add(normalize_name(without_article))
                variations.add(without_article.replace(' ', '-'))
                variations.add(without_article.replace(' ', ''))
        
        # Handle common suffixes (expanded list)
        suffixes_to_remove = [
            ' tv', ' television', ' channel', ' network', ' hd', ' plus', '+1', ' +1',
            ' 1', ' one', ' 2', ' two', ' 3', ' three', ' 4', ' four', ' 5', ' five',
            ' hd1', ' sd', ' fhd', ' uhd', ' 4k', ' live', ' streaming', ' online',
            ' news', ' sport', ' sports', ' movies', ' films', ' music', ' kids',
            ' family', ' drama', ' comedy', ' documentary', ' lifestyle', ' reality'
        ]
        for suffix in suffixes_to_remove:
            if name_lower.endswith(suffix):
                base_name = name_lower[:-len(suffix)].strip()
                if base_name:  # Only add if not empty
                    variations.add(normalize_name(base_name))
                    variations.add(base_name.replace(' ', '-'))
                    variations.add(base_name.replace(' ', ''))
        
        # Handle common prefixes (expanded list)
        prefixes_to_remove = [
            'bbc ', 'itv ', 'sky ', 'fox ', 'discovery ', 'national geographic ',
            'cbs ', 'nbc ', 'abc ', 'cnn ', 'mtv ', 'vh1 ', 'e! ', 'tlc ',
            'history ', 'animal planet ', 'cartoon network ', 'disney ',
            'nickelodeon ', 'nick ', 'comedy central ', 'channel ', 'tv '
        ]
        for prefix in prefixes_to_remove:
            if name_lower.startswith(prefix):
                base_name = name_lower[len(prefix):].strip()
                if base_name:  # Only add if not empty
                    variations.add(normalize_name(base_name))
                    variations.add(base_name.replace(' ', '-'))
                    variations.add(base_name.replace(' ', ''))
        
        # Handle special channel naming patterns
        # Pattern: "Channel Name HD" -> "channelnameHD", "channel-name-hd"
        if ' hd' in name_lower:
            hd_base = name_lower.replace(' hd', '')
            variations.add(hd_base + 'hd')
            variations.add(normalize_name(hd_base) + '-hd')
        
        # Pattern: "News 24" -> "news24", "24news"
        news_pattern = re.search(r'(news)\s+(\d+)', name_lower)
        if news_pattern:
            news_base = news_pattern.group(1)
            news_num = news_pattern.group(2)
            variations.add(f"{news_base}{news_num}")
            variations.add(f"{news_num}{news_base}")
            variations.add(f"{news_base}-{news_num}")
        
        # Pattern: "Sport 1" -> "sport1", "sports1"
        sport_pattern = re.search(r'(sport|sports)\s+(\d+)', name_lower)
        if sport_pattern:
            sport_base = sport_pattern.group(1)
            sport_num = sport_pattern.group(2)
            variations.add(f"{sport_base}{sport_num}")
            # Add both singular and plural
            if sport_base == 'sport':
                variations.add(f"sports{sport_num}")
            else:
                variations.add(f"sport{sport_num}")
        
        # Handle regional variations (e.g., "BBC One Wales" -> "bbcone", "bbc1wales")
        regions = ['wales', 'scotland', 'ireland', 'london', 'south', 'north', 'east', 'west']
        for region in regions:
            if region in name_lower:
                without_region = name_lower.replace(f' {region}', '').replace(f'{region} ', '')
                if without_region != name_lower:
                    variations.add(normalize_name(without_region))
                    variations.add(without_region.replace(' ', '-'))
                    variations.add(without_region.replace(' ', ''))
        
        # Remove empty variations and convert back to list
        return [v for v in variations if v]
    
    # Get all normalized variations including aliases
    tvg_variations = get_normalized_variations(tvg_name)
    
    # Add variations from channel aliases
    channel_aliases = get_channel_aliases(tvg_name)
    for alias in channel_aliases:
        tvg_variations.extend(get_normalized_variations(alias))
    
    # Remove duplicates and empty strings
    tvg_variations = list(set([v for v in tvg_variations if v]))
    tvg_norm = tvg_variations[0] if tvg_variations else ""
    
    if debug_callback and len(channel_aliases) > 1:
        debug_callback(f"Found aliases for '{tvg_name}': {channel_aliases[:5]}...")  # Show first 5 aliases
    
    # Break tvg_name into words for partial matching
    tvg_words = [w for w in re.split(r'[^a-zA-Z0-9]', tvg_name.lower()) if w and len(w) > 1]
    
    # Flag to indicate if we should search all country folders
    search_all = False
    
    # Build a prioritized list of potential country folder names to check
    country_variations = []
    priority_countries_from_category = []
    
    # 1. Highest priority: exact folder name from category-extracted country code
    if country_code in COUNTRY_MAP:
        priority_countries_from_category.append(COUNTRY_MAP[country_code])
        country_variations.append(COUNTRY_MAP[country_code])
        if debug_callback:
            debug_callback(f"HIGH PRIORITY: Mapped category country code '{country_code}' to folder '{COUNTRY_MAP[country_code]}'")
    
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
    except (OSError, PermissionError) as e:
        if debug_callback:
            debug_callback(f"Error accessing country folders: {str(e)}")
    
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
            
            # STAGE 1: Enhanced exact filename matching
            for variation in tvg_variations:
                for fname in files:
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Check different patterns:
                    # 1. Exact match: "itv-2" == "itv-2"
                    # 2. With country suffix: "itv-2-uk" 
                    # 3. With common logo suffixes: "itv-2-light", "itv-2-dark", "itv-2-white"
                    logo_suffixes = ['', '-light', '-dark', '-white', '-black', '-color', '-colour', '-logo', '-icon']
                    
                    for suffix in logo_suffixes:
                        test_names = [
                            f"{variation}{suffix}",
                            f"{variation}{country_suffix}{suffix}",
                            f"{variation}{suffix}{country_suffix}"
                        ]
                        
                        if base_name in test_names or any(base_name == test_name for test_name in test_names):
                            if any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                                if debug_callback:
                                    debug_callback(f"EXACT VARIATION MATCH: {fname} (matched {variation}{suffix})")
                                return os.path.join(country_path, fname)
                    
                    # Original exact matching logic
                    if (base_name == variation or 
                        base_name == f"{variation}{country_suffix}" or
                        variation == base_name.replace(f"{country_suffix}", "")) and \
                        any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        if debug_callback:
                            debug_callback(f"EXACT VARIATION MATCH: {fname} (matched {variation})")
                        return os.path.join(country_path, fname)
            
            # STAGE 2: Enhanced prefix and substring matching
            for variation in tvg_variations:
                for fname in files:
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Check for prefix matches with minimum length requirement
                    min_match_length = max(3, len(variation) // 2)  # At least 3 chars or half the variation length
                    
                    if any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        # Prefix matching
                        if (len(variation) >= min_match_length and base_name.startswith(variation)) or \
                           (len(base_name) >= min_match_length and variation.startswith(base_name)):
                            if debug_callback:
                                debug_callback(f"PREFIX VARIATION MATCH: {fname} (matched {variation})")
                            return os.path.join(country_path, fname)
                        
                        # Substring matching for longer names
                        if len(variation) >= 4 and variation in base_name and len(base_name) <= len(variation) + 6:
                            if debug_callback:
                                debug_callback(f"SUBSTRING VARIATION MATCH: {fname} (contains {variation})")
                            return os.path.join(country_path, fname)
            
            # STAGE 3: Enhanced word matching with flexible ordering
            if tvg_words:
                # Find files where significant words from tvg_name appear
                significant_words = [w for w in tvg_words if len(w) > 2]  # Only words longer than 2 chars
                
                for fname in files:
                    fname_lower = fname.lower()
                    if not any(fname_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        continue
                        
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Method 1: Check if all words appear in order
                    all_words_found = True
                    last_pos = 0
                    for word in significant_words:
                        pos = base_name.find(word, last_pos)
                        if pos == -1:
                            all_words_found = False
                            break
                        last_pos = pos + len(word)
                    
                    if all_words_found:
                        if debug_callback:
                            debug_callback(f"WORDS ORDER MATCH: {fname}")
                        return os.path.join(country_path, fname)
                    
                    # Method 2: Check if most important words appear (relaxed order)
                    if len(significant_words) >= 2:
                        words_found = sum(1 for word in significant_words if word in base_name)
                        word_coverage = words_found / len(significant_words)
                        
                        # Require at least 70% word coverage and first word must match
                        if word_coverage >= 0.7 and significant_words[0] in base_name:
                            if debug_callback:
                                debug_callback(f"WORDS COVERAGE MATCH: {fname} ({words_found}/{len(significant_words)} words)")
                            return os.path.join(country_path, fname)
                    
                    # Method 3: Single word match for very short channel names
                    elif len(significant_words) == 1 and len(significant_words[0]) >= 4:
                        if significant_words[0] in base_name and len(base_name) <= len(significant_words[0]) + 8:
                            if debug_callback:
                                debug_callback(f"SINGLE WORD MATCH: {fname}")
                            return os.path.join(country_path, fname)
                
                # STAGE 4: Enhanced fuzzy matching with multiple scoring algorithms
                best_match = None
                best_score = 0
                best_similarity = 0
                
                for fname in files:
                    if not any(fname.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        continue
                        
                    fname_lower = fname.lower()
                    base_name = os.path.splitext(fname_lower)[0]
                    
                    # Initialize scoring components
                    exact_score = 0
                    word_score = 0
                    similarity_score = 0
                    bonus_score = 0
                    penalty_score = 0
                    
                    # 1. Exact variation matching (highest weight)
                    for variation in tvg_variations:
                        if variation == base_name:
                            exact_score += 100  # Perfect match
                        elif variation in base_name:
                            exact_score += len(variation) * 3  # Substring match
                        elif base_name in variation:
                            exact_score += len(base_name) * 2  # Reverse substring
                    
                    # 2. Fuzzy similarity matching (text + phonetic)
                    max_similarity = 0
                    max_phonetic_similarity = 0
                    
                    for variation in tvg_variations:
                        # Regular text similarity
                        similarity = calculate_similarity(variation, base_name)
                        max_similarity = max(max_similarity, similarity)
                        
                        # Phonetic similarity for sound-alike matches
                        phonetic_sim = calculate_phonetic_similarity(variation, base_name)
                        max_phonetic_similarity = max(max_phonetic_similarity, phonetic_sim)
                        
                        # Combined scoring
                        if similarity > 0.8:  # High text similarity
                            similarity_score += similarity * 50
                        elif similarity > 0.6:  # Medium text similarity
                            similarity_score += similarity * 30
                        elif similarity > 0.4:  # Low text similarity
                            similarity_score += similarity * 15
                        
                        # Bonus for phonetic matches
                        if phonetic_sim > 0.7:  # High phonetic similarity
                            similarity_score += phonetic_sim * 25
                            if debug_callback:
                                debug_callback(f"Strong phonetic match: {variation} ≈ {base_name} (phonetic: {phonetic_sim:.3f})")
                        elif phonetic_sim > 0.5:  # Medium phonetic similarity
                            similarity_score += phonetic_sim * 15
                    
                    # 3. Word-based scoring
                    words_found = 0
                    for word in tvg_words:
                        if word in base_name:
                            word_score += len(word) * 2
                            words_found += 1
                    
                    # Bonus for finding multiple words
                    if words_found > 1:
                        word_score += words_found * 5
                    
                    # 4. Position and context bonuses
                    # Bonus if first word matches (channel names often start the same)
                    if tvg_words and len(tvg_words[0]) > 2 and base_name.startswith(tvg_words[0]):
                        bonus_score += 15
                    
                    # Bonus if country code appears in the filename
                    if country_code and f"-{country_code}" in base_name:
                        bonus_score += 12
                    
                    # Bonus for shorter filenames (often main logos)
                    if len(base_name) <= 10:
                        bonus_score += 3
                    
                    # 5. Penalties
                    # Penalize very different lengths
                    length_diff = abs(len(base_name) - len(tvg_norm))
                    penalty_score = min(length_diff * 0.5, 15)  # Cap the penalty
                    
                    # Penalize files with too many extra words
                    extra_words = len(re.findall(r'\b\w+\b', base_name)) - len(tvg_words)
                    if extra_words > 2:
                        penalty_score += extra_words * 2
                    
                    # Calculate total score
                    total_score = exact_score + word_score + similarity_score + bonus_score - penalty_score
                    
                    # Update best match if this is better
                    if total_score > best_score or (total_score == best_score and max_similarity > best_similarity):
                        best_score = total_score
                        best_similarity = max_similarity
                        best_match = fname
                        if debug_callback:
                            debug_callback(f"New best candidate: {fname} (score: {total_score:.1f}, similarity: {max_similarity:.3f})")
                
                # Enhanced threshold - require either good score, high similarity, or strong phonetic match
                score_threshold = 15
                similarity_threshold = 0.7
                phonetic_threshold = 0.8
                
                # Also check phonetic similarity for the best match
                best_phonetic = 0
                if best_match:
                    best_match_base = os.path.splitext(best_match.lower())[0]
                    for variation in tvg_variations:
                        phonetic_sim = calculate_phonetic_similarity(variation, best_match_base)
                        best_phonetic = max(best_phonetic, phonetic_sim)
                
                if best_match and (best_score >= score_threshold or 
                                 best_similarity >= similarity_threshold or 
                                 best_phonetic >= phonetic_threshold):
                    if debug_callback:
                        debug_callback(f"BEST FUZZY MATCH (score {best_score:.1f}, similarity {best_similarity:.3f}, phonetic {best_phonetic:.3f}): {best_match}")
                    return os.path.join(country_path, best_match)
                    
            # Try default logos
            for default_name in [f"{country_name}.png", "flag.png", "logo.png"]:
                default_path = os.path.join(country_path, default_name)
                if os.path.exists(default_path):
                    if debug_callback:
                        debug_callback(f"Using default logo: {default_name}")
                    return default_path
                    
        except (OSError, PermissionError, UnicodeDecodeError) as e:
            if debug_callback:
                debug_callback(f"Error searching in {country_path}: {str(e)}")
                
        return None
    
    # PRIORITY SEARCH 1: Search category-derived countries first (highest priority)
    for country_name in priority_countries_from_category:
        country_path = os.path.join(countries_dir, country_name)
        if debug_callback:
            debug_callback(f"PRIORITY SEARCH: Checking category-derived country: {country_name}")
        result = find_logo_in_folder(country_path, country_name)
        if result:
            if debug_callback:
                debug_callback(f"SUCCESS: Found logo in category-derived country: {country_name}")
            with _cache_lock:
                _logo_cache[cache_key] = result
            return result
    
    # PRIORITY SEARCH 2: Search other likely country folders
    for country_name in country_variations:
        if country_name not in priority_countries_from_category:  # Skip already searched
            country_path = os.path.join(countries_dir, country_name)
            result = find_logo_in_folder(country_path, country_name)
            if result:
                with _cache_lock:
                    _logo_cache[cache_key] = result
                return result
    
    # If no match or told to search all, try all country folders
    if search_all:
        if debug_callback:
            debug_callback("Searching all country folders as fallback...")
            
        # Try specific countries first based on common patterns in the tvg_name
        priority_countries = []
        
        # Look for country hints in the channel name (expanded list)
        country_suffixes = ['-uk', '-us', '-usa', '-ca', '-au', '-jp', '-de', '-ger', '-fr', '-it', '-es', '-nl', '-be', '-ch', '-at', '-se', '-no', '-dk', '-fi', '-pl', '-cz', '-ie', '-pt']
        for suffix in country_suffixes:
            if any(variation.endswith(suffix) for variation in tvg_variations):
                country_code_hint = suffix[1:]  # Remove the '-'
                if country_code_hint in COUNTRY_MAP:
                    priority_countries.append(COUNTRY_MAP[country_code_hint])
                    if debug_callback:
                        debug_callback(f"Found country hint in channel name: {suffix} -> {COUNTRY_MAP[country_code_hint]}")
        
        # Also check for country hints in the middle of names (e.g., "bbcone-uk-hd")
        for code, country in COUNTRY_MAP.items():
            if any(f'-{code}-' in variation or f'_{code}_' in variation for variation in tvg_variations):
                if country not in priority_countries:
                    priority_countries.append(country)
                    if debug_callback:
                        debug_callback(f"Found embedded country hint: {code} -> {country}")
        
        # Try channel name hint countries (lower priority than category)
        for country_name in priority_countries:
            if (country_name not in country_variations and 
                country_name not in priority_countries_from_category):  # Skip already searched
                country_path = os.path.join(countries_dir, country_name)
                result = find_logo_in_folder(country_path, country_name)
                if result:
                    with _cache_lock:
                        _logo_cache[cache_key] = result
                    return result
        
        # Last resort - try ALL countries (but prioritize category countries)
        remaining_countries = [c for c in all_countries 
                             if c not in country_variations 
                             and c not in priority_countries 
                             and c not in priority_countries_from_category]
        
        for country_name in remaining_countries:
            country_path = os.path.join(countries_dir, country_name)
            result = find_logo_in_folder(country_path, country_name)
            if result:
                with _cache_lock:
                    _logo_cache[cache_key] = result
                return result
    
    # Final fallback: try partial matching with very relaxed criteria
    if debug_callback:
        debug_callback("Attempting final fallback with relaxed matching...")
    
    # Try a very simple substring match as last resort
    for country_name in all_countries[:5]:  # Only check first 5 countries to avoid excessive processing
        country_path = os.path.join(countries_dir, country_name)
        if not os.path.isdir(country_path):
            continue
        try:
            files = os.listdir(country_path)
            for fname in files:
                if not any(fname.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                    continue
                fname_lower = fname.lower()
                base_name = os.path.splitext(fname_lower)[0]
                
                # Very basic substring matching
                first_word = tvg_words[0] if tvg_words and len(tvg_words[0]) > 3 else None
                if first_word and first_word in base_name and len(base_name) < len(tvg_norm) + 10:
                    if debug_callback:
                        debug_callback(f"FALLBACK MATCH found: {fname} (contains '{first_word}')")
                    return os.path.join(country_path, fname)
        except (OSError, PermissionError, UnicodeDecodeError):
            continue
    
    if debug_callback:
        debug_callback(f"No logo found for '{tvg_name}' in any country folder")
    
    # Cache the result (empty in this case)
    with _cache_lock:
        _logo_cache[cache_key] = ''
    return ''

# Main GUI Application
class M3UParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title('M3U Logo Matcher')
        self.m3u_path = ''
        self.m3u_url = ''
        self.countries_dir = os.path.join(os.getcwd(), 'countries')
        self.tempfile_path = None  # For downloaded M3U

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

        # Mode: Local file or URL
        self.input_mode = tk.StringVar(value="file")

        # Output formats: txt, html, m3u (multi-select)
        self.output_format_txt = tk.BooleanVar(value=True)
        self.output_format_html = tk.BooleanVar(value=False)
        self.output_format_m3u = tk.BooleanVar(value=False)

        # Create a more compact layout
        main_frame = ttk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Top control panel with fixed width sections
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill="x", pady=5)
        

        # Left: Input section (radio buttons + file/url selection + output formats)
        left_outer_frame = ttk.Frame(control_frame)
        left_outer_frame.pack(side="left", fill="x", expand=True)

        # Radio button container (row 0)
        input_select_frame = ttk.Frame(left_outer_frame)
        input_select_frame.grid(row=0, column=0, sticky="w", pady=(0, 2))
        file_radio = ttk.Radiobutton(input_select_frame, text="Local File", variable=self.input_mode, value="file", command=self.update_input_mode)
        url_radio = ttk.Radiobutton(input_select_frame, text="URL", variable=self.input_mode, value="url", command=self.update_input_mode)
        file_radio.pack(side="left", padx=(0,2))
        url_radio.pack(side="left", padx=(0,2))

        # File selection frame (row 1)
        file_frame = ttk.Frame(left_outer_frame)
        file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        self.select_btn = ttk.Button(file_frame, text='Browse', command=self.browse_m3u)
        self.select_btn.pack(side="left", padx=2)
        self.file_label = ttk.Label(file_frame, text="No file selected")
        self.file_label.pack(side="left", padx=5, fill="x")
        self.file_frame = file_frame

        # URL entry frame (row 2)
        url_frame = ttk.Frame(left_outer_frame)
        url_frame.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        self.url_entry = tk.Entry(url_frame, width=32, bg=DARK_FIELD, fg=DARK_TEXT, insertbackground=DARK_TEXT, relief="flat")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(2,0))
        
        # Placeholder text handling
        self.url_placeholder = "Paste M3U URL here..."
        self.url_entry.insert(0, self.url_placeholder)
        self.url_entry.config(fg='#888888')  # Dim color for placeholder
        
        def on_url_focus_in(event):
            if self.url_entry.get() == self.url_placeholder:
                self.url_entry.delete(0, tk.END)
                self.url_entry.config(fg=DARK_TEXT)
        
        def on_url_focus_out(event):
            if not self.url_entry.get().strip():
                self.url_entry.insert(0, self.url_placeholder)
                self.url_entry.config(fg='#888888')
        
        self.url_entry.bind("<FocusIn>", on_url_focus_in)
        self.url_entry.bind("<FocusOut>", on_url_focus_out)
        self.url_entry.bind("<KeyRelease>", self._on_url_entry_change)
        url_frame.grid_remove()  # Hide initially
        self.url_frame = url_frame

        # Output format selector (row 3, visually separated)
        output_format_frame = tk.LabelFrame(left_outer_frame, text="Output Formats", bg=DARK_BG, fg=DARK_TEXT, highlightbackground=DARK_FIELD, highlightcolor=DARK_FIELD)
        output_format_frame.grid(row=3, column=0, sticky="ew", pady=(4,0), padx=(0,0))
        # Style checkbuttons for dark mode
        self.format_txt_check = tk.Checkbutton(output_format_frame, text="Text", variable=self.output_format_txt, bg=DARK_BG, fg=DARK_TEXT, selectcolor=DARK_FIELD, activebackground=DARK_FIELD, activeforeground=DARK_TEXT)
        self.format_html_check = tk.Checkbutton(output_format_frame, text="HTML", variable=self.output_format_html, bg=DARK_BG, fg=DARK_TEXT, selectcolor=DARK_FIELD, activebackground=DARK_FIELD, activeforeground=DARK_TEXT)
        self.format_m3u_check = tk.Checkbutton(output_format_frame, text="M3U", variable=self.output_format_m3u, bg=DARK_BG, fg=DARK_TEXT, selectcolor=DARK_FIELD, activebackground=DARK_FIELD, activeforeground=DARK_TEXT)
        self.format_txt_check.pack(side="left", padx=(2, 2), pady=2)
        self.format_html_check.pack(side="left", padx=(2, 2), pady=2)
        self.format_m3u_check.pack(side="left", padx=(2, 2), pady=2)

        # Right: Style selector and process button
        right_frame = ttk.Frame(control_frame)
        right_frame.pack(side="right", padx=0, fill="none")  # Fixed width, doesn't expand

        ttk.Label(right_frame, text="Style:").pack(side="left", padx=(10, 2))
        style_dropdown = tk.OptionMenu(right_frame, self.selected_style, 
                                     *self.url_styles.keys(), 
                                     command=self.update_style)
        style_dropdown.configure(bg=DARK_BUTTON, fg=DARK_TEXT, 
                               activebackground=DARK_ACCENT, activeforeground=DARK_TEXT,
                               highlightbackground=DARK_BG, highlightthickness=0,
                               relief="flat", bd=0)
        style_dropdown["menu"].configure(bg=DARK_FIELD, fg=DARK_TEXT,
                                      activebackground=DARK_ACCENT, activeforeground=DARK_TEXT)
        style_dropdown.pack(side="left")

        # Remove old M3U output option (now in output formats)

        # Help button
        self.help_btn = ttk.Button(right_frame, text='?', width=2, command=self.show_help)
        self.help_btn.pack(side="left", padx=2)

        self.process_btn = ttk.Button(right_frame, text='Process', command=self.process, state='disabled')
        self.process_btn.pack(side="left", padx=5)

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

    def _on_url_entry_change(self, event=None):
        url = self.url_entry.get().strip()
        if self.input_mode.get() == "url":
            # Check if URL is valid and not placeholder
            if url.startswith('http') and url != self.url_placeholder:
                self.process_btn.config(state='normal')
            else:
                self.process_btn.config(state='disabled')
    def update_input_mode(self):
        """Show/hide widgets depending on input mode (file/url)"""
        mode = self.input_mode.get()
        if mode == "file":
            self.url_frame.grid_remove()
            self.file_frame.grid()
            self.process_btn.config(state='normal' if self.m3u_path else 'disabled')
        else:
            self.file_frame.grid_remove()
            self.url_frame.grid()
            url = self.url_entry.get().strip()
            self.process_btn.config(state='normal' if url.startswith('http') and url != self.url_placeholder else 'disabled')

        self.root.update()

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
                # Properly join URL using urllib.parse
                return urllib.parse.urljoin(self.github_base_url + '/', relative_path)
            return local_path  # Return unchanged if pattern not found
        except (ValueError, TypeError):
            return local_path
            
    def show_help(self):
        """Show help message explaining the application usage."""
        help_text = (
            "TV Logos M3U Matcher Help\n\n"
            "This application helps you match TV channel logos with entries in your M3U files.\n\n"
            "Main Features:\n"
            "• Process local M3U files or download from URLs\n"
            "• Choose between White or Colour logo styles\n"
            "• Generate output in text or HTML format with matched logo URLs\n"
            "• Interactive HTML output with expandable categories\n"
            "• Optionally update your M3U file with the logo URLs\n\n"
            "Usage Notes:\n"
            "1. Select input mode (Local File or URL)\n"
            "2. Choose logo style (White or Colour)\n"
            "3. Check 'Update M3U' if you want to modify the M3U file\n"
            "4. Click 'Process' to begin matching\n"
            "5. Choose save locations for output files (at the beginning)\n"
            "6. For HTML output, just save with a .html extension\n\n"
            "HTML Output:\n"
            "• Channels are grouped by category with expandable sections\n"
            "• Shows logo previews for each channel\n"
            "• Includes 'Copy URL' button for easy copying\n"
            "• Shows match statistics for each category\n\n"
            "File Save Dialogs:\n"
            "• Save dialogs appear at the START of processing\n"
            "• Choose .txt for simple text output or .html for interactive output\n"
            "• If 'Update M3U' is checked, you'll be asked where to save it\n"
            "• You can cancel either save dialog at any time\n"
            "• If you cancel the main output, the entire process will be stopped\n"
            "• If you cancel the M3U save, only the main output will be created\n\n"
            "Note: Closing a save dialog without selecting a file will cancel that output."
        )
        messagebox.showinfo('Help', help_text)

    def write_html_output(self, output_path, structured_data, matches, total_channels):
        """Generate an HTML output file with expandable categories and image previews"""
        html_template = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>M3U Logo Matcher Results</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #2d2d2d;
            color: #f0f0f0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            background-color: #007acc;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        h1 {
            margin: 0;
            font-size: 24px;
        }
        .summary {
            background-color: #3d3d3d;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .category {
            background-color: #3d3d3d;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .category-header {
            background-color: #444444;
            padding: 10px 15px;
            border-radius: 5px 5px 0 0;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
        }
        .category-header .expand-icon {
            margin-left: 10px;
            font-size: 18px;
            transition: transform 0.3s;
        }
        .category-content {
            padding: 0;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            display: block;
        }
        .category-content.expanded {
            padding: 15px;
            max-height: 10000px;
            transition: max-height 0.5s ease;
        }
        .category-content:not(.expanded) {
            max-height: 0;
            padding: 0;
        }
        .channel-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            grid-gap: 15px;
        }
        .channel-card {
            background-color: #232323;
            border-radius: 5px;
            padding: 10px 10px 15px 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            transition: box-shadow 0.2s;
        }
        .channel-card:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        }
        .logo-container {
            width: 120px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 8px;
            background: #181818;
            border-radius: 4px;
        }
        .logo-container img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        .channel-name {
            font-weight: bold;
            margin-bottom: 8px;
            text-align: center;
            min-height: 32px;
            display: flex;
            align-items: center;
            color: #fff;
            font-size: 15px;
        }
        .copy-button {
            background-color: #007acc;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 4px 10px;
            cursor: pointer;
            transition: background-color 0.3s;
            margin-top: 3px;
            font-size: 13px;
        }
        .copy-button:active, .copy-button:focus {
            outline: none;
            background-color: #005999;
        }
        .copy-button:hover {
            background-color: #005999;
        }
        .match-count {
            font-weight: normal;
            font-size: 14px;
            margin-left: 10px;
        }
        .no-logo {
            color: #ff6b6b;
            font-style: italic;
            font-size: 12px;
        }
        footer {
            margin-top: 30px;
            text-align: center;
            color: #aaaaaa;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container"> 
        <header>
            <h1>M3U Logo Matcher Results</h1>
        </header>
        
        <div class="summary">
            <p>Matched <strong>{{matches}}</strong> out of <strong>{{total_channels}}</strong> channels ({{match_percent}}%).</p>
            <p>Generated on {{date_time}}</p>
        </div>
        
        {{categories_html}}
        
        <footer>
            <p>Generated by TV Logos M3U Matcher</p>
        </footer>
    </div>

    <script>
        // Function to toggle category expansion
        function toggleCategory(element) {
            const content = element.nextElementSibling;
            const icon = element.querySelector('.expand-icon');
            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                icon.textContent = '▼';
            } else {
                content.classList.add('expanded');
                icon.textContent = '▲';
            }
        }

        // Function to copy logo URL to clipboard
        function copyLogoUrl(event, url) {
            event.stopPropagation();
            const button = event.target;
            const originalText = button.textContent;
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(url).then(() => {
                    button.textContent = 'Copied!';
                    setTimeout(() => {
                        button.textContent = originalText;
                    }, 1500);
                }, () => fallbackCopyTextToClipboard(url, button, originalText));
            } else {
                fallbackCopyTextToClipboard(url, button, originalText);
            }
        }

        function fallbackCopyTextToClipboard(text, button, originalText) {
            let textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.top = 0;
            textArea.style.left = 0;
            textArea.style.width = '2em';
            textArea.style.height = '2em';
            textArea.style.padding = 0;
            textArea.style.border = 'none';
            textArea.style.outline = 'none';
            textArea.style.boxShadow = 'none';
            textArea.style.background = 'transparent';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                button.textContent = 'Copied!';
                setTimeout(() => {
                    button.textContent = originalText;
                }, 1500);
            } catch (err) {
                button.textContent = 'Failed!';
                setTimeout(() => {
                    button.textContent = originalText;
                }, 1500);
            }
            document.body.removeChild(textArea);
        }

        // Expand the first category by default
        document.addEventListener('DOMContentLoaded', function() {
            const firstCategory = document.querySelector('.category-header');
            if (firstCategory) {
                toggleCategory(firstCategory);
            }
        });
    </script>
</body>
</html>
"""

        # Format the datetime
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate match percentage
        match_percent = int(matches / total_channels * 100) if total_channels > 0 else 0
        
        # Generate HTML for each category
        categories_html = []
        
        # Sort categories alphabetically
        sorted_categories = sorted(structured_data.keys())
        
        for category in sorted_categories:
            channels = structured_data[category]
            # Count matches in this category
            category_matches = sum(1 for ch in channels if ch['has_logo'])
            
            # Generate channel cards for this category
            channel_cards = []
            for channel in channels:
                # Fix logo URL using proper URL parsing
                logo_url = channel["logo_url"]
                if channel['has_logo'] and logo_url:
                    try:
                        # Parse and reconstruct URL to ensure it's valid
                        parsed = urllib.parse.urlparse(logo_url)
                        if not parsed.scheme:
                            # If no scheme, assume https
                            logo_url = 'https://' + logo_url
                        elif parsed.scheme == 'http':
                            # Convert http to https for security
                            logo_url = logo_url.replace('http://', 'https://', 1)
                        # Clean up any double slashes in path
                        parsed = urllib.parse.urlparse(logo_url)
                        clean_path = re.sub(r'/+', '/', parsed.path)
                        logo_url = urllib.parse.urlunparse((
                            parsed.scheme, parsed.netloc, clean_path,
                            parsed.params, parsed.query, parsed.fragment
                        ))
                    except (ValueError, TypeError):
                        # Fallback to original URL if parsing fails
                        pass
                        
                logo_html = f'<img src="{logo_url}" alt="{channel["name"]} logo">' if channel['has_logo'] else '<span class="no-logo">No logo found</span>'
                
                # Build the copy button separately
                copy_button = ''
                if channel['has_logo']:
                    # Use single quotes for JS argument to avoid escaping issues
                    escaped_url = channel["logo_url"].replace("'", "&#39;")
                    copy_button = f"<button class='copy-button' onclick=\"copyLogoUrl(event, '{escaped_url}')\">Copy URL</button>"

                card_html = f"""
                <div class="channel-card">
                    <div class="logo-container">
                        {logo_html}
                    </div>
                    <div class="channel-name">{channel["name"]}</div>
                    {copy_button}
                </div>
                """
                channel_cards.append(card_html)
            
            # Create the category section
            category_html = f"""
            <div class="category">
                <div class="category-header" onclick="toggleCategory(this)">
                    <span>{category} <span class="match-count">({category_matches}/{len(channels)} matched)</span></span>
                    <span class="expand-icon">▼</span>
                </div>
                <div class="category-content">
                    <div class="channel-grid">
                        {"".join(channel_cards)}
                    </div>
                </div>
            </div>
            """
            categories_html.append(category_html)
        
        # Combine all categories
        # Use str.replace to substitute the placeholders after escaping curly braces
        final_html = html_template.replace("{{matches}}", str(matches)) \
            .replace("{{total_channels}}", str(total_channels)) \
            .replace("{{match_percent}}", str(match_percent)) \
            .replace("{{date_time}}", date_time) \
            .replace("{{categories_html}}", "\n".join(categories_html))
        
        # Write the HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)

    def process(self):
        self.log_text.delete(1.0, tk.END)  # Clear log

        if not os.path.exists(self.countries_dir):
            messagebox.showerror('Error', f'Countries folder not found: {self.countries_dir}')
            return

        # Determine input mode
        mode = self.input_mode.get()
        m3u_path = None
        temp_file = None

        # Gather selected output formats
        selected_formats = []
        if self.output_format_txt.get():
            selected_formats.append("txt")
        if self.output_format_html.get():
            selected_formats.append("html")
        if self.output_format_m3u.get():
            selected_formats.append("m3u")

        if not selected_formats:
            messagebox.showerror('Error', 'Please select at least one output format.')
            return

        # Prompt for output file(s) at the start
        output_paths = {}
        if mode == "file":
            default_dir = os.path.dirname(self.m3u_path) if self.m3u_path else os.getcwd()
            default_filename = os.path.splitext(os.path.basename(self.m3u_path))[0] if self.m3u_path else "channel_logos"
        else:
            default_dir = os.getcwd()
            default_filename = "channel_logos"

        # Prompt for each selected output type
        for fmt in selected_formats:
            if fmt == "txt":
                ext = ".txt"
                filetypes = [("Text files", "*.txt"), ("All files", "*.*")]
            elif fmt == "html":
                ext = ".html"
                filetypes = [("HTML files", "*.html"), ("All files", "*.*")]
            elif fmt == "m3u":
                ext = ".m3u"
                filetypes = [("M3U files", "*.m3u"), ("All files", "*.*")]
            else:
                continue
            self.root.update()
            output_path = filedialog.asksaveasfilename(
                defaultextension=ext,
                filetypes=filetypes,
                initialdir=default_dir,
                initialfile=f"{default_filename}_output{ext}" if fmt != "m3u" else f"{default_filename}{ext}",
                title=f"Save {fmt.upper()} Output As"
            )
            if not output_path:
                self.log(f"{fmt.upper()} output was cancelled by user")
                if fmt == "txt" or fmt == "html":
                    self.status_label.config(text="Ready")
                    self.progress["value"] = 0
                    messagebox.showinfo('Operation Cancelled', f'Processing was cancelled because you closed the {fmt.upper()} save dialog.')
                    return
                else:
                    continue
            output_paths[fmt] = output_path

        # Now fetch and parse the M3U file
        if mode == "file":
            m3u_path = self.m3u_path
            if not m3u_path or not os.path.exists(m3u_path):
                messagebox.showerror('Error', 'No M3U file selected.')
                return
            self.log(f"Processing M3U file: {os.path.basename(m3u_path)}")
        else:
            url = self.url_entry.get().strip()
            if not url or not url.lower().startswith('http') or url == self.url_placeholder:
                messagebox.showerror('Error', 'Please enter a valid M3U URL.')
                return
            self.log(f"Downloading M3U from URL: {url}")
            try:
                # Create request with timeout and user agent
                request = urllib.request.Request(url, headers={
                    'User-Agent': 'M3U Logo Matcher/1.0'
                })
                
                temp_fd, temp_path = tempfile.mkstemp(suffix='.m3u')
                with os.fdopen(temp_fd, 'wb') as f:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        # Check content length if available
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            size = int(content_length)
                            if size > 50 * 1024 * 1024:  # 50MB limit
                                raise ValueError(f"File too large: {size} bytes (max 50MB)")
                        
                        # Read in chunks with size limit
                        total_read = 0
                        max_size = 50 * 1024 * 1024  # 50MB
                        chunk_size = 8192
                        
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            total_read += len(chunk)
                            if total_read > max_size:
                                raise ValueError(f"File too large: exceeded {max_size} bytes")
                            f.write(chunk)
                            
                m3u_path = temp_path
                temp_file = temp_path
                self.log(f"Downloaded {total_read} bytes to temporary file: {temp_path}")
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as e:
                if temp_fd:
                    try:
                        os.close(temp_fd)
                        os.remove(temp_path)
                    except:
                        pass
                messagebox.showerror('Error', f'Failed to download M3U: {e}')
                return
            except Exception as e:
                if temp_fd:
                    try:
                        os.close(temp_fd)
                        os.remove(temp_path)
                    except:
                        pass
                messagebox.showerror('Error', f'Unexpected error downloading M3U: {e}')
                return

        self.log(f"Using {self.selected_style.get()} logos")

        # Parse the channels first
        channels, m3u_content = parse_m3u(m3u_path)
        total_channels = len(channels)
        self.log(f"Found {total_channels} channels in the M3U file")

        # Reset progress bar
        self.progress["value"] = 0
        self.progress["maximum"] = total_channels

        output_lines = []
        matches = 0
        channel_logos = {}
        structured_data = {}

        # Process each channel
        for i, ch in enumerate(channels):
            self.progress["value"] = i + 1
            progress_pct = int((i + 1) / total_channels * 100)
            self.status_label.config(text=f"Processing: {progress_pct}% complete")
            self.root.update()

            self.log(f"\nChannel {i+1}/{total_channels}: '{ch['tvg_name']}'")
            local_logo_path = match_logo(ch['group_title'], ch['tvg_name'], self.countries_dir, self.log)
            github_logo_url = self.convert_to_github_url(local_logo_path)
            if local_logo_path:
                matches += 1
                if 'line_index' in ch:
                    channel_logos[ch['line_index']] = github_logo_url
            output_lines.append(f"group title='{ch['group_title']}' - tvg-name='{ch['tvg_name']}' logo path='{github_logo_url}'")
            if 'group_title' not in ch:
                ch['group_title'] = 'Uncategorized'
            if ch['group_title'] not in structured_data:
                structured_data[ch['group_title']] = []
            structured_data[ch['group_title']].append({
                'name': ch['tvg_name'] or 'Unknown',
                'logo_url': github_logo_url,
                'has_logo': bool(local_logo_path)
            })


        # Write all selected outputs
        output_msgs = []
        if "txt" in output_paths:
            try:
                with open(output_paths["txt"], 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output_lines))
                self.log(f"Text output written to: {output_paths['txt']}")
                output_msgs.append(f"Text output written to {os.path.basename(output_paths['txt'])}")
            except Exception as e:
                self.log(f"ERROR writing text output: {e}")
                messagebox.showerror('Error', f'Failed to write text output: {e}')
                return
        if "html" in output_paths:
            try:
                self.write_html_output(output_paths["html"], structured_data, matches, total_channels)
                self.log(f"HTML output written to: {output_paths['html']}")
                output_msgs.append(f"HTML output written to {os.path.basename(output_paths['html'])}")
            except Exception as e:
                self.log(f"ERROR writing HTML output: {e}")
                messagebox.showerror('Error', f'Failed to write HTML output: {e}')
                return
        if "m3u" in output_paths:
            self.log(f"Creating updated M3U file with logo URLs")
            for i, line in enumerate(m3u_content):
                if i in channel_logos and line.startswith('#EXTINF'):
                    # Escape the logo URL to prevent injection
                    escaped_logo_url = channel_logos[i].replace('\\', '\\\\').replace('"', '\\"')
                    
                    if 'tvg-logo="' in line:
                        # Use re.escape for the replacement to handle special characters
                        m3u_content[i] = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{escaped_logo_url}"', line)
                    else:
                        comma_pos = line.rfind(',')
                        if comma_pos != -1:
                            m3u_content[i] = line[:comma_pos] + f' tvg-logo="{escaped_logo_url}"' + line[comma_pos:]
            try:
                with open(output_paths["m3u"], 'w', encoding='utf-8') as f:
                    f.write('\n'.join(m3u_content))
                self.log(f"Updated M3U written to: {output_paths['m3u']}")
                output_msgs.append(f"Updated M3U written to {os.path.basename(output_paths['m3u'])}")
            except Exception as e:
                self.log(f"ERROR writing M3U output: {e}")
                messagebox.showerror('Error', f'Failed to write M3U output: {e}')
                return

        output_msg = f"Matched {matches} out of {total_channels} channels.\n" + "\n".join(output_msgs)

        # Update final status
        match_percent = int(matches / total_channels * 100) if total_channels > 0 else 0
        self.status_label.config(text=f"Complete: {match_percent}% matches found")
        self.stats_label.config(text=f"Matched {matches} out of {total_channels} channels")

        self.log(f"\nMatched {matches} out of {total_channels} channels ({match_percent}%)")
        messagebox.showinfo('Done', output_msg)

        # Clean up temp file if used - moved to the end to ensure cleanup in all scenarios
        if temp_file:
            try:
                os.remove(temp_file)
                self.log("Temporary file cleaned up")
            except Exception as e:
                self.log(f"Failed to clean up temporary file: {e}")
                pass

if __name__ == '__main__':
    import os.path
    
    # Check for first run by looking for config file
    user_home = os.path.expanduser("~")
    config_dir = os.path.join(user_home, ".m3u_logo_matcher")
    first_run_flag = os.path.join(config_dir, "first_run_completed")
    show_help_at_start = not os.path.exists(first_run_flag)
    
    # Create config directory if it doesn't exist
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir)
        except (OSError, PermissionError):
            pass
    
    root = tk.Tk()
    app = M3UParserApp(root)
    root.geometry("700x450")
    root.minsize(650, 400)
    
    # Show help dialog on first run
    if show_help_at_start:
        # Use after to make sure the UI is fully loaded
        root.after(500, app.show_help)
        
        # Create the flag file to mark that first run is complete
        try:
            with open(first_run_flag, 'w') as f:
                f.write("First run completed")
        except (OSError, PermissionError):
            pass
    
    root.mainloop()
