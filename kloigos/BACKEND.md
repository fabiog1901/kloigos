# 🏛️ Kloigos Backend Architecture

This project follows a **Layered Architecture** with a focus on decoupling business logic from data persistence. It supports multiple database backends (Postgres/SQLite) through a **Repository Pattern** and uses FastAPI's **Lifespan** and **Dependency Injection** systems for resource management.

## 📐 Architecture Overview

The system is divided into three primary layers to ensure maintainability and testability:

1. **API Layer (FastAPI):** Handles HTTP routing, request validation, and response serialization. It communicates exclusively with the Service Layer.
2. **Service Layer (Business Logic):** Contains the core "rules" of the application. It is database-agnostic and relies on Repository abstractions.
3. **Repository Layer (Data Access):** Handles raw database operations. We provide two implementations: `PostgresRepo` (using `psycopg_pool`) and `SQLiteRepo`.

---

## 🛠️ Key Design Patterns

### 1. The Repository Pattern

To allow switching between Postgres and SQLite without changing business logic, we use a Repository abstraction.

* **Benefits:** The service layer doesn't know if it's talking to a `.sqlite3` file or a high-performance Postgres cluster.
* **Implementation:** Both repositories share the same method signatures (Duck Typing / Protocols).

### 2. Global Resource Registry (via `dependencies.py`)

Because this project uses a **Mounted App** structure (`app.mount("/api", api)`), we use a global registry in `dependencies.py` to share the database pool.

* **The Problem:** Sub-apps have isolated `app.state`, making it difficult to share a connection pool.
* **The Solution:** We store the `db_pool` and `repo_factory` as module-level variables. This ensures that every part of the Python process—regardless of which "app" handles the request—accesses the same pool.

### 3. Lazy-Loading Lifespan

Database drivers are only loaded when needed. If the system is configured for SQLite, the `psycopg` and `psycopg_pool` libraries are never imported.

* **Efficiency:** Reduces memory footprint and prevents crashes on systems missing specific drivers.
* **Graceful Shutdown:** The `lifespan` event ensures that the Postgres connection pool is drained and closed cleanly when the server stops.

---

## 🚦 Request Flow

When a request hits an endpoint (e.g., `/api/compute/`):

1. **DI Resolution:** FastAPI calls `Depends(get_service)`.
2. **Service Instantiation:** `get_service` calls `Depends(get_repo)`.
3. **Repo Retrieval:** `get_repo` looks at the global `repo_factory` (initialized at startup) and returns the active repository instance.
4. **Logic Execution:** The Service performs business checks and calls `repo.get_data()`.
5. **Response:** The result flows back up to the API layer to be returned as JSON.

---

## ⚙️ Configuration & Deployment

### Database Selection

The engine is toggled via environment variables:

* `DB_ENGINE`: `postgres` or `sqlite`
* `DB_URL`: The connection string (only required for Postgres)

### Production Stack

The application is designed to run in a production environment using:

* **Gunicorn** with **Uvicorn workers** (Process management)
* **Nginx** (Reverse proxy and SSL termination)
* **Systemd** (Ensuring the service stays alive)

---

## 🧪 Testing

The architecture is designed for easy testing via **Dependency Overrides**. To test a service without a database, you can override the `repo_factory` in your test suite:

```python
from app.core import dependencies

def test_my_service():
    # Inject a mock repo instead of a real DB
    dependencies.repo_factory = lambda: MockRepository()
    # ... run tests ...

```
