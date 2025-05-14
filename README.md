# Nestlé Waters Egypt - Competitor Price Tracker

This web application is designed for Nestlé Waters Egypt's Commercial Development Team to track and analyze competitor product prices on Amazon Egypt. The application allows users to search for products by keyword, scrape product information, and view price statistics.

## Key Features

- **Product Search**: Search for products using keywords and specify the maximum number of products to retrieve.
- **Price Analysis Dashboard**: View statistics including average price, minimum price, maximum price, and the number of products analyzed.
- **Product Listings**: Detailed information about scraped products is displayed in a table format.
- **Data Export**: Download the scraped data and price statistics as CSV files.

## User Interface Components

- **Search Form**: Input keyword and specify the product count limit, with options for detailed information.
- **Price Statistics Cards**: Display key metrics such as average price, minimum price, and maximum price.
- **Product Listing Table**: Show detailed product information.
- **Download Buttons**: Export data and price statistics as CSV files.

## Features Overview

1. **Product Scraping**:
   - Scrape Amazon.eg for water products, with a focus on Nestlé Pure Life and competitors.
   - Automatically detect water brands and sizes using pattern matching.
   - Compare prices across different water brands and sizes.
   - Track product availability based on price thresholds.

2. **Price Analysis**:
   - Compare prices for different brands and sizes.
   - Show best deals and offers for each water size category.
   - Track availability for specific brands (e.g., Nestlé Pure Life and Baraka).

3. **Data Export**:
   - Export scraped product data and price statistics to CSV files.

## Improvements

1. **Arabic Text Support**:
   - Added Arabic brand name mappings to detect brands in Arabic product titles.
   - Normalized Arabic text to handle diacritics and special characters.
   - Enhanced size detection for Arabic water sizes (e.g., "1.5 لتر" for 1.5L).

2. **Enhanced Brand Filtering**:
   - Improved brand detection with multiple search terms for each brand.
   - Used both Arabic and English brand names for better search results.

3. **Multiple Search Strategy**:
   - The scraper now uses multiple search queries for each brand, both in English and Arabic.

4. **Duplicate Protection**:
   - Added logic to handle duplicate products and keep the one with better pricing.

5. **Better Error Handling**:
   - Enhanced error handling for alternative searches and random delays to avoid blocking.

6. **Improved User Interface**:
   - Created a modern, responsive dashboard interface.
   - Added visual elements like badges and progress bars.
   - Brand-specific styling for Nestlé Pure Life and competitors.

## Installation and Usage

### Requirements
- Python 3.7 or higher
- Flask
- Requests
- BeautifulSoup4
- pandas
- Other dependencies listed in `requirements.txt`

### Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/your-repository-url](https://github.com/sallmamostaffa/nestle-price-tracker.git)
   cd nestle-price-tracker
