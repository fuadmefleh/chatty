"""Amazon order PDF and CSV parser with SQLite database storage."""

import sqlite3
import re
import csv
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import PyPDF2
import base64
import os
import shutil
from openai import AsyncOpenAI


class AmazonOrderDB:
    """SQLite database manager for Amazon orders."""
    
    def __init__(self, db_path: str = "data/amazon/amazon_orders.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        # Orders table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                order_date TEXT,
                total_amount REAL,
                subtotal REAL,
                tax REAL,
                shipping REAL,
                discounts REAL,
                pdf_filename TEXT,
                parsed_date TEXT,
                raw_text TEXT
            )
        """)
        
        # Order items table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                category TEXT,
                seller TEXT,
                FOREIGN KEY (order_id) REFERENCES orders (order_id)
            )
        """)
        
        self.conn.commit()
        
        # Add category column if it doesn't exist (for existing databases)
        try:
            self.cursor.execute("ALTER TABLE order_items ADD COLUMN category TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Add seller column if it doesn't exist
        try:
            self.cursor.execute("ALTER TABLE order_items ADD COLUMN seller TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass
    
    @staticmethod
    def categorize_item(item_name: str) -> str:
        """Categorize an item based on its name.
        
        Categories:
        - Food: Groceries, snacks, frozen food, fresh produce, meat, dairy
        - Beverages: Drinks, milk, juice, water, coffee
        - Household: Cleaning products, paper products, trash bags
        - Kitchen Supplies: Cookware, utensils, disposable items, foil
        - Personal Care: Toiletries, hygiene products
        - Pet Supplies: Pet food, pet care items
        - Health: Vitamins, medications, first aid
        - Baby & Kids: Baby products, diapers, kid-specific items
        - Electronics: Tech products, cables, accessories
        - Books & Media: Books, movies, music
        - Clothing: Apparel, shoes, accessories
        - Home & Garden: Furniture, decor, tools
        - Sports & Outdoors: Fitness, camping, outdoor gear
        - Other: Everything else
        """
        item_lower = item_name.lower()
        
        # Electronics - Check FIRST for Apple products and other electronics
        # Apple products must be checked before food to avoid 'apple' matching
        electronics_keywords = [
            'imac', 'macbook', 'ipad', 'iphone', 'airpods', 'apple watch',
            'mac mini', 'apple tv', 'apple pencil', 'apple m1', 'apple m2', 'apple m3', 'apple m4',
            'laptop', 'computer', 'tablet', 'smartphone', 'desktop',
            'cable', 'charger', 'adapter', 'usb', 'hdmi', 'bluetooth',
            'headphone', 'earbud', 'speaker', 'mouse', 'keyboard',
            'phone case', 'screen protector', 'battery', 'power bank',
            'monitor', 'webcam', 'carplay'
        ]
        
        if any(keyword in item_lower for keyword in electronics_keywords):
            return 'Electronics'
        
        # Health & Supplements - check before food (melatonin chewables, etc.)
        health_keywords = [
            'vitamin', 'supplement', 'melatonin', 'probiotic', 'omega',
            'medicine', 'medication', 'pill', 'tablet', 'capsule',
            'bandage', 'first aid', 'aspirin', 'pain relief', 'antacid',
            'hydrocortisone', 'anti itch', 'medicated', 'drug-free',
            'sleep supplement', 'sleep aid'
        ]
        
        if any(keyword in item_lower for keyword in health_keywords):
            return 'Health'
        
        # High priority food indicators
        high_priority_food = [
            'fresh ', 'ice cream', 'frozen', 'refrigerated', 'yogurt', 'cheese',
            'cereal', 'snack', 'candy', 'chocolate', 'cookie', 'cracker',
            'apple', 'banana', 'orange', 'strawberr', 'berry', 'grape',
            'avocado', 'potato', 'carrot', 'onion', 'tomato', 'lettuce', 'salad',
            'chicken', 'beef', 'pork', 'meat', 'bacon', 'sausage', 'turkey',
            'pizza', 'pasta', 'bread', 'bagel', 'tortilla',
            'milk', 'egg', 'butter', 'sauce', 'ketchup', 'mustard',
            'coffee grounds', 'tea bags', 'spice', 'seasoning', 'oil', 'vinegar'
        ]
        
        if any(keyword in item_lower for keyword in high_priority_food):
            return 'Food'
        
        # Beverages
        beverage_keywords = [
            'water bottle', 'juice', 'soda', 'pop', 'beverage',
            'coffee drink', 'tea drink', 'energy drink', 'sports drink'
        ]
        
        if any(keyword in item_lower for keyword in beverage_keywords):
            return 'Beverages'
        
        # Baby & Kids
        baby_keywords = [
            'diaper', 'infant', 'toddler', 'baby formula', 'baby food',
            'pacifier', 'bottle', 'newborn', 'baby clothes', 'onesie',
            'kids\' ', 'children\'s', 'toddler'
        ]
        
        if any(keyword in item_lower for keyword in baby_keywords):
            return 'Baby & Kids'
        
        # Personal Care
        personal_care_keywords = [
            'shampoo', 'conditioner', 'body wash', 'lotion', 'deodorant',
            'toothpaste', 'toothbrush', 'dental', 'razor', 'shave',
            'makeup', 'cosmetic', 'skincare', 'hair care', 'perfume', 'cologne',
            'hand soap', 'soap', 'moisturizer', 'sunscreen'
        ]
        
        if any(keyword in item_lower for keyword in personal_care_keywords):
            return 'Personal Care'
        
        # Household
        household_keywords = [
            'detergent', 'bleach', 'disinfect', 'cleaner', 'cleaning',
            'paper towel', 'toilet paper', 'tissue', 'napkin',
            'trash bag', 'garbage bag', 'laundry', 'fabric softener',
            'dishwasher', 'dish soap', 'sponge', 'scrub'
        ]
        
        if any(keyword in item_lower for keyword in household_keywords):
            return 'Household'
        
        # Kitchen Supplies
        kitchen_keywords = [
            'pan', 'pot', 'skillet', 'cookware', 'bakeware',
            'foil', 'aluminum foil', 'plastic wrap', 'parchment',
            'ziploc', 'storage bag', 'food storage',
            'utensil', 'fork', 'spoon', 'knife', 'cutting board',
            'disposable plate', 'paper plate', 'paper cup'
        ]
        
        if any(keyword in item_lower for keyword in kitchen_keywords):
            return 'Kitchen Supplies'
        
        # Pet Supplies
        pet_keywords = [
            'dog', 'cat', 'pet', 'puppy', 'kitten', 'pet food',
            'pet treat', 'leash', 'collar', 'litter'
        ]
        
        if any(keyword in item_lower for keyword in pet_keywords):
            return 'Pet Supplies'
        
        # Books & Media
        books_media_keywords = [
            'book', 'novel', 'paperback', 'hardcover', 'kindle',
            'dvd', 'blu-ray', 'cd', 'vinyl', 'audiobook'
        ]
        
        if any(keyword in item_lower for keyword in books_media_keywords):
            return 'Books & Media'
        
        # Clothing
        clothing_keywords = [
            'shirt', 't-shirt', 'pants', 'jeans', 'shorts', 'dress',
            'jacket', 'coat', 'sweater', 'hoodie', 'socks', 'underwear',
            'shoes', 'sneakers', 'boots', 'sandals', 'hat', 'cap',
            'gloves', 'scarf', 'belt'
        ]
        
        if any(keyword in item_lower for keyword in clothing_keywords):
            return 'Clothing'
        
        # Home & Garden
        home_garden_keywords = [
            'furniture', 'chair', 'table', 'desk', 'lamp', 'light',
            'pillow', 'blanket', 'sheet', 'towel', 'curtain',
            'plant', 'seed', 'gardening', 'tool', 'drill', 'hammer',
            'decor', 'frame', 'mirror', 'rug', 'mat'
        ]
        
        if any(keyword in item_lower for keyword in home_garden_keywords):
            return 'Home & Garden'
        
        # Sports & Outdoors
        sports_keywords = [
            'fitness', 'workout', 'exercise', 'yoga', 'dumbbell', 'weight',
            'camping', 'tent', 'sleeping bag', 'backpack', 'hiking',
            'bicycle', 'bike', 'sports equipment', 'ball', 'racket'
        ]
        
        if any(keyword in item_lower for keyword in sports_keywords):
            return 'Sports & Outdoors'
        
        return 'Other'
    
    def insert_order(self, order_data: Dict[str, Any], items: List[Dict[str, Any]]):
        """Insert an order and its items into the database."""
        try:
            # Insert order
            self.cursor.execute("""
                INSERT OR REPLACE INTO orders 
                (order_id, order_date, total_amount, subtotal, tax, shipping, 
                 discounts, pdf_filename, parsed_date, raw_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_data.get('order_id'),
                order_data.get('order_date'),
                order_data.get('total_amount'),
                order_data.get('subtotal'),
                order_data.get('tax'),
                order_data.get('shipping'),
                order_data.get('discounts'),
                order_data.get('pdf_filename'),
                datetime.now().isoformat(),
                order_data.get('raw_text', '')
            ))
            
            # Delete existing items for this order (in case of re-parsing)
            self.cursor.execute("DELETE FROM order_items WHERE order_id = ?", 
                              (order_data.get('order_id'),))
            
            # Insert items
            for item in items:
                item_name = item.get('name')
                category = self.categorize_item(item_name)
                self.cursor.execute("""
                    INSERT INTO order_items 
                    (order_id, item_name, quantity, unit_price, total_price, category, seller)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_data.get('order_id'),
                    item_name,
                    item.get('quantity', 1),
                    item.get('unit_price'),
                    item.get('total_price'),
                    category,
                    item.get('seller', 'Amazon.com')
                ))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Database error: {str(e)}")
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an order by ID with all items."""
        self.cursor.execute("""
            SELECT order_id, order_date, total_amount, subtotal, tax, shipping, 
                   discounts, pdf_filename, parsed_date
            FROM orders WHERE order_id = ?
        """, (order_id,))
        
        row = self.cursor.fetchone()
        if not row:
            return None
        
        order = {
            'order_id': row[0],
            'order_date': row[1],
            'total_amount': row[2],
            'subtotal': row[3],
            'tax': row[4],
            'shipping': row[5],
            'discounts': row[6],
            'pdf_filename': row[7],
            'parsed_date': row[8]
        }
        
        # Get items
        self.cursor.execute("""
            SELECT item_name, quantity, unit_price, total_price, category, seller
            FROM order_items WHERE order_id = ?
            ORDER BY id
        """, (order_id,))
        
        order['items'] = [
            {
                'name': row[0],
                'quantity': row[1],
                'unit_price': row[2],
                'total_price': row[3],
                'category': row[4],
                'seller': row[5]
            }
            for row in self.cursor.fetchall()
        ]
        
        return order
    
    def get_all_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all orders, most recent first."""
        self.cursor.execute("""
            SELECT order_id, order_date, total_amount, pdf_filename
            FROM orders 
            ORDER BY order_date DESC 
            LIMIT ?
        """, (limit,))
        
        return [
            {
                'order_id': row[0],
                'order_date': row[1],
                'total_amount': row[2],
                'pdf_filename': row[3]
            }
            for row in self.cursor.fetchall()
        ]
    
    def get_all_items(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all items purchased across all orders."""
        self.cursor.execute("""
            SELECT oi.item_name, oi.quantity, oi.unit_price, oi.total_price,
                   o.order_id, o.order_date, oi.category, oi.seller
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            ORDER BY o.order_date DESC, oi.id DESC
            LIMIT ?
        """, (limit,))
        
        return [
            {
                'name': row[0],
                'quantity': row[1],
                'unit_price': row[2],
                'total_price': row[3],
                'order_id': row[4],
                'order_date': row[5],
                'category': row[6],
                'seller': row[7]
            }
            for row in self.cursor.fetchall()
        ]
    
    def search_items(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for items by name."""
        self.cursor.execute("""
            SELECT oi.item_name, SUM(oi.quantity) as total_qty, 
                   AVG(oi.unit_price) as avg_price, COUNT(DISTINCT o.order_id) as order_count,
                   oi.category
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.item_name LIKE ?
            GROUP BY oi.item_name, oi.category
            ORDER BY total_qty DESC
        """, (f'%{search_term}%',))
        
        return [
            {
                'name': row[0],
                'total_quantity': row[1],
                'avg_unit_price': round(row[2], 2),
                'times_purchased': row[3],
                'category': row[4]
            }
            for row in self.cursor.fetchall()
        ]
    
    def get_orders_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get orders within a date range."""
        self.cursor.execute("""
            SELECT order_id, order_date, total_amount, pdf_filename
            FROM orders 
            WHERE order_date BETWEEN ? AND ?
            ORDER BY order_date DESC
        """, (start_date, end_date))
        
        return [
            {
                'order_id': row[0],
                'order_date': row[1],
                'total_amount': row[2],
                'pdf_filename': row[3]
            }
            for row in self.cursor.fetchall()
        ]
    
    def get_total_spent(self, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> float:
        """Get total amount spent in date range."""
        if start_date and end_date:
            self.cursor.execute("""
                SELECT SUM(total_amount) FROM orders
                WHERE order_date BETWEEN ? AND ?
            """, (start_date, end_date))
        else:
            self.cursor.execute("SELECT SUM(total_amount) FROM orders")
        
        result = self.cursor.fetchone()[0]
        return result if result else 0.0
    
    def get_spending_by_category(self, start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get total spending broken down by category."""
        if start_date and end_date:
            self.cursor.execute("""
                SELECT oi.category, 
                       SUM(oi.total_price) as total_spent,
                       COUNT(*) as item_count,
                       SUM(oi.quantity) as total_quantity
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE o.order_date BETWEEN ? AND ?
                GROUP BY oi.category
                ORDER BY total_spent DESC
            """, (start_date, end_date))
        else:
            self.cursor.execute("""
                SELECT oi.category, 
                       SUM(oi.total_price) as total_spent,
                       COUNT(*) as item_count,
                       SUM(oi.quantity) as total_quantity
                FROM order_items oi
                GROUP BY oi.category
                ORDER BY total_spent DESC
            """)
        
        results = []
        total = 0.0
        rows = self.cursor.fetchall()
        
        # Calculate total for percentages
        for row in rows:
            total += row[1] if row[1] else 0.0
        
        # Build results with percentages
        for row in rows:
            spent = row[1] if row[1] else 0.0
            percentage = (spent / total * 100) if total > 0 else 0.0
            results.append({
                'category': row[0] if row[0] else 'Uncategorized',
                'total_spent': round(spent, 2),
                'item_count': row[2],
                'total_quantity': row[3],
                'percentage': round(percentage, 1)
            })
        
        return results
    
    def get_items_by_category(self, category: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all items in a specific category."""
        self.cursor.execute("""
            SELECT oi.item_name, oi.quantity, oi.unit_price, oi.total_price,
                   o.order_id, o.order_date, oi.category, oi.seller
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.category = ?
            ORDER BY o.order_date DESC, oi.id DESC
            LIMIT ?
        """, (category, limit))
        
        return [
            {
                'name': row[0],
                'quantity': row[1],
                'unit_price': row[2],
                'total_price': row[3],
                'order_id': row[4],
                'order_date': row[5],
                'category': row[6],
                'seller': row[7]
            }
            for row in self.cursor.fetchall()
        ]
    
    def update_all_categories(self):
        """Update categories for all existing items in the database."""
        # Get all items
        self.cursor.execute("SELECT id, item_name FROM order_items")
        items = self.cursor.fetchall()
        
        # Update each item's category
        for item_id, item_name in items:
            category = self.categorize_item(item_name)
            self.cursor.execute(
                "UPDATE order_items SET category = ? WHERE id = ?",
                (category, item_id)
            )
        
        self.conn.commit()
        return len(items)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


class AmazonPDFParser:
    """Parser for Amazon order PDFs and CSV files."""
    
    @staticmethod
    async def analyze_with_vision(pdf_path: str) -> Dict[str, Any]:
        """Use OpenAI Vision to analyze the PDF and extract order details including quantities."""
        try:
            from pdf2image import convert_from_path
            
            # Convert PDF to image
            images = convert_from_path(pdf_path, dpi=150)
            
            # Convert first page to base64
            import io
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            base64_image = base64.b64encode(img_byte_arr).decode('utf-8')
            
            # Call OpenAI Vision API
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return {"error": "OPENAI_API_KEY not set"}
            
            client = AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this Amazon order receipt and extract:
1. Order ID (format: 111-1234567-1234567)
2. Order date
3. For EACH item in the order:
   - Item name
   - Quantity (look for quantity badges/bubbles on product images - they're usually small circles with numbers)
   - Unit price
   - Total price for that item
4. Item(s) Subtotal
5. Shipping & Handling
6. Tax
7. Grand Total

Pay special attention to quantity indicators which may appear as small numbered circles/badges on or near product images.

Return the data in JSON format like:
{
  "order_id": "...",
  "order_date": "...",
  "items": [
    {"name": "...", "quantity": 2, "unit_price": 11.19, "total_price": 22.38}
  ],
  "subtotal": 22.38,
  "shipping": 2.99,
  "tax": 0.50,
  "grand_total": 25.87
}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )
            
            # Parse the response
            import json
            result_text = response.choices[0].message.content
            
            # Extract JSON from response (it might be wrapped in markdown code blocks)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            vision_data = json.loads(result_text)
            return vision_data
            
        except Exception as e:
            return {"error": f"Vision analysis failed: {str(e)}"}
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """Extract text content from a PDF file, using OCR if needed."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                
                # If no text was extracted, try OCR
                if len(text.strip()) < 50:
                    try:
                        from pdf2image import convert_from_path
                        import pytesseract
                        
                        # Convert PDF to images
                        images = convert_from_path(pdf_path)
                        
                        # Extract text from each image using OCR
                        ocr_text = ""
                        for i, image in enumerate(images):
                            page_text = pytesseract.image_to_string(image)
                            ocr_text += page_text + "\n"
                        
                        if len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                    except Exception as ocr_error:
                        print(f"OCR extraction failed: {ocr_error}")
                
                return text
        except Exception as e:
            raise Exception(f"Failed to read PDF: {str(e)}")
    
    @staticmethod
    def parse_order_text(text: str, pdf_filename: str = "") -> Dict[str, Any]:
        """Parse Amazon order text to extract structured data."""
        order_data = {
            'order_id': None,
            'order_date': None,
            'total_amount': None,
            'subtotal': None,
            'tax': None,
            'shipping': None,
            'discounts': 0.0,
            'pdf_filename': pdf_filename,
            'raw_text': text
        }
        
        # Extract order ID - Amazon format: 111-1234567-1234567
        order_id_patterns = [
            r'Order\s*#\s*([0-9]{3}-[0-9]{7}-[0-9]{7})',
            r'Order\s+Number\s*:?\s*([0-9]{3}-[0-9]{7}-[0-9]{7})',
            r'orderID=([0-9]{3}-[0-9]{7}-[0-9]{7})',
        ]
        for pattern in order_id_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                order_data['order_id'] = match.group(1)
                break
        
        # Extract order date - Amazon format: "January 16, 2026" or "Order placed January 16, 2026"
        date_patterns = [
            r'Order placed\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})',
            r'Ordered on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})',
            r'Order date:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                order_data['order_date'] = match.group(1)
                break
        
        # Detect two-column layout (labels on left, values on right)
        # This happens when "Grand Total:" is followed by multiple prices
        is_two_column = False
        gt_pos = text.lower().find('grand total:')
        if gt_pos >= 0:
            after_gt = text[gt_pos:gt_pos+200]
            # Count newlines between "Grand Total:" and first price
            first_price_match = re.search(r'Grand Total:(.+?)\$[\d,]+\.\d{2}', after_gt, re.IGNORECASE | re.DOTALL)
            if first_price_match:
                between = first_price_match.group(1)
                newline_count = between.count('\n')
                # If there are 2+ newlines before the first price, likely two-column
                if newline_count >= 2:
                    is_two_column = True
        
        if is_two_column:
            # Two-column layout: extract prices from after "Grand Total:"
            gt_pos = text.lower().find('grand total:')
            if gt_pos >= 0:
                after_gt = text[gt_pos:gt_pos+500]
                prices = re.findall(r'\$?([\d,]+\.\d{2})', after_gt)
                if prices:
                    # The grand total is the last price in the order summary
                    order_data['total_amount'] = float(prices[-1].replace(',', ''))
            
            # Extract subtotal from two-column layout
            # In two-column, all the labels come first, then all the values
            # So we need to find prices that appear in the Order Summary section
            # The first price after "Item(s) Subtotal:" label (even if separated) is the subtotal
            subtotal_pos = text.lower().find('item(s) subtotal:')
            if subtotal_pos >= 0:
                # Get text from subtotal label to end of order summary
                # Look ahead to find all prices up to end of doc or a major section break
                after_subtotal = text[subtotal_pos:subtotal_pos+500]
                # Find all prices in this section
                all_prices = re.findall(r'\$?([\d,]+\.\d{2})', after_subtotal)
                if all_prices:
                    # The first price is the subtotal value
                    order_data['subtotal'] = float(all_prices[0].replace(',', ''))
        else:
            # Standard inline format: "Grand Total: $XX.XX"
            grand_total_match = re.search(r'Grand Total:\s*\$?([\d,]+\.?\d{0,2})', text, re.IGNORECASE)
            if grand_total_match:
                order_data['total_amount'] = float(grand_total_match.group(1).replace(',', ''))
            
            # Extract subtotal (standard format)
            subtotal_match = re.search(r'Item\(?s\)?\s+Subtotal:\s*\$?([\d,]+\.?\d{0,2})', text, re.IGNORECASE)
            if subtotal_match:
                order_data['subtotal'] = float(subtotal_match.group(1).replace(',', ''))
        
        # Extract tax (handle multiline format from OCR)
        tax_match = re.search(r'(?:Estimated\s+)?[Tt]ax(?:\s+to\s+be\s+collected)?:\s*\$?([\d,]+\.?\d{0,2})', text)
        if not tax_match:
            # Try multiline format
            tax_match = re.search(r'(?:Estimated\s+)?[Tt]ax(?:\s+to\s+be\s+collected)?:\s*\n\s*\$?([\d,]+\.?\d{0,2})', text)
        if tax_match:
            order_data['tax'] = float(tax_match.group(1).replace(',', ''))
        
        # Extract shipping (handle multiline format from OCR)
        shipping_patterns = [
            r'Shipping\s*&\s*[Hh]andling:\s*\$?([\d,]+\.?\d{0,2})',
            r'Shipping\s*&\s*[Hh]andling:\s*\n\s*\$?([\d,]+\.?\d{0,2})',
            r'Delivery\s*[Cc]harge:\s*\$?([\d,]+\.?\d{0,2})',
            r'Delivery\s*[Cc]harge:\s*\n\s*\$?([\d,]+\.?\d{0,2})',
        ]
        for pattern in shipping_patterns:
            match = re.search(pattern, text)
            if match:
                order_data['shipping'] = float(match.group(1).replace(',', ''))
                break
        
        # Extract discounts (Subscribe & Save, promotions, etc.)
        discount_patterns = [
            r'Subscribe\s*&\s*Save:\s*-?\$?([\d,]+\.?\d{0,2})',
            r'Promotion[s]?\s*Applied:\s*-?\$?([\d,]+\.?\d{0,2})',
            r'Discount:\s*-?\$?([\d,]+\.?\d{0,2})',
        ]
        total_discounts = 0.0
        for pattern in discount_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                total_discounts += float(match.group(1).replace(',', ''))
        if total_discounts > 0:
            order_data['discounts'] = total_discounts
        
        return order_data
    
    @staticmethod
    def parse_items(text: str) -> List[Dict[str, Any]]:
        """Extract items from Amazon order text."""
        items = []
        
        # Amazon order structure:
        # - Item name (may span multiple lines)
        # - "Sold by: [seller]"
        # - Other info (return info, auto-delivery, etc.)
        # - Price at the end (e.g., "$9.21" or "Auto-delivered: Every 7 weeks$9.21")
        
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for "Sold by:" as an anchor - item name comes before it
            if 'sold by:' in line.lower():
                seller_match = re.search(r'Sold by:\s*(.+)', line, re.IGNORECASE)
                seller = seller_match.group(1).strip() if seller_match else "Amazon.com"
                
                # Look backwards to find the item name (should be within previous 5 lines)
                item_lines = []
                quantity = 1  # Default quantity
                
                for j in range(i-1, max(0, i-6), -1):
                    prev_line = lines[j].strip()
                    
                    # Stop if we hit a header or divider
                    if any(pattern in prev_line.lower() for pattern in [
                        'order summary', 'order placed', 'ship to', 'payment method',
                        'grand total', 'subtotal', 'shipping', 'tax', 'delivered',
                        'your package', 'item(s) subtotal', 'total before tax'
                    ]):
                        break
                    
                    # Check for quantity badge (often just a number in a circle near the image)
                    # Look for standalone small numbers (1-99) that might be quantity
                    if re.match(r'^[1-9]\d?$', prev_line) and len(prev_line) <= 2:
                        # This might be a quantity badge
                        try:
                            potential_qty = int(prev_line)
                            if 1 <= potential_qty <= 99:
                                quantity = potential_qty
                        except ValueError:
                            pass
                    
                    # Also check for explicit "Qty: X" or "Quantity: X" patterns
                    qty_match = re.search(r'(?:qty|quantity)[:\s]*(\d+)', prev_line, re.IGNORECASE)
                    if qty_match:
                        quantity = int(qty_match.group(1))
                    
                    # Add non-empty lines to item name (skip standalone numbers)
                    if len(prev_line) > 5 and not prev_line.startswith('$') and not re.match(r'^[1-9]\d?$', prev_line):
                        item_lines.insert(0, prev_line)
                    
                    # If we find a price (start of previous item), stop
                    if re.search(r'\$[\d,]+\.\d{2}', prev_line):
                        break
                
                # Combine lines to form item name
                item_name = ' '.join(item_lines).strip()
                
                # Look forward for the price (within next 5 lines)
                price = None
                for j in range(i+1, min(i+6, len(lines))):
                    next_line = lines[j].strip()
                    
                    # Look for price pattern - may be at end of line with other text
                    price_match = re.search(r'\$?([\d,]+\.\d{2})$', next_line)
                    if price_match:
                        price = float(price_match.group(1).replace(',', ''))
                        break
                    
                    # Stop if we hit the next item or footer
                    if 'sold by:' in next_line.lower() or 'back to top' in next_line.lower():
                        break
                
                # Add item if we have both name and price
                if item_name and price and len(item_name) > 10:
                    unit_price = price / quantity if quantity > 0 else price
                    items.append({
                        'name': item_name[:300],  # Limit name length
                        'quantity': quantity,
                        'total_price': round(price, 2),
                        'unit_price': round(unit_price, 2),
                        'seller': seller
                    })
                
                # Skip ahead past this item
                i += 5
                continue
            
            i += 1
        
        return items
    
    @staticmethod
    def parse_csv(csv_path: str) -> tuple[List[Dict[str, Any]], List[tuple[Dict[str, Any], List[Dict[str, Any]]]]]:
        """Parse Amazon order history CSV file.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            Tuple of (errors, list of (order_data, items) tuples)
        """
        errors = []
        parsed_orders = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Skip summary rows (SUBTOTAL formulas)
                    if not row.get('order id') or row['order id'].startswith('='):
                        continue
                    
                    try:
                        order_id = row['order id'].strip()
                        
                        # Parse date (format: YYYY-MM-DD)
                        order_date = row.get('date', '').strip()
                        
                        # Parse monetary values
                        def parse_money(val):
                            if not val or val.strip() == '':
                                return 0.0
                            return float(val.strip().replace('$', '').replace(',', ''))
                        
                        total = parse_money(row.get('total', '0'))
                        shipping = parse_money(row.get('shipping', '0'))
                        tax = parse_money(row.get('tax', '0'))
                        refund = parse_money(row.get('refund', '0'))
                        
                        # Calculate subtotal (total - shipping - tax)
                        subtotal = total - shipping - tax
                        
                        order_data = {
                            'order_id': order_id,
                            'order_date': order_date,
                            'total_amount': total,
                            'subtotal': subtotal,
                            'tax': tax,
                            'shipping': shipping,
                            'discounts': 0.0,  # Not in CSV
                            'pdf_filename': Path(csv_path).name,
                            'raw_text': f"CSV: {row}"
                        }
                        
                        # Parse items (semicolon-delimited)
                        items_str = row.get('items', '').strip()
                        items = []
                        
                        if items_str:
                            # Split by semicolon and clean up
                            item_names = [item.strip() for item in items_str.split(';') if item.strip()]
                            
                            if item_names:
                                # Calculate price per item (equal distribution)
                                price_per_item = subtotal / len(item_names) if len(item_names) > 0 else subtotal
                                
                                for item_name in item_names:
                                    # Amazon CSV doesn't include quantity info in item names
                                    # Commas are part of product descriptions (e.g., size, color)
                                    items.append({
                                        'name': item_name[:200],  # Limit name length
                                        'quantity': 1,
                                        'unit_price': round(price_per_item, 2),
                                        'total_price': round(price_per_item, 2)
                                    })
                        
                        # If no items found, create a generic item
                        if not items:
                            items.append({
                                'name': 'Unknown Item',
                                'quantity': 1,
                                'unit_price': round(subtotal, 2),
                                'total_price': round(subtotal, 2)
                            })
                        
                        parsed_orders.append((order_data, items))
                        
                    except Exception as e:
                        errors.append({
                            'order_id': row.get('order id', 'unknown'),
                            'error': str(e)
                        })
                        continue
        
        except Exception as e:
            errors.append({
                'file': csv_path,
                'error': f"Failed to read CSV: {str(e)}"
            })
        
        return errors, parsed_orders


async def execute(pdf_path: Optional[str] = None, action: str = "parse", use_vision: bool = True) -> Dict[str, Any]:
    """
    Execute Amazon order operations.
    
    Args:
        pdf_path: Path to PDF file or None to process all PDFs
        action: Action to perform - "parse", "list", "query", "stats", or "items"
        use_vision: Use OpenAI Vision API for better quantity detection (default: True)
    
    Returns:
        Dictionary with results
    """
    db = AmazonOrderDB()
    parser = AmazonPDFParser()
    
    try:
        if action == "parse":
            if pdf_path:
                # Parse single file (PDF or CSV)
                full_path = Path(pdf_path)
                if not full_path.is_absolute():
                    full_path = Path("data/amazon") / pdf_path
                
                if not full_path.exists():
                    return {"error": f"File not found: {pdf_path}"}
                
                # Check if it's a CSV file
                if full_path.suffix.lower() == '.csv':
                    # Parse CSV
                    errors, parsed_orders = parser.parse_csv(str(full_path))
                    
                    # Insert all orders from CSV
                    success_count = 0
                    for order_data, items in parsed_orders:
                        try:
                            db.insert_order(order_data, items)
                            success_count += 1
                        except Exception as e:
                            errors.append({
                                'order_id': order_data.get('order_id'),
                                'error': str(e)
                            })
                    
                    # Move CSV to archived
                    archived_dir = full_path.parent / "archived"
                    archived_dir.mkdir(exist_ok=True)
                    archived_path = archived_dir / full_path.name
                    
                    if archived_path.exists():
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        archived_path = archived_dir / f"{full_path.stem}_{timestamp}{full_path.suffix}"
                    
                    shutil.move(str(full_path), str(archived_path))
                    
                    return {
                        "success": True,
                        "message": f"Parsed {success_count} orders from CSV (moved to archived)",
                        "orders_parsed": success_count,
                        "errors": errors,
                        "archived_path": str(archived_path)
                    }
                
                # Try vision analysis first if enabled (for PDFs)
                if use_vision:
                    vision_result = await parser.analyze_with_vision(str(full_path))
                    
                    if "error" not in vision_result and vision_result.get('order_id'):
                        # Vision analysis succeeded - use it
                        order_data = {
                            'order_id': vision_result.get('order_id'),
                            'order_date': vision_result.get('order_date'),
                            'total_amount': vision_result.get('grand_total'),
                            'subtotal': vision_result.get('subtotal'),
                            'tax': vision_result.get('tax'),
                            'shipping': vision_result.get('shipping'),
                            'discounts': 0.0,
                            'pdf_filename': full_path.name,
                            'raw_text': ''
                        }
                        
                        items = []
                        for item_data in vision_result.get('items', []):
                            items.append({
                                'name': item_data.get('name', ''),
                                'quantity': item_data.get('quantity', 1),
                                'unit_price': item_data.get('unit_price', 0.0),
                                'total_price': item_data.get('total_price', 0.0),
                                'seller': 'Amazon.com'
                            })
                        
                        db.insert_order(order_data, items)
                        
                        # Move file to archived folder after successful parsing
                        archived_dir = full_path.parent / "archived"
                        archived_dir.mkdir(exist_ok=True)
                        archived_path = archived_dir / full_path.name
                        
                        # If file already exists in archived, add timestamp
                        if archived_path.exists():
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            archived_path = archived_dir / f"{full_path.stem}_{timestamp}{full_path.suffix}"
                        
                        shutil.move(str(full_path), str(archived_path))
                        
                        return {
                            "success": True,
                            "message": f"Parsed order {order_data['order_id']} with {len(items)} items (using vision analysis, moved to archived)",
                            "order": order_data,
                            "items": items,
                            "items_count": len(items),
                            "method": "vision",
                            "archived_path": str(archived_path)
                        }
                
                # Fall back to text extraction
                text = parser.extract_text_from_pdf(str(full_path))
                order_data = parser.parse_order_text(text, full_path.name)
                items = parser.parse_items(text)
                
                if not order_data['order_id']:
                    return {"error": "Could not extract order ID from PDF"}
                
                # Calculate/verify quantities using subtotal
                if order_data.get('subtotal') and items:
                    if len(items) == 1:
                        # Single item: calculate quantity from subtotal
                        item = items[0]
                        unit_price = item['unit_price']
                        subtotal = order_data['subtotal']
                        
                        if unit_price > 0:
                            calculated_qty = round(subtotal / unit_price)
                            if abs(calculated_qty * unit_price - subtotal) < 0.02:  # Within 2 cents tolerance
                                item['quantity'] = calculated_qty
                                item['total_price'] = subtotal
                    else:
                        # Multiple items: verify if current quantities sum to subtotal
                        current_total = sum(item['total_price'] for item in items)
                        subtotal = order_data['subtotal']
                        
                        # If current total doesn't match subtotal (off by more than 1%)
                        if abs(current_total - subtotal) > subtotal * 0.01:
                            # Try to find if any single item needs quantity adjustment
                            for item in items:
                                unit_price = item['unit_price']
                                if unit_price > 0:
                                    # Check if this item might have wrong quantity
                                    for test_qty in range(1, 10):  # Test quantities 1-9
                                        test_total = current_total - item['total_price'] + (unit_price * test_qty)
                                        if abs(test_total - subtotal) < 0.02:
                                            # Found a quantity that makes it work
                                            item['quantity'] = test_qty
                                            item['total_price'] = unit_price * test_qty
                                            break
                
                db.insert_order(order_data, items)
                
                # Move file to archived folder after successful parsing
                archived_dir = full_path.parent / "archived"
                archived_dir.mkdir(exist_ok=True)
                archived_path = archived_dir / full_path.name
                
                # If file already exists in archived, add timestamp
                if archived_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archived_path = archived_dir / f"{full_path.stem}_{timestamp}{full_path.suffix}"
                
                shutil.move(str(full_path), str(archived_path))
                
                return {
                    "success": True,
                    "message": f"Parsed order {order_data['order_id']} with {len(items)} items (moved to archived)",
                    "order": order_data,
                    "items": items,
                    "items_count": len(items),
                    "archived_path": str(archived_path)
                }
            else:
                # Parse all files in amazon folder (not archived subfolder)
                amazon_dir = Path("data/amazon")
                pdf_files = list(amazon_dir.glob("*.pdf"))  # Only top-level PDFs, not archived
                csv_files = list(amazon_dir.glob("*.csv"))  # CSV files
                all_files = pdf_files + csv_files
                
                results = []
                
                # Process CSV files
                for csv_file in csv_files:
                    try:
                        errors, parsed_orders = parser.parse_csv(str(csv_file))
                        
                        success_count = 0
                        for order_data, items in parsed_orders:
                            try:
                                db.insert_order(order_data, items)
                                success_count += 1
                            except Exception as e:
                                pass  # Continue with other orders
                        
                        # Move to archived
                        archived_dir = csv_file.parent / "archived"
                        archived_dir.mkdir(exist_ok=True)
                        archived_path = archived_dir / csv_file.name
                        
                        if archived_path.exists():
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            archived_path = archived_dir / f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
                        
                        shutil.move(str(csv_file), str(archived_path))
                        
                        results.append({
                            "file": csv_file.name,
                            "type": "csv",
                            "orders_count": success_count,
                            "errors_count": len(errors),
                            "success": True,
                            "archived": True
                        })
                    except Exception as e:
                        results.append({
                            "file": csv_file.name,
                            "type": "csv",
                            "success": False,
                            "error": str(e)
                        })
                
                # Process PDF files
                for pdf_file in pdf_files:
                    try:
                        text = parser.extract_text_from_pdf(str(pdf_file))
                        order_data = parser.parse_order_text(text, pdf_file.name)
                        items = parser.parse_items(text)
                        
                        if order_data['order_id']:
                            # Calculate quantities if subtotal is available and there's only one item
                            if order_data.get('subtotal') and len(items) == 1:
                                item = items[0]
                                unit_price = item['unit_price']
                                subtotal = order_data['subtotal']
                                
                                # Calculate quantity from subtotal
                                if unit_price > 0:
                                    calculated_qty = round(subtotal / unit_price)
                                    if abs(calculated_qty * unit_price - subtotal) < 0.02:  # Within 2 cents tolerance
                                        item['quantity'] = calculated_qty
                                        item['total_price'] = subtotal
                            
                            db.insert_order(order_data, items)
                            
                            # Move to archived
                            archived_dir = pdf_file.parent / "archived"
                            archived_dir.mkdir(exist_ok=True)
                            archived_path = archived_dir / pdf_file.name
                            
                            if archived_path.exists():
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                archived_path = archived_dir / f"{pdf_file.stem}_{timestamp}{pdf_file.suffix}"
                            
                            shutil.move(str(pdf_file), str(archived_path))
                            
                            results.append({
                                "file": pdf_file.name,
                                "order_id": order_data['order_id'],
                                "items_count": len(items),
                                "success": True,
                                "archived": True
                            })
                        else:
                            results.append({
                                "file": pdf_file.name,
                                "success": False,
                                "error": "Could not extract order ID"
                            })
                    except Exception as e:
                        results.append({
                            "file": pdf_file.name,
                            "success": False,
                            "error": str(e)
                        })
                
                return {
                    "success": True,
                    "message": f"Processed {len(all_files)} files ({len(pdf_files)} PDFs, {len(csv_files)} CSVs)",
                    "results": results
                }
        
        elif action == "list":
            orders = db.get_all_orders(limit=50)
            return {
                "success": True,
                "orders": orders,
                "count": len(orders)
            }
        
        elif action == "stats":
            total_spent = db.get_total_spent()
            all_orders = db.get_all_orders(limit=1000)
            
            return {
                "success": True,
                "total_spent": total_spent,
                "total_orders": len(all_orders),
                "average_order": total_spent / len(all_orders) if all_orders else 0
            }
        
        elif action == "query":
            if pdf_path:  # Use pdf_path as order_id for query
                order = db.get_order(pdf_path)
                if order:
                    return {
                        "success": True,
                        "order": order
                    }
                else:
                    return {"error": f"Order {pdf_path} not found"}
            else:
                return {"error": "No order ID provided for query"}
        
        elif action == "items":
            # List all items or search
            if pdf_path:  # Use as search term
                items = db.search_items(pdf_path)
                return {
                    "success": True,
                    "items": items,
                    "search_term": pdf_path
                }
            else:
                items = db.get_all_items(limit=100)
                return {
                    "success": True,
                    "items": items,
                    "count": len(items)
                }
        
        else:
            return {"error": f"Unknown action: {action}"}
    
    finally:
        db.close()
