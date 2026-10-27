"""MySQL database creation and map-to-shelf synchronization."""

import hashlib
import os
import random
import re

from db_config import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER
from store_seed_data import STANDARD_ITEMS

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

#_____________________________SETTINGS_____________________________
MAP_WIDTH = 25
MAP_HEIGHT = 15
MAP_TILES = {"#", ".", "P", "S", "C", "R", "E"}


class DatabaseSetupError(RuntimeError):
    """error raised when the store database is unavailable."""

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
    """chec the store map and return its shelf coordinates in reading order."""
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

    return shelf_positions, "\n".join(lines)

#_____________________________CONNECT_____________________________
def _connect(database=None):
    if mysql is None:
        raise DatabaseSetupError("mysql-connector-python is not installed. Install it before starting the launcher.")
    options = {"host": DB_HOST, "port": DB_PORT, "user": DB_USER, "password": DB_PASSWORD,}
    if database:
        options["database"] = database

    try:
        return mysql.connector.connect(**options)
    except MySQLError as error:
        raise DatabaseSetupError(f"Could not connect to MySQL at {DB_HOST}:{DB_PORT}. Check db_config.py and ensure MySQL Server is running. ({error})") from error


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
    cursor = connection.cursor()
    try:
        cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
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
            price DECIMAL(10, 2) NOT NULL,
            minimum_quantity INT UNSIGNED NOT NULL,
            maximum_quantity INT UNSIGNED NOT NULL,
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
    )
    cursor = connection.cursor()
    try:
        for statement in statements:
            cursor.execute(statement)
    finally:
        cursor.close()


def _seed_catalogue_if_empty(connection):
    """Copy the starter list into MySQL once, without overwriting saved edits."""
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        if product_count == 0:
            cursor.executemany(
                """
                INSERT INTO products
                    (item_id, item_name, price, minimum_quantity, maximum_quantity)
                VALUES (%s, %s, %s, %s, %s)
                """,
                STANDARD_ITEMS,
            )
            return len(STANDARD_ITEMS)
        return 0
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


DEFAULT_EMPLOYEES = [
    (101, "Rahul Sharma", "Cashier", 18000.00),
    (102, "Priya Patel", "Stocker", 16000.00),
    (103, "Amit Kumar", "Store Assistant", 15000.00),
]


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
    """Create a small random starter selection from the saved product catalogue."""
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
    return [
        (
            shelf_id,
            product["item_id"],
            product["item_name"],
            random.randint(product["minimum_quantity"], product["maximum_quantity"]),
            product["price"],
        )
        for product in selected_products
    ]


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
    """create/synch the map database and return a short status report."""
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
        _seed_catalogue_if_empty(database_connection)
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
            SELECT item_id, item_name, price, minimum_quantity, maximum_quantity
            FROM products
            ORDER BY item_id
            """
        )
        return tuple(
            (
                row["item_id"],
                row["item_name"],
                float(row["price"]),
                row["minimum_quantity"],
                row["maximum_quantity"],
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
def add_catalogue_product(map_path, item_id, item_name, price, minimum_quantity, maximum_quantity):
    """Add a product that can later be placed on shelves."""
    _check_product_values(item_id, item_name, price, minimum_quantity, maximum_quantity)
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO products
                (item_id, item_name, price, minimum_quantity, maximum_quantity)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (item_id, item_name.strip(), price, minimum_quantity, maximum_quantity),
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
):
    """Edit a catalogue product without rewriting existing shelf listings."""
    _check_product_values(item_id, item_name, price, minimum_quantity, maximum_quantity)
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
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
            """
            UPDATE products
            SET item_id = %s, item_name = %s, price = %s,
                minimum_quantity = %s, maximum_quantity = %s
            WHERE item_id = %s
            """,
            (
                item_id,
                item_name.strip(),
                price,
                minimum_quantity,
                maximum_quantity,
                old_item_id,
            ),
        )
        if cursor.rowcount != 1:
            raise DatabaseSetupError("That catalogue product no longer exists.")
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
    """Save a new inventory record for one shelf."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
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
    finally:
        cursor.close()
        connection.close()


def delete_shelf_item(map_path, shelf_id, item_id):
    """Remove one inventory record from one shelf."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM shelf_inventory WHERE shelf_id = %s AND item_id = %s",
            (shelf_id, item_id),
        )
        if cursor.rowcount != 1:
            raise DatabaseSetupError("That shelf item no longer exists in MySQL.")
        connection.commit()
    except MySQLError as error:
        connection.rollback()
        raise DatabaseSetupError(f"Could not remove the item from shelf {shelf_id}. ({error})") from error
    finally:
        cursor.close()
        connection.close()


def update_shelf_item(map_path, shelf_id, old_item_id, item_id, item_name, quantity, price):
    """Save an edited shelf inventory record, including its selected product."""
    connection = _connect(database_name_for_map(map_path))
    cursor = connection.cursor()
    try:
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
    finally:
        cursor.close()
        connection.close()
