# This file provides a singleton pattern to access the storage instance
# from anywhere in the application without import errors

import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global storage instance
_storage_instance = None

def get_storage():
    """
    Get the global storage instance.
    This function centralizes storage access and avoids circular imports.
    """
    global _storage_instance
    
    if _storage_instance is not None:
        return _storage_instance
    
    # First try to import faiss_storage
    try:
        logger.info("Attempting to import FAISS storage...")
        
        # Try different import approaches to make it work in any environment
        try:
            # Try to import directly from current package
            from faiss_storage import FAISSVectorStorage
            logger.info("Imported FAISSVectorStorage directly")
        except ImportError:
            # Try with package prefix
            try:
                from python_backend.faiss_storage import FAISSVectorStorage
                logger.info("Imported FAISSVectorStorage with python_backend prefix")
            except ImportError:
                # Try with relative import
                try:
                    from .faiss_storage import FAISSVectorStorage
                    logger.info("Imported FAISSVectorStorage with relative import")
                except ImportError:
                    # Last resort - modify sys.path
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from python_backend.faiss_storage import FAISSVectorStorage
                    logger.info("Imported FAISSVectorStorage after modifying sys.path")
        
        # Create and initialize storage
        _storage_instance = FAISSVectorStorage()
        logger.info("FAISS storage initialized successfully")
        
    except ImportError as e:
        logger.warning(f"Could not import FAISS storage: {e}")
        logger.info("Falling back to memory storage...")
        
        # Try to import fallback_storage
        try:
            # Try different import approaches
            try:
                from fallback_storage import MemoryStorage
            except ImportError:
                try:
                    from python_backend.fallback_storage import MemoryStorage
                except ImportError:
                    try:
                        from .fallback_storage import MemoryStorage
                    except ImportError:
                        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        from python_backend.fallback_storage import MemoryStorage
                        
            # Create and initialize fallback storage
            _storage_instance = MemoryStorage()
            logger.info("Memory storage initialized successfully")
            
        except ImportError as e:
            logger.error(f"Could not import any storage module: {e}")
            raise ImportError(f"Failed to initialize storage. Check your Python environment: {e}")
            
    return _storage_instance

# Expose storage as a singleton
storage = get_storage()