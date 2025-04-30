"""
Contextual Compression Retriever for the Finance AI Assistant.
This provides an enhanced retrieval mechanism that compresses and focuses document chunks.
"""

import logging
from typing import List, Dict, Optional, Any

# Import LangChain components for the compression retriever
try:
    from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
    from langchain.retrievers.document_compressors import LLMChainExtractor
    from langchain.chains import create_extraction_chain
    from langchain.prompts import ChatPromptTemplate
    from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
    
    compression_available = True
except ImportError:
    compression_available = False
    logging.warning("LangChain compression components not available")

# Import storage
from .storage_singleton import storage
import os

# Set up logging
logger = logging.getLogger(__name__)

# Check if we have Azure OpenAI credentials
using_azure = (
    os.environ.get("AZURE_OPENAI_ENDPOINT") and 
    os.environ.get("AZURE_OPENAI_KEY") and 
    os.environ.get("AZURE_OPENAI_DEPLOYMENT")
)

# Initialize the appropriate LLM
if using_azure:
    try:
        llm = AzureChatOpenAI(
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_key=os.environ.get("AZURE_OPENAI_KEY"),
            azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
            api_version="2024-02-01-preview"
        )
    except Exception as e:
        using_azure = False
        logger.error(f"Error initializing Azure OpenAI: {e}")
        logger.warning("Falling back to OpenAI")

if not using_azure:
    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=0
        )
    except Exception as e:
        logger.error(f"Error initializing OpenAI: {e}")
        compression_available = False

def get_compression_retriever(faiss_index, embedding_function, agent_id: Optional[int] = None):
    """
    Create a contextual compression retriever for the given FAISS index
    
    Args:
        faiss_index: The FAISS vector store instance
        embedding_function: The embedding function to use
        agent_id: Optional agent ID to filter documents
        
    Returns:
        A contextual compression retriever
    """
    if not compression_available:
        logger.warning("Compression retriever not available, using standard retrieval")
        return None
    
    try:
        # Define custom prompt for the LLM compressor
        prompt = ChatPromptTemplate.from_template(
            """You are an expert financial context extractor. 
            Given a user query and a document passage, extract only the parts of the passage that are directly 
            relevant to answering the query. Focus on data points, figures, financial insights, and key facts.
            
            If the passage contains data tables, preserve their structure.
            If the passage contains financial metrics or statistics, include them.
            
            Query: {query}
            
            Document passage: {document}
            
            Relevant extracted parts:"""
        )
        
        # Create the document compressor
        compressor = LLMChainExtractor.from_llm(
            llm=llm,
            prompt=prompt
        )
        
        # Create a custom retriever class that integrates with our FAISS storage
        class CustomFAISSRetriever:
            def __init__(self, faiss_index, embedding_function, agent_id=None):
                self.faiss_index = faiss_index
                self.embedding_function = embedding_function
                self.agent_id = agent_id
                
            def get_relevant_documents(self, query):
                # Use our storage's retrieval method
                results = storage.retrieve_relevant_documents(
                    query=query,
                    agent_id=self.agent_id,
                    limit=10  # Retrieve more documents for compression
                )
                
                # Convert to LangChain Document format
                from langchain.schema import Document
                
                documents = []
                for result in results:
                    doc = Document(
                        page_content=result["content"],
                        metadata=result["metadata"]
                    )
                    documents.append(doc)
                
                return documents
        
        # Create the base retriever
        base_retriever = CustomFAISSRetriever(
            faiss_index=faiss_index,
            embedding_function=embedding_function,
            agent_id=agent_id
        )
        
        # Create the compression retriever
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever
        )
        
        return compression_retriever
        
    except Exception as e:
        logger.error(f"Error creating compression retriever: {e}")
        import traceback
        traceback.print_exc()
        return None

def retrieve_with_compression(query: str, faiss_index, embedding_function, agent_id: Optional[int] = None, limit: int = 5):
    """
    Retrieve documents using contextual compression
    
    Args:
        query: The search query
        faiss_index: The FAISS vector store instance
        embedding_function: The embedding function to use
        agent_id: Optional agent ID to filter documents
        limit: Maximum number of results to return
        
    Returns:
        List of compressed document chunks with metadata
    """
    try:
        # Get the compression retriever
        retriever = get_compression_retriever(faiss_index, embedding_function, agent_id)
        
        if retriever:
            # Use the compression retriever
            documents = retriever.get_relevant_documents(query)
            
            # Format the results
            results = []
            for i, doc in enumerate(documents[:limit]):  # Limit the number of results
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 1.0 - (i * 0.1)  # Simulate a score since compression doesn't provide scores
                })
                
            return results
        else:
            # Fallback to standard retrieval
            return storage.retrieve_relevant_documents(query, agent_id, limit)
            
    except Exception as e:
        logger.error(f"Error retrieving with compression: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to standard retrieval
        return storage.retrieve_relevant_documents(query, agent_id, limit)