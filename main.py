from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Optional
import asyncio
import os
import uuid
from datetime import datetime

from reader import DocumentReader
from processor import DocumentProcessor
from llm_client import LLMClient
from writer import DocumentWriter
from logger_config import get_logger

app = FastAPI(title="Legal Document Processor", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = get_logger(__name__)

# In-memory storage for processing status (use Redis/DB in production)
processing_status = {}
processed_files = {}

# Initialize components
document_reader = DocumentReader()
document_processor = DocumentProcessor()
llm_client = LLMClient()
document_writer = DocumentWriter()

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

@app.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    titles: Optional[List[str]] = None,
    sections: Optional[List[str]] = None
):
    """Upload documents for processing"""
    try:
        job_id = str(uuid.uuid4())
        file_info = []
        
        # Save uploaded files
        for i, file in enumerate(files):
            file_id = str(uuid.uuid4())
            file_path = f"uploads/{file_id}_{file.filename}"
            
            # Save file to disk
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Prepare file metadata
            metadata = {
                "title": titles[i] if titles and i < len(titles) else file.filename,
                "sections": sections[i] if sections and i < len(sections) else None,
                "original_filename": file.filename,
                "file_path": file_path,
                "file_id": file_id
            }
            file_info.append(metadata)
        
        # Initialize processing status
        processing_status[job_id] = {
            "status": "queued",
            "files": [{"filename": f["original_filename"], "status": "queued"} for f in file_info],
            "total_files": len(files),
            "completed_files": 0,
            "started_at": datetime.now().isoformat()
        }
        
        # Start background processing
        background_tasks.add_task(process_documents_async, job_id, file_info)
        
        logger.info(f"Job {job_id} queued with {len(files)} files")
        return {"job_id": job_id, "status": "queued", "file_count": len(files)}
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/status/{job_id}")
async def get_processing_status(job_id: str):
    """Get processing status for a job"""
    if job_id not in processing_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return processing_status[job_id]

@app.get("/download/{file_id}/{file_type}")
async def download_file(file_id: str, file_type: str):
    """Download processed file"""
    if file_id not in processed_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_paths = processed_files[file_id]
    
    if file_type == "plain":
        file_path = file_paths.get("plain_english")
    elif file_type == "summary":
        file_path = file_paths.get("summary")
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=os.path.basename(file_path)
    )

async def process_documents_async(job_id: str, file_info: List[dict]):
    """Background task to process documents"""
    try:
        processing_status[job_id]["status"] = "processing"
        logger.info(f"Starting processing for job {job_id}")
        
        for i, file_data in enumerate(file_info):
            try:
                # Update file status
                processing_status[job_id]["files"][i]["status"] = "processing"
                
                # Read document
                logger.info(f"Reading document: {file_data['original_filename']}")
                content = document_reader.read_document(
                    file_data["file_path"], 
                    file_data["original_filename"]
                )
                
                # Process into sections
                sections = document_processor.create_sections(content)
                logger.info(f"Document split into {len(sections)} sections")
                
                # Generate both versions
                plain_english_content = []
                summary_content = []
                
                for section in sections:
                    # Plain English conversion
                    plain_prompt = document_processor.create_plain_english_prompt(section)
                    plain_result = await llm_client.call_llm_async(plain_prompt)
                    plain_english_content.append(plain_result)
                    
                    # Summary conversion
                    summary_prompt = document_processor.create_summary_prompt(section)
                    summary_result = await llm_client.call_llm_async(summary_prompt)
                    summary_content.append(summary_result)
                
                # Write output files
                base_name = os.path.splitext(file_data["original_filename"])[0]
                
                plain_path = document_writer.write_docx(
                    "\n\n".join(plain_english_content),
                    f"{base_name}_plainEnglish.docx"
                )
                
                summary_path = document_writer.write_docx(
                    "\n\n".join(summary_content),
                    f"{base_name}_summary.docx"
                )
                
                # Store file paths for download
                processed_files[file_data["file_id"]] = {
                    "plain_english": plain_path,
                    "summary": summary_path
                }
                
                # Update status
                processing_status[job_id]["files"][i]["status"] = "completed"
                processing_status[job_id]["files"][i]["file_id"] = file_data["file_id"]
                processing_status[job_id]["completed_files"] += 1
                
                logger.info(f"Completed processing: {file_data['original_filename']}")
                
            except Exception as e:
                logger.error(f"Error processing {file_data['original_filename']}: {str(e)}")
                processing_status[job_id]["files"][i]["status"] = "error"
                processing_status[job_id]["files"][i]["error"] = str(e)
        
        # Mark job as completed
        processing_status[job_id]["status"] = "completed"
        processing_status[job_id]["completed_at"] = datetime.now().isoformat()
        logger.info(f"Job {job_id} completed")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        processing_status[job_id]["status"] = "failed"
        processing_status[job_id]["error"] = str(e)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Legal Document Processor API", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)