# SkillSwap

A time-bank skill exchange platform where users offer and request skills, bidding with time credits rather than money.

Built with Django 6.0.3, Bootstrap 5.3, and vanilla JavaScript (AJAX).

> University of Glasgow — Internet Technology M — Group W

---

## Features

- User registration, login, and profile management
- Post skill requests and receive bids from other users
- Accept bids and complete exchanges tracked by a double-entry ledger
- Live marketplace search with AJAX filtering
- Messaging between users
- Leave reviews after completed exchanges
- Fully responsive UI with accessibility support (WCAG 2.1)

---

## Tech Stack

| Layer      | Technology          |
|------------|---------------------|
| Backend    | Django 6.0.3        |
| Frontend   | Bootstrap 5.3       |
| JavaScript | Vanilla JS + AJAX   |
| Database   | SQLite (dev)        |
| Images     | Pillow 11.1.0       |

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/pubaaaali/skillswap.git
cd skillswap
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply migrations

```bash
python3 manage.py migrate
```

### 5. (Optional) Load demo data

```bash
python3 populate.py
```

### 6. Run the development server

```bash
python3 manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## Demo Accounts

After running `populate.py`:

| Username | Password   |
|----------|------------|
| alice    | skillswap  |
| bob      | skillswap  |
| carol    | skillswap  |
| dave     | skillswap  |
| admin    | admin123   |

---

## Running Tests

```bash
python3 manage.py test core
```

29 unit tests covering models, views, and AJAX endpoints.
