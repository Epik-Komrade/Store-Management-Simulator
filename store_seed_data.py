"""Starter products copied to MySQL only when a new store database is created.
All products are organized into major supermarket retail departments.
Tuple format: (item_id, item_name, category, retail_price, min_qty, max_qty, wholesale_price)
"""

CATEGORIES = (
    "Frozen Goods",
    "Bed & Bath",
    "Appliances",
    "Groceries & Pantry",
    "Beverages & Snacks",
    "Household & Cleaning",
)

STANDARD_ITEMS = (
    # -------------------------------------------------------------------------
    # 1. FROZEN GOODS (IDs 101 - 114)
    # -------------------------------------------------------------------------
    (101, "Vanilla Ice Cream", "Frozen Goods", "90.00", 6, 16, "54.00"),
    (102, "Chocolate Ice Cream", "Frozen Goods", "110.00", 6, 16, "66.00"),
    (103, "Frozen Green Peas", "Frozen Goods", "75.00", 8, 20, "45.00"),
    (104, "Frozen Sweet Corn", "Frozen Goods", "65.00", 8, 20, "39.00"),
    (105, "French Fries", "Frozen Goods", "120.00", 8, 22, "72.00"),
    (106, "Frozen Cheese Pizza", "Frozen Goods", "220.00", 5, 14, "132.00"),
    (107, "Chicken Nuggets", "Frozen Goods", "190.00", 5, 15, "114.00"),
    (108, "Fish Fillets", "Frozen Goods", "280.00", 4, 12, "168.00"),
    (109, "Frozen Paratha", "Frozen Goods", "95.00", 8, 20, "57.00"),
    (110, "Veg Burger Patties", "Frozen Goods", "140.00", 6, 18, "84.00"),
    (111, "Ice Cream Sandwiches", "Frozen Goods", "130.00", 6, 16, "78.00"),
    (112, "Frozen Waffles", "Frozen Goods", "160.00", 5, 14, "96.00"),
    (113, "Fruit Popsicles", "Frozen Goods", "40.00", 12, 30, "24.00"),
    (114, "Frozen Mixed Veg", "Frozen Goods", "85.00", 8, 22, "51.00"),

    # -------------------------------------------------------------------------
    # 2. BED & BATH (IDs 121 - 134)
    # -------------------------------------------------------------------------
    (121, "Cotton Bed Sheet", "Bed & Bath", "550.00", 4, 12, "330.00"),
    (122, "Memory Foam Pillow", "Bed & Bath", "650.00", 3, 10, "390.00"),
    (123, "Pillowcase Pair", "Bed & Bath", "180.00", 6, 18, "108.00"),
    (124, "Bath Towel", "Bed & Bath", "320.00", 6, 18, "192.00"),
    (125, "Hand Towel 2-Pack", "Bed & Bath", "160.00", 8, 22, "96.00"),
    (126, "Bath Soap", "Bed & Bath", "40.00", 12, 35, "24.00"),
    (127, "Herbal Shampoo", "Bed & Bath", "140.00", 6, 18, "84.00"),
    (128, "Hair Conditioner", "Bed & Bath", "160.00", 5, 15, "96.00"),
    (129, "Body Wash", "Bed & Bath", "190.00", 5, 16, "114.00"),
    (130, "Toothpaste", "Bed & Bath", "55.00", 10, 28, "33.00"),
    (131, "Toothbrush 4-Pack", "Bed & Bath", "85.00", 8, 24, "51.00"),
    (132, "Shower Gel", "Bed & Bath", "175.00", 5, 15, "105.00"),
    (133, "Bath Loofah", "Bed & Bath", "45.00", 10, 25, "27.00"),
    (134, "Liquid Handwash", "Bed & Bath", "80.00", 8, 22, "48.00"),

    # -------------------------------------------------------------------------
    # 3. APPLIANCES (IDs 141 - 154)
    # -------------------------------------------------------------------------
    (141, "Electric Kettle", "Appliances", "850.00", 3, 8, "510.00"),
    (142, "2-Slice Toaster", "Appliances", "1100.00", 2, 6, "660.00"),
    (143, "Hand Blender", "Appliances", "1250.00", 2, 6, "750.00"),
    (144, "Dry Iron", "Appliances", "650.00", 3, 8, "390.00"),
    (145, "Steam Iron", "Appliances", "1400.00", 2, 5, "840.00"),
    (146, "Compact Microwave", "Appliances", "4500.00", 1, 4, "2700.00"),
    (147, "Drip Coffee Maker", "Appliances", "1850.00", 2, 5, "1110.00"),
    (148, "Ionic Hair Dryer", "Appliances", "950.00", 3, 8, "570.00"),
    (149, "Desk Table Fan", "Appliances", "1200.00", 2, 6, "720.00"),
    (150, "Sandwich Maker", "Appliances", "990.00", 3, 7, "594.00"),
    (151, "Electric Rice Cooker", "Appliances", "1650.00", 2, 5, "990.00"),
    (152, "Portable Smoothie Blender", "Appliances", "890.00", 3, 8, "534.00"),
    (153, "Induction Cooktop", "Appliances", "2400.00", 2, 5, "1440.00"),
    (154, "Digital Kitchen Scale", "Appliances", "480.00", 4, 10, "288.00"),

    # -------------------------------------------------------------------------
    # 4. GROCERIES & PANTRY (IDs 161 - 176)
    # -------------------------------------------------------------------------
    (161, "Basmati Rice 5kg", "Groceries & Pantry", "320.00", 6, 18, "192.00"),
    (162, "Wheat Flour 5kg", "Groceries & Pantry", "240.00", 6, 18, "144.00"),
    (163, "White Sugar 1kg", "Groceries & Pantry", "48.00", 12, 35, "28.00"),
    (164, "Iodized Salt 1kg", "Groceries & Pantry", "22.00", 15, 45, "13.00"),
    (165, "Sunflower Cooking Oil 1L", "Groceries & Pantry", "150.00", 8, 22, "90.00"),
    (166, "Pure Desi Ghee 500g", "Groceries & Pantry", "340.00", 4, 12, "204.00"),
    (167, "Turmeric Powder 200g", "Groceries & Pantry", "38.00", 10, 28, "22.00"),
    (168, "Red Chilli Powder 200g", "Groceries & Pantry", "46.00", 10, 28, "27.00"),
    (169, "Garam Masala 100g", "Groceries & Pantry", "58.00", 8, 24, "34.00"),
    (170, "Macaroni Pasta", "Groceries & Pantry", "70.00", 8, 24, "42.00"),
    (171, "Instant Noodles 4-Pack", "Groceries & Pantry", "56.00", 12, 35, "33.00"),
    (172, "Rolled Oats 1kg", "Groceries & Pantry", "130.00", 6, 18, "78.00"),
    (173, "Cornflakes 500g", "Groceries & Pantry", "145.00", 6, 18, "87.00"),
    (174, "Mixed Fruit Jam", "Groceries & Pantry", "125.00", 6, 18, "75.00"),
    (175, "Creamy Peanut Butter", "Groceries & Pantry", "220.00", 4, 12, "132.00"),
    (176, "Fresh Milk 1L", "Groceries & Pantry", "34.00", 12, 32, "20.00"),

    # -------------------------------------------------------------------------
    # 5. BEVERAGES & SNACKS (IDs 181 - 194)
    # -------------------------------------------------------------------------
    (181, "Premium Black Tea 500g", "Beverages & Snacks", "160.00", 6, 18, "96.00"),
    (182, "Instant Coffee 100g", "Beverages & Snacks", "190.00", 6, 18, "114.00"),
    (183, "Fruit Juice 1L", "Beverages & Snacks", "95.00", 8, 24, "57.00"),
    (184, "Soft Drink 1.5L", "Beverages & Snacks", "65.00", 10, 30, "39.00"),
    (185, "Bottled Mineral Water", "Beverages & Snacks", "20.00", 15, 50, "12.00"),
    (186, "Salted Potato Chips", "Beverages & Snacks", "25.00", 15, 45, "15.00"),
    (187, "Masala Banana Chips", "Beverages & Snacks", "35.00", 12, 36, "21.00"),
    (188, "Dark Chocolate Bar", "Beverages & Snacks", "85.00", 8, 25, "51.00"),
    (189, "Milk Chocolate", "Beverages & Snacks", "50.00", 10, 30, "30.00"),
    (190, "Cream Biscuits", "Beverages & Snacks", "30.00", 15, 45, "18.00"),
    (191, "Energy Drink", "Beverages & Snacks", "110.00", 8, 24, "66.00"),
    (192, "Roasted Cashews 200g", "Beverages & Snacks", "240.00", 4, 12, "144.00"),
    (193, "Roasted Almonds 200g", "Beverages & Snacks", "220.00", 4, 12, "132.00"),
    (194, "Tomato Ketchup 500g", "Beverages & Snacks", "85.00", 8, 22, "51.00"),

    # -------------------------------------------------------------------------
    # 6. HOUSEHOLD & CLEANING (IDs 201 - 214)
    # -------------------------------------------------------------------------
    (201, "Laundry Detergent 1kg", "Household & Cleaning", "170.00", 6, 18, "102.00"),
    (202, "Fabric Softener 1L", "Household & Cleaning", "185.00", 5, 15, "111.00"),
    (203, "Dishwashing Gel 500ml", "Household & Cleaning", "95.00", 8, 24, "57.00"),
    (204, "Antibacterial Floor Cleaner", "Household & Cleaning", "135.00", 6, 18, "81.00"),
    (205, "Glass Cleaning Spray", "Household & Cleaning", "110.00", 6, 18, "66.00"),
    (206, "Disinfectant Surface Spray", "Household & Cleaning", "165.00", 6, 18, "99.00"),
    (207, "Heavy-Duty Trash Bags", "Household & Cleaning", "85.00", 8, 24, "51.00"),
    (208, "Paper Towel 2-Roll", "Household & Cleaning", "90.00", 8, 24, "54.00"),
    (209, "Toilet Paper 4-Pack", "Household & Cleaning", "95.00", 8, 24, "57.00"),
    (210, "Scrub Sponge 3-Pack", "Household & Cleaning", "45.00", 12, 35, "27.00"),
    (211, "Broom and Dustpan Set", "Household & Cleaning", "220.00", 4, 12, "132.00"),
    (212, "Air Freshener Spray", "Household & Cleaning", "125.00", 6, 18, "75.00"),
    (213, "Mosquito Vaporizer Refill", "Household & Cleaning", "75.00", 8, 24, "45.00"),
    (214, "Kitchen Aluminum Foil", "Household & Cleaning", "115.00", 6, 18, "69.00"),
)
