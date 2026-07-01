// Telegram Web App initialization
const tg = window.Telegram.WebApp;
tg.expand();

// API base URL - update this when using ngrok
const API_BASE = window.location.origin + '/api/walmart';

// Current state
let currentOrders = [];
let currentCategories = [];

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadStats();
    loadOrders();
    
    // Setup search input
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchItems();
        }
    });
});

// Tab switching
function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            
            // Remove active class from all tabs and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Add active class to clicked tab and corresponding content
            button.classList.add('active');
            document.getElementById(targetTab + 'Tab').classList.add('active');
            
            // Load data for the tab if needed
            if (targetTab === 'categories' && currentCategories.length === 0) {
                loadCategories();
            }
        });
    });
}

// Load overall statistics
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('totalOrders').textContent = data.stats.total_orders;
            document.getElementById('totalSpent').textContent = `$${data.stats.total_spent.toFixed(2)}`;
            document.getElementById('avgOrder').textContent = `$${data.stats.average_order.toFixed(2)}`;
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load orders
async function loadOrders() {
    const container = document.getElementById('ordersContainer');
    container.innerHTML = '<p class="loading">Loading orders...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/orders?limit=50`);
        const data = await response.json();
        
        if (data.success) {
            currentOrders = data.orders;
            displayOrders(currentOrders);
        } else {
            container.innerHTML = `<p class="error">Error: ${data.error}</p>`;
        }
    } catch (error) {
        console.error('Error loading orders:', error);
        container.innerHTML = '<p class="error">Failed to load orders. Please check your connection.</p>';
    }
}

// Display orders
function displayOrders(orders) {
    const container = document.getElementById('ordersContainer');
    
    if (orders.length === 0) {
        container.innerHTML = '<p class="empty-state">No orders found</p>';
        return;
    }
    
    container.innerHTML = orders.map(order => `
        <div class="order-card" onclick="toggleOrderDetails('${order.order_id}')">
            <div class="order-header">
                <div class="order-id">Order #${order.order_id}</div>
                <div class="order-amount">$${(order.total_amount || 0).toFixed(2)}</div>
            </div>
            <div class="order-date">${order.order_date || 'Unknown date'}</div>
            <div class="order-items" id="items-${order.order_id}">
                <p class="loading">Loading items...</p>
            </div>
        </div>
    `).join('');
}

// Toggle order details
async function toggleOrderDetails(orderId) {
    const card = event.currentTarget;
    const itemsDiv = document.getElementById(`items-${orderId}`);
    
    if (card.classList.contains('expanded')) {
        card.classList.remove('expanded');
        return;
    }
    
    card.classList.add('expanded');
    
    try {
        const response = await fetch(`${API_BASE}/orders/${orderId}`);
        const data = await response.json();
        
        if (data.success && data.order.items) {
            const items = data.order.items;
            
            if (items.length === 0) {
                itemsDiv.innerHTML = '<p class="empty-state">No items found</p>';
                return;
            }
            
            itemsDiv.innerHTML = items.map(item => `
                <div class="item-row">
                    <div class="item-name">${item.item_name}</div>
                    <div class="item-quantity">Qty: ${item.quantity || 1}</div>
                    <div class="item-price">$${(item.total_price || 0).toFixed(2)}</div>
                </div>
            `).join('');
        } else {
            itemsDiv.innerHTML = '<p class="empty-state">No items found</p>';
        }
    } catch (error) {
        console.error('Error loading order details:', error);
        itemsDiv.innerHTML = '<p class="error">Failed to load items</p>';
    }
}

// Load categories
async function loadCategories() {
    const container = document.getElementById('categoriesContainer');
    container.innerHTML = '<p class="loading">Loading categories...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/categories`);
        const data = await response.json();
        
        if (data.success) {
            currentCategories = data.categories;
            displayCategories(currentCategories);
        } else {
            container.innerHTML = `<p class="error">Error: ${data.error}</p>`;
        }
    } catch (error) {
        console.error('Error loading categories:', error);
        container.innerHTML = '<p class="error">Failed to load categories. Please check your connection.</p>';
    }
}

// Display categories
function displayCategories(categories) {
    const container = document.getElementById('categoriesContainer');
    
    if (categories.length === 0) {
        container.innerHTML = '<p class="empty-state">No categories found</p>';
        return;
    }
    
    container.innerHTML = categories.map(cat => `
        <div class="category-card">
            <div class="category-header">
                <div class="category-name">${cat.category}</div>
                <div class="category-amount">$${(cat.total_spent || 0).toFixed(2)}</div>
            </div>
            <div class="category-stats">
                <span>${cat.item_count || 0} items</span>
                <span>Avg: $${(cat.avg_price || 0).toFixed(2)}</span>
            </div>
        </div>
    `).join('');
}

// Search items
async function searchItems() {
    const query = document.getElementById('searchInput').value.trim();
    const resultsDiv = document.getElementById('searchResults');
    
    if (!query) {
        resultsDiv.innerHTML = '<p class="empty-state">Enter a search term to find items</p>';
        return;
    }
    
    resultsDiv.innerHTML = '<p class="loading">Searching...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/items/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success) {
            displaySearchResults(data.items);
        } else {
            resultsDiv.innerHTML = `<p class="error">Error: ${data.error}</p>`;
        }
    } catch (error) {
        console.error('Error searching items:', error);
        resultsDiv.innerHTML = '<p class="error">Search failed. Please check your connection.</p>';
    }
}

// Display search results
function displaySearchResults(items) {
    const resultsDiv = document.getElementById('searchResults');
    
    if (items.length === 0) {
        resultsDiv.innerHTML = '<p class="empty-state">No items found matching your search</p>';
        return;
    }
    
    // Group items by name
    const groupedItems = {};
    items.forEach(item => {
        const name = item.item_name;
        if (!groupedItems[name]) {
            groupedItems[name] = {
                name: name,
                purchases: [],
                totalSpent: 0,
                totalQuantity: 0
            };
        }
        groupedItems[name].purchases.push({
            order_id: item.order_id,
            date: item.order_date,
            quantity: item.quantity || 1,
            price: item.total_price || 0
        });
        groupedItems[name].totalSpent += item.total_price || 0;
        groupedItems[name].totalQuantity += item.quantity || 1;
    });
    
    resultsDiv.innerHTML = Object.values(groupedItems).map(item => `
        <div class="search-result-item">
            <div class="result-item-name">${item.name}</div>
            <div class="result-item-stats">
                <span>Purchased ${item.purchases.length} time(s)</span>
                <span>Total: $${item.totalSpent.toFixed(2)}</span>
                <span>Qty: ${item.totalQuantity}</span>
            </div>
            <div class="result-purchases">
                ${item.purchases.map(purchase => `
                    <div class="result-purchase-row">
                        <span>Order #${purchase.order_id}</span>
                        <span>${purchase.date || 'Unknown date'}</span>
                        <span>$${purchase.price.toFixed(2)}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}
