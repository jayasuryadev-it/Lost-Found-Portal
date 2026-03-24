# 🚀 Lost & Found Portal (AI-Powered)

## 📌 Overview

Lost & Found Portal is a full-stack web application designed to help users report, track, and recover lost items efficiently. The system uses an AI-based matching engine to automatically identify potential matches between lost and found items and notify users.

This project focuses on building a scalable backend system with intelligent matching, secure authentication, and structured data handling.

---

## ⚙️ Tech Stack

**Backend**

* FastAPI (Python)
* PostgreSQL (Neon Cloud)
* SQLAlchemy (ORM)
* JWT Authentication (python-jose)
* bcrypt (Password hashing)

**Frontend**

* HTML, CSS, JavaScript (Vanilla)
* Tailwind CSS

**AI & Features**

* TF-IDF (Text similarity using scikit-learn)
* OpenCV (Image similarity)
* EmailJS (Notification system)

---

## 🚀 Key Features

* 🔐 User Authentication (JWT-based login & registration)
* 📦 Report Lost & Found Items
* 🔍 Search & Filter Items
* 🤖 AI-Based Auto Matching System
* 📧 Email Notifications for Matches
* 📊 Admin Dashboard (User & Item Management)
* 📱 Responsive UI

---

## 🧠 AI Matching System

The system automatically matches **FOUND items with LOST items** using:

* **Text Similarity (60%)**

  * TF-IDF vectorization
  * Cosine similarity

* **Image Similarity (40%)**

  * OpenCV histogram comparison

**Final Score Calculation:**

```
score = (0.6 × text_similarity) + (0.4 × image_similarity)
```

Items above a threshold are considered matches and trigger email notifications.

---

## 🗄️ Database Design

* **Users Table** → stores user details and authentication
* **Items Table** → stores lost/found item data

Relationship:

```
One User → Many Items
```

Supports:

* Item status tracking (OPEN, CLAIMED, CLOSED)
* Category-based filtering (LOST / FOUND)

---

## 🔐 Authentication Flow

* User login returns JWT token
* Token stored on frontend
* Protected routes use Bearer authentication
* Role-based access (User / Admin)

---

## 📡 API Highlights

* `/api/register` → User registration
* `/api/login` → Authentication
* `/api/items` → CRUD operations
* `/api/my-items` → User-specific items
* `/api/admin/*` → Admin controls

---

## 🖥️ System Architecture

Frontend (HTML/CSS/JS) → REST API → FastAPI Backend → PostgreSQL Database

Includes:

* Modular backend (Auth, Items, Admin, Matcher)
* ORM-based database handling
* External services (EmailJS, Neon DB)

---

## 📸 Screenshots

<img width="1791" height="896" alt="image" src="https://github.com/user-attachments/assets/ea98343a-c64d-4fab-ad31-7bf9f46fb92d" />

<img width="1804" height="895" alt="image" src="https://github.com/user-attachments/assets/37396a64-ad8b-44c6-a0d2-b34182746fc1" />

<img width="1765" height="893" alt="image" src="https://github.com/user-attachments/assets/401959ab-6a72-4232-a6b5-5e90f16aaca5" />

---

## ⚙️ Setup Instructions

### Backend

```bash
cd last_found_backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd last_found_frontend
python -m http.server 5500
```

---

## 📈 Future Improvements

* Real-time notifications
* Advanced ML-based matching
* Mobile app version
* Geo-location tracking

---

## 👤 Author

Jayasurya
GitHub: https://github.com/jayasuryadev-it
LinkedIn: https://www.linkedin.com/in/jayasuryadev-it/
