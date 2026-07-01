"""PDF document processing tools."""

import re
from pathlib import Path
from typing import Dict, Any, Optional
import PyPDF2


async def detect_pdf_type(pdf_path: str, caption: str = "") -> Optional[str]:
    """Detect if a PDF is a Walmart or Amazon order.
    
    Args:
        pdf_path: Path to the PDF file
        caption: Optional caption/description provided by user
        
    Returns:
        "walmart", "amazon", or None if not recognized
    """
    try:
        # First check caption for explicit hints
        caption_lower = caption.lower()
        if 'walmart' in caption_lower or 'wal-mart' in caption_lower:
            return "walmart"
        elif 'amazon' in caption_lower:
            return "amazon"
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            # Read all pages to detect type
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
            
            text_lower = text.lower()
            
            # Check for Walmart indicators (more comprehensive)
            walmart_indicators = [
                'walmart.com',
                'walmart',
                'save money. live better',
                'wal-mart',
                'bentonville, ar',
                'walmart stores',
                'walmartimages'
            ]
            
            # Check for Amazon indicators (more comprehensive)
            amazon_indicators = [
                'amazon.com',
                'amazon',
                'prime',
                'sold by: amazon',
                'shipped by amazon',
                'order summary',
                'order placed',
                'ship to',
                'grand total',
                'item(s) subtotal'
            ]
            
            # Count indicators
            walmart_count = sum(1 for indicator in walmart_indicators if indicator in text_lower)
            amazon_count = sum(1 for indicator in amazon_indicators if indicator in text_lower)
            
            # Check for specific order number formats
            # Walmart: 1234567-12345678 or similar
            # Amazon: 123-1234567-1234567
            has_walmart_order_format = bool(re.search(r'\d{6,}-\d{7,}', text))
            has_amazon_order_format = bool(re.search(r'\d{3}-\d{7}-\d{7}', text))
            
            # Amazon is very likely if it has the specific order format and any amazon indicators
            if has_amazon_order_format and amazon_count >= 2:
                return "amazon"
            
            # Walmart is very likely if it has walmart order format and any walmart indicators
            if has_walmart_order_format and walmart_count >= 1:
                return "walmart"
            
            # Fall back to indicator counts (need at least 2 indicators to be confident)
            if walmart_count >= 2 and walmart_count > amazon_count:
                return "walmart"
            elif amazon_count >= 3 and amazon_count > walmart_count:
                return "amazon"
            
            # If still unclear, be more lenient - just need strong indicator count
            if amazon_count >= 5:
                return "amazon"
            elif walmart_count >= 3:
                return "walmart"
            
            return None
            
    except Exception as e:
        print(f"Error detecting PDF type: {e}")
        return None


async def process_order_pdf(pdf_path: str, original_filename: str, caption: str = "") -> Dict[str, Any]:
    """Process an order PDF - detect type and parse.
    
    Args:
        pdf_path: Path to the downloaded PDF file
        original_filename: Original filename from upload
        caption: Optional caption/description provided by user
        
    Returns:
        Dictionary with processing results
    """
    # Detect PDF type
    pdf_type = await detect_pdf_type(pdf_path, caption)
    
    if not pdf_type:
        return {
            "success": False,
            "error": "Could not determine if this is a Walmart or Amazon order PDF"
        }
    
    # Determine destination folder
    if pdf_type == "walmart":
        dest_dir = Path("data/walmart")
    else:  # amazon
        dest_dir = Path("data/amazon")
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Move file to destination with original filename
    dest_path = dest_dir / original_filename
    
    # If file already exists, add timestamp
    if dest_path.exists():
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = dest_path.stem
        suffix = dest_path.suffix
        dest_path = dest_dir / f"{stem}_{timestamp}{suffix}"
    
    # Move the file
    import shutil
    shutil.move(pdf_path, dest_path)
    
    # Parse the PDF
    if pdf_type == "walmart":
        from skills.walmart_orders.walmart_parser import execute
        result = await execute(pdf_path=original_filename, action="parse")
    else:  # amazon
        from skills.amazon_orders.amazon_parser import execute
        result = await execute(pdf_path=original_filename, action="parse")
    
    if result.get("success"):
        order_data = result.get("order", {})
        items_count = result.get("items_count", 0)
        
        return {
            "success": True,
            "type": pdf_type,
            "order_id": order_data.get("order_id"),
            "order_date": order_data.get("order_date"),
            "total_amount": order_data.get("total_amount"),
            "items_count": items_count,
            "message": f"Successfully processed {pdf_type.capitalize()} order {order_data.get('order_id')} with {items_count} items"
        }
    else:
        return {
            "success": False,
            "type": pdf_type,
            "error": result.get("error", "Unknown error parsing PDF")
        }
