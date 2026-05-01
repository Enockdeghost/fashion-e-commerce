#!/usr/bin/env python3
"""
Database Initialization Script for LUXÉ Fashion E-Commerce
Run this script to create all database tables.
"""

from app import create_app
from app.extensions import db
from app.models import *

def init_database():
    """Create all database tables."""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully!")
        
        # Create some sample data
        create_sample_data()

def create_sample_data():
    """Create sample categories, brands, and products for testing."""
    from app.models import Category, Brand, Product, Collection
    
    # Check if data already exists
    if Category.query.first():
        print("📊 Sample data already exists, skipping...")
        return
    
    print("🌱 Creating sample data...")
    
    # Create categories
    categories_data = [
        {'name': 'Women', 'slug': 'women', 'description': "Women's fashion collection"},
        {'name': 'Men', 'slug': 'men', 'description': "Men's fashion collection"},
        {'name': 'Accessories', 'slug': 'accessories', 'description': 'Luxury accessories'},
        {'name': 'New Arrivals', 'slug': 'new-arrivals', 'description': 'Latest additions to our collection'},
        {'name': 'Sale', 'slug': 'sale', 'description': 'Discounted luxury items'},
    ]
    
    categories = {}
    for cat_data in categories_data:
        cat = Category(**cat_data)
        db.session.add(cat)
        categories[cat_data['slug']] = cat
    
    db.session.commit()
    print(f" Created {len(categories)} categories")
    
    # Create brands
    brands_data = [
        {'name': 'LUXÉ', 'slug': 'luxe', 'description': 'Our signature luxury brand'},
        {'name': 'Maison Élégance', 'slug': 'maison-elegance', 'description': 'French luxury fashion house'},
        {'name': 'Artisan Collection', 'slug': 'artisan-collection', 'description': 'Handcrafted luxury items'},
    ]
    
    brands = {}
    for brand_data in brands_data:
        brand = Brand(**brand_data)
        db.session.add(brand)
        brands[brand_data['slug']] = brand
    
    db.session.commit()
    print(f"✅ Created {len(brands)} brands")
    
    # Create a sample collection
    artisan_collection = Collection(
        name='Artisan Collection',
        slug='artisan',
        description='Handcrafted pieces by skilled artisans'
    )
    db.session.add(artisan_collection)
    db.session.commit()
    
    print("✅ Sample data created successfully!")
    print("\n🎉 Database initialization complete!")
    print("📝 You can now run the application with: python run.py")

if __name__ == '__main__':
    print("🚀 Initializing LUXÉ Fashion Database...")
    init_database()