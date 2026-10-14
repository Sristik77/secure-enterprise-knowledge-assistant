# Secure Enterprise Knowledge Assistant — Architecture

## 1. Objective

Build a secure enterprise knowledge assistant that answers questions
using authorized company documents, with source citations and
server-enforced access control.

## 2. Technology Stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Database migrations: Alembic
- Semantic retrieval: pgvector
- Authentication: JWT-based access tokens and secure password hashing
- Testing: pytest, HTTPX, and Vitest
- Deployment: Docker and Docker Compose

Dependency versions will be pinned and verified during implementation.

## 3. Main Components

### Frontend

- Login and session handling
- Chat interface
- Source citation display
- Document management interface for authorized users
- Administrative user and permission management

### Backend

- Authentication and authorization
- User, role, and document management APIs
- Document ingestion and text extraction
- Chunking and embedding generation
- Permission-filtered semantic retrieval
- LLM integration and answer generation
- Health checks and structured error handling

### Database

Initial entities:

- users
- roles
- user_roles
- documents
- document_permissions
- document_chunks
- conversations
- messages

Relationships, constraints, and indexes will be specified before
the initial database migration.

## 4. Question-Answering Flow

1. Authenticate the user.
2. Validate the request.
3. Determine the user's effective document permissions.
4. Retrieve only chunks belonging to authorized documents.
5. Construct the LLM context from the permitted retrieved chunks.
6. Generate an answer grounded in the supplied context.
7. Return the answer with source references.
8. Persist permitted conversation metadata and results as configured.

Authorization must be enforced by the backend, not by the frontend.
Unauthorized document content must never enter the LLM context.

## 5. Document Ingestion Flow

1. Validate the uploaded file type and size.
2. Check the uploader's permission.
3. Extract and normalize text.
4. Split the text into bounded chunks.
5. Generate embeddings through the configured provider.
6. Store document metadata, permissions, chunks, and embeddings.
7. Make the document available for authorized retrieval only.

Ingestion failures must not expose partial or unauthorized document data.

## 6. Security Requirements

- Hash passwords using a modern password-hashing algorithm.
- Validate tokens and enforce authorization on protected endpoints.
- Apply document-level access checks during retrieval.
- Store secrets in environment variables or a secret manager.
- Never commit real credentials.
- Validate uploads and enforce size limits.
- Use parameterized database access through the ORM.
- Avoid logging passwords, tokens, or sensitive document content.
- Test cross-role and cross-document access attempts.

## 7. Reliability and Testing

- Use database migrations for schema changes.
- Add automated unit and integration tests.
- Test authentication, permissions, retrieval filtering, and error paths.
- Provide health and readiness checks.
- Keep configuration separate from application code.
- Use reproducible dependency versions and deployment configuration.

## 8. Implementation Milestones

1. Repository setup — completed.
2. Architecture and backend foundation.
3. Database models and migrations.
4. Authentication and authorization.
5. Document ingestion.
6. Retrieval and RAG generation.
7. React frontend and integration.
8. Automated testing, security review, and deployment.

## 9. Open Implementation Decisions

- Select and verify the LLM and embedding provider.
- Define role and document-permission semantics.
- Choose document storage appropriate to the deployment.
- Define token lifetime, revocation, and session behavior.
- Establish production database and deployment configuration.
