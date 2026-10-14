# Secure Enterprise Knowledge Assistant

A secure enterprise knowledge assistant that uses Retrieval-Augmented
Generation (RAG) to answer questions from authorized company documents.

## Planned capabilities

- Document ingestion and semantic retrieval
- Answers grounded in retrieved document passages
- Source citations for generated answers
- Authentication and backend-enforced role-based access control
- React frontend and FastAPI backend
- PostgreSQL persistence
- Automated tests and deployment configuration

## Planned architecture

- `backend/` — FastAPI API, authentication, authorization, and RAG pipeline
- `frontend/` — React user interface
- `docs/` — Architecture and development documentation

## Development status

Milestone 1: Initial repository setup.

Application features are not implemented yet.

## Getting started

Setup instructions will be added after the backend and frontend dependencies
and configuration have been established and verified.

## Security

- Keep credentials in a local `.env` file or deployment secret manager.
- Never commit API keys, passwords, tokens, or production database credentials.
- Enforce document access permissions on the server before retrieval.
