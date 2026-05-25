"""
Bsale API adapter.
Docs: https://www.bsale.com.pe/docs/api/
"""
import logging
import requests
from typing import List, Optional

from .base import BaseStoreAdapter, RemoteEntity, ConnectionTestResult

logger = logging.getLogger(__name__)


class BsaleAdapter(BaseStoreAdapter):

    def __init__(self, config: dict):
        super().__init__(config)
        # Bsale uses access_token in header
        self.api_base = f"{self.base_url}/v1" if "/v1" not in self.base_url else self.base_url
        self.headers = {
            "access_token": self.access_token or "",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None, timeout: int = 30):
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        try:
            resp = requests.request(
                method, url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Cannot connect to {self.base_url}: {e}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Bsale API error ({resp.status_code}): {resp.text[:300]}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request to {url} timed out after {timeout}s")

    def test_connection(self) -> ConnectionTestResult:
        try:
            resp = self._request("GET", "products.json", params={"limit": 1})
            data = resp.json()
            count = data.get("count", 0)
            return ConnectionTestResult(
                success=True,
                message="Connected successfully to Bsale",
                store_name="Bsale Store",
                entity_count=count,
                api_version="Bsale v1",
            )
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    def _parse_entity(self, item: dict) -> RemoteEntity:
        variants = []
        for v in item.get("variants", {}).get("items", []):
            variants.append({
                "id": str(v.get("id", "")),
                "sku": v.get("code", ""),
                "barcode": v.get("barCode", ""),
                "price": str(v.get("finalPrice", "")),
                "stock": "",
            })

        first_variant = variants[0] if variants else {}
        entity_type = item.get("entity_type", {})

        return RemoteEntity(
            remote_id=str(item.get("id", "")),
            name=item.get("name", ""),
            canonical_url=item.get("urlSlug", "") or f"{self.base_url}/product/{item.get('id', '')}",
            sku=first_variant.get("sku", ""),
            barcode=first_variant.get("barcode", ""),
            price=first_variant.get("price", ""),
            compare_at_price=None,
            stock=None,
            status="active" if item.get("state") == 0 else "inactive",
            description=item.get("description", ""),
            short_description=None,
            brand=None,
            category=entity_type.get("name", "") if isinstance(entity_type, dict) else "",
            tags=[],
            images=[],
            weight=None,
            dimensions=None,
            variants=variants,
            raw_data=item,
        )

    def fetch_entities(self, page: int = 1, per_page: int = 50) -> List[RemoteEntity]:
        offset = (page - 1) * per_page
        resp = self._request("GET", "products.json", params={"limit": per_page, "offset": offset, "expand": "[variants]"})
        data = resp.json()
        items = data.get("items", [])
        return [self._parse_entity(item) for item in items]

    def fetch_entity_by_id(self, remote_id: str) -> Optional[RemoteEntity]:
        try:
            resp = self._request("GET", f"products/{remote_id}.json", params={"expand": "[variants]"})
            return self._parse_entity(resp.json())
        except Exception as exc:
            logger.warning("Bsale fetch_entity_by_id(%s) failed: %s", remote_id, exc)
            return None

    def fetch_entity_count(self) -> int:
        try:
            resp = self._request("GET", "products.json", params={"limit": 1})
            return resp.json().get("count", 0)
        except Exception as exc:
            logger.warning("Bsale fetch_entity_count failed: %s", exc)
            return 0

    def push_entity_update(self, remote_id: str, updates: dict) -> bool:
        payload: dict = {}
        if "name" in updates:
            payload["name"] = updates["name"]
        if "description" in updates:
            payload["description"] = updates["description"]

        try:
            if payload:
                self._request("PUT", f"products/{remote_id}.json", json_data=payload)
            return True
        except Exception as exc:
            logger.warning("Bsale push_entity_update(%s) failed: %s", remote_id, exc)
            return False
