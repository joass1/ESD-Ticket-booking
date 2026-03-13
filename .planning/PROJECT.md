# Event Ticketing Platform

## What This Is

A microservices-based event ticketing platform for IS213 (Enterprise Solution Development) at SMU Singapore. Users browse events, select seats, book tickets with real-time concurrency protection, receive QR-code e-tickets via WebSocket, and get notified of event changes. Event organizers manage listings through an OutSystems admin dashboard. The platform demonstrates orchestration-based sagas, choreography-based event-driven patterns, and topic exchange fan-out across 3 user scenarios.

## Core Value

Users can reliably book seats under high concurrency with real-time e-ticket delivery, while the platform handles failures gracefully through compensating transactions and event-driven choreography.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Docker Compose infrastructure (MySQL, RabbitMQ, Redis, Kong)
- [ ] Shared AMQP library with multi-threading support
- [ ] Event Service — CRUD + cancellation trigger (Scenario 3)
- [ ] Booking Service — booking records + status management
- [ ] Seat Service — seat inventory with Redis distributed locking
- [ ] Payment Service — Stripe integration for charges and refunds
- [ ] Notification Service — email (Gmail SMTP) and SMS (Twilio) triggered by AMQP events
- [ ] Ticket Service — QR code generation + WebSocket delivery via Flask-SocketIO
- [ ] Waitlist Service — choreography-based waitlist with cascading promotions
- [ ] Charging Service — service fee calculation (10% retention on refunds)
- [ ] Booking Orchestrator — saga orchestration with payment expiry (APScheduler)
- [ ] Scenario 1: High-demand seat booking with orchestration-based saga + payment timeout
- [ ] Scenario 2: Waitlist management with choreography via AMQP (no direct HTTP between Seat/Waitlist)
- [ ] Scenario 3: Event cancellation with batch refund + service fee retention (topic exchange fan-out)
- [ ] React frontend — event browsing, seat selection, booking flow, WebSocket e-ticket display
- [ ] Kong API Gateway — DB-less mode, declarative YAML, rate limiting
- [ ] OutSystems admin dashboard integration — event management exposed via REST

### Out of Scope

- Mobile app — web-first for this project
- Real-time chat — not core to ticketing
- Video/media uploads — unnecessary complexity
- OAuth/social login — email/password sufficient for university demo
- Payment processing with real money — Stripe test mode only

## Context

- **Course**: IS213 Enterprise Solution Development, SMU Singapore, Year 2 Semester 2
- **Team size**: 5 members, but building full platform end-to-end
- **Professor feedback** (critical constraints):
  1. Payment expiry logic lives INSIDE the Booking Orchestrator (APScheduler, 30s interval)
  2. Ticket Service delivers e-tickets via Flask-SocketIO WebSocket (UI joins room by booking_id)
  3. Seat Service and Waitlist Service communicate ONLY through RabbitMQ — NO direct HTTP
  4. Every service needing both HTTP and AMQP must use multi-threading (Flask main thread + AMQP daemon thread)
  5. Charging Service retains 10% platform fee — does NOT refund 100%
- **BTL (Beyond The Lecture) features**: Kong API Gateway, Redis distributed locking, Flask-SocketIO WebSocket
- **External APIs**: Stripe (test keys), Twilio (test), Gmail SMTP (app password)

## Constraints

- **Tech stack**: Python 3.11 / Flask, MySQL 8.0, RabbitMQ 3, Redis 7, Kong 3.6, Docker — mandated by course
- **Frontend**: React SPA (team decision)
- **Architecture**: One database per microservice — NEVER share databases
- **Communication**: Sync HTTP for immediate responses, Async AMQP for fire-and-forget, WebSocket for real-time push
- **Timeline**: ~2 weeks to working demo
- **Deliverable**: Working demo with all 3 scenarios runnable via Docker Compose
- **OutSystems**: Admin dashboard must integrate with Event Service REST API — manual OutSystems build by team

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Orchestration saga for Scenario 1 | Professor requirement — Booking Orchestrator coordinates Seat + Payment + Booking | — Pending |
| Choreography for Scenario 2 | Professor requirement — Seat/Waitlist decoupled via RabbitMQ only | — Pending |
| Topic exchange fan-out for Scenario 3 | Single event.cancelled triggers 5 parallel service reactions | — Pending |
| React for frontend | Team preference over plain HTML/JS | — Pending |
| Real test keys for Stripe/Twilio/Gmail | Available and ready — no mocking needed | — Pending |
| 10% service fee on refunds | Professor feedback — platform retains revenue on cancellations | — Pending |
| Kong DB-less mode | Declarative YAML config, no database overhead | — Pending |

---
*Last updated: 2026-03-13 after initialization*
