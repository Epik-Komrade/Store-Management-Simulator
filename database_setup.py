"""MySQL database creation and map-to-shelf synchronization."""

import hashlib
import importlib
import os
import random
import re

import db_config
from db_config import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER
from store_seed_data import CATEGORIES, STANDARD_ITEMS

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

#_____________________________SETTINGS_____________________________
MAP_WIDTH = 25
MAP_HEIGHT = 15
MAP_TILES = {"#", ".", "P", "S", "C", "R", "E", "B"}
MAX_SHELF_CAPACITY = 50

DEFAULT_EMPLOYEES = [
    (101, "Rahul Sharma", "Cashier", 18000.00),
    (102, "Priya Patel", "Stocker", 16000.00),
    (103, "Amit Kumar", "Store Assistant", 15000.00),
]


class DatabaseSetupError(RuntimeError):
    """Error raised when the store database is unavailable."""

#_____________________________NAME & MAP LOAD_____________________________
def database_name_for_map(map_path):
    """MySQL database name from a map filename."""
    map_stem = os.path.splitext(os.path.basename(map_path))[0].lower()
    safe_stem = re.sub(r"[^a-z0-9_]", "_", map_stem).strip("_") or "store"
    name = safe_stem
    if len(name) > 64:
        suffix = hashlib.sha256(map_stem.encode("utf-8")).hexdigest()[:8]
        name = f"{name[:55]}_{suffix}"
    return name


def read_store_map(map_path):
    """Check the store map and return its shelf coordinates in reading order."""
    try:
        with open(map_path, "r", encoding="utf-8") as map_file:
            lines = [line.rstrip("\r\n") for line in map_file]
    except OSError as error:
        raise DatabaseSetupError(f"Cannot read the map file: {error}") from error

    if len(lines) != MAP_HEIGHT or any(len(line) != MAP_WIDTH for line in lines):
        raise DatabaseSetupError(f"The map must be exactly {MAP_WIDTH} columns by {MAP_HEIGHT} rows.")

    player_count = 0
    catalogue_count = 0
    register_count = 0
    employee_count = 0
    storage_count = 0
    shelf_positions = []
    for y, line in enumerate(lines):
        for x, tile in enumerate(line):
            if tile not in MAP_TILES:
                raise DatabaseSetupError(f"Unsupported map symbol {tile!r} at row {y + 1}, column {x + 1}.")
            if tile == "P":
                player_count += 1
            elif tile == "C":
                catalogue_count += 1
            elif tile == "R":
                register_count += 1
            elif tile == "E":
                employee_count += 1
            elif tile == "B":
                storage_count += 1
            elif tile == "S":
                shelf_positions.append((x, y))

    if player_count != 1:
        raise DatabaseSetupError("The store map must contain exactly one player spawn (P).")
    if catalogue_count != 1:
        raise DatabaseSetupError("The store map must contain exactly one product catalogue (C). Edit store_level1.txt.")
    if register_count != 1:
        raise DatabaseSetupError("The store map must contain exactly one cash register (R). Edit store_level1.txt.")
    if employee_count != 1:
        raise DatabaseSetupError("The store map must contain exactly one employee terminal (E). Edit store_level1.txt.")
    if storage_count > 1:
        raise DatabaseSetupError("The store map can contain at most one storage depot (B). Edit store_level1.txt.")

    return shelf_positions, "\n".join(lines)

#_____________________________CONNECT_____________________________
CHARSET_COLLATIONS = {
    "utf8mb4": "utf8mb4_unicode_ci",
    "utf8": "utf8_general_ci",
    "latin1": "latin1_swedish_ci",
}


def reload_db_config():
    """Reload db_config.py at runtime after launcher settings are updated."""
    global DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
    importlib.reload(db_config)
    DB_HOST = db_config.DB_HOST
    DB_PORT = db_config.DB_PORT
    DB_USER = db_config.DB_USER
    DB_PASSWORD = db_config.DB_PASSWORD
    return db_config


def _connect(database=None):
    if mysql is None:
        raise DatabaseSetupError("mysql-connector-python is not installed. Install it before starting the launcher.")
    charset = getattr(db_config, "DB_CHARSET", "utf8mb4") or "utf8mb4"
    base_options = {
        "host": db_config.DB_HOST,
        "port": int(db_config.DB_PORT),
        "user": db_config.DB_USER,
        "password": db_config.DB_PASSWORD,
    }
    if database:
        base_options["database"] = database

    # Try configured charset first, with automatic fallbacks for both legacy MySQL 5.0
    # (ERROR 1115: Unknown character set 'utf8mb4') and modern Connector/Python 9.x
    attempts = [
        {**base_options, "charset": charset},
        base_options,
        {**base_options, "charset": "utf8"},
        {**base_options, "charset": "latin1"},
    ]
    last_error = None
    for opts in attempts:
        try:
            return mysql.connector.connect(**opts)
        except Exception as error:
            last_error = error
            err_text = str(error).lower()
            if (
                getattr(error, "errno", None) == 1115
                or "character set" in err_text
                or "collation" in err_text
            ):
                continue
            break

    raise DatabaseSetupError(
        f"Could not connect to MySQL at {db_config.DB_HOST}:{db_config.DB_PORT}. "
        f"Check db_config.py and ensure MySQL Server is running. ({last_error})"
    ) from last_error


def _database_exists(connection, database_name):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
            (database_name,),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _create_database(connection, database_name):
    charset = getattr(db_config, "DB_CHARSET", "utf8mb4") or "utf8mb4"
    collation = CHARSET_COLLATIONS.get(charset, "utf8_general_ci")
    cursor = connection.cursor()
    try:
        candidates = [
            f"CREATE DATABASE `{database_name}` CHARACTER SET {charset} COLLATE {collation}",
            f"CREATE DATABASE `{database_name}` CHARACTER SET utf8 COLLATE utf8_general_ci",
            f"CREATE DATABASE `{database_name}` CHARACTER SET latin1 COLLATE latin1_swedish_ci",
            f"CREATE DATABASE `{database_name}`",
        ]
        last_error = None
        for sql in candidates:
            try:
                cursor.execute(sql)
                return
            except MySQLError as error:
                last_error = error
                err_text = str(error).lower()
                if (
                    getattr(error, "errno", None) == 1115
                    or "character set" in err_text
                    or "collation" in err_text
                ):
                    continue
                raise
        if last_error:
            raise last_error
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not create database {database_name!r}. ({error})") from error
    finally:
        cursor.close()

#_____________________________TABLE CREATION_____________________________
def _create_tables(connection):
    statements = (
        """
        CREATE TABLE IF NOT EXISTS map_metadata (
            metadata_id TINYINT PRIMARY KEY,
            map_filename VARCHAR(255) NOT NULL,
            map_hash CHAR(64) NOT NULL,
            map_width SMALLINT UNSIGNED NOT NULL,
            map_height SMALLINT UNSIGNED NOT NULL,
            last_synced TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shelves (
            shelf_id INT AUTO_INCREMENT PRIMARY KEY,
            map_x SMALLINT UNSIGNED NOT NULL,
            map_y SMALLINT UNSIGNED NOT NULL,
            category VARCHAR(50) DEFAULT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_shelf_position (map_x, map_y)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS products (
            item_id INT PRIMARY KEY,
            item_name VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'General',
            price DECIMAL(10, 2) NOT NULL,
            minimum_quantity INT UNSIGNED NOT NULL,
            maximum_quantity INT UNSIGNED NOT NULL,
            wholesale_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shelf_inventory (
            shelf_id INT NOT NULL,
            item_id INT NOT NULL,
            item_name VARCHAR(100) NOT NULL,
            quantity INT UNSIGNED NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            PRIMARY KEY (shelf_id, item_id),
            CONSTRAINT shelf_inventory_shelf_fk
                FOREIGN KEY (shelf_id) REFERENCES shelves(shelf_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS store_finance (
            finance_id TINYINT PRIMARY KEY,
            current_balance DECIMAL(12, 2) NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS finance_history (
            history_id INT AUTO_INCREMENT PRIMARY KEY,
            finance_id TINYINT NOT NULL,
            change_type VARCHAR(10) NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            previous_balance DECIMAL(12, 2) NOT NULL,
            new_balance DECIMAL(12, 2) NOT NULL,
            recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT finance_history_finance_fk
                FOREIGN KEY (finance_id) REFERENCES store_finance(finance_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            role VARCHAR(30) NOT NULL,
            salary DECIMAL(10, 2) NOT NULL,
            hire_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS storage_inventory (
            item_id INT PRIMARY KEY,
            quantity INT NOT NULL DEFAULT 0,
            wholesale_price DECIMAL(10, 2) NOT NULL,
            last_restocked TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT storage_inventory_prod_fk
                FOREIGN KEY (item_id) REFERENCES products(item_id) ON DELETE CASCADE
        )
        """,
    )
    cursor = connection.cursor()
    try:
        for statement in statements:
            try:
                cursor.execute(statement)
            except MySQLError as error:
                # Fallback for legacy MySQL 5.0/5.5 single CURRENT_TIMESTAMP restriction (ERROR 1293)
                if getattr(error, "errno", None) == 1293:
                    legacy_stmt = statement.replace(
                        "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
                        "created_at TIMESTAMP NULL DEFAULT NULL,",
                    )
                    cursor.execute(legacy_stmt)
                else:
                    raise
    finally:
        cursor.close()


def _migrate_database_schema(connection):
    """Ensure existing tables have new columns and storage_inventory exists."""
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SHOW COLUMNS FROM products")
        prod_cols = {row["Field"].lower() for row in cursor.fetchall()}
        if "category" not in prod_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN category VARCHAR(50) NOT NULL DEFAULT 'General'")
        if "wholesale_price" not in prod_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN wholesale_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00")

        cursor.execute("SHOW COLUMNS FROM shelves")
        shelf_cols = {row["Field"].lower() for row in cursor.fetchall()}
        if "category" not in shelf_cols:
            cursor.execute("ALTER TABLE shelves ADD COLUMN category VARCHAR(50) DEFAULT NULL")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_inventory (
                item_id INT PRIMARY KEY,
                quantity INT NOT NULL DEFAULT 0,
                wholesale_price DECIMAL(10, 2) NOT NULL,
                last_restocked TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT storage_inventory_prod_fk
                    FOREIGN KEY (item_id) REFERENCES products(item_id) ON DELETE CASCADE
            )
            """
        )
    finally:
        cursor.close()


def _sync_catalogue_and_storage(connection):
    """Sync all standard catalogue items and ensure storage_inventory has starter stock."""
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS cnt FROM products")
        product_count = cursor.fetchone()["cnt"]
        if product_count == 0:
            cursor.executemany(
                """
                INSERT INTO products
                    (item_id, item_name, category, price, minimum_quantity, maximum_quantity, wholesale_price)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                STANDARD_ITEMS,
            )
        else:
            for item in STANDARD_ITEMS:
                cursor.execute(
                    """
                    INSERT INTO products
                        (item_id, item_name, category, price, minimum_quantity, maximum_quantity, wholesale_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        category = VALUES(category),
                        wholesale_price = VALUES(wholesale_price)
                    """,
                    item,
                )

        # Seed storage_inventory with starter stock (25 units) if missing
        cursor.execute(
            """
            INSERT IGNORE INTO storage_inventory (item_id, quantity, wholesale_price)
            SELECT item_id, 25, COALESCE(wholesale_price, ROUND(price * 0.6, 2))
            FROM products
            """
        )
        return len(STANDARD_ITEMS)
    finally:
        cursor.close()


def _initialize_finance_if_needed(connection):
    """Give each store database its initial Rs. 20,000 balance exactly once."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT IGNORE INTO store_finance (finance_id, current_balance) VALUES (1, %s)",
            (20000.00,),
        )
    finally:
        cursor.close()


def _seed_employees_if_empty(connection):
    """Seed initial store employees if the table is empty."""
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM employees")
        emp_count = cursor.fetchone()[0]
        if emp_count == 0:
            cursor.executemany(
                """
                INSERT INTO employees (employee_id, name, role, salary)
                VALUES (%s, %s, %s, %s)
                """,
                DEFAULT_EMPLOYEES,
            )
            return len(DEFAULT_EMPLOYEES)
        return 0
    finally:
        cursor.close()


def _new_shelf_inventory(cursor, shelf_id):
    """Create a small random starter selection from the saved product catalogue within shelf capacity."""
    cursor.execute(
        """
        SELECT item_id, item_name, price, minimum_quantity, maximum_quantity
        FROM products
        ORDER BY item_id
        """
    )
    products = cursor.fetchall()
    if not products:
        return []

    selection_size = random.randint(min(3, len(products)), min(5, len(products)))
    selected_products = random.sample(products, selection_size)
    starter = []
    remaining_cap = 38
    for idx, product in enumerate(selected_products):
        items_left = len(selected_products) - idx
        max_for_this = max(1, remaining_cap - (items_left - 1))
        low = min(product["minimum_quantity"], 4, max_for_this)
        high = min(product["maximum_quantity"], 10, max_for_this)
        qty = random.randint(max(1, low), max(1, high))
        remaining_cap = max(0, remaining_cap - qty)
        starter.append(
            (
                shelf_id,
                product["item_id"],
                product["item_name"],
                qty,
                product["price"],
            )
        )
    return starter


def _clamp_overcapacity_shelves(cursor):
    """Ensure no existing shelf exceeds MAX_SHELF_CAPACITY (50) from legacy random seeding."""
    cursor.execute(
        """
        SELECT shelf_id, SUM(quantity) AS total_q
        FROM shelf_inventory
        GROUP BY shelf_id
        HAVING total_q > 50
        """
    )
    over_shelves = cursor.fetchall()
    for s_row in over_shelves:
        s_id = s_row["shelf_id"]
        cursor.execute(
            "SELECT item_id, quantity FROM shelf_inventory WHERE shelf_id = %s ORDER BY item_id",
            (s_id,),
        )
        items = cursor.fetchall()
        if not items:
            continue
        target_per_item = max(2, 36 // len(items))
        for it in items:
            old_q = int(it["quantity"])
            new_q = min(old_q, target_per_item)
            if new_q < old_q:
                cursor.execute(
                    "UPDATE shelf_inventory SET quantity = %s WHERE shelf_id = %s AND item_id = %s",
                    (new_q, s_id, it["item_id"]),
                )


def _sync_shelves(connection, shelf_positions):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT shelf_id, map_x, map_y, is_active FROM shelves")
        existing = {(row["map_x"], row["map_y"]): row for row in cursor.fetchall()}
        current_positions = set(shelf_positions)
        added = 0
        reactivated = 0
        deactivated = 0

        for x, y in shelf_positions:
            saved_shelf = existing.get((x, y))
            if saved_shelf is None:
                cursor.execute(
                    "INSERT INTO shelves (map_x, map_y, is_active) VALUES (%s, %s, TRUE)",
                    (x, y),
                )
                shelf_id = cursor.lastrowid
                starter_items = _new_shelf_inventory(cursor, shelf_id)
                if starter_items:
                    cursor.executemany(
                        """
                        INSERT INTO shelf_inventory (shelf_id, item_id, item_name, quantity, price)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        starter_items,
                    )
                added += 1
            elif not saved_shelf["is_active"]:
                cursor.execute(
                    "UPDATE shelves SET is_active = TRUE WHERE shelf_id = %s",
                    (saved_shelf["shelf_id"],),
                )
                reactivated += 1

        for position, saved_shelf in existing.items():
            if saved_shelf["is_active"] and position not in current_positions:
                cursor.execute(
                    "UPDATE shelves SET is_active = FALSE WHERE shelf_id = %s",
                    (saved_shelf["shelf_id"],),
                )
                deactivated += 1

        _clamp_overcapacity_shelves(cursor)
        return added, reactivated, deactivated
    finally:
        cursor.close()

#_____________________________MAP HASH_____________________________
def _save_map_metadata(connection, map_path, map_contents):
    map_hash = hashlib.sha256(map_contents.encode("utf-8")).hexdigest()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO map_metadata (metadata_id, map_filename, map_hash, map_width, map_height)
            VALUES (1, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                map_filename = %s,
                map_hash = %s,
                map_width = %s,
                map_height = %s
            """,
            (
                os.path.basename(map_path),
                map_hash,
                MAP_WIDTH,
                MAP_HEIGHT,
                os.path.basename(map_path),
                map_hash,
                MAP_WIDTH,
                MAP_HEIGHT,
            ),
        )
    finally:
        cursor.close()


def ensure_store_database(map_path):
    """Create/sync the map database and return a short status report."""
    shelf_positions, map_contents = read_store_map(map_path)
    database_name = database_name_for_map(map_path)

    server_connection = _connect()
    try:
        created_database = not _database_exists(server_connection, database_name)
        if created_database:
            _create_database(server_connection, database_name)
    finally:
        server_connection.close()

    database_connection = _connect(database_name)
    try:
        _create_tables(database_connection)
        _migrate_database_schema(database_connection)
        _sync_catalogue_and_storage(database_connection)
        _initialize_finance_if_needed(database_connection)
        _seed_employees_if_empty(database_connection)
        added, reactivated, deactivated = _sync_shelves(database_connection, shelf_positions)
        _save_map_metadata(database_connection, map_path, map_contents)
        database_connection.commit()
    except MySQLError as error:
        database_connection.rollback()
        raise DatabaseSetupError(f"Could not synchronize the store database. ({error})") from error
    finally:
        database_connection.close()

    if created_database:
        return f"Created {database_name} with {added} shelves."
    if added or reactivated or deactivated:
        return (
            f"Updated {database_name}: {added} added, {reactivated} restored, "
            f"{deactivated} archived."
        )
    return f"{database_name} is ready; map layout is unchanged."

#_____________________________DB LOAD_____________________________
def load_shelf_inventory(map_path):
    """Return saved shelf IDs and inventory rows, indexed by map position."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT s.shelf_id, s.map_x, s.map_y,
                   i.item_id, i.item_name, i.quantity, i.price
            FROM shelves AS s
            LEFT JOIN shelf_inventory AS i ON i.shelf_id = s.shelf_id
            WHERE s.is_active = TRUE
            ORDER BY s.map_y, s.map_x, i.item_id
            """
        )
        shelves_by_position = {}
        for row in cursor.fetchall():
            position = (row["map_x"], row["map_y"])
            if position not in shelves_by_position:
                shelves_by_position[position] = [row["shelf_id"], []]

            if row["item_id"] is not None:
                shelves_by_position[position][1].append(
                    (
                        row["item_id"],
                        row["item_name"],
                        row["quantity"],
                        float(row["price"]),
                    )
                )

        return {
            position: (shelf_id, tuple(items))
            for position, (shelf_id, items) in shelves_by_position.items()
        }
    except MySQLError as error:
        raise DatabaseSetupError(
            f"Could not load shelf inventory from {database_name!r}. ({error})"
        ) from error
    finally:
        cursor.close()
        connection.close()


def load_product_catalogue(map_path):
    """Return the permanent MySQL product catalogue in item-ID order."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT item_id, item_name, category, price, minimum_quantity, maximum_quantity, wholesale_price
            FROM products
            ORDER BY category, item_id
            """
        )
        return tuple(
            (
                row["item_id"],
                row["item_name"],
                float(row["price"]),
                row["minimum_quantity"],
                row["maximum_quantity"],
                row.get("category") or "General",
                float(row.get("wholesale_price") or round(float(row["price"]) * 0.6, 2)),
            )
            for row in cursor.fetchall()
        )
    except MySQLError as error:
        raise DatabaseSetupError(
            f"Could not load the product catalogue from {database_name!r}. ({error})"
        ) from error
    finally:
        cursor.close()
        connection.close()


def _check_product_values(item_id, item_name, price, minimum_quantity, maximum_quantity):
    if not isinstance(item_id, int) or item_id <= 0:
        raise DatabaseSetupError("Item ID must be a positive whole number.")
    if not isinstance(item_name, str) or not item_name.strip() or len(item_name.strip()) > 100:
        raise DatabaseSetupError("Product name must contain 1 to 100 characters.")
    if price <= 0:
        raise DatabaseSetupError("Price must be greater than zero.")
    if minimum_quantity < 0 or maximum_quantity < minimum_quantity:
        raise DatabaseSetupError("Quantity range must be zero or higher, with a valid maximum.")

#_____________________________CAT DB UPDATES_____________________________
def add_catalogue_product(
    map_path,
    item_id,
    item_name,
    price,
    minimum_quantity,
    maximum_quantity,
    category="General",
    wholesale_price=None,
):
    """Add a product that can later be placed on shelves."""
    _check_product_values(item_id, item_name, price, minimum_quantity, maximum_quantity)
    ws_price = float(wholesale_price) if wholesale_price is not None else round(price * 0.6, 2)
    cat = (category or "General").strip()
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO products
                (item_id, item_name, category, price, minimum_quantity, maximum_quantity, wholesale_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (item_id, item_name.strip(), cat, price, minimum_quantity, maximum_quantity, ws_price),
        )
        cursor.execute(
            """
            INSERT INTO storage_inventory (item_id, quantity, wholesale_price)
            VALUES (%s, 20, %s)
            ON DUPLICATE KEY UPDATE wholesale_price = VALUES(wholesale_price)
            """,
            (item_id, ws_price),
        )
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        if getattr(error, "errno", None) == 1062:
            raise DatabaseSetupError("That Item ID is already in the catalogue.") from error
        raise DatabaseSetupError(f"Could not add the catalogue product. ({error})") from error
    finally:
        cursor.close()
        connection.close()


def update_catalogue_product(
    map_path,
    old_item_id,
    item_id,
    item_name,
    price,
    minimum_quantity,
    maximum_quantity,
    category="General",
    wholesale_price=None,
):
    """Edit a catalogue product and synchronize storage and shelf item names."""
    _check_product_values(item_id, item_name, price, minimum_quantity, maximum_quantity)
    ws_price = float(wholesale_price) if wholesale_price is not None else round(price * 0.6, 2)
    cat = (category or "General").strip()
    clean_name = item_name.strip()
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        saved_storage_qty = 20
        if old_item_id != item_id:
            cursor.execute(
                "SELECT COUNT(*) FROM shelf_inventory WHERE item_id = %s",
                (old_item_id,),
            )
            if cursor.fetchone()[0]:
                raise DatabaseSetupError(
                    "Remove this product from every shelf before changing its Item ID."
                )
            cursor.execute(
                "SELECT quantity FROM storage_inventory WHERE item_id = %s",
                (old_item_id,),
            )
            storage_row = cursor.fetchone()
            if storage_row is not None:
                saved_storage_qty = int(storage_row[0])
                cursor.execute(
                    "DELETE FROM storage_inventory WHERE item_id = %s",
                    (old_item_id,),
                )
        cursor.execute(
            """
            UPDATE products
            SET item_id = %s, item_name = %s, category = %s, price = %s,
                minimum_quantity = %s, maximum_quantity = %s, wholesale_price = %s
            WHERE item_id = %s
            """,
            (
                item_id,
                clean_name,
                cat,
                price,
                minimum_quantity,
                maximum_quantity,
                ws_price,
                old_item_id,
            ),
        )
        if cursor.rowcount != 1:
            raise DatabaseSetupError("That catalogue product no longer exists.")
        cursor.execute(
            """
            INSERT INTO storage_inventory (item_id, quantity, wholesale_price)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE wholesale_price = VALUES(wholesale_price)
            """,
            (item_id, saved_storage_qty, ws_price),
        )
        if old_item_id == item_id:
            cursor.execute(
                "UPDATE shelf_inventory SET item_name = %s WHERE item_id = %s",
                (clean_name, item_id),
            )
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        if getattr(error, "errno", None) == 1062:
            raise DatabaseSetupError("That Item ID is already in the catalogue.") from error
        raise DatabaseSetupError(f"Could not update the catalogue product. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def delete_catalogue_product(map_path, item_id):
    """Delete an unused catalogue product while preserving shelf history."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM shelf_inventory WHERE item_id = %s",
            (item_id,),
        )
        if cursor.fetchone()[0]:
            raise DatabaseSetupError(
                "Remove this product from every shelf before deleting it from the catalogue."
            )
        cursor.execute("DELETE FROM products WHERE item_id = %s", (item_id,))
        if cursor.rowcount != 1:
            raise DatabaseSetupError("That catalogue product no longer exists.")
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not delete the catalogue product. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

#_____________________________FIN LOAD_____________________________
def load_finance_data(map_path):
    """Load the current balance and newest-first permanent finance history."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT current_balance FROM store_finance WHERE finance_id = 1"
        )
        finance_row = cursor.fetchone()
        if finance_row is None:
            raise DatabaseSetupError("The store finance record has not been initialized.")
        cursor.execute(
            """
            SELECT history_id, change_type, amount, new_balance, recorded_at
            FROM finance_history
            WHERE finance_id = 1
            ORDER BY history_id DESC
            """
        )
        history = tuple(
            (
                row["history_id"],
                row["change_type"],
                float(row["amount"]),
                float(row["new_balance"]),
                row["recorded_at"],
            )
            for row in cursor.fetchall()
        )
        return float(finance_row["current_balance"]), history
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not load store finance. ({error})") from error
    finally:
        cursor.close()
        connection.close()

#_____________________________DB UPDATES_____________________________
def set_store_balance(map_path, new_balance):
    """Save a manual balance change and its profit/loss difference in one transaction."""
    if new_balance < 0:
        raise DatabaseSetupError("Balance cannot be negative.")

    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT current_balance FROM store_finance WHERE finance_id = 1 FOR UPDATE"
        )
        finance_row = cursor.fetchone()
        if finance_row is None:
            raise DatabaseSetupError("The store finance record has not been initialized.")

        old_balance = float(finance_row[0])
        difference = round(new_balance - old_balance, 2)
        if difference == 0:
            connection.rollback()
            return old_balance, None

        change_type = "Profit" if difference > 0 else "Loss"
        amount = abs(difference)
        cursor.execute(
            "UPDATE store_finance SET current_balance = %s WHERE finance_id = 1",
            (new_balance,),
        )
        cursor.execute(
            """
            INSERT INTO finance_history
                (finance_id, change_type, amount, previous_balance, new_balance)
            VALUES (1, %s, %s, %s, %s)
            """,
            (change_type, amount, old_balance, new_balance),
        )
        history_id = cursor.lastrowid
        connection.commit()
        return new_balance, (history_id, change_type, amount, None)
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not save the new balance. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def add_shelf_item(map_path, shelf_id, item_id, item_name, quantity, price):
    """Save a new inventory record for one shelf, enforcing capacity and deducting from storage."""
    if quantity <= 0:
        raise DatabaseSetupError("Quantity must be at least 1.")
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT category FROM shelves WHERE shelf_id = %s", (shelf_id,))
        shelf_row = cursor.fetchone()
        shelf_cat = (shelf_row["category"] if shelf_row else None) or "General"

        cursor.execute("SELECT category, price, wholesale_price FROM products WHERE item_id = %s", (item_id,))
        prod_row = cursor.fetchone()
        prod_cat = (prod_row["category"] if prod_row else None) or "General"
        if shelf_cat != "General" and prod_cat != shelf_cat:
            raise DatabaseSetupError(f"This shelf only accepts {shelf_cat} products.")

        cursor.execute(
            """
            SELECT COALESCE(SUM(si.quantity), 0) AS current_qty
            FROM shelf_inventory si
            JOIN products p ON si.item_id = p.item_id
            WHERE si.shelf_id = %s
              AND (%s = 'General' OR COALESCE(p.category, 'General') = %s)
            """,
            (shelf_id, shelf_cat, shelf_cat),
        )
        current_qty = int(cursor.fetchone()["current_qty"])
        if current_qty + quantity > MAX_SHELF_CAPACITY:
            space_left = max(0, MAX_SHELF_CAPACITY - current_qty)
            raise DatabaseSetupError(
                f"Shelf capacity limit reached! Max {MAX_SHELF_CAPACITY} units ({space_left} space left)."
            )

        cursor.execute(
            "SELECT quantity FROM storage_inventory WHERE item_id = %s FOR UPDATE",
            (item_id,),
        )
        storage_row = cursor.fetchone()
        avail_storage = int(storage_row["quantity"]) if storage_row else 0
        if quantity > avail_storage:
            raise DatabaseSetupError(
                f"Not enough stock in Storage Depot! Available: {avail_storage} units."
            )

        cursor.execute(
            "UPDATE storage_inventory SET quantity = quantity - %s WHERE item_id = %s",
            (quantity, item_id),
        )
        cursor.execute(
            """
            INSERT INTO shelf_inventory (shelf_id, item_id, item_name, quantity, price)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (shelf_id, item_id, item_name, quantity, price),
        )
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not add the item to shelf {shelf_id}. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def delete_shelf_item(map_path, shelf_id, item_id):
    """Remove one inventory record from one shelf and return its stock to storage."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT quantity FROM shelf_inventory WHERE shelf_id = %s AND item_id = %s FOR UPDATE",
            (shelf_id, item_id),
        )
        row = cursor.fetchone()
        if not row:
            raise DatabaseSetupError("That shelf item no longer exists in MySQL.")
        old_qty = int(row["quantity"])

        cursor.execute(
            "DELETE FROM shelf_inventory WHERE shelf_id = %s AND item_id = %s",
            (shelf_id, item_id),
        )
        if old_qty > 0:
            cursor.execute(
                """
                INSERT INTO storage_inventory (item_id, quantity, wholesale_price)
                SELECT %s, %s, COALESCE(wholesale_price, ROUND(price * 0.6, 2))
                FROM products WHERE item_id = %s
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """,
                (item_id, old_qty, item_id),
            )
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not remove the item from shelf {shelf_id}. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def update_shelf_item(map_path, shelf_id, old_item_id, item_id, item_name, quantity, price):
    """Save an edited shelf inventory record, enforcing capacity and syncing with storage."""
    if quantity <= 0:
        raise DatabaseSetupError("Quantity must be at least 1 (use X to remove item).")
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT quantity FROM shelf_inventory WHERE shelf_id = %s AND item_id = %s FOR UPDATE",
            (shelf_id, old_item_id),
        )
        old_row = cursor.fetchone()
        if not old_row:
            raise DatabaseSetupError("That shelf item no longer exists in MySQL.")
        old_qty = int(old_row["quantity"])

        cursor.execute("SELECT category FROM shelves WHERE shelf_id = %s", (shelf_id,))
        shelf_row = cursor.fetchone()
        shelf_cat = (shelf_row["category"] if shelf_row else None) or "General"

        cursor.execute("SELECT category FROM products WHERE item_id = %s", (item_id,))
        prod_row = cursor.fetchone()
        prod_cat = (prod_row["category"] if prod_row else None) or "General"
        if shelf_cat != "General" and prod_cat != shelf_cat:
            raise DatabaseSetupError(f"This shelf only accepts {shelf_cat} products.")

        cursor.execute(
            """
            SELECT COALESCE(SUM(si.quantity), 0) AS other_qty
            FROM shelf_inventory si
            JOIN products p ON si.item_id = p.item_id
            WHERE si.shelf_id = %s
              AND si.item_id != %s
              AND (%s = 'General' OR COALESCE(p.category, 'General') = %s)
            """,
            (shelf_id, old_item_id, shelf_cat, shelf_cat),
        )
        other_qty = int(cursor.fetchone()["other_qty"])
        if other_qty + quantity > MAX_SHELF_CAPACITY:
            space_left = max(0, MAX_SHELF_CAPACITY - other_qty)
            raise DatabaseSetupError(
                f"Shelf capacity limit reached! Max {MAX_SHELF_CAPACITY} units ({space_left} max for this item)."
            )

        if old_item_id == item_id:
            delta = quantity - old_qty
            if delta > 0:
                cursor.execute(
                    "SELECT quantity FROM storage_inventory WHERE item_id = %s FOR UPDATE",
                    (item_id,),
                )
                s_row = cursor.fetchone()
                avail_storage = int(s_row["quantity"]) if s_row else 0
                if delta > avail_storage:
                    raise DatabaseSetupError(
                        f"Not enough stock in Storage Depot! Need {delta} more, available: {avail_storage}."
                    )
                cursor.execute(
                    "UPDATE storage_inventory SET quantity = quantity - %s WHERE item_id = %s",
                    (delta, item_id),
                )
            elif delta < 0:
                cursor.execute(
                    """
                    INSERT INTO storage_inventory (item_id, quantity, wholesale_price)
                    SELECT %s, %s, COALESCE(wholesale_price, ROUND(price * 0.6, 2))
                    FROM products WHERE item_id = %s
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """,
                    (item_id, -delta, item_id),
                )
        else:
            cursor.execute(
                "SELECT quantity FROM storage_inventory WHERE item_id = %s FOR UPDATE",
                (item_id,),
            )
            s_row = cursor.fetchone()
            avail_storage = int(s_row["quantity"]) if s_row else 0
            if quantity > avail_storage:
                raise DatabaseSetupError(
                    f"Not enough stock in Storage Depot! Available: {avail_storage} units."
                )
            if old_qty > 0:
                cursor.execute(
                    """
                    INSERT INTO storage_inventory (item_id, quantity, wholesale_price)
                    SELECT %s, %s, COALESCE(wholesale_price, ROUND(price * 0.6, 2))
                    FROM products WHERE item_id = %s
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """,
                    (old_item_id, old_qty, old_item_id),
                )
            cursor.execute(
                "UPDATE storage_inventory SET quantity = quantity - %s WHERE item_id = %s",
                (quantity, item_id),
            )

        cursor.execute(
            """
            UPDATE shelf_inventory
            SET item_id = %s, item_name = %s, quantity = %s, price = %s
            WHERE shelf_id = %s AND item_id = %s
            """,
            (item_id, item_name, quantity, price, shelf_id, old_item_id),
        )
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not update shelf {shelf_id}. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


#_____________________________EMPLOYEES CRUD_____________________________
def load_employees(map_path):
    """Return all saved employees from MySQL ordered by employee_id."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT employee_id, name, role, salary, hire_date
            FROM employees
            ORDER BY employee_id ASC
            """
        )
        rows = cursor.fetchall()
        employees = []
        for row in rows:
            emp_id = int(row[0])
            name = str(row[1])
            role = str(row[2])
            salary = float(row[3])
            hire_date = str(row[4])
            employees.append((emp_id, name, role, salary, hire_date))
        return employees
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not load employee records. ({error})") from error
    finally:
        cursor.close()
        connection.close()


def add_employee(map_path, employee_id, name, role, salary):
    """Hire / add a new employee record to MySQL."""
    if not name.strip():
        raise DatabaseSetupError("Employee name cannot be empty.")
    if salary < 0:
        raise DatabaseSetupError("Salary cannot be negative.")

    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO employees (employee_id, name, role, salary)
            VALUES (%s, %s, %s, %s)
            """,
            (employee_id, name.strip(), role.strip(), salary),
        )
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        if getattr(error, "errno", None) == 1062:
            raise DatabaseSetupError(f"Employee ID {employee_id} already exists.") from error
        raise DatabaseSetupError(f"Could not add employee. ({error})") from error
    finally:
        cursor.close()
        connection.close()


def update_employee(map_path, old_id, new_id, name, role, salary):
    """Update an existing employee record."""
    if not name.strip():
        raise DatabaseSetupError("Employee name cannot be empty.")
    if salary < 0:
        raise DatabaseSetupError("Salary cannot be negative.")

    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE employees
            SET employee_id = %s, name = %s, role = %s, salary = %s
            WHERE employee_id = %s
            """,
            (new_id, name.strip(), role.strip(), salary, old_id),
        )
        if cursor.rowcount == 0:
            raise DatabaseSetupError("That employee record no longer exists.")
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        if getattr(error, "errno", None) == 1062:
            raise DatabaseSetupError(f"Employee ID {new_id} already exists.") from error
        raise DatabaseSetupError(f"Could not update employee. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def delete_employee(map_path, employee_id):
    """Fire / remove an employee record from MySQL."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM employees WHERE employee_id = %s",
            (employee_id,),
        )
        if cursor.rowcount != 1:
            raise DatabaseSetupError("That employee record no longer exists.")
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not remove employee {employee_id}. ({error})") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


#_____________________________STORAGE DEPOT & SALES_____________________________

def load_storage_inventory(map_path):
    """Return all products in backroom storage with stock counts and shelf distribution."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT 
                p.item_id,
                p.item_name,
                p.category,
                p.price,
                COALESCE(s.wholesale_price, p.wholesale_price, ROUND(p.price * 0.6, 2)) AS wholesale_price,
                COALESCE(s.quantity, 0) AS storage_quantity,
                COALESCE(SUM(CASE
                    WHEN sh.is_active = TRUE
                     AND (sh.category IS NULL OR sh.category = 'General' OR sh.category = COALESCE(p.category, 'General'))
                    THEN si.quantity ELSE 0 END), 0) AS total_shelf_quantity
            FROM products p
            LEFT JOIN storage_inventory s ON p.item_id = s.item_id
            LEFT JOIN shelf_inventory si ON p.item_id = si.item_id
            LEFT JOIN shelves sh ON si.shelf_id = sh.shelf_id
            GROUP BY p.item_id, p.item_name, p.category, p.price, wholesale_price, storage_quantity
            ORDER BY p.category, p.item_id
            """
        )
        return tuple(
            (
                row["item_id"],
                row["item_name"],
                row.get("category") or "General",
                float(row["price"]),
                float(row["wholesale_price"]),
                int(row["storage_quantity"]),
                int(row["total_shelf_quantity"]),
            )
            for row in cursor.fetchall()
        )
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not load storage inventory. ({error})") from error
    finally:
        cursor.close()
        connection.close()


def get_product_shelf_distribution(map_path, item_id):
    """Return a list of all active shelves currently holding this product."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT 
                sh.shelf_id,
                sh.map_x,
                sh.map_y,
                sh.category AS shelf_category,
                si.quantity,
                si.price
            FROM shelf_inventory si
            JOIN shelves sh ON si.shelf_id = sh.shelf_id
            JOIN products p ON si.item_id = p.item_id
            WHERE si.item_id = %s
              AND sh.is_active = TRUE
              AND si.quantity > 0
              AND (sh.category IS NULL OR sh.category = 'General' OR sh.category = COALESCE(p.category, 'General'))
            ORDER BY sh.shelf_id
            """,
            (item_id,),
        )
        return tuple(
            (
                row["shelf_id"],
                row["map_x"],
                row["map_y"],
                row["shelf_category"] or "General",
                row["quantity"],
                float(row["price"]),
            )
            for row in cursor.fetchall()
        )
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not load product shelf distribution. ({error})") from error
    finally:
        cursor.close()
        connection.close()


def order_storage_stock(map_path, item_id, quantity):
    """Order stock from supplier: deducts money from finances and adds stock to storage."""
    if quantity <= 0:
        raise DatabaseSetupError("Order quantity must be at least 1.")
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT item_name, price, wholesale_price FROM products WHERE item_id = %s", (item_id,))
        prod = cursor.fetchone()
        if not prod:
            raise DatabaseSetupError(f"Product {item_id} not found in catalogue.")

        wholesale_price = float(prod.get("wholesale_price") or round(float(prod["price"]) * 0.6, 2))
        total_cost = wholesale_price * quantity

        cursor.execute("SELECT current_balance FROM store_finance WHERE finance_id = 1 FOR UPDATE")
        finance_row = cursor.fetchone()
        if not finance_row:
            raise DatabaseSetupError("Store finances record missing.")
        current_balance = float(finance_row["current_balance"])
        if current_balance < total_cost:
            raise DatabaseSetupError(
                f"Insufficient funds! Need Rs. {total_cost:,.2f}, balance is Rs. {current_balance:,.2f}."
            )

        new_balance = current_balance - total_cost
        cursor.execute("UPDATE store_finance SET current_balance = %s WHERE finance_id = 1", (new_balance,))
        cursor.execute(
            """
            INSERT INTO finance_history (finance_id, change_type, amount, previous_balance, new_balance)
            VALUES (1, 'Loss', %s, %s, %s)
            """,
            (total_cost, current_balance, new_balance),
        )
        cursor.execute(
            """
            INSERT INTO storage_inventory (item_id, quantity, wholesale_price)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                quantity = quantity + VALUES(quantity),
                wholesale_price = VALUES(wholesale_price)
            """,
            (item_id, quantity, wholesale_price),
        )
        connection.commit()
        return new_balance, total_cost
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Failed to process stock order: {error}") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def update_shelf_category(map_path, shelf_id, category):
    """Assign a department category to a shelf (or set to None/General)."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor()
    try:
        cat_val = category.strip() if category and category != "General" else None
        cursor.execute("UPDATE shelves SET category = %s WHERE shelf_id = %s", (cat_val, shelf_id))
        connection.commit()
        return True
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not update shelf category: {error}") from error
    finally:
        cursor.close()
        connection.close()


def sell_shelf_stock(map_path, shelf_id, item_id, quantity):
    """Sell items from a shelf: reduces shelf quantity and adds revenue to store finances."""
    if quantity <= 0:
        raise DatabaseSetupError("Quantity to sell must be at least 1.")
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT item_name, quantity, price FROM shelf_inventory WHERE shelf_id = %s AND item_id = %s FOR UPDATE",
            (shelf_id, item_id),
        )
        shelf_item = cursor.fetchone()
        if not shelf_item:
            raise DatabaseSetupError("Item is not present on this shelf.")
        current_qty = shelf_item["quantity"]
        if current_qty < quantity:
            raise DatabaseSetupError(f"Not enough stock on shelf! Requested {quantity}, available: {current_qty}.")

        unit_price = float(shelf_item["price"])
        revenue = unit_price * quantity

        cursor.execute("SELECT current_balance FROM store_finance WHERE finance_id = 1 FOR UPDATE")
        finance_row = cursor.fetchone()
        if not finance_row:
            raise DatabaseSetupError("Store finances record missing.")
        current_balance = float(finance_row["current_balance"])
        new_balance = current_balance + revenue

        new_qty = current_qty - quantity
        if new_qty <= 0:
            cursor.execute("DELETE FROM shelf_inventory WHERE shelf_id = %s AND item_id = %s", (shelf_id, item_id))
        else:
            cursor.execute(
                "UPDATE shelf_inventory SET quantity = %s WHERE shelf_id = %s AND item_id = %s",
                (new_qty, shelf_id, item_id),
            )

        cursor.execute("UPDATE store_finance SET current_balance = %s WHERE finance_id = 1", (new_balance,))
        cursor.execute(
            """
            INSERT INTO finance_history (finance_id, change_type, amount, previous_balance, new_balance)
            VALUES (1, 'Profit', %s, %s, %s)
            """,
            (revenue, current_balance, new_balance),
        )
        connection.commit()
        return new_balance, revenue, new_qty
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Failed to process sale: {error}") from error
    except DatabaseSetupError:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def load_shelf_categories(map_path):
    """Return a mapping of shelf_id -> category string."""
    database_name = database_name_for_map(map_path)
    connection = _connect(database_name)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT shelf_id, category FROM shelves WHERE is_active = TRUE")
        return {row["shelf_id"]: (row["category"] or "General") for row in cursor.fetchall()}
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not load shelf categories. ({error})") from error
    finally:
        cursor.close()
        connection.close()
