"""
FAISS vector storage implementation for the Finance AI Assistant.
This provides persistent storage using FAISS for vector embeddings and JSON files for metadata.
"""

import os
import json
import shutil
import traceback
import sys
from datetime import datetime
from typing import List, Dict, Optional, Any, Union, Tuple
import logging
import faiss
import numpy as np
from langchain_community.vectorstores import FAISS
from langchain.embeddings.base import Embeddings
from langchain_community.embeddings import OpenAIEmbeddings, AzureOpenAIEmbeddings
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers import FAISSRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain.chat_models import ChatOpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory to store FAISS indexes and metadata
DATA_DIR = "data/faiss"

# Global storage instance (singleton)
_storage_instance = None

class FAISSVectorStorage:
    """
    Storage implementation using FAISS for vector storage and JSON files for metadata.
    This class handles agent configurations, chat messages, and document management.
    """
    
    def __init__(self):
        logger.info("Initializing FAISS vector storage")
        self.agents = []
        self.messages = []
        self.documents = []
        self.agent_id_counter = 0
        self.message_id_counter = 0
        self.document_id_counter = 0
        
        # Create data directory structure if it doesn't exist
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(f"{DATA_DIR}/documents", exist_ok=True)
        
        # Initialize embeddings
        self.embedding_function = self._initialize_embeddings()
        
        # Load data from json files if they exist
        self._load_data()
        self.initialize_counters()
        
        # Initialize document index
        self.document_index = self._initialize_document_index()
        
    def _initialize_embeddings(self) -> Embeddings:
        """Initialize the appropriate embedding function based on available credentials"""
        try:
            # Check for Azure OpenAI credentials first
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_key = os.getenv("AZURE_OPENAI_KEY")
            azure_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "Embedding-Model")
            azure_api_version = "2024-08-01-preview"  # Latest API version
            
            if azure_endpoint and azure_key and azure_deployment:
                logger.info("Using Azure OpenAI embeddings")
                return AzureOpenAIEmbeddings(
                    azure_endpoint=azure_endpoint,
                    api_key=azure_key,
                    api_version=azure_api_version,
                    deployment=azure_deployment,
                    model="text-embedding-r-large",
                )
            else:
                # Fallback to regular OpenAI
                logger.info("Using OpenAI embeddings")
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if not openai_api_key:
                    logger.warning("WARNING: OPENAI_API_KEY environment variable not set")
                return OpenAIEmbeddings(
                    model="text-embedding-ada-002",
                    openai_api_key=openai_api_key
                )
        except Exception as e:
            logger.error(f"Error initializing embeddings: {e}")
            raise
    
    def _load_data(self):
        """Load data from json files"""
        try:
            if os.path.exists(f"{DATA_DIR}/agents.json"):
                with open(f"{DATA_DIR}/agents.json", "r") as f:
                    self.agents = json.load(f)
            
            if os.path.exists(f"{DATA_DIR}/messages.json"):
                with open(f"{DATA_DIR}/messages.json", "r") as f:
                    self.messages = json.load(f)
                    
            if os.path.exists(f"{DATA_DIR}/documents.json"):
                with open(f"{DATA_DIR}/documents.json", "r") as f:
                    self.documents = json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            traceback.print_exc()
    
    def _save_data(self):
        """Save data to json files"""
        try:
            with open(f"{DATA_DIR}/agents.json", "w") as f:
                json.dump(self.agents, f)
            
            with open(f"{DATA_DIR}/messages.json", "w") as f:
                json.dump(self.messages, f)
                
            with open(f"{DATA_DIR}/documents.json", "w") as f:
                json.dump(self.documents, f)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            traceback.print_exc()
    
    def _initialize_document_index(self) -> Optional[FAISS]:
        """Initialize or load the FAISS index for documents"""
        index_path = f"{DATA_DIR}/documents/index"
        
        if os.path.exists(index_path) and self.documents:
            try:
                logger.info("Loading existing FAISS document index")
                return FAISS.load_local(
                    index_path,
                    self.embedding_function,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                logger.error(f"Error loading FAISS index: {e}")
                # If loading fails, we'll create a new index
        
        # Create a new empty index
        try:
            logger.info("Creating new FAISS document index")
            
            # If we have existing documents in metadata but no index,
            # recreate the index from the document texts
            if self.documents:
                # Just initialize with dummy text to be overwritten later
                # when documents are added back
                empty_index = FAISS.from_texts(
                    ["placeholder"], 
                    self.embedding_function
                )
                empty_index.save_local(index_path)
                return empty_index
            else:
                # Brand new empty index with placeholder
                empty_index = FAISS.from_texts(
                    ["placeholder"], 
                    self.embedding_function
                )
                empty_index.save_local(index_path)
                return empty_index
        except Exception as e:
            logger.error(f"Error creating FAISS index: {e}")
            traceback.print_exc()
            return None
    
    def initialize_counters(self):
        """Initialize ID counters based on existing data"""
        if self.agents:
            self.agent_id_counter = max(agent.get("id", 0) for agent in self.agents)
        
        if self.messages:
            self.message_id_counter = max(msg.get("id", 0) for msg in self.messages)
            
        if self.documents:
            # Handle both numeric and string IDs
            doc_ids = []
            for doc in self.documents:
                doc_id = doc.get("id", "")
                if isinstance(doc_id, int):
                    doc_ids.append(doc_id)
                elif isinstance(doc_id, str) and doc_id.startswith("doc_"):
                    try:
                        doc_ids.append(int(doc_id[4:]))  # Extract number from "doc_X"
                    except ValueError:
                        pass
            
            self.document_id_counter = max(doc_ids) if doc_ids else 0
    
    # Agent operations
    def get_agents(self) -> List[Dict]:
        """Get all agents"""
        return self.agents
    
    def get_agent(self, agent_id: int) -> Optional[Dict]:
        """Get an agent by ID"""
        for agent in self.agents:
            if agent.get("id") == agent_id:
                return agent
        return None
    
    def create_agent(self, agent_data: Dict) -> Dict:
        """Create a new agent"""
        self.agent_id_counter += 1
        new_agent = {
            "id": self.agent_id_counter,
            "name": agent_data.get("name", ""),
            "systemPrompt": agent_data.get("systemPrompt", ""),
            "model": agent_data.get("model", "gpt-4o"),
            "retrieverStrategy": agent_data.get("retrieverStrategy", "default"),
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }
        self.agents.append(new_agent)
        self._save_data()
        return new_agent
    
    def update_agent(self, agent_id: int, updates: Dict) -> Optional[Dict]:
        """Update an existing agent"""
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        # Update fields
        for key, value in updates.items():
            if key in ["name", "systemPrompt", "model", "retrieverStrategy"]:
                agent[key] = value
        
        agent["updatedAt"] = datetime.now().isoformat()
        self._save_data()
        return agent
    
    def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent and all associated data"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        # Remove the agent
        self.agents = [a for a in self.agents if a.get("id") != agent_id]
        
        # Remove associated messages
        self.messages = [m for m in self.messages if m.get("agentId") != agent_id]
        
        # Remove associated documents (needs separate handling for the vector index)
        agent_documents = self.get_agent_documents(agent_id)
        for doc in agent_documents:
            self.delete_document(doc.get("id"))
        
        self._save_data()
        return True
    
    # Message operations
    def get_agent_messages(self, agent_id: int) -> List[Dict]:
        """Get all messages for an agent"""
        return [m for m in self.messages if m.get("agentId") == agent_id]
    
    def create_message(self, message_data: Dict) -> Dict:
        """Create a new message"""
        self.message_id_counter += 1
        
        new_message = {
            "id": self.message_id_counter,
            "agentId": message_data["agentId"],
            "role": message_data["role"],
            "content": message_data["content"],
            "timestamp": datetime.now().isoformat()
        }
        
        self.messages.append(new_message)
        self._save_data()
        return new_message
    
    # Document operations
    def get_agent_documents(self, agent_id: int) -> List[Dict]:
        """Get all documents for a specific agent"""
        agent_id_str = str(agent_id)
        return [
            # Create a copy without the text field to reduce response size
            {k: v for k, v in doc.items() if k != "text"}
            for doc in self.documents 
            if doc.get("agentId") == agent_id_str
        ]
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get a specific document by ID"""
        for doc in self.documents:
            if doc.get("id") == document_id:
                return doc
        return None
    
    def add_document(self, document_info: Dict, text_chunks: List[Dict]) -> Dict:
        """Add a document and its chunked text to the vector store"""
        try:
            # Generate a unique document ID
            self.document_id_counter += 1
            document_id = f"doc_{self.document_id_counter}"
            
            # Add document ID to the metadata
            document_info["id"] = document_id
            
            # Print debugging information
            logger.info(f"Adding document: {document_id}")
            
            # Ensure all metadata values are strings for consistency
            sanitized_metadata = {}
            for key, value in document_info.items():
                if key in ["text", "pages_data"]:
                    continue  # Skip the text and pages_data fields
                
                if value is None:
                    sanitized_metadata[key] = ""
                else:
                    # Convert all values to strings
                    sanitized_metadata[key] = str(value)
            
            # Store the document metadata
            self.documents.append({**document_info})
            self._save_data()
            
            # Add document chunks to FAISS index
            if self.document_index and text_chunks:
                # Check if we have the new chunk format (dict) or old format (string)
                using_new_format = isinstance(text_chunks[0], dict) if text_chunks else False
                
                # Extract chunk texts and prepare metadata
                chunk_texts = []
                metadatas = []
                
                for i, chunk in enumerate(text_chunks):
                    # Handle both old and new format chunks
                    if using_new_format:
                        chunk_text = chunk["text"]
                        chunk_custom_metadata = chunk.get("metadata", {})
                    else:
                        # Legacy format - directly use the string
                        chunk_text = chunk
                        chunk_custom_metadata = {}
                        
                    # Create base metadata for this chunk
                    chunk_metadata = sanitized_metadata.copy()
                    chunk_metadata["chunk_id"] = f"{document_id}_chunk_{i}"
                    
                    # Add page number to metadata if available
                    if "page" in chunk_custom_metadata:
                        chunk_metadata["page"] = str(chunk_custom_metadata["page"])
                        # Also add source reference for easy display
                        chunk_metadata["source_ref"] = f"{document_info.get('filename', 'document')}, p.{chunk_custom_metadata['page']}"
                    
                    chunk_texts.append(chunk_text)
                    metadatas.append(chunk_metadata)
                
                # Add texts to the index with metadata
                self.document_index.add_texts(
                    chunk_texts, 
                    metadatas=metadatas
                )
                
                # Save the updated index
                index_path = f"{DATA_DIR}/documents/index"
                self.document_index.save_local(index_path)
                logger.info(f"Added {len(text_chunks)} chunks to FAISS index")
            
            return document_info
            
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            traceback.print_exc()
            raise
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks from the vector store"""
        try:
            # Find document in metadata
            document = self.get_document(document_id)
            if not document:
                return False
            
            # Remove document from metadata
            self.documents = [d for d in self.documents if d.get("id") != document_id]
            self._save_data()
            
            # Deleting from FAISS requires rebuilding the index
            # Since FAISS doesn't support direct deletion
            # So we need to recreate the index without the deleted document
            
            # Save remaining docs temporarily
            temp_docs = []
            temp_chunks = []
            temp_metadatas = []
            
            # Try to reconstruct from existing documents with chunks
            for doc in self.documents:
                doc_id = doc.get("id")
                # Skip if it's the document we're deleting (should be gone already)
                if doc_id == document_id:
                    continue
                
                # If the document has text, we'll use it to rebuild
                if "text" in doc:
                    from .document_processor import chunk_text
                    chunks = chunk_text(doc["text"])
                    for i, chunk_obj in enumerate(chunks):
                        # Handle the new chunk format (dict with text and metadata)
                        if isinstance(chunk_obj, dict):
                            chunk_text = chunk_obj["text"]
                            chunk_custom_metadata = chunk_obj.get("metadata", {})
                        else:
                            # Legacy format
                            chunk_text = chunk_obj
                            chunk_custom_metadata = {}
                            
                        temp_chunks.append(chunk_text)
                        
                        # Start with base document metadata
                        chunk_metadata = {
                            k: v for k, v in doc.items() if k not in ["text", "pages_data"]
                        }
                        
                        # Add chunk ID
                        chunk_metadata["chunk_id"] = f"{doc_id}_chunk_{i}"
                        
                        # Add page metadata if available
                        if "page" in chunk_custom_metadata:
                            chunk_metadata["page"] = str(chunk_custom_metadata["page"])
                            # Also add source reference
                            chunk_metadata["source_ref"] = f"{doc.get('filename', 'document')}, p.{chunk_custom_metadata['page']}"
                            
                        temp_metadatas.append(chunk_metadata)
            
            # Rebuild the index if we have documents to retain
            if temp_chunks:
                # Create new index
                new_index = FAISS.from_texts(
                    temp_chunks,
                    self.embedding_function,
                    metadatas=temp_metadatas
                )
                
                # Save the new index
                index_path = f"{DATA_DIR}/documents/index"
                new_index.save_local(index_path)
                
                # Update the instance's index
                self.document_index = new_index
                logger.info(f"Rebuilt FAISS index after document deletion")
            else:
                # If no documents left, create empty index with placeholder
                empty_index = FAISS.from_texts(
                    ["placeholder"], 
                    self.embedding_function
                )
                
                # Save empty index
                index_path = f"{DATA_DIR}/documents/index"
                empty_index.save_local(index_path)
                
                # Update the instance's index
                self.document_index = empty_index
                logger.info("Created empty FAISS index after deleting all documents")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            traceback.print_exc()
            return False
    
    def retrieve_relevant_documents(self, query: str, agent_id: Optional[int] = None, limit: int = 5) -> List[Dict]:
        """
        Retrieve relevant document chunks based on the query
        
        Args:
            query: The search query
            agent_id: Optional agent ID to filter documents
            limit: Maximum number of results to return
            
        Returns:
            List of document chunks with metadata
        """
        if not self.document_index:
            logger.warning("Document index is not initialized")
            return []
        
        try:
            # FAISS similarity search
            if agent_id is not None:
                # Convert agent_id to string for filtering
                agent_id_str = str(agent_id)
                
                # Use the filter parameter with a function that checks agentId
                docs_with_scores = self.document_index.similarity_search_with_score(
                    query,
                    k=limit * 2  # Fetch more than needed to filter
                )
                
                # Filter results by agent_id
                filtered_results = []
                for doc, score in docs_with_scores:
                    if doc.metadata.get("agentId") == agent_id_str:
                        filtered_results.append((doc, score))
                
                # Limit the results
                results = filtered_results[:limit]
            else:
                # No agent filtering
                docs_with_scores = self.document_index.similarity_search_with_score(
                    query,
                    k=limit
                )
                results = docs_with_scores
            
            # Format the results
            documents = []
            for doc, score in results:
                # Skip the placeholder document if it exists
                if doc.page_content == "placeholder":
                    continue
                    
                metadata = doc.metadata.copy() if doc.metadata else {}
                documents.append({
                    "content": doc.page_content,
                    "metadata": metadata,
                    "score": float(score)  # Convert numpy float to Python float
                })
            
            return documents
        
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            traceback.print_exc()