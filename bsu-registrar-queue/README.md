# BSU Registrar Queue System

Queue management system for Bulacan State University - Meneses Campus Registrar.

## Tech Stack
- **Backend**: Python FastAPI, Celery, Redis, PostgreSQL
- **Frontend**: Vue 3, Tailwind CSS, Pinia
- **Deployment**: Docker Compose

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for frontend development)

### Development Setup

1. Clone and navigate to the project:
   ```bash
   cd bsu-registrar-queue
   ```

2. Start all services:
   ```bash
   docker-compose up -d
   ```

3. Frontend dev server (for hot-reloading):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Apply database migrations (after building models):
   ```bash
   cd backend
   alembic upgrade head
   ```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints
│   │   ├── core/         # Database, config, security
│   │   ├── models/       # Pydantic/SQLAlchemy models
│   │   └── services/     # Business logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # Vue components
│   │   ├── views/        # Page views
│   │   ├── stores/       # Pinia state management
│   │   └── router/       # Vue Router
│   └── package.json
└── docker-compose.yml
```

## API Endpoints

- `POST /api/auth/login` - Staff authentication
- `GET /api/queues` - List available services
- `POST /api/tickets` - Take a queue ticket
- `GET /api/tickets/my-ticket` - Get current ticket
- `POST /api/tickets/{id}/complete` - Mark ticket completed (staff)

## Features

- Multi-service queues (Enrollment, Documents, Clearance, Scholarship)
- Priority handling (graduating students, scholars, varsity)
- Real-time queue position updates
- Time slot management to prevent overcrowding
- Admin dashboard for staff