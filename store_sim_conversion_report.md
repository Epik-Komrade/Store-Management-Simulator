# Store Management Simulator — Current Project Report

## Project purpose

This project is a top-down store-management simulator made with Python, Pygame, and MySQL. The player is a store manager who moves around a tile-based store, inspects shelves, manages item records, and keeps persistent data in MySQL.

The project has two stages:

1. A complete Class 12 project with inventory, an editable catalogue, an employee register, and a finance tracker.
2. A future management game with real stock movement, customers, employee behaviour, and a day cycle.

## Current architecture

| Part | Current implementation |
|---|---|
| Game engine | Python with Pygame |
| Database | MySQL through `mysql.connector` |
| Map | `store_level1.txt`, a 25 × 15 text map |
| Launcher | `store_launcher.py` initializes/synchronizes MySQL, then starts the simulation |
| Simulator | `store_sim.py` handles movement, interactions, rendering, and UI |
| Database layer | `database_setup.py` creates/synchronizes shelves, products, and inventory operations |
| Starter catalogue | `store_seed_data.py` contains 50 first-run products; MySQL stores the live catalogue |

The database name is derived from the map filename. For example, `store_level1.txt` uses the database `store_level1`.

## Completed features

### Store map and interaction

- `#` is a solid wall.
- `P` is the one player spawn point.
- `S` is a collidable, interactable shelf.
- `C` is the one required product-catalogue terminal.
- The player has WASD movement, mouse aiming, and collision with walls/shelves.
- Interactions require aiming at a nearby tile and pressing `E`.
- The map is validated before launch: it must be 25 × 15, contain one `P`, and contain one `C`.

### Persistent shelf inventory

| Table | Purpose |
|---|---|
| `map_metadata` | Saves map name, hash, and dimensions. |
| `shelves` | Saves each shelf's grid coordinate and active status. |
| `shelf_inventory` | Saves the item ID, name, quantity, and price for each shelf. |
| `products` | Saves every catalogue product, its default price, and its starter quantity range. |

- New shelves receive 3–5 random starter products from the 50-product seed list.
- Existing shelf data is not overwritten on restart.
- The simulation reads shelf inventory from MySQL.
- Removed shelf positions are archived instead of deleted.

### Product catalogue and shelf UI

- The starter list is copied into `products` only when a new database has an empty catalogue. Later game edits are preserved.
- The catalogue terminal reads directly from MySQL and displays all saved products.
- It shows item ID, product name, price, and starter quantity range.
- Catalogue rows can be selected, added with `+`, edited, and removed with `X`.
- Catalogue add/edit forms accept an item ID, name, price, minimum quantity, and maximum quantity. Quantity ranges also have `+` / `−` controls.
- A stocked product cannot be deleted, and its Item ID cannot change until it has been removed from all shelves. This preserves shelf history.
- Catalogue and shelf tables support scrolling and visible scrollbars.
- Shelf rows can be selected one at a time and are highlighted when selected.
- Shelf items can be added, removed with `X`, or edited.
- Add and edit screens use the MySQL catalogue product picker, which avoids duplicate products on one shelf.
- Quantity and price support direct text input as well as `+` / `−` buttons.
- Shelf changes are saved to MySQL immediately.

## Remaining school-project scope

The following are the final planned features for the school version. Employee and customer entities are not required yet.

### 1. Employee register

Add a new interactable employee-register tile and a permanent `employees` table. It will be a register only; employees will not move in the store for the school project.

| Role | Future responsibility |
|---|---|
| Cashier | Handles checkout. |
| Stocker | Restocks low shelves. |
| Store Assistant | Helps customers. |

Each employee will have an employee ID, name, role, and salary.

### 2. Cash register and finance history

Add a new cash-register tile with a permanent finance tracker.

- The store begins with **Rs. 20,000**.
- The player manually enters a new balance.
- The game compares it with the previous balance and saves the difference in a history table.
- Example: Rs. 20,000 → Rs. 19,000 records `Loss: -Rs. 1,000`.
- Example: Rs. 19,000 → Rs. 21,000 records `Profit: +Rs. 2,000`.
- The register displays the current balance and permanent history.

Suggested tables:

| Table | Purpose |
|---|---|
| `store_finance` | Saves current and starting balances. |
| `finance_history` | Saves each balance change, its difference, description, and timestamp. |

## School-project build order

1. Add the employee-register tile, employee table, and roster UI.
2. Add the cash-register tile, manual balance input, and finance history.
3. Test all map validation and database CRUD operations.
4. Prepare screenshots, schema notes, and explanation material for submission.

## Future development after the school project

- Backroom/storage inventory with limited quantities.
- Shelf restocking that transfers stock from storage instead of creating items freely.
- Supplier purchases and deliveries.
- Low-stock warnings and shelf capacity.
- Customers that select shelf products, pay money, and leave.
- Employee entities that act as cashiers, stockers, and store assistants.
- Staff salaries, customer satisfaction, lost sales, and a daily store cycle.
- End-of-day reports, store upgrades, random events, and sales charts.
- A map editor for shelves, registers, storage, and staff terminals.
- A simple plaintext launcher password for the local/school version; a hashed password system can replace it later.

## Technical rules to preserve

- MySQL is the permanent source of truth, but the game must not query it every frame.
- Read/write only for discrete actions: opening a screen, saving an edit, recording a balance change, or a future sale/restock.
- Validate map tiles before launch.
- Use one database transaction when a future action changes multiple values such as stock and money.
- Preserve the current player movement, aiming, collision, and interaction behaviour while management systems are added.
