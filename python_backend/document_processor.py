import os
import io
import re
import tempfile
import json
import traceback
from typing import List, Dict, Optional, BinaryIO, Tuple
import PyPDF2
import docx
import openpyxl
import pandas as pd
from datetime import datetime

# Enable detailed debugging
DEBUG = True

def debug_log(message):
    """Print debug information with a visible prefix"""
    if DEBUG:
        print(f"[DEBUG_DOCUMENT] {message}")

# Function to extract text from PDF
def extract_text_from_pdf(file: BinaryIO) -> dict:
    """Extract text from PDF with page tracking.
    
    Returns a dictionary with full text and a list of pages with text and their page numbers.
    """
    pdf_reader = PyPDF2.PdfReader(file)
    full_text = ""
    pages = []
    
    for page_num in range(len(pdf_reader.pages)):
        page_text = pdf_reader.pages[page_num].extract_text()
        if page_text.strip():  # Only process non-empty pages
            # Add page marker at the beginning of the text
            full_text += f"\n[Page {page_num + 1}]\n{page_text}"
            # Store page text with metadata
            pages.append({
                "page_num": page_num + 1,
                "text": page_text
            })
    
    return {
        "text": full_text,
        "pages": pages,
        "total_pages": len(pdf_reader.pages)
    }

# Function to extract text from DOCX
def extract_text_from_docx(file: BinaryIO) -> str:
    doc = docx.Document(file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# Function to extract text from CSV using pandas
def extract_text_from_csv(file: BinaryIO) -> str:
    debug_log("Starting CSV extraction with pandas")
    temp_path = None
    
    try:
        # Save the file to a temporary location
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name
            # Read all content from the file and write to temp file
            file_content = file.read()
            debug_log(f"Read {len(file_content)} bytes from CSV file")
            temp_file.write(file_content)
        
        debug_log(f"Saved CSV file to temporary location: {temp_path}")
        
        # Use pandas to read the CSV file
        try:
            # Try different encodings and delimiters if needed
            try:
                df = pd.read_csv(temp_path)
            except Exception as utf8_err:
                debug_log(f"Failed with default settings, trying alternate encoding: {str(utf8_err)}")
                try:
                    df = pd.read_csv(temp_path, encoding='latin1')
                except Exception as latin1_err:
                    debug_log(f"Failed with latin1 encoding, trying with different delimiter: {str(latin1_err)}")
                    # Try with different delimiters
                    df = pd.read_csv(temp_path, sep=';')
            
            debug_log(f"Successfully loaded CSV with {len(df)} rows and {len(df.columns)} columns")
            
            # Handle potential column type issues
            text = ""
            
            # First add a title
            text += "CSV Data Analysis:\n"
            
            # Add summary statistics
            text += "\nSummary Statistics:\n"
            
            # Convert all columns to appropriate types for analysis
            for col in df.columns:
                try:
                    # Try to convert to numeric for numeric analysis
                    if df[col].dtype == 'object':
                        try:
                            # Check if column contains numbers
                            numeric_col = pd.to_numeric(df[col], errors='coerce')
                            # If more than 70% of values are numeric, treat as numeric
                            if numeric_col.notnull().sum() > 0.7 * len(df):
                                df[col] = numeric_col
                                debug_log(f"Converted column {col} to numeric")
                        except:
                            pass
                except Exception as col_err:
                    debug_log(f"Error analyzing column {col}: {str(col_err)}")
            
            # Generate summary statistics for numeric columns
            try:
                # Get basic statistics
                stats = df.describe().to_string()
                text += stats + "\n\n"
                debug_log(f"Added {len(stats)} characters of statistics")
            except Exception as stats_err:
                debug_log(f"Error generating statistics: {str(stats_err)}")
                text += "[Could not generate statistics for this dataset]\n\n"
            
            # Add column information
            text += "\nColumn Information:\n"
            for col in df.columns:
                try:
                    # Add column name and type
                    dtype_str = str(df[col].dtype)
                    non_null = df[col].count()
                    null_count = df[col].isna().sum()
                    text += f"- {col} (Type: {dtype_str}, Non-null: {non_null}, Null: {null_count})\n"
                    
                    # Add unique values for categorical columns (if not too many)
                    if df[col].dtype == 'object' and df[col].nunique() < 10:
                        unique_vals = df[col].dropna().unique()
                        text += f"  Unique values: {', '.join(str(val) for val in unique_vals[:10])}"
                        if len(unique_vals) > 10:
                            text += f" and {len(unique_vals) - 10} more"
                        text += "\n"
                except Exception as col_info_err:
                    debug_log(f"Error getting column info for {col}: {str(col_info_err)}")
            
            text += "\n"
            
            # Add dataframe content
            text += "\nData Preview (first 20 rows):\n"
            try:
                # Fill NA values and convert to string
                df_display = df.head(20).fillna("")
                
                # Convert columns to string one by one
                for col in df_display.columns:
                    try:
                        df_display[col] = df_display[col].astype(str)
                    except Exception as col_err:
                        debug_log(f"Error converting column {col}: {str(col_err)}")
                        # Try element by element conversion
                        df_display[col] = df_display[col].apply(lambda x: str(x) if x is not None else "")
                
                # Generate string representation
                df_string = df_display.to_string(index=False)
                text += df_string + "\n\n"
                debug_log(f"Added {len(df_string)} characters of content from CSV preview")
            except Exception as str_err:
                debug_log(f"Error in string conversion: {str(str_err)}")
                # Fallback to manual column iteration
                text += "COLUMNS: " + " | ".join([str(col) for col in df.columns]) + "\n"
                for _, row in df.head(20).iterrows():
                    row_values = []
                    for val in row:
                        try:
                            if val is None:
                                row_values.append("")
                            else:
                                row_values.append(str(val))
                        except:
                            row_values.append("[ERROR]")
                    text += " | ".join(row_values) + "\n"
                
            # Add total row count
            text += f"\nTotal rows in dataset: {len(df)}\n"
            
        except Exception as csv_err:
            error_info = f"Error processing CSV file: {str(csv_err)}\n"
            debug_log(error_info)
            debug_log(traceback.format_exc())
            return f"[ERROR: Could not process CSV file: {str(csv_err)}]"
        
    except Exception as e:
        error_msg = f"Error processing CSV file: {str(e)}"
        debug_log(error_msg)
        debug_log(traceback.format_exc())
        return f"[ERROR: Could not process CSV file: {str(e)}]"
    
    finally:
        # Clean up temporary file
        if temp_path:
            try:
                os.unlink(temp_path)
                debug_log(f"Removed temporary file: {temp_path}")
            except Exception as del_err:
                debug_log(f"Failed to delete temporary file: {str(del_err)}")
    
    debug_log(f"CSV extraction complete - generated {len(text)} characters")
    return text

# Function to extract and analyze text from Excel files
def extract_text_from_excel(file: BinaryIO) -> str:
    debug_log("Starting Excel extraction with pandas and openpyxl")
    temp_path = None
    
    try:
        # Save the file to a temporary location
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            temp_path = temp_file.name
            # Read all content from the file and write to temp file
            file_content = file.read()
            debug_log(f"Read {len(file_content)} bytes from Excel file")
            temp_file.write(file_content)
        
        debug_log(f"Saved Excel file to temporary location: {temp_path}")
        
        # Use pandas to read the Excel file
        try:
            # Get all sheet names first
            xls = pd.ExcelFile(temp_path)
            sheet_names = xls.sheet_names
            debug_log(f"Found {len(sheet_names)} sheets: {', '.join(sheet_names)}")
            
            text = "Excel Data Analysis:\n\n"
            
            # Add sheet overview
            text += f"File contains {len(sheet_names)} sheets: {', '.join(sheet_names)}\n\n"
            
            # Check if this looks like an S&P 500 EPS estimate file
            is_sp500_file = False
            try:
                # Read the first few rows to check for S&P 500 content
                sample_df = pd.read_excel(temp_path, nrows=10)
                first_col = sample_df.iloc[:, 0].astype(str).str.lower()
                if any("s&p 500" in val for val in first_col if isinstance(val, str)):
                    is_sp500_file = True
                    debug_log("Detected S&P 500 EPS estimates file - using specialized processing")
            except Exception as detect_err:
                debug_log(f"Error during file type detection: {str(detect_err)}")
            
            # Process each sheet
            for sheet_name in sheet_names:
                debug_log(f"Processing sheet: {sheet_name}")
                try:
                    # Read the sheet
                    df = pd.read_excel(temp_path, sheet_name=sheet_name)
                    debug_log(f"Sheet {sheet_name} has {len(df)} rows and {len(df.columns)} columns")
                    
                    # Add sheet header
                    text += f"--- Sheet: {sheet_name} ---\n"
                    text += f"Dimensions: {len(df)} rows × {len(df.columns)} columns\n\n"
                    
                    # Special handling for S&P 500 EPS estimate files
                    if is_sp500_file:
                        text += "S&P 500 Earnings and Estimate Report Analysis:\n\n"
                        
                        # Find sectors section
                        sector_rows = []
                        sector_start_idx = -1
                        
                        # Look for sector rows (Communication Services, Financials, etc.)
                        for idx, row in df.iterrows():
                            first_val = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ""
                            if first_val in ["Communication Services", "Consumer Discretionary", "Consumer Staples", 
                                           "Energy", "Financials", "Health Care", "Industrials", 
                                           "Information Technology", "Materials", "Real Estate", "Utilities"]:
                                sector_rows.append((idx, first_val))
                                if sector_start_idx == -1:
                                    sector_start_idx = idx
                        
                        if sector_rows:
                            text += f"Found {len(sector_rows)} sectors: {', '.join([s[1] for s in sector_rows])}\n\n"
                            
                            # Look for operating earnings contribution section
                            contrib_idx = -1
                            for idx, row in df.iterrows():
                                first_val = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ""
                                if "OPERATING EARNINGS CONTRIBUTION" in first_val:
                                    contrib_idx = idx
                                    break
                            
                            if contrib_idx > 0:
                                text += "Operating Earnings Contribution:\n"
                                # Extract earnings contribution data, typically a few rows after the header
                                contrib_data = df.iloc[contrib_idx+3:contrib_idx+15]
                                contrib_data = contrib_data.iloc[:, [0, -1]].dropna(how='all')
                                
                                # Format and add to text
                                try:
                                    contrib_data.columns = ['Sector', 'Contribution']
                                    contrib_str = contrib_data.to_string(index=False)
                                    text += contrib_str + "\n\n"
                                except Exception as contrib_err:
                                    debug_log(f"Error formatting contribution data: {str(contrib_err)}")
                                    # Fallback
                                    text += "Sector contributions found but could not be parsed properly.\n\n"
                        
                        # Extract any available estimate data
                        text += "Note: This file contains S&P 500 earnings estimates. The data is structured in a complex format.\n"
                        text += "You can ask questions about specific sectors, time periods, or financial metrics from this report.\n\n"
                    
                    # Add column information
                    text += "Column Information:\n"
                    for col in df.columns:
                        try:
                            # Add column name and type
                            dtype_str = str(df[col].dtype)
                            non_null = df[col].count()
                            null_count = df[col].isna().sum()
                            text += f"- {col} (Type: {dtype_str}, Non-null: {non_null}, Null: {null_count})\n"
                        except Exception as col_err:
                            debug_log(f"Error getting column info for {col}: {str(col_err)}")
                    
                    text += "\n"
                    
                    # Try to generate statistics if there are numeric columns
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    if numeric_cols:
                        text += "Summary Statistics (numeric columns only):\n"
                        try:
                            stats = df[numeric_cols].describe().to_string()
                            text += stats + "\n\n"
                        except Exception as stats_err:
                            debug_log(f"Error generating statistics: {str(stats_err)}")
                            text += "[Could not generate statistics for numeric columns]\n\n"
                    
                    # Data preview
                    text += "Data Preview (first 20 rows):\n"
                    try:
                        # Fill NA values with blank and convert to string
                        preview_df = df.head(20).fillna("")
                        # Convert all columns to string
                        for col in preview_df.columns:
                            preview_df[col] = preview_df[col].astype(str)
                        
                        preview_text = preview_df.to_string(index=False)
                        text += preview_text + "\n\n"
                    except Exception as preview_err:
                        debug_log(f"Error generating preview: {str(preview_err)}")
                        text += "[Error displaying data preview]\n\n"
                    
                except Exception as sheet_err:
                    debug_log(f"Error processing sheet {sheet_name}: {str(sheet_err)}")
                    text += f"[Error processing sheet {sheet_name}: {str(sheet_err)}]\n\n"
            
            return text
            
        except Exception as excel_err:
            error_info = f"Error processing Excel file: {str(excel_err)}\n"
            debug_log(error_info)
            debug_log(traceback.format_exc())
            return f"[ERROR: Could not process Excel file: {str(excel_err)}]"
        
    except Exception as e:
        error_msg = f"Error processing Excel file: {str(e)}"
        debug_log(error_msg)
        debug_log(traceback.format_exc())
        return f"[ERROR: Could not process Excel file: {str(e)}]"
    
    finally:
        # Clean up temporary file
        if temp_path:
            try:
                os.unlink(temp_path)
                debug_log(f"Removed temporary file: {temp_path}")
            except Exception as del_err:
                debug_log(f"Failed to delete temporary file: {str(del_err)}")
    
    debug_log(f"Excel extraction complete")

# Function to process uploaded document
def process_document(
    file: BinaryIO, 
    filename: str, 
    agent_id: int,
    description: Optional[str] = None
) -> Dict:
    try:
        # Determine file type
        file_extension = os.path.splitext(filename)[1].lower()
        
        # Reset file cursor to beginning to ensure we can read the full file
        file.seek(0)
        
        # Extract text based on file type
        if file_extension == '.pdf':
            pdf_data = extract_text_from_pdf(file)
            text = pdf_data["text"]
            doc_type = 'pdf'
            pages_data = pdf_data.get("pages", [])
            total_pages = pdf_data.get("total_pages", 0)
        elif file_extension in ['.docx', '.doc']:
            # Reset file position before reading
            file.seek(0)
            text = extract_text_from_docx(file)
            doc_type = 'docx'
            pages_data = []
            total_pages = 0
        elif file_extension == '.csv':
            # Reset file position before reading
            file.seek(0)
            text = extract_text_from_csv(file)
            doc_type = 'csv'
            pages_data = []
            total_pages = 0
        elif file_extension in ['.xlsx', '.xls']:
            # Tell user Excel is no longer supported
            file.seek(0)
            text = extract_text_from_excel(file)
            doc_type = 'excel'
            pages_data = []
            total_pages = 0
        else:
            raise ValueError(f"Unsupported file type: {file_extension}. Supported types are: PDF, DOCX, CSV")
        
        # Ensure agent_id is a string for consistent handling
        # This is important for ChromaDB which can't handle mixed types
        agent_id_str = str(agent_id)
        
        # Create document metadata
        now = datetime.now().isoformat()
        document_info = {
            "filename": filename,
            "type": doc_type,
            "agentId": agent_id_str,  # Use string version for ChromaDB
            "agent_id_int": agent_id,  # Keep original int version for reference
            "description": description or filename,
            "uploadedAt": now,
            "text": text,  # Store the extracted text
            "pages_data": pages_data,  # Store page data for PDF files
            "total_pages": total_pages  # Store total page count
        }
        
        debug_log(f"Successfully processed {doc_type} document: {filename}")
        return document_info
    except Exception as e:
        error_msg = f"Error processing document: {str(e)}"
        debug_log(error_msg)
        debug_log(traceback.format_exc())
        raise ValueError(error_msg)

# Function to chunk text for embedding
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[dict]:
    """Split text into overlapping chunks for better embedding and retrieval.
    
    Returns a list of dictionaries with text and metadata about page references.
    """
    if not text:
        return []
    
    # Check if the text contains page markers
    page_marker_pattern = r'\n\[Page \d+\]\n'
    has_page_markers = bool(re.search(page_marker_pattern, text))
    
    if has_page_markers:
        debug_log("Text contains page markers - using page-aware chunking")
        # Process text with page markers
        chunks = []
        current_text = ""
        current_page = None
        
        # Split text into lines for processing
        lines = text.split('\n')
        
        for line in lines:
            # Check if this line is a page marker
            page_match = re.match(r'\[Page (\d+)\]', line.strip())
            
            if page_match:
                # Found a new page marker
                page_num = int(page_match.group(1))
                
                # Chunk any accumulated text with the previous page number
                if current_text and current_page is not None:
                    for i in range(0, len(current_text), chunk_size - overlap):
                        chunk = current_text[i:i + chunk_size]
                        if chunk.strip():  # Only add non-empty chunks
                            chunks.append({
                                "text": chunk,
                                "metadata": {
                                    "page": current_page
                                }
                            })
                
                # Start new page
                current_page = page_num
                current_text = ""
            else:
                # Regular content - add to current text
                current_text += line + "\n"
        
        # Process any remaining text
        if current_text and current_page is not None:
            for i in range(0, len(current_text), chunk_size - overlap):
                chunk = current_text[i:i + chunk_size]
                if chunk.strip():  # Only add non-empty chunks
                    chunks.append({
                        "text": chunk,
                        "metadata": {
                            "page": current_page
                        }
                    })
        
        debug_log(f"Created {len(chunks)} chunks with page information")
        return chunks
    else:
        debug_log("Text does not contain page markers - using simple chunking")
        # No page markers found, use simple chunking
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():  # Only add non-empty chunks
                chunks.append({
                    "text": chunk,
                    "metadata": {}  # No page info
                })
        
        debug_log(f"Created {len(chunks)} chunks without page information")
        return chunks