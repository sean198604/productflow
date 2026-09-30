"""Replace converted USD demo prices with United States launch MSRP values.

Revision ID: 20260930_0017
Revises: 20260930_0016
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260930_0017"
down_revision: str | None = "20260930_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEMO_SKUS = (
    "NT-HH-002", "NT-HH-003", "NT-HH-004", "NT-HH-005", "NT-HH-006",
    "NT-HH-007", "NT-HH-008", "NT-HH-009", "NT-HH-010", "NT-HH-011",
    "NT-HH-012", "NT-HH-013", "NT-HH-014", "NT-HH-015", "NT-HH-016",
    "NT-HH-017", "NT-HH-018", "NT-HH-019", "NT-HH-020", "NT-HH-021",
    "NT-HH-022", "NT-HH-023",
)


def _quoted_skus() -> str:
    return ", ".join(f"'{sku}'" for sku in DEMO_SKUS)


def upgrade() -> None:
    op.execute(
        """
        UPDATE field_definitions
        SET label = 'US Launch MSRP (USD)',
            options = (
                COALESCE(options, '{}'::jsonb)
                - 'base_currency' - 'exchange_rate' - 'rate_date' - 'rate_source'
            ) || jsonb_build_object(
                'currency', 'USD',
                'price_basis', 'us_launch_msrp',
                'source_kind', 'market_msrp',
                'sources', jsonb_build_array(
                    'https://www.nintendoworldreport.com/pr/8149/game-boy-advance-sp-the-press-release',
                    'https://www.nintendoworldreport.com/news/9915/nintendo-ds-launch-details',
                    'https://www.nintendo.co.jp/ir/pdf/2017/170201_2e.pdf',
                    'https://www.nintendo.com/us/whatsnew/nintendo-switch-2-launches-june-5-bringing-new-forms-of-game-communication-to-life/'
                )
            ),
            updated_at = now()
        WHERE code = 'price_usd' AND is_system
        """
    )
    op.execute(
        f"""
        DELETE FROM product_field_values AS value
        USING products AS product, field_definitions AS field
        WHERE value.product_id = product.id
          AND value.field_definition_id = field.id
          AND field.tenant_id = product.tenant_id
          AND field.code = 'price_usd'
          AND product.sku IN ({_quoted_skus()})
        """
    )
    # Game Boy Light was Japan-only. The standard-size New Nintendo 3DS did not
    # have a standalone U.S. launch MSRP, so both intentionally remain empty.
    op.execute(
        """
        WITH usd_prices(sku, amount) AS (
            VALUES
                ('NT-HH-002', 89.99::numeric),
                ('NT-HH-003', 69.99::numeric),
                ('NT-HH-005', 79.95::numeric),
                ('NT-HH-006', 39.99::numeric),
                ('NT-HH-007', 99.99::numeric),
                ('NT-HH-008', 99.95::numeric),
                ('NT-HH-009', 99.99::numeric),
                ('NT-HH-010', 149.99::numeric),
                ('NT-HH-011', 129.99::numeric),
                ('NT-HH-012', 169.99::numeric),
                ('NT-HH-013', 189.99::numeric),
                ('NT-HH-014', 249.99::numeric),
                ('NT-HH-015', 199.99::numeric),
                ('NT-HH-016', 129.99::numeric),
                ('NT-HH-018', 199.99::numeric),
                ('NT-HH-019', 149.99::numeric),
                ('NT-HH-020', 299.99::numeric),
                ('NT-HH-021', 199.99::numeric),
                ('NT-HH-022', 349.99::numeric),
                ('NT-HH-023', 449.99::numeric)
        )
        INSERT INTO product_field_values (
            tenant_id, product_id, field_definition_id, value
        )
        SELECT
            product.tenant_id,
            product.id,
            field.id,
            to_jsonb(usd_prices.amount::text)
        FROM usd_prices
        JOIN products AS product ON product.sku = usd_prices.sku
        JOIN field_definitions AS field
          ON field.tenant_id = product.tenant_id
         AND field.code = 'price_usd'
        ON CONFLICT (tenant_id, product_id, field_definition_id)
        DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM product_field_values AS value
        USING products AS product, field_definitions AS field
        WHERE value.product_id = product.id
          AND value.field_definition_id = field.id
          AND field.tenant_id = product.tenant_id
          AND field.code = 'price_usd'
          AND product.sku IN ({_quoted_skus()})
        """
    )
    op.execute(
        f"""
        INSERT INTO product_field_values (
            tenant_id, product_id, field_definition_id, value
        )
        SELECT
            price_value.tenant_id,
            price_value.product_id,
            usd_field.id,
            to_jsonb(round((price_value.value #>> '{{}}')::numeric / 157.38, 2)::text)
        FROM product_field_values AS price_value
        JOIN field_definitions AS price_field
          ON price_field.tenant_id = price_value.tenant_id
         AND price_field.id = price_value.field_definition_id
         AND price_field.code = 'price'
        JOIN field_definitions AS usd_field
          ON usd_field.tenant_id = price_value.tenant_id
         AND usd_field.code = 'price_usd'
        JOIN products AS product ON product.id = price_value.product_id
        WHERE product.sku IN ({_quoted_skus()})
          AND price_value.value #>> '{{}}' ~ '^[0-9]+([.][0-9]+)?$'
        ON CONFLICT (tenant_id, product_id, field_definition_id)
        DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """
    )
    op.execute(
        """
        UPDATE field_definitions
        SET label = 'USD Quote',
            options = jsonb_build_object(
                'currency', 'USD',
                'base_currency', 'JPY',
                'exchange_rate', '157.38',
                'rate_date', '2026-09-29',
                'rate_source', 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/fx260929.pdf'
            ),
            updated_at = now()
        WHERE code = 'price_usd' AND is_system
        """
    )
