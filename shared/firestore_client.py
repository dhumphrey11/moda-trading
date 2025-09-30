"""
Firestore client wrapper for consistent database operations across services.
"""

import os
from typing import Dict, List, Optional, Any
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import structlog

logger = structlog.get_logger()


class FirestoreClient:
    """Wrapper for Google Cloud Firestore operations."""

    def __init__(self, project_id: str = "moda-trader"):
        """Initialize Firestore client."""
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)
        logger.info("Firestore client initialized", project_id=project_id)

    async def create_document(self, collection: str, document_id: str, data: Dict[str, Any]) -> bool:
        """Create a new document in the specified collection."""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.set(data)
            logger.info("Document created", collection=collection,
                        document_id=document_id)
            return True
        except Exception as e:
            logger.error("Failed to create document", collection=collection,
                         document_id=document_id, error=str(e))
            return False

    async def update_document(self, collection: str, document_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing document."""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.update(data)
            logger.info("Document updated", collection=collection,
                        document_id=document_id)
            return True
        except Exception as e:
            logger.error("Failed to update document", collection=collection,
                         document_id=document_id, error=str(e))
            return False

    async def upsert_document(self, collection: str, document_id: str, data: Dict[str, Any]) -> bool:
        """Create or update a document."""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.set(data, merge=True)
            logger.info("Document upserted", collection=collection,
                        document_id=document_id)
            return True
        except Exception as e:
            logger.error("Failed to upsert document", collection=collection,
                         document_id=document_id, error=str(e))
            return False

    async def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error("Failed to get document", collection=collection,
                         document_id=document_id, error=str(e))
            return None

    async def query_documents(self, collection: str, filters: Optional[List[tuple]] = None,
                              order_by: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query documents with optional filters."""
        try:
            query = self.db.collection(collection)

            if filters:
                for field, operator, value in filters:
                    query = query.where(
                        filter=FieldFilter(field, operator, value))

            if order_by:
                query = query.order_by(order_by)

            if limit:
                query = query.limit(limit)

            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)

            logger.info("Documents queried",
                        collection=collection, count=len(results))
            return results
        except Exception as e:
            logger.error("Failed to query documents",
                         collection=collection, error=str(e))
            return []

    async def delete_document(self, collection: str, document_id: str) -> bool:
        """Delete a document."""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.delete()
            logger.info("Document deleted", collection=collection,
                        document_id=document_id)
            return True
        except Exception as e:
            logger.error("Failed to delete document", collection=collection,
                         document_id=document_id, error=str(e))
            return False

    async def batch_write(self, operations: List[Dict[str, Any]]) -> bool:
        """Perform batch write operations."""
        try:
            batch = self.db.batch()

            for op in operations:
                collection = op['collection']
                document_id = op['document_id']
                data = op['data']
                operation = op.get('operation', 'set')

                doc_ref = self.db.collection(collection).document(document_id)

                if operation == 'set':
                    batch.set(doc_ref, data)
                elif operation == 'update':
                    batch.update(doc_ref, data)
                elif operation == 'delete':
                    batch.delete(doc_ref)

            batch.commit()
            logger.info("Batch write completed",
                        operations_count=len(operations))
            return True
        except Exception as e:
            logger.error("Failed to perform batch write", error=str(e))
            return False
