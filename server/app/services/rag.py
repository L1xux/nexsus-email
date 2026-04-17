import os
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
import uuid

from app.core.config import get_settings

settings = get_settings()

# Vector size for embedding model
VECTOR_SIZE = 1024  # bge-large-en-v1.5 uses 1024 dimensions
COLLECTION_NAME = "email_feedback"


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance (supports both local and cloud)."""
    # Check if using Qdrant Cloud (has URL and API key)
    if settings.qdrant_url and settings.qdrant_api_key:
        return QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    # Fallback to local Qdrant
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )


async def ensure_collection_exists():
    """Create the email_feedback collection if it doesn't exist."""
    client = get_qdrant_client()
    
    try:
        # Check if collection exists
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if COLLECTION_NAME not in collection_names:
            # Create collection with cosine distance
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Created Qdrant collection: {COLLECTION_NAME}")
        else:
            print(f"Collection {COLLECTION_NAME} already exists")
            
    except Exception as e:
        print(f"Error ensuring collection exists: {e}")
        raise


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text using HuggingFace Inference API (free)."""
    from huggingface_hub import InferenceClient

    if not settings.hf_token:
        raise ValueError("HuggingFace token not configured")

    client = InferenceClient(token=settings.hf_token)

    try:
        embedding = client.feature_extraction(
            model="BAAI/bge-large-en-v1.5",
            text=text,
        )
        # Convert numpy array to list if needed
        if hasattr(embedding, 'tolist'):
            return embedding.tolist()
        return list(embedding)
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise


def generate_embedding_sync(text: str) -> List[float]:
    """Generate embedding synchronously for use in non-async contexts."""
    from huggingface_hub import InferenceClient

    if not settings.hf_token:
        raise ValueError("HuggingFace token not configured")

    client = InferenceClient(token=settings.hf_token)

    try:
        embedding = client.feature_extraction(
            model="BAAI/bge-large-en-v1.5",
            text=text,
        )
        if hasattr(embedding, 'tolist'):
            return embedding.tolist()
        return list(embedding)
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise


async def save_feedback(
    email_id: int,
    sender: str,
    subject: str,
    body: str,
    correct_status: str,
    user_id: int,
    original_status: Optional[str] = None,
    user_comment: Optional[str] = None,
) -> Optional[str]:
    """
    Save feedback to Qdrant vector database.

    Args:
        email_id: The email ID
        sender: Email sender
        subject: Email subject
        body: Email body text
        correct_status: The correct status (ToDo/Waiting/Done)
        user_id: The user ID for filtering
        original_status: The original AI-classified status
        user_comment: Optional user comment about the correction

    Returns:
        The point ID in Qdrant, or None if failed
    """
    try:
        # Combine text for embedding
        combined_text = f"Sender: {sender}\nSubject: {subject}\nBody: {body[:500]}"

        # Generate embedding
        vector = await generate_embedding(combined_text)

        # Create payload with metadata
        payload = {
            "email_id": email_id,
            "user_id": user_id,
            "sender": sender,
            "subject": subject,
            "original_status": original_status,
            "correct_status": correct_status,
            "user_comment": user_comment,
        }

        # Generate unique point ID
        point_id = str(uuid.uuid4())

        # Save to Qdrant
        client = get_qdrant_client()
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ]
        )

        print(f"Saved feedback to Qdrant: email_id={email_id}, status={correct_status}")
        return point_id

    except Exception as e:
        print(f"Error saving feedback to Qdrant: {e}")
        return None


async def retrieve_similar_examples(
    text_to_embed: str,
    user_id: int,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Retrieve similar past feedback examples from Qdrant.

    Args:
        text_to_embed: The email text to find similar examples for
        user_id: Filter by user ID (stored in payload)
        top_k: Number of similar examples to retrieve

    Returns:
        List of similar examples with their payloads and scores
    """
    try:
        # Generate embedding for the input text
        vector = await generate_embedding(text_to_embed)

        # Search Qdrant
        client = get_qdrant_client()

        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=Filter(
                must=[
                    {
                        "key": "user_id",
                        "match": {"value": user_id}
                    }
                ]
            ),
            limit=top_k,
        )

        # Format results
        examples = []
        for result in results:
            examples.append({
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            })

        return examples

    except Exception as e:
        print(f"Error retrieving similar examples: {e}")
        return []


def format_rag_examples(examples: List[Dict[str, Any]]) -> str:
    """
    Format RAG examples for injection into the system prompt.
    
    Args:
        examples: List of similar examples from Qdrant
    
    Returns:
        Formatted string for few-shot learning
    """
    if not examples:
        return ""
    
    formatted_lines = ["\n\nFEW-SHOT EXAMPLES FROM PAST FEEDBACK:"]
    
    for i, example in enumerate(examples, 1):
        payload = example.get("payload", {})
        score = example.get("score", 0)
        
        sender = payload.get("sender", "Unknown")
        subject = payload.get("subject", "")
        original = payload.get("original_status", "Unknown")
        correct = payload.get("correct_status", "Unknown")
        comment = payload.get("user_comment", "")
        
        formatted_lines.append(f"""
Example {i} (similarity: {score:.2f}):
- From: {sender}
- Subject: {subject}
- Original classification: {original}
- Corrected to: {correct}
- User comment: {comment or 'N/A'}
""")
    
    return "\n".join(formatted_lines)


async def initialize_rag():
    """Initialize RAG system - ensure collection exists."""
    await ensure_collection_exists()
