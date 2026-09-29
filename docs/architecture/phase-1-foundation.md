# Phase 1 foundation boundaries

## Confirmed domain model

The implementation must preserve these aggregate boundaries:

- Tenant, users, customers, customer settings, and customer template bindings
- Products, typed field definitions, product images, and product sets
- Versioned import and output templates with validated mappings
- Immutable generation snapshots for customer, product set, products, images, and template versions
- Tenant-scoped files, audit logs, and AI provider configuration

## Non-negotiable security boundaries

- Business tables are tenant-scoped and use composite tenant foreign keys.
- PostgreSQL row-level security is mandatory for tenant tables.
- Customer render contexts are explicit allowlists and never receive raw product objects.
- Internal fields cannot be bound by customer-facing templates.
- Template versions and mappings are rejected when the file SHA256 changes.
- Rendered files are published atomically only after structural validation.

## Phase 1 scope

Phase 1 establishes runtime infrastructure and the tenant-context database primitives. Domain tables and authentication behavior are added in the following phases through repeatable Alembic migrations; no single-tenant shortcut is introduced in this foundation.

