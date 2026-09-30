"""Add JPY and USD product quotation fields.

Revision ID: 20260930_0016
Revises: 20260930_0015
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260930_0016"
down_revision: str | None = "20260930_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Bank of Japan USD/JPY spot midpoint at 17:00 JST on 2026-09-29.
USD_JPY_RATE = "157.38"
RATE_DATE = "2026-09-29"
RATE_SOURCE = "https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/fx260929.pdf"


def upgrade() -> None:
    op.execute(
        """
        UPDATE field_definitions
        SET label = 'Launch Price (JPY)',
            options = COALESCE(options, '{}'::jsonb) || '{"currency":"JPY"}'::jsonb,
            updated_at = now()
        WHERE code = 'price' AND is_system
        """
    )
    op.execute(
        f"""
        INSERT INTO field_definitions (
            tenant_id, code, label, data_type, scope, is_system, is_core,
            is_required, options, sort_order, status
        )
        SELECT
            tenant_id,
            'price_usd',
            'USD Quote',
            'money',
            'customer',
            true,
            false,
            false,
            jsonb_build_object(
                'currency', 'USD',
                'base_currency', 'JPY',
                'exchange_rate', '{USD_JPY_RATE}',
                'rate_date', '{RATE_DATE}',
                'rate_source', '{RATE_SOURCE}'
            ),
            sort_order + 1,
            'active'
        FROM field_definitions
        WHERE code = 'price'
        ON CONFLICT (tenant_id, code) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE field_definitions
        SET options = jsonb_set(
                COALESCE(options, '{}'::jsonb),
                '{choices}',
                CASE
                    WHEN COALESCE(options->'choices', '[]'::jsonb) ? 'JPY'
                        THEN COALESCE(options->'choices', '[]'::jsonb)
                    ELSE COALESCE(options->'choices', '[]'::jsonb) || '["JPY"]'::jsonb
                END,
                true
            ),
            updated_at = now()
        WHERE code = 'currency'
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
            to_jsonb(
                round((price_value.value #>> '{{}}')::numeric / {USD_JPY_RATE}::numeric, 2)::text
            )
        FROM product_field_values AS price_value
        JOIN field_definitions AS price_field
          ON price_field.tenant_id = price_value.tenant_id
         AND price_field.id = price_value.field_definition_id
         AND price_field.code = 'price'
        JOIN field_definitions AS usd_field
          ON usd_field.tenant_id = price_value.tenant_id
         AND usd_field.code = 'price_usd'
        JOIN field_definitions AS currency_field
          ON currency_field.tenant_id = price_value.tenant_id
         AND currency_field.code = 'currency'
        JOIN product_field_values AS currency_value
          ON currency_value.tenant_id = price_value.tenant_id
         AND currency_value.product_id = price_value.product_id
         AND currency_value.field_definition_id = currency_field.id
        WHERE currency_value.value #>> '{{}}' = 'JPY'
          AND price_value.value #>> '{{}}' ~ '^[0-9]+([.][0-9]+)?$'
        ON CONFLICT (tenant_id, product_id, field_definition_id)
        DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM product_field_values
        WHERE field_definition_id IN (
            SELECT id FROM field_definitions WHERE code = 'price_usd' AND is_system
        )
        """
    )
    op.execute("DELETE FROM field_definitions WHERE code = 'price_usd' AND is_system")
    op.execute(
        """
        UPDATE field_definitions
        SET label = 'Price', options = options - 'currency', updated_at = now()
        WHERE code = 'price' AND is_system
        """
    )
