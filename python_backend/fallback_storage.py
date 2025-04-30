"""
Fallback storage module for when ChromaDB is not available.
This provides basic in-memory storage so the application can still function.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Union
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryStorage:
    """In-memory storage that mimics ChromaDB collections for basic functionality"""
    
    def __init__(self):
        logger.info("Initializing fallback memory storage")
        self.agents = []
        self.messages = []
        self.documents = []
        self.agent_id_counter = 0
        self.message_id_counter = 0
        self.document_id_counter = 0
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Load data from json files if they exist
        self._load_data()
        self.initialize_counters()
        
    def _load_data(self):
        """Load data from json files"""
        try:
            if os.path.exists("data/agents.json"):
                with open("data/agents.json", "r") as f:
                    self.agents = json.load(f)
            
            if os.path.exists("data/messages.json"):
                with open("data/messages.json", "r") as f:
                    self.messages = json.load(f)
                    
            if os.path.exists("data/documents.json"):
                with open("data/documents.json", "r") as f:
                    self.documents = json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def _save_data(self):
        """Save data to json files"""
        try:
            with open("data/agents.json", "w") as f:
                json.dump(self.agents, f)
            
            with open("data/messages.json", "w") as f:
                json.dump(self.messages, f)
                
            with open("data/documents.json", "w") as f:
                json.dump(self.documents, f)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def initialize_counters(self):
        """Initialize ID counters based on existing data"""
        if self.agents:
            self.agent_id_counter = max(agent.get("id", 0) for agent in self.agents)
        
        if self.messages:
            self.message_id_counter = max(msg.get("id", 0) for msg in self.messages)
            
        if self.documents:
            doc_ids = [int(doc.get("id", "0")) for doc in self.documents if doc.get("id", "").isdigit()]
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
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }
        self.agents.append(new_agent)
        self._save_data()
        return new_agent
    
    def update_agent(self, agent_id: int, updates: Dict) -> Optional[Dict]:
        """Update an existing agent"""
        for i, agent in enumerate(self.agents):
            if agent.get("id") == agent_id:
                for key, value in updates.items():
                    if key in agent and value is not None:
                        agent[key] = value
                agent["updatedAt"] = datetime.now().isoformat()
                self.agents[i] = agent
                self._save_data()
                return agent
        return None
    
    def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent"""
        for i, agent in enumerate(self.agents):
            if agent.get("id") == agent_id:
                self.agents.pop(i)
                # Also delete related messages
                self.messages = [msg for msg in self.messages if msg.get("agentId") != agent_id]
                # Also delete related documents
                self.documents = [doc for doc in self.documents if doc.get("agentId") != agent_id]
                self._save_data()
                return True
        return False
    
    # Message operations
    def get_agent_messages(self, agent_id: int) -> List[Dict]:
        """Get all messages for an agent"""
        return [msg for msg in self.messages if msg.get("agentId") == agent_id]
    
    def create_message(self, message_data: Dict) -> Dict:
        """Create a new message"""
        self.message_id_counter += 1
        new_message = {
            "id": self.message_id_counter,
            "agentId": message_data.get("agentId"),
            "role": message_data.get("role", "user"),
            "content": message_data.get("content", ""),
            "timestamp": datetime.now().isoformat()
        }
        self.messages.append(new_message)
        self._save_data()
        return new_message
    
    # Document operations
    def get_agent_documents(self, agent_id: int) -> List[Dict]:
        """Get all documents for an agent"""
        return [doc for doc in self.documents if doc.get("agentId") == agent_id]
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get a document by ID"""
        for doc in self.documents:
            if doc.get("id") == document_id:
                return doc
        return None
    
    def add_document(self, document_info: Dict, text_chunks: List[str]) -> Dict:
        """Add a document"""
        self.document_id_counter += 1
        doc_id = str(self.document_id_counter)
        new_document = {
            "id": doc_id,
            "filename": document_info.get("filename", ""),
            "type": document_info.get("type", ""),
            "description": document_info.get("description", ""),
            "agentId": document_info.get("agentId"),
            "uploadedAt": datetime.now().isoformat(),
            "text_chunks": text_chunks
        }
        self.documents.append(new_document)
        self._save_data()
        return {k: v for k, v in new_document.items() if k != "text_chunks"}
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document"""
        for i, doc in enumerate(self.documents):
            if doc.get("id") == document_id:
                self.documents.pop(i)
                self._save_data()
                return True
        return False
        
    # RAG operations
    def retrieve_document_chunks(self, query: str, agent_id: Optional[int] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fallback retrieval method that does simple keyword matching
        """
        # Simple keyword-based search
        query_terms = set(query.lower().split())
        
        results = []
        for doc in self.documents:
            if agent_id is not None and doc.get("agentId") != agent_id:
                continue
                
            chunks = doc.get("text_chunks", [])
            for i, chunk in enumerate(chunks):
                # Simple scoring: count how many query terms appear in the chunk
                chunk_lower = chunk.lower()
                score = sum(1 for term in query_terms if term in chunk_lower)
                
                if score > 0:
                    results.append({
                        "text": chunk,
                        "score": score,
                        "metadata": {
                            "document_id": doc.get("id"),
                            "filename": doc.get("filename"),
                            "type": doc.get("type"),
                            "chunk_index": i
                        }
                    })
        
        # Sort by score and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]