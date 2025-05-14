from flask import Flask, render_template, request, Response, redirect, url_for
from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import random
import re
import io
import csv
import os
import unicodedata
from datetime import datetime
from urllib.parse import quote_plus

app = Flask(__name__)

# Create necessary folders
os.makedirs('static', exist_ok=True)
os.makedirs('static/data', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Global variables to store scraped data
df_products = None
price_stats = None
last_scrape_time = None
filtered_brand = None

# Water brands and their price thresholds for NPL
# Added Arabic brand names to improve detection
WATER_BRANDS = [
    "Elano", "Nestlé Pure Life", "Baraka", "Puvana", "Aquafina", 
    "ISIS", "Hayat", "Safi", "Aqua Delta", "evian", 
    "Dasani", "FLO"
]

# Add Arabic brand names mapping
ARABIC_BRAND_MAPPINGS = {
    "نستله بيور لايف": "Nestlé Pure Life",
    "بيور لايف": "Nestlé Pure Life",
    "نستله": "Nestlé Pure Life",
    "بركة": "Baraka",
    "باراكا": "Baraka",
    "إيلانو": "Elano",
    "ايلانو": "Elano",
    "بوفانا": "Puvana",
    "أكوافينا": "Aquafina",
    "اكوافينا": "Aquafina",
    "ايزيس": "ISIS",
    "إيزيس": "ISIS",
    "حياة": "Hayat",
    "صافي": "Safi",
    "اكوا دلتا": "Aqua Delta",
    "أكوا دلتا": "Aqua Delta",
    "إيفيان": "evian",
    "ايفيان": "evian",
    "داساني": "Dasani",
    "فلو": "FLO"
}

# Add Brand URLs for more accurate filtering
BRAND_SEARCH_TERMS = {
    "Nestlé Pure Life": ["nestle pure life", "nestle", "نستله بيور لايف", "نستله", "بيور لايف"],
    "Baraka": ["baraka", "بركة", "باراكا"],
    "Elano": ["elano", "إيلانو", "ايلانو"],
    "Puvana": ["puvana", "بوفانا"],
    "Aquafina": ["aquafina", "أكوافينا", "اكوافينا"],
    "ISIS": ["isis water", "isis mineral", "ايزيس", "إيزيس"],
    "Hayat": ["hayat", "حياة"],
    "Safi": ["safi", "صافي"],
    "Aqua Delta": ["aqua delta", "aquadelta", "اكوا دلتا", "أكوا دلتا"],
    "evian": ["evian", "ايفيان", "إيفيان"],
    "Dasani": ["dasani", "داساني"],
    "FLO": ["flo water", "flo mineral", "فلو"]
}

NPL_PRICE_THRESHOLDS = {
    "0.33L": 100,
    "0.6L": 100,
    "1L": 100,
    "1.5L": 100,
    "6L": 200,
    "0.24L Sparkling": 300,
    "5 Gallons": 100
}

# List of standard sizes in order we want them to appear
STANDARD_SIZES = [
    "0.33L", "0.6L", "1L", "1.5L", "6L", "0.24L Sparkling", "5 Gallons"
]

# Add Arabic size mappings
ARABIC_SIZE_MAPPINGS = {
    "0.33 لتر": "0.33L",
    "0.6 لتر": "0.6L",
    "1 لتر": "1L",
    "1.5 لتر": "1.5L",
    "6 لتر": "6L",
    "0.24 لتر فوار": "0.24L Sparkling",
    "5 جالون": "5 Gallons"
}

# Function to extract Product Title
def get_title(soup):
    try:
        # Try multiple possible title elements
        title = soup.find("span", attrs={"id": "productTitle"})
        if not title:
            title = soup.find("span", class_="a-size-base-plus a-color-base a-text-normal")
            if not title:
                title = soup.find("span", class_="a-size-medium a-color-base a-text-normal")
        
        return title.text.strip() if title else "Title not found"
    except AttributeError:
        return "Error extracting title"

# Function to extract Product Price
def get_price(soup):
    try:
        # Try multiple possible price elements
        price = soup.find("span", class_="a-offscreen")
        if not price:
            price = soup.find("span", class_="a-price-whole")
        
        return price.text.strip() if price else "Price not found"
    except AttributeError:
        return "Error extracting price"

# Function to extract Product Availability
def get_availability(soup):
    try:
        # Try multiple possible availability elements
        available = soup.find("span", id="availability")
        
        if not available:
            available = soup.find("div", id="availability")
            
        if not available:
            available = soup.find("div", id="merchantInfoFeature")
            
        if not available:
            delivery_block = soup.find("div", id="deliveryBlockMessage")
            if delivery_block:
                available = delivery_block.find("span")
        
        # Clean up the text if found
        if available:
            availability_text = available.text.strip()
            # Remove extra whitespace
            availability_text = re.sub(r'\s+', ' ', availability_text)
            return availability_text
        else:
            return "Availability not found"
    except AttributeError:
        return "Error extracting availability"

def normalize_text(text):
    """Normalize text to make it easier to compare"""
    # Remove diacritics
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                  if unicodedata.category(c) != 'Mn')
    # Convert to lowercase
    text = text.lower()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_brand_from_title(title):
    """Extract the water brand from the product title"""
    normalized_title = normalize_text(title)
    
    # First check if any Arabic brand names are in the title
    for arabic_name, english_brand in ARABIC_BRAND_MAPPINGS.items():
        if normalize_text(arabic_name) in normalized_title:
            return english_brand
    
    # Then check for English brand patterns
    for brand, search_terms in BRAND_SEARCH_TERMS.items():
        for term in search_terms:
            if normalize_text(term) in normalized_title:
                return brand
    
    # If no match found, try a simple approach for each brand
    for brand in WATER_BRANDS:
        if normalize_text(brand) in normalized_title:
            return brand
    
    return "Other"

def extract_size_from_title(title):
    """Extract the water size from the product title"""
    normalized_title = normalize_text(title)
    
    # First check Arabic size mappings
    for arabic_size, english_size in ARABIC_SIZE_MAPPINGS.items():
        if normalize_text(arabic_size) in normalized_title:
            return english_size
    
    # Specific size detection patterns
    size_patterns = [
        # Standard sizes
        (r'(?:^|\s)0\.33\s*l(?:iter)?(?:\s|$)', "0.33L"),
        (r'(?:^|\s)330\s*ml(?:\s|$)', "0.33L"),
        (r'(?:^|\s)0\.6\s*l(?:iter)?(?:\s|$)', "0.6L"),
        (r'(?:^|\s)600\s*ml(?:\s|$)', "0.6L"),
        (r'(?:^|\s)1\s*l(?:iter)?(?:\s|$)', "1L"),
        (r'(?:^|\s)1000\s*ml(?:\s|$)', "1L"),
        (r'(?:^|\s)1\.5\s*l(?:iter)?(?:\s|$)', "1.5L"),
        (r'(?:^|\s)1500\s*ml(?:\s|$)', "1.5L"),
        (r'(?:^|\s)6\s*l(?:iter)?(?:\s|$)', "6L"),
        (r'(?:^|\s)6000\s*ml(?:\s|$)', "6L"),
        (r'(?:^|\s)0\.24\s*l(?:iter)?(?:\s|sparkling)', "0.24L Sparkling"),
        (r'(?:^|\s)240\s*ml(?:\s|sparkling)', "0.24L Sparkling"),
        (r'(?:^|\s)5\s*gallon(?:s)?(?:\s|$)', "5 Gallons"),
        
        # Alternative formats
        (r'(?:^|\s)1\s*-\s*liter(?:\s|$)', "1L"),
        (r'(?:^|\s)1\.5\s*-\s*liter(?:\s|$)', "1.5L"),
        (r'(?:^|\s)6\s*-\s*liter(?:\s|$)', "6L"),
        
        # Arabic numbers with L
        (r'(?:^|\s)0[,.]33\s*l(?:iter)?(?:\s|$)', "0.33L"),
        (r'(?:^|\s)0[,.]6\s*l(?:iter)?(?:\s|$)', "0.6L"),
        (r'(?:^|\s)1[,.]5\s*l(?:iter)?(?:\s|$)', "1.5L"),
        
        # Common Arabic patterns (using English numbers)
        (r'(?:^|\s)0\.33\s*لتر(?:\s|$)', "0.33L"),
        (r'(?:^|\s)0\.6\s*لتر(?:\s|$)', "0.6L"),
        (r'(?:^|\s)1\s*لتر(?:\s|$)', "1L"),
        (r'(?:^|\s)1\.5\s*لتر(?:\s|$)', "1.5L"),
        (r'(?:^|\s)6\s*لتر(?:\s|$)', "6L"),
        (r'(?:^|\s)5\s*جالون(?:\s|$)', "5 Gallons"),
        
        # Specific packs that indicate size
        (r'(?:^|\s)pack\s*of\s*6\s*[xX]\s*1\.5\s*l(?:iter)?(?:\s|$)', "1.5L"),
        (r'(?:^|\s)pack\s*of\s*12\s*[xX]\s*0\.33\s*l(?:iter)?(?:\s|$)', "0.33L"),
        (r'(?:^|\s)pack\s*of\s*6\s*[xX]\s*1\s*l(?:iter)?(?:\s|$)', "1L"),
        
        # More general patterns for bottle sizes
        (r'(?:^|\s)(\d+(?:\.\d+)?)\s*l(?:iter)?(?:\s|$)', lambda m: f"{m.group(1)}L"),
        (r'(?:^|\s)(\d+)\s*ml(?:\s|$)', lambda m: f"{float(m.group(1))/1000:.2f}L".replace(".00", "")),
        (r'(?:^|\s)(\d+)\s*gallon(?:s)?(?:\s|$)', lambda m: f"{m.group(1)} Gallons"),
    ]
    
    # Check all patterns
    for pattern, size in size_patterns:
        match = re.search(pattern, normalized_title)
        if match:
            if callable(size):
                return size(match)
            else:
                return size
    
    # Additional check for sparkling water
    if "sparkling" in normalized_title or "فوار" in normalized_title:
        return "0.24L Sparkling"
    
    return "Unknown Size"

def check_availability(price_text, size):
    """
    Check if a product is available based on NPL price thresholds
    """
    if price_text == "Price not found":
        return "Unknown"
    
    # Extract numeric price value
    price_match = re.search(r'([\d,.]+)', price_text)
    if not price_match:
        return "Unknown"
    
    # Clean and convert price to float
    price_str = price_match.group(1).replace(',', '')
    try:
        price = float(price_str)
    except ValueError:
        return "Unknown"
    
    # Check against threshold for NPL
    threshold = NPL_PRICE_THRESHOLDS.get(size)
    if threshold and price > threshold:
        return "Not Available"
    
    return "Available"

def create_price_table(df):
    """
    Create a table with SKUs and prices for each brand
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Filter out products without brand or size info
    df_valid = df[(df['Brand'] != 'Other') & (df['Size'] != 'Unknown Size')]
    
    if df_valid.empty:
        # Create an empty DataFrame with the expected structure
        empty_df = pd.DataFrame(columns=WATER_BRANDS)
        empty_df.index.name = 'Size'
        return empty_df
    
    # Create pivot table: Size x Brand with Price values
    pivot_df = df_valid.pivot_table(
        index='Size', 
        columns='Brand', 
        values='Numeric Price',
        aggfunc='min'  # Min price for each size-brand combination
    )
    
    # Fill NaN with empty string for better display
    pivot_df = pivot_df.fillna('')
    
    # Round numeric values to whole numbers
    for col in pivot_df.columns:
        pivot_df[col] = pivot_df[col].apply(lambda x: round(x) if isinstance(x, (int, float)) else x)
    
    # Reindex to ensure standard size order
    if not pivot_df.empty:
        # Filter sizes to only those that exist in the pivot table
        valid_sizes = [size for size in STANDARD_SIZES if size in pivot_df.index]
        if valid_sizes:
            pivot_df = pivot_df.reindex(valid_sizes)
    
    return pivot_df

def calculate_availability_percentage(df, brand='Nestlé Pure Life'):
    """
    Calculate the availability percentage for a given brand
    """
    if df is None or df.empty:
        return 0
    
    # Filter for the specified brand
    brand_df = df[df['Brand'] == brand]
    
    if len(brand_df) == 0:
        return 0
    
    # Count available products
    available_count = len(brand_df[brand_df['Availability Status'] == 'Available'])
    
    # Calculate percentage
    percentage = (available_count / len(brand_df)) * 100
    
    return round(percentage, 2)

def find_best_offers(df):
    """
    Find the best price offers for each size
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Filter for valid products
    df_valid = df[(df['Brand'] != 'Other') & 
                 (df['Size'] != 'Unknown Size') & 
                 (df['Numeric Price'] > 0)]
    
    if df_valid.empty:
        return pd.DataFrame()
    
    # Group by size and find minimum price
    best_offers = df_valid.groupby('Size').apply(
        lambda x: x.loc[x['Numeric Price'].idxmin()]
    )[['Size', 'Brand', 'Numeric Price']]
    
    # Rename columns for clarity
    best_offers = best_offers.rename(columns={'Numeric Price': 'Best Price'})
    
    return best_offers

def scrape_amazon(keyword="water", brand_filter=None, max_products=48):
    """
    Scrape Amazon products based on keyword search
    """
    global df_products, price_stats, last_scrape_time, filtered_brand
    
    # Track the filtered brand
    filtered_brand = brand_filter
    
    # Headers for request to mimic a browser visit
    HEADERS = ({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        'Accept-Language': 'en-US, en;q=0.5'
    })
    
    # If brand filter is specified, use more specific search terms
    search_terms = []
    if brand_filter:
        # Check if brand filter is a known brand
        for brand, terms in BRAND_SEARCH_TERMS.items():
            if normalize_text(brand_filter) in normalize_text(brand):
                # Use all search terms for this brand
                search_terms = [f"{keyword} {term}" for term in terms]
                break
        
        # If no specific terms found, use the brand filter as is
        if not search_terms:
            search_terms = [f"{keyword} {brand_filter}"]
    else:
        search_terms = [keyword]
    
    # Initialize empty lists for data collection
    all_titles = []
    all_prices = []
    all_brands = []
    all_sizes = []
    all_numeric_prices = []
    all_availability_statuses = []
    
    # Scrape for each search term
    for search_term in search_terms:
        # URL encode the search term
        encoded_search = quote_plus(search_term)
        URL = f"https://www.amazon.eg/s?k={encoded_search}&ref=nb_sb_noss_1"
        
        try:
            # HTTP Request with a random delay to avoid being blocked
            time.sleep(random.uniform(1, 2))
            webpage = requests.get(URL, headers=HEADERS)
            
            # Check if request was successful
            if webpage.status_code != 200:
                continue  # Skip this search term and try the next one
            
            # Soup Object containing all data
            soup = BeautifulSoup(webpage.content, "html.parser")
            
            # Fetch product cards
            products = soup.select("div.s-result-item[data-component-type='s-search-result']")
            
            if not products:
                continue  # Skip this search term and try the next one
            
            # Extract data from search results page
            product_count = min(len(products), max_products)
            
            for product in products[:product_count]:
                # Extract product URL - try multiple possible selectors
                a_tag = None
                
                # Try different possible a tag classes
                possible_a_classes = [
                    "a-link-normal s-no-outline",
                    "a-link-normal s-underline-text s-underline-link-text s-link-style a-text-normal",
                    "a-link-normal s-link-style a-text-normal", 
                    "a-link-normal a-text-normal"
                ]
                
                for class_name in possible_a_classes:
                    a_tag = product.find("a", class_=class_name)
                    if a_tag:
                        break
                        
                # If still not found, try just finding any a tag with title in h2
                if not a_tag:
                    h2 = product.find("h2")
                    if h2:
                        a_tag = h2.find("a")
                
                # Extract title - try multiple possible selectors
                title_element = None
                # Try h2 first as it often contains the product title
                h2 = product.find("h2")
                if h2:
                    title_element = h2
                
                # If not in h2, try common span classes
                if not title_element:
                    possible_title_classes = [
                        "a-size-base-plus a-color-base a-text-normal",
                        "a-size-medium a-color-base a-text-normal",
                        "a-size-base a-color-base"
                    ]
                    
                    for class_name in possible_title_classes:
                        title_element = product.find("span", class_=class_name)
                        if title_element:
                            break
                
                # Extract price
                price_element = product.find("span", class_="a-offscreen")
                if not price_element:
                    price_element = product.find("span", class_="a-price-whole")
                
                title = title_element.text.strip() if title_element else "Title not found"
                price = price_element.text.strip() if price_element else "Price not found"
                
                # Extract brand and size from title
                brand = extract_brand_from_title(title)
                size = extract_size_from_title(title)
                
                # Extract numeric price for calculations
                numeric_price = 0
                if price != "Price not found":
                    price_match = re.search(r'([\d,.]+)', price)
                    if price_match:
                        try:
                            numeric_price = float(price_match.group(1).replace(',', ''))
                        except ValueError:
                            numeric_price = 0
                
                # Check availability based on NPL price thresholds
                availability_status = check_availability(price, size)
                
                # Add data - check if this product is already in our list
                duplicate = False
                for i, existing_title in enumerate(all_titles):
                    if normalize_text(title) == normalize_text(existing_title):
                        duplicate = True
                        # If this price is better, update the existing record
                        if numeric_price > 0 and numeric_price < all_numeric_prices[i]:
                            all_prices[i] = price
                            all_numeric_prices[i] = numeric_price
                        break
                
                if not duplicate:
                    all_titles.append(title)
                    all_prices.append(price)
                    all_brands.append(brand)
                    all_sizes.append(size)
                    all_numeric_prices.append(numeric_price)
                    all_availability_statuses.append(availability_status)
                
        except Exception as e:
            print(f"Error scraping {search_term}: {str(e)}")
            continue  # Skip this search term and try the next one
    
    # Create DataFrame with all collected data
    if all_titles:
        data = {
            "Product Title": all_titles,
            "Price": all_prices,
            "Brand": all_brands,
            "Size": all_sizes,
            "Numeric Price": all_numeric_prices,
            "Availability Status": all_availability_statuses
        }
        
        df_products = pd.DataFrame(data)
        
        # Filter by brand if specified
        if brand_filter:
            # Try to find the canonical brand name if using a partial name
            canonical_brand = None
            for brand_name in WATER_BRANDS:
                if normalize_text(brand_filter) in normalize_text(brand_name):
                    canonical_brand = brand_name
                    break
            
            if canonical_brand:
                df_products = df_products[df_products['Brand'] == canonical_brand]
            else:
                # Use fuzzy matching for brand filtering
                normalized_filter = normalize_text(brand_filter)
                brand_mask = df_products['Brand'].apply(
                    lambda x: normalized_filter in normalize_text(x)
                )
                title_mask = df_products['Product Title'].apply(
                    lambda x: normalized_filter in normalize_text(x)
                )
                df_products = df_products[brand_mask | title_mask]
        
        # Create price table
        price_table = create_price_table(df_products)
        
        # Find best offers
        best_offers = find_best_offers(df_products)
        
        # Calculate availability percentages
        npl_availability = calculate_availability_percentage(df_products, "Nestlé Pure Life")
        baraka_availability = calculate_availability_percentage(df_products, "Baraka")
        
        # Price analysis statistics
        valid_prices = [p for p in all_numeric_prices if p > 0]
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            
            price_stats = {
                "Average Price": f"{avg_price:.2f} EGP",
                "Minimum Price": f"{min_price:.2f} EGP",
                "Maximum Price": f"{max_price:.2f} EGP",
                "Number of Products": len(valid_prices),
                "NPL Availability": f"{npl_availability}%",
                "Baraka Availability": f"{baraka_availability}%",
                "Price Table": price_table,
                "Best Offers": best_offers
            }
        else:
            price_stats = {"message": "No valid prices found for analysis"}
        
        last_scrape_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to CSV
        df_products.to_csv('static/data/products.csv', index=False, encoding='utf-8-sig')
        
        # Save price table to CSV
        price_table.to_csv('static/data/price_table.csv', encoding='utf-8-sig')
        
        return {"status": "success", "products": len(all_titles)}
    else:
        return {"status": "error", "message": "No products found or all searches failed"}

@app.route('/')
def index():
    price_table = None
    best_offers = None
    
    if price_stats and 'Price Table' in price_stats:
        price_table = price_stats['Price Table']
    
    if price_stats and 'Best Offers' in price_stats:
        best_offers = price_stats['Best Offers']
    
    return render_template('index.html', 
                           products=df_products, 
                           stats=price_stats,
                           last_scrape=last_scrape_time,
                           filtered_brand=filtered_brand,
                           price_table=price_table,
                           best_offers=best_offers,
                           brands=WATER_BRANDS)

@app.route('/scrape', methods=['POST'])
def scrape():
    keyword = request.form.get('keyword', 'water')
    brand_filter = request.form.get('brand_filter', None)
    max_products = int(request.form.get('max_products', 48))
    
    # If brand filter is empty string, set to None
    if brand_filter == "":
        brand_filter = None
    
    result = scrape_amazon(keyword, brand_filter, max_products)
    
    if result["status"] == "success":
        return redirect(url_for('index'))
    else:
        return render_template('error.html', error=result["message"])

@app.route('/download')
def download():
    if df_products is None:
        return redirect(url_for('index'))
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(df_products.columns.tolist())
    
    # Write data
    for _, row in df_products.iterrows():
        writer.writerow(row.tolist())
    
    output.seek(0)
    
    # Generate the response
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=amazon_products_{timestamp}.csv"})

@app.route('/download_price_table')
def download_price_table():
    if price_stats is None or 'Price Table' not in price_stats:
        return redirect(url_for('index'))
    
    price_table = price_stats['Price Table']
    
    output = io.StringIO()
    price_table.to_csv(output)
    
    output.seek(0)
    
    # Generate the response
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=price_table_{timestamp}.csv"})

@app.route('/download_stats')
def download_stats():
    if price_stats is None:
        return redirect(url_for('index'))
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers and data
    writer.writerow(["Statistic", "Value"])
    
    for key, value in price_stats.items():
        # Skip dataframes in the stats
        if key not in ['Price Table', 'Best Offers']:
            writer.writerow([key, value])
    
    output.seek(0)
    
    # Generate the response
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=price_analysis_{timestamp}.csv"})
if __name__ == '__main__':
    app.run(debug=True)