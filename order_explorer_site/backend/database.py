import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
from collections import Counter

# Absolute paths
AMAZON_DB = "/home/edgeworks-server/chatty/data/amazon/amazon_orders.db"
WALMART_DB = "/home/edgeworks-server/chatty/data/walmart/walmart_orders.db"
ROCKETMONEY_DB = "/home/edgeworks-server/chatty/data/rocketmoney/rocketmoney_transactions.db"

def get_db_connection(db_path):
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    return None

def get_all_orders() -> List[Dict[str, Any]]:
    orders = []

    # Amazon
    conn = get_db_connection(AMAZON_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, order_date, total_amount, 'Amazon' as source FROM orders")
        for row in cursor.fetchall():
            orders.append({
                "id": f"amazon_{row['order_id']}",
                "original_id": row['order_id'],
                "date": row['order_date'],
                "total": row['total_amount'],
                "source": "Amazon",
                "items_summary": "View items" # Placeholder or separate query
            })
        conn.close()

    # Walmart
    conn = get_db_connection(WALMART_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, order_date, total_amount, 'Walmart' as source FROM orders")
        for row in cursor.fetchall():
            orders.append({
                "id": f"walmart_{row['order_id']}",
                "original_id": row['order_id'],
                "date": row['order_date'],
                "total": row['total_amount'],
                "source": "Walmart",
                "items_summary": "View items"
            })
        conn.close()

    # Rocket Money
    conn = get_db_connection(ROCKETMONEY_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, date, amount, name, category, 'RocketMoney' as source FROM transactions")
        for row in cursor.fetchall():
            orders.append({
                "id": f"rm_{row['id']}",
                "original_id": str(row['id']),
                "date": row['date'],
                "total": row['amount'],
                "source": "RocketMoney",
                "items_summary": row['name']
            })
        conn.close()
    
    # Sort by date desc
    def parse_date(d):
        if not d: return datetime.min
        try:
            return datetime.fromisoformat(d.replace('Z', ''))
        except:
            pass
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except:
            return datetime.min

    orders.sort(key=lambda x: parse_date(x['date']), reverse=True)
    return orders

def get_all_items() -> List[Dict[str, Any]]:
    items = []

    # Amazon
    conn = get_db_connection(AMAZON_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                oi.item_name, oi.unit_price, oi.quantity, oi.total_price, oi.category, 
                o.order_date, o.order_id
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
        """)
        for row in cursor.fetchall():
            items.append({
                "name": row['item_name'],
                "price": row['unit_price'],
                "quantity": row['quantity'],
                "total_price": row['total_price'],
                "category": row['category'],
                "date": row['order_date'],
                "source": "Amazon",
                "order_id": f"amazon_{row['order_id']}"
            })
        conn.close()

    # Walmart
    conn = get_db_connection(WALMART_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                oi.item_name, oi.unit_price, oi.quantity, oi.total_price, oi.category, 
                o.order_date, o.order_id, oi.delivery_status
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
        """)
        for row in cursor.fetchall():
            items.append({
                "name": row['item_name'],
                "price": row['unit_price'],
                "quantity": row['quantity'],
                "total_price": row['total_price'],
                "category": row['category'],
                "date": row['order_date'],
                "source": "Walmart",
                "order_id": f"walmart_{row['order_id']}",
                "delivery_status": row['delivery_status']
            })
        conn.close()

    # Rocket Money (Treating transactions as items)
    conn = get_db_connection(ROCKETMONEY_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, date, amount, name, category FROM transactions")
        for row in cursor.fetchall():
            items.append({
                "name": row['name'],
                "price": row['amount'],
                "quantity": 1,
                "total_price": row['amount'],
                "category": row['category'],
                "date": row['date'],
                "source": "RocketMoney",
                "order_id": f"rm_{row['id']}"
            })
        conn.close()
    
    return items

def get_item_history(item_name: str) -> List[Dict[str, Any]]:
    all_items = get_all_items()
    # Simple exact match or case-insensitive contains?
    # User said "click an item", implying we have a distinct list of items. 
    # Let's do exact match or case insensitive match on the passed name
    target = item_name.lower().strip()
    
    history = [
        item for item in all_items 
        if item['name'] and item['name'].lower().strip() == target
    ]
    
    # Sort by date
    def parse_date(d):
        if not d: return datetime.min
        try:
             return datetime.fromisoformat(d.replace('Z', ''))
        except:
            pass
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except:
             return datetime.min

    history.sort(key=lambda x: parse_date(x['date']))
    
    # Debug logging
    if history:
        print(f"get_item_history returning {len(history)} items for '{item_name}'")
        print(f"First item keys: {list(history[0].keys())}")
        print(f"First item: {history[0]}")
    
    return history

def get_order_items(order_id: str) -> List[Dict[str, Any]]:
    # Deconstruct order_id
    if order_id.startswith("amazon_"):
        source = "Amazon"
        original_id = order_id[7:]
    elif order_id.startswith("walmart_"):
        source = "Walmart"
        original_id = order_id[8:]
    elif order_id.startswith("rm_"):  
        source = "RocketMoney"
        original_id = order_id[3:]
    else:
        return []

    items = []
    
    if source == "Amazon":
        conn = get_db_connection(AMAZON_DB)
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_name, unit_price, quantity, total_price, category 
                FROM order_items WHERE order_id = ?
            """, (original_id,))
            for row in cursor.fetchall():
                 items.append({
                    "name": row['item_name'],
                    "price": row['unit_price'],
                    "quantity": row['quantity'],
                    "total_price": row['total_price'],
                    "category": row['category'],
                    "source": "Amazon",
                    "order_id": order_id
                })
            conn.close()

    elif source == "Walmart":
         conn = get_db_connection(WALMART_DB)
         if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_name, unit_price, quantity, total_price, category, delivery_status
                FROM order_items WHERE order_id = ?
            """, (original_id,))
            for row in cursor.fetchall():
                 items.append({
                    "name": row['item_name'],
                    "price": row['unit_price'],
                    "quantity": row['quantity'],
                    "total_price": row['total_price'],
                    "delivery_status": row['delivery_status'],
                    "category": row['category'],
                    "source": "Walmart",
                    "order_id": order_id
                })
            conn.close()

    elif source == "RocketMoney":
         conn = get_db_connection(ROCKETMONEY_DB)
         if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, amount, category FROM transactions WHERE id = ?", (original_id,))
            row = cursor.fetchone()
            if row:
                items.append({
                    "name": row['name'],
                    "price": row['amount'],
                    "quantity": 1,
                    "total_price": row['amount'],
                    "category": row['category'],
                    "source": "RocketMoney",
                    "order_id": order_id
                })
            conn.close()

    return items

def get_dashboard_stats() -> Dict[str, Any]:
    """Get comprehensive dashboard statistics"""
    all_orders = get_all_orders()
    all_items = get_all_items()
    
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    current_year = now.strftime("%Y")
    
    # Filter orders for current month and year
    this_month_orders = [o for o in all_orders if o.get('date', '').startswith(current_month)]
    this_year_orders = [o for o in all_orders if o.get('date', '').startswith(current_year)]
    
    # Total spending
    total_spending_month = sum(o.get('total', 0) for o in this_month_orders)
    total_spending_year = sum(o.get('total', 0) for o in this_year_orders)
    total_spending_all = sum(o.get('total', 0) for o in all_orders)
    
    # Most expensive purchase this month
    most_expensive_month = None
    if this_month_orders:
        most_expensive_month = max(this_month_orders, key=lambda x: x.get('total', 0))
    
    # Average order value
    avg_order_value = total_spending_all / len(all_orders) if all_orders else 0
    
    # Most purchased products (by quantity)
    item_quantities = Counter()
    item_details = {}
    for item in all_items:
        name = item.get('name', 'Unknown')
        qty = item.get('quantity', 0)
        item_quantities[name] += qty
        if name not in item_details:
            item_details[name] = {
                'name': name,
                'category': item.get('category', 'Unknown'),
                'total_quantity': qty,
                'avg_price': item.get('price', 0),
                'price_count': 1
            }
        else:
            item_details[name]['total_quantity'] += qty
            item_details[name]['avg_price'] += item.get('price', 0)
            item_details[name]['price_count'] += 1
    
    # Calculate average prices
    for name in item_details:
        item_details[name]['avg_price'] = item_details[name]['avg_price'] / item_details[name]['price_count']
    
    most_purchased = [
        {
            'name': name,
            'quantity': qty,
            'category': item_details[name]['category'],
            'avg_price': item_details[name]['avg_price']
        }
        for name, qty in item_quantities.most_common(10)
    ]
    
    # Top categories by spending
    category_spending = Counter()
    for item in all_items:
        category = item.get('category', 'Unknown')
        total_price = item.get('total_price', 0)
        category_spending[category] += total_price
    
    top_categories = [
        {'category': cat, 'total': total}
        for cat, total in category_spending.most_common(10)
    ]
    
    # Monthly spending trend (last 6 months)
    monthly_spending = {}
    for order in all_orders:
        date = order.get('date', '')
        if date:
            month = date[:7]  # YYYY-MM
            monthly_spending[month] = monthly_spending.get(month, 0) + order.get('total', 0)
    
    sorted_months = sorted(monthly_spending.keys(), reverse=True)[:6]
    spending_trend = [
        {'month': month, 'total': monthly_spending[month]}
        for month in reversed(sorted_months)
    ]
    
    # Recent orders (last 5)
    recent_orders = all_orders[:5] if all_orders else []
    
    # Order count stats
    order_count_month = len(this_month_orders)
    order_count_year = len(this_year_orders)
    order_count_all = len(all_orders)
    
    return {
        'total_spending': {
            'month': total_spending_month,
            'year': total_spending_year,
            'all_time': total_spending_all
        },
        'order_counts': {
            'month': order_count_month,
            'year': order_count_year,
            'all_time': order_count_all
        },
        'most_expensive_month': most_expensive_month,
        'avg_order_value': avg_order_value,
        'most_purchased': most_purchased,
        'top_categories': top_categories,
        'spending_trend': spending_trend,
        'recent_orders': recent_orders
    }

def get_monthly_breakdown() -> List[Dict[str, Any]]:
    """Get detailed spending breakdown by month"""
    all_orders = get_all_orders()
    all_items = get_all_items()
    
    # Group orders by month
    monthly_data = {}
    for order in all_orders:
        date = order.get('date', '')
        if date:
            month = date[:7]  # YYYY-MM
            if month not in monthly_data:
                monthly_data[month] = {
                    'month': month,
                    'total_spending': 0,
                    'order_count': 0,
                    'orders': [],
                    'categories': Counter(),
                    'sources': Counter(),
                    'item_count': 0
                }
            
            monthly_data[month]['total_spending'] += order.get('total', 0)
            monthly_data[month]['order_count'] += 1
            monthly_data[month]['orders'].append(order)
            monthly_data[month]['sources'][order.get('source', 'Unknown')] += 1
    
    # Add item details per month
    for item in all_items:
        date = item.get('date', '')
        if date:
            month = date[:7]
            if month in monthly_data:
                category = item.get('category', 'Unknown')
                monthly_data[month]['categories'][category] += item.get('total_price', 0)
                monthly_data[month]['item_count'] += item.get('quantity', 0)
    
    # Convert to list and add calculated fields
    result = []
    for month, data in sorted(monthly_data.items(), reverse=True):
        top_category = None
        if data['categories']:
            top_category = data['categories'].most_common(1)[0]
        
        result.append({
            'month': month,
            'total_spending': data['total_spending'],
            'order_count': data['order_count'],
            'item_count': data['item_count'],
            'avg_order_value': data['total_spending'] / data['order_count'] if data['order_count'] > 0 else 0,
            'top_category': top_category[0] if top_category else 'N/A',
            'top_category_spending': top_category[1] if top_category else 0,
            'sources': dict(data['sources']),
            'top_categories': [
                {'category': cat, 'total': total}
                for cat, total in data['categories'].most_common(5)
            ]
        })
    
    return result

def get_yearly_breakdown() -> List[Dict[str, Any]]:
    """Get comprehensive breakdown by year"""
    all_orders = get_all_orders()
    all_items = get_all_items()
    
    yearly_data = {}
    
    # Aggregate orders by year
    for order in all_orders:
        date_str = order.get('date', '')
        if not date_str:
            continue
        
        year = date_str[:4]
        if year not in yearly_data:
            yearly_data[year] = {
                'year': year,
                'total_spending': 0,
                'order_count': 0,
                'item_count': 0,
                'sources': Counter(),
                'categories': Counter()
            }
        
        yearly_data[year]['total_spending'] += order.get('total', 0)
        yearly_data[year]['order_count'] += 1
        yearly_data[year]['sources'][order.get('source', 'Unknown')] += 1
    
    # Add item details
    for item in all_items:
        date_str = item.get('date', '')
        if not date_str:
            continue
        
        year = date_str[:4]
        if year in yearly_data:
            yearly_data[year]['item_count'] += item.get('quantity', 0)
            category = item.get('category', 'Unknown')
            yearly_data[year]['categories'][category] += item.get('total_price', 0)
    
    # Calculate metrics for each year
    years = []
    for year, data in yearly_data.items():
        data['avg_order_value'] = data['total_spending'] / data['order_count'] if data['order_count'] > 0 else 0
        
        # Top category
        if data['categories']:
            top_cat = data['categories'].most_common(1)[0]
            data['top_category'] = top_cat[0]
            data['top_category_spending'] = top_cat[1]
        else:
            data['top_category'] = 'None'
            data['top_category_spending'] = 0
        
        # Clean up
        del data['sources']
        del data['categories']
        
        years.append(data)
    
    # Sort by year descending
    years.sort(key=lambda x: x['year'], reverse=True)
    
    return years

def get_category_analysis() -> Dict[str, Any]:
    """Get detailed analysis by category"""
    all_items = get_all_items()
    
    # Group by category
    category_data = {}
    for item in all_items:
        category = item.get('category', 'Uncategorized')
        if category not in category_data:
            category_data[category] = {
                'category': category,
                'total_spending': 0,
                'item_count': 0,
                'order_count': 0,
                'items': [],
                'avg_price': 0,
                'sources': Counter()
            }
        
        category_data[category]['total_spending'] += item.get('total_price', 0)
        category_data[category]['item_count'] += item.get('quantity', 0)
        category_data[category]['items'].append(item)
        category_data[category]['sources'][item.get('source', 'Unknown')] += 1
    
    # Calculate trends
    for cat in category_data:
        items = category_data[cat]['items']
        category_data[cat]['order_count'] = len(items)
        category_data[cat]['avg_price'] = category_data[cat]['total_spending'] / category_data[cat]['item_count'] if category_data[cat]['item_count'] > 0 else 0
        
        # Monthly trend
        monthly = {}
        for item in items:
            date = item.get('date', '')
            if date:
                month = date[:7]
                monthly[month] = monthly.get(month, 0) + item.get('total_price', 0)
        
        category_data[cat]['monthly_trend'] = [
            {'month': month, 'total': total}
            for month, total in sorted(monthly.items())
        ]
        category_data[cat]['sources'] = dict(category_data[cat]['sources'])
        del category_data[cat]['items']  # Don't send all items
    
    # Convert to list and sort by spending
    categories = list(category_data.values())
    categories.sort(key=lambda x: x['total_spending'], reverse=True)
    
    return {
        'categories': categories,
        'total_categories': len(categories),
        'top_category': categories[0] if categories else None
    }

def get_vendor_analysis() -> Dict[str, Any]:
    """Get detailed analysis by vendor/source"""
    all_orders = get_all_orders()
    all_items = get_all_items()
    
    vendor_data = {}
    for order in all_orders:
        source = order.get('source', 'Unknown')
        if source not in vendor_data:
            vendor_data[source] = {
                'vendor': source,
                'total_spending': 0,
                'order_count': 0,
                'item_count': 0,
                'avg_order_value': 0,
                'categories': Counter()
            }
        
        vendor_data[source]['total_spending'] += order.get('total', 0)
        vendor_data[source]['order_count'] += 1
    
    # Add item details
    for item in all_items:
        source = item.get('source', 'Unknown')
        if source in vendor_data:
            vendor_data[source]['item_count'] += item.get('quantity', 0)
            category = item.get('category', 'Unknown')
            vendor_data[source]['categories'][category] += item.get('total_price', 0)
    
    # Calculate averages and format
    vendors = []
    for source, data in vendor_data.items():
        data['avg_order_value'] = data['total_spending'] / data['order_count'] if data['order_count'] > 0 else 0
        data['top_categories'] = [
            {'category': cat, 'total': total}
            for cat, total in data['categories'].most_common(5)
        ]
        del data['categories']
        vendors.append(data)
    
    vendors.sort(key=lambda x: x['total_spending'], reverse=True)
    
    return {
        'vendors': vendors,
        'total_vendors': len(vendors)
    }

def search_items(query: str, category: str = None, source: str = None, 
                 min_price: float = None, max_price: float = None) -> List[Dict[str, Any]]:
    """Advanced search for items"""
    all_items = get_all_items()
    results = []
    
    query_lower = query.lower() if query else ''
    
    for item in all_items:
        # Text search
        if query_lower:
            name = (item.get('name') or '').lower()
            if query_lower not in name:
                continue
        
        # Category filter
        if category and item.get('category') != category:
            continue
        
        # Source filter
        if source and item.get('source') != source:
            continue
        
        # Price range filter
        price = item.get('price', 0)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        
        results.append(item)
    
    return results

def get_recurring_items() -> List[Dict[str, Any]]:
    """Identify items purchased multiple times"""
    all_items = get_all_items()
    
    item_purchases = {}
    for item in all_items:
        name = item.get('name', 'Unknown')
        if name not in item_purchases:
            item_purchases[name] = {
                'name': name,
                'purchase_count': 0,
                'total_spent': 0,
                'avg_price': 0,
                'category': item.get('category', 'Unknown'),
                'sources': set(),
                'dates': []
            }
        
        item_purchases[name]['purchase_count'] += 1
        item_purchases[name]['total_spent'] += item.get('total_price', 0)
        item_purchases[name]['sources'].add(item.get('source', 'Unknown'))
        item_purchases[name]['dates'].append(item.get('date', ''))
    
    # Filter items purchased more than once and calculate metrics
    recurring = []
    for name, data in item_purchases.items():
        if data['purchase_count'] > 1:
            data['avg_price'] = data['total_spent'] / data['purchase_count']
            data['sources'] = list(data['sources'])
            
            # Calculate average days between purchases
            dates = sorted([d for d in data['dates'] if d])
            if len(dates) >= 2:
                try:
                    first_date = datetime.fromisoformat(dates[0].replace('Z', ''))
                    last_date = datetime.fromisoformat(dates[-1].replace('Z', ''))
                    days_diff = (last_date - first_date).days
                    data['avg_days_between'] = days_diff / (len(dates) - 1)
                except:
                    data['avg_days_between'] = None
            else:
                data['avg_days_between'] = None
            
            data['last_purchase'] = dates[-1] if dates else None
            data['first_purchase'] = dates[0] if dates else None
            del data['dates']
            recurring.append(data)
    
    # Sort by purchase count
    recurring.sort(key=lambda x: x['purchase_count'], reverse=True)
    
    return recurring

def get_budget_summary(monthly_limit: float = None) -> Dict[str, Any]:
    """Get budget tracking information"""
    all_orders = get_all_orders()
    all_items = get_all_items()
    
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    
    # Current month spending
    month_orders = [o for o in all_orders if o.get('date', '').startswith(current_month)]
    month_spending = sum(o.get('total', 0) for o in month_orders)
    
    # Category breakdown for current month
    month_items = [i for i in all_items if i.get('date', '').startswith(current_month)]
    category_spending = Counter()
    for item in month_items:
        category = item.get('category', 'Uncategorized')
        category_spending[category] += item.get('total_price', 0)
    
    # Calculate projections
    day_of_month = now.day
    days_in_month = 30  # Simplified
    daily_avg = month_spending / day_of_month if day_of_month > 0 else 0
    projected_spending = daily_avg * days_in_month
    
    # Historical monthly averages
    monthly_totals = {}
    for order in all_orders:
        date = order.get('date', '')
        if date:
            month = date[:7]
            monthly_totals[month] = monthly_totals.get(month, 0) + order.get('total', 0)
    
    avg_monthly_spending = sum(monthly_totals.values()) / len(monthly_totals) if monthly_totals else 0
    
    result = {
        'current_month': current_month,
        'month_spending': month_spending,
        'daily_average': daily_avg,
        'projected_month_end': projected_spending,
        'avg_monthly_historical': avg_monthly_spending,
        'day_of_month': day_of_month,
        'category_breakdown': [
            {'category': cat, 'total': total, 'percentage': (total / month_spending * 100) if month_spending > 0 else 0}
            for cat, total in category_spending.most_common()
        ]
    }
    
    if monthly_limit:
        result['monthly_limit'] = monthly_limit
        result['remaining'] = monthly_limit - month_spending
        result['percentage_used'] = (month_spending / monthly_limit * 100) if monthly_limit > 0 else 0
        result['on_track'] = month_spending <= (monthly_limit * day_of_month / days_in_month)
    
    return result

def get_all_categories() -> List[str]:
    """Get all unique categories across all data sources"""
    categories = set()
    
    # Amazon
    conn = get_db_connection(AMAZON_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM order_items WHERE category IS NOT NULL")
        for row in cursor.fetchall():
            if row['category']:
                categories.add(row['category'])
        conn.close()
    
    # Walmart
    conn = get_db_connection(WALMART_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM order_items WHERE category IS NOT NULL")
        for row in cursor.fetchall():
            if row['category']:
                categories.add(row['category'])
        conn.close()
    
    # Rocket Money
    conn = get_db_connection(ROCKETMONEY_DB)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL")
        for row in cursor.fetchall():
            if row['category']:
                categories.add(row['category'])
        conn.close()
    
    return sorted(list(categories))

def update_item_category(item_name: str, new_category: str) -> bool:
    """Update the category of ALL instances of an item across all databases"""
    total_updated = 0
    
    # Update Amazon
    conn = get_db_connection(AMAZON_DB)
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE order_items SET category = ? WHERE item_name = ?",
                (new_category, item_name)
            )
            conn.commit()
            total_updated += cursor.rowcount
            print(f"Updated {cursor.rowcount} items in Amazon DB")
        except Exception as e:
            print(f"Error updating Amazon category: {e}")
        finally:
            conn.close()
    
    # Update Walmart
    conn = get_db_connection(WALMART_DB)
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE order_items SET category = ? WHERE item_name = ?",
                (new_category, item_name)
            )
            conn.commit()
            total_updated += cursor.rowcount
            print(f"Updated {cursor.rowcount} items in Walmart DB")
        except Exception as e:
            print(f"Error updating Walmart category: {e}")
        finally:
            conn.close()
    
    # Update RocketMoney
    conn = get_db_connection(ROCKETMONEY_DB)
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE name = ?",
                (new_category, item_name)
            )
            conn.commit()
            total_updated += cursor.rowcount
            print(f"Updated {cursor.rowcount} items in RocketMoney DB")
        except Exception as e:
            print(f"Error updating RocketMoney category: {e}")
        finally:
            conn.close()
    
    print(f"Total items updated: {total_updated}")
    return total_updated > 0
