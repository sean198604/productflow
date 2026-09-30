import asyncio
import json

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import ProductImage, StoredFile
from app.services.image_processing import ProductImageProcessor


async def backfill_product_image_cutouts() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_admin_url or settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    processor = ProductImageProcessor()
    processed_count = 0
    removed_count = 0
    try:
        async with factory() as session, session.begin():
            rows = (
                await session.execute(
                    select(ProductImage, StoredFile)
                    .join(
                        StoredFile,
                        and_(
                            StoredFile.tenant_id == ProductImage.tenant_id,
                            StoredFile.id == ProductImage.stored_file_id,
                        ),
                    )
                    .where(ProductImage.processed_file_id.is_(None))
                    .order_by(ProductImage.created_at)
                )
            ).all()
            for product_image, original in rows:
                transparent, background_removed = await processor.ensure_transparent_variant(
                    session,
                    tenant_id=product_image.tenant_id,
                    original=original,
                )
                product_image.processed_file_id = transparent.id
                product_image.background_removed = background_removed
                processed_count += 1
                removed_count += int(background_removed)
            await session.flush()
        print(
            json.dumps(
                {
                    "status": "completed",
                    "processed": processed_count,
                    "background_removed": removed_count,
                },
                ensure_ascii=False,
            )
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(backfill_product_image_cutouts())


if __name__ == "__main__":
    main()
