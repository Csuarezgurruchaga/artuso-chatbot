import os
import uuid
import logging
from typing import Optional

import google.auth
from google.auth.transport.requests import AuthorizedSession

logger = logging.getLogger(__name__)


class GcsStorageService:
    def __init__(self):
        self.bucket_name = os.getenv("GCS_BUCKET_NAME", "").strip()
        self._session = None

    def _get_session(self) -> AuthorizedSession:
        if self._session is not None:
            return self._session
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"]
        )
        self._session = AuthorizedSession(creds)
        return self._session

    def upload_public(self, content: bytes, content_type: str, ext: str) -> Optional[str]:
        if not self.bucket_name:
            logger.error("GCS_BUCKET_NAME not set")
            return None

        object_name = f"comprobantes/{uuid.uuid4().hex}{ext}"
        url = f"https://storage.googleapis.com/{self.bucket_name}/{object_name}"

        session = self._get_session()
        upload_url = f"https://storage.googleapis.com/upload/storage/v1/b/{self.bucket_name}/o"
        params = {"uploadType": "media", "name": object_name}
        headers = {"Content-Type": content_type}

        resp = session.post(upload_url, params=params, headers=headers, data=content, timeout=20)
        if resp.status_code not in (200, 201):
            logger.error("GCS upload failed: %s - %s", resp.status_code, resp.text)
            return None

        return url


gcs_storage_service = GcsStorageService()
