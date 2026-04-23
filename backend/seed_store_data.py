import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from appname.models import User, Store, Product, StoreInventory

# Create products
products_data = [
    # Snacks
    {'name': 'Samosa', 'category': 'SNACKS', 'base_price': 15},
    {'name': 'Vada Pav', 'category': 'SNACKS', 'base_price': 20},
    {'name': 'Chips (Lays)', 'category': 'SNACKS', 'base_price': 20},
    {'name': 'Biscuits (Parle-G)', 'category': 'SNACKS', 'base_price': 10},
    {'name': 'Banana', 'category': 'SNACKS', 'base_price': 5},
    {'name': 'Peanuts', 'category': 'SNACKS', 'base_price': 10},
    
    # Beverages
    {'name': 'Tea', 'category': 'BEVERAGES', 'base_price': 10},
    {'name': 'Coffee', 'category': 'BEVERAGES', 'base_price': 15},
    {'name': 'Bottled Water', 'category': 'BEVERAGES', 'base_price': 20},
    {'name': 'Coca Cola', 'category': 'BEVERAGES', 'base_price': 40},
    {'name': 'Limca', 'category': 'BEVERAGES', 'base_price': 40},
    {'name': 'Frooti', 'category': 'BEVERAGES', 'base_price': 20},
    
    # Meals
    {'name': 'Veg Thali', 'category': 'MEALS', 'base_price': 80},
    {'name': 'Non-Veg Thali', 'category': 'MEALS', 'base_price': 120},
    {'name': 'Idli (2 pcs)', 'category': 'MEALS', 'base_price': 30},
    {'name': 'Dosa', 'category': 'MEALS', 'base_price': 40},
    {'name': 'Poha', 'category': 'MEALS', 'base_price': 25},
    {'name': 'Upma', 'category': 'MEALS', 'base_price': 25},
    
    # Newspapers
    {'name': 'The Hindu', 'category': 'NEWSPAPERS', 'base_price': 8},
    {'name': 'Mathrubhumi', 'category': 'NEWSPAPERS', 'base_price': 6},
    {'name': 'Malayala Manorama', 'category': 'NEWSPAPERS', 'base_price': 6},
    {'name': 'India Today', 'category': 'NEWSPAPERS', 'base_price': 50},
    
    # Toiletries
    {'name': 'Hand Sanitizer', 'category': 'TOILETRIES', 'base_price': 30},
    {'name': 'Tissue Paper', 'category': 'TOILETRIES', 'base_price': 10},
    {'name': 'Wet Wipes', 'category': 'TOILETRIES', 'base_price': 20},
    
    # Miscellaneous
    {'name': 'Mobile Charger', 'category': 'MISC', 'base_price': 150},
    {'name': 'Earphones', 'category': 'MISC', 'base_price': 100},
    {'name': 'Pen', 'category': 'MISC', 'base_price': 10},
    {'name': 'Notebook', 'category': 'MISC', 'base_price': 40},
]

print("Creating products...")
for p in products_data:
    product, created = Product.objects.get_or_create(
        name=p['name'],
        defaults={
            'category': p['category'],
            'base_price': p['base_price'],
            'active': True
        }
    )
    if created:
        print(f"  Created: {product.name} - ₹{product.base_price}")

# Get existing stores
stores_data = [
    'Platform 1 Store',
    'Platform 2 Store', 
    'Main Hall Store',
    'Food Court',
    'Book & News Stall',
    'General Store'
]

print("\nGetting existing stores...")
stores = list(Store.objects.filter(active=True).order_by('id'))
for store in stores:
    print(f"  Found: {store.name}")

# Assign staff to stores
print("\nAssigning staff to stores...")
staff_users = User.objects.filter(role='STORE_STAFF').order_by('id')
for idx, staff in enumerate(staff_users):
    store = stores[idx] if idx < len(stores) else stores[0]
    staff.assigned_store = store
    staff.save()
    print(f"  {staff.email} -> {store.name}")

# Add initial inventory to each store
print("\nAdding initial inventory to stores...")
import random
all_products = Product.objects.all()
for store in stores:
    # Add random products to each store
    num_products = random.randint(15, 25)
    selected_products = random.sample(list(all_products), min(num_products, len(all_products)))
    
    for product in selected_products:
        quantity = random.randint(20, 100)
        StoreInventory.objects.get_or_create(
            store=store,
            product=product,
            defaults={
                'quantity': quantity,
                'reorder_level': 10
            }
        )
    print(f"  {store.name}: {num_products} products added")

print("\n✓ Store data seeded successfully!")
print(f"  Products: {Product.objects.count()}")
print(f"  Stores: {Store.objects.count()}")
print(f"  Staff assigned: {User.objects.filter(role='STORE_STAFF', assigned_store__isnull=False).count()}")
