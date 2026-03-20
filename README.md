# Nexus — Autonomous Competitive Intelligence Platform

Nexus is a microservices platform that continuously monitors competitors, scrapes intelligence from the web, and synthesizes insights using a multi-agent LangGraph pipeline.

## Architecture

```
                        ┌─────────────┐
                        │    nginx     │  :80
                        └──────┬──────┘
               ┌───────────────┼───────────────┐
               │               │               │
        /api/auth/          /api/           /ws/
               │               │               │
    ┌──────────▼──┐   ┌────────▼──────┐        │
    │ auth-service│   │   core-api    │◄────────┘
    │  (Django 8001)  │ (Django+Channels 8000)
    └──────────┬──┘   └────────┬──────┘
               │               │
               └───────┬───────┘
                       │ MySQL + Redis
                       │
          ┌────────────┼─────────────┐
          │            │             │
  ┌───────▼──────┐  ┌──▼──────────────────┐
  │scraper-service│  │   agent-service      │
  │  Scrapy+     │  │  LangGraph pipeline  │
  │  Selenium    │  │  (4-node multi-agent)│
  │  +Celery     │  │  +Celery             │
  └──────────────┘  └──────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Gateway | Nginx |
| Auth Service | Django 4.2, DRF, SimpleJWT, MySQL |
| Core API | Django 4.2, DRF, Django Channels, MySQL, Redis |
| Scraping | Scrapy, Selenium (headless Chrome), Celery |
| AI Pipeline | LangGraph, LangChain, OpenAI GPT-4 |
| Message Queue | Redis + Celery |
| Database | MySQL 8.0 |
| Cache / Pub-Sub | Redis 7 |
| Containerization | Docker + docker-compose |

## Quickstart

```bash
# 1. Clone
git clone https://github.com/yuriao/nexus.git
cd nexus

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start all services
docker-compose up --build

# 4. Run migrations
docker-compose exec auth-service python manage.py migrate
docker-compose exec core-api python manage.py migrate

# 5. Create superuser
docker-compose exec auth-service python manage.py createsuperuser
```

Services will be available at:
- API Gateway: http://localhost:80
- Auth API: http://localhost:80/api/auth/
- Core API: http://localhost:80/api/
- WebSocket: ws://localhost:80/ws/reports/{report_id}/

## Services

### auth-service (port 8001)
JWT authentication service. Handles user registration, login, token refresh, and API key management.

### core-api (port 8000)
Main REST API + WebSocket server. Manages companies, watchlists, alerts, and research reports. Django Channels provides real-time report progress via WebSocket.

### scraper-service
Celery workers that orchestrate Scrapy spiders and Selenium scrapers. Rate-limited via Redis sliding window. Saves raw data to MySQL.

### agent-service
LangGraph multi-agent pipeline:
1. **Researcher** — gathers intelligence using web search and collected data
2. **Analyst** — identifies opportunities, risks, and trends
3. **Writer** — synthesizes a structured report
4. **Critic** — fact-checks and scores confidence; loops back if quality is low

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register/ | Register new user |
| POST | /api/auth/login/ | Get JWT token pair |
| POST | /api/auth/refresh/ | Refresh access token |
| GET/POST | /api/auth/api-keys/ | List/create API keys |
| GET/POST | /api/companies/ | List/create companies |
| GET/PUT/DELETE | /api/companies/{id}/ | Company detail |
| GET/POST | /api/companies/{id}/watchlist/ | Manage watchlist |
| POST | /api/reports/trigger/ | Trigger agent analysis |
| GET | /api/reports/{id}/status/ | Report status |
| GET | /api/reports/{id}/ | Full report |
| GET | /api/reports/ | List reports (paginated) |
| WS | /ws/reports/{id}/ | Real-time report progress |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DB_HOST` | MySQL host |
| `DB_PORT` | MySQL port (default 3306) |
| `DB_NAME` | Database name |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `REDIS_URL` | Redis connection URL |
| `DJANGO_SECRET_KEY` | Django secret key |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | JWT access token TTL |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | JWT refresh token TTL |
| `BRAVE_API_KEY` | Brave Search API key |
| `OPENAI_API_KEY` | OpenAI API key (for LangGraph agents) |
| `CELERY_BROKER_URL` | Celery broker (Redis URL) |
| `SELENIUM_HEADLESS` | Run Chrome headless (true/false) |

## License

MIT
