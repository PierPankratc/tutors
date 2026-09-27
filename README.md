# 🎓 Tutors API

[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.1-green)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-red)](https://www.django-rest-framework.org)
[![JWT](https://img.shields.io/badge/JWT-Auth-orange)](https://django-rest-framework-simplejwt.readthedocs.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

> REST API для поиска репетиторов с отзывами, рейтингом, фильтрацией и кэшированием

---

## 📖 О проекте

**Tutors API** — это backend для платформы поиска репетиторов. Пользователи могут:
- 🔍 Искать репетиторов по предметам, цене, рейтингу
- ⭐ Оставлять отзывы и оценки
- 📅 Бронировать уроки
- 👤 Управлять профилем

**Ключевые особенности:**
- ✅ JWT-авторизация (в процессе разработки)
- ✅ Автоматический пересчёт рейтинга через сигналы
- ✅ Фильтрация, поиск, сортировка (django-filter)
- ✅ Кэширование через Redis
- ✅ Swagger/OpenAPI документация
- ✅ Docker + docker-compose

---

## 🛠 Стек технологий

| Категория | Технологии |
|-----------|-----------|
| **Backend** | Python 3.14, Django 6.1, DRF |
| **Auth** | JWT (SimpleJWT) |
| **DB** | PostgreSQL / SQLite |
| **Cache** | Redis |
| **Filtering** | django-filter |
| **Docs** | drf-spectacular (Swagger) |
| **Tests** | pytest, pytest-django, coverage |
| **Deploy** | Docker, docker-compose, Nginx |
| **CI/CD** | GitHub Actions |

---

## 🚀 Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/PierPankratc/tutors.git
cd tutors