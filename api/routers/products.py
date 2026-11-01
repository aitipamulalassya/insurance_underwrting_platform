
from fastapi import APIRouter, HTTPException, Query

from api.database import get_connection

router = APIRouter()


@router.get("/products")
def get_products():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM products ORDER BY product_id"
            )
            return cur.fetchall()


@router.get("/products/{product_id}")
def get_product(product_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM products
                WHERE product_id = %s
                """,
                (product_id,)
            )
            product = cur.fetchone()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return product
